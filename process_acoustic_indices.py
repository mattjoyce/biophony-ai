#!/usr/bin/env python3
"""
Acoustic Indices Processing Script
Separate processing for temporal (WAV) and spectral (NPZ) indices with sharding support
"""

import argparse
import gc
import os
import time
from pathlib import Path
from typing import List

import torch
import yaml
from filelock import FileLock, Timeout
from rich.console import Console
from rich.progress import Progress, TaskID, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import box

from indices import DatabaseManager, SpectralIndicesProcessor, TemporalIndicesProcessor
from spectrogram_utils import find_all_wav_files

# Initialize Rich console
console = Console()


def parse_arguments():
    """Parse command line arguments with mutually exclusive processing types"""
    parser = argparse.ArgumentParser(
        description="Process acoustic indices from audio/spectrogram files"
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Input directory with files (optional - uses input_directory from config if not provided)",
    )
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    parser.add_argument(
        "--target",
        type=int,
        nargs="+",
        help="Target subset(s): e.g. --target 0 1 2 (defaults to all 0-9)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Force reprocessing of existing files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually doing any work",
    )

    # Mutually exclusive processing type flags
    processing_group = parser.add_mutually_exclusive_group(required=True)
    processing_group.add_argument(
        "--TEMPORAL",
        action="store_true",
        help="Process temporal indices from WAV files",
    )
    processing_group.add_argument(
        "--SPECTRAL",
        action="store_true",
        help="Process spectral indices from NPZ spectrogram files",
    )

    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file and store config in database"""
    with console.status(f"[bold blue]Loading configuration from {config_path}..."):
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

    # Store configuration in database for future reference
    try:
        config_name = os.path.basename(config_path)
        db_manager = DatabaseManager(config.get("database_path", "audiomoth.db"), config=config)
        db_manager.store_index_configuration(config_name, config)
        console.print(f"[green]✓[/green] Configuration loaded and stored: {config_name}")
    except Exception as e:
        console.print(f"[yellow]⚠️  Could not store configuration: {e}[/yellow]")

    return config


def setup_device() -> torch.device:
    """Setup processing device with GPU if available"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        console.print(f"[green]✓[/green] Using GPU: [bold]{torch.cuda.get_device_name()}[/bold]")
        torch.cuda.empty_cache()
    else:
        device = torch.device("cpu")
        console.print("[green]✓[/green] Using CPU for processing")

    return device


def find_files_by_type(root_dir: str, processing_type: str) -> List[str]:
    """Find files based on processing type"""
    with console.status(f"[bold blue]Searching for {processing_type} files in {root_dir}..."):
        if processing_type == "temporal":
            files = find_all_wav_files(root_dir)
            console.print(f"[green]Found {len(files)} WAV files for temporal processing[/green]")
            return files
        elif processing_type == "spectral":
            files = find_all_npz_files(root_dir)
            console.print(f"[green]Found {len(files)} NPZ files for spectral processing[/green]")
            return files
        else:
            raise ValueError(f"Unknown processing type: {processing_type}")


def find_all_npz_files(root_dir: str) -> List[str]:
    """Find all NPZ spectrogram files recursively"""
    import glob

    pattern = os.path.join(root_dir, "**", "*_spec.npz")
    files = glob.glob(pattern, recursive=True)
    return sorted(files)


def filter_files_by_target(files: List[str], target_indices: List[int]) -> List[str]:
    """Filter files based on target subset indices"""
    filtered_files = []
    for i, file_path in enumerate(files):
        if i % 10 in target_indices:
            filtered_files.append(file_path)

    return filtered_files


def create_dry_run_report(
    processing_type: str, config: dict, target_files: List[str], all_files: List[str]
) -> None:
    """
    Create a detailed dry-run report showing what would be processed

    Args:
        processing_type: "temporal" or "spectral"
        config: Configuration dictionary
        target_files: Files that would be processed
        all_files: All files found
    """
    console.print()
    console.rule("[bold blue]DRY-RUN REPORT", style="blue")
    
    # Create summary table
    summary_table = Table(title="Processing Summary", box=box.ROUNDED)
    summary_table.add_column("Metric", style="cyan", no_wrap=True)
    summary_table.add_column("Value", style="magenta")
    
    summary_table.add_row("Processing Type", processing_type.upper())
    summary_table.add_row("Total Files Found", str(len(all_files)))
    summary_table.add_row("Files in Target", f"{len(target_files)} ({len(target_files)/len(all_files)*100:.1f}%)")
    
    console.print(summary_table)

    # Get enabled indices from config
    indices_config = config.get("acoustic_indices", {}).get(processing_type, {})

    # Create indices table
    indices_table = Table(title="Configured Indices", box=box.ROUNDED)
    indices_table.add_column("Index Name", style="green")
    indices_table.add_column("Processor", style="blue")
    indices_table.add_column("Parameters", style="yellow")

    if "enabled" in indices_config:
        # Legacy format
        enabled_indices = indices_config.get("enabled", [])
        for idx in enabled_indices:
            indices_table.add_row(idx, "legacy", "N/A")
    else:
        # New generalized format
        named_indices = {
            k: v
            for k, v in indices_config.items()
            if isinstance(v, dict) and "processor" in v
        }
        for name, idx_config in named_indices.items():
            processor = idx_config["processor"]
            params = idx_config.get("params", {})
            params_str = str(params) if params else "None"
            indices_table.add_row(name, processor, params_str)

    console.print(indices_table)

    # Estimate processing time
    if target_files:
        indices_count = (
            len(enabled_indices) if "enabled" in indices_config else len(named_indices)
        )
        if indices_count > 0:
            avg_time_per_file = 4.0  # seconds (rough estimate)
            total_time_sec = len(target_files) * avg_time_per_file
            total_time_min = total_time_sec / 60
            
            # Create timing panel
            timing_text = f"[green]⏱️  Estimated processing time: {total_time_min:.1f} minutes[/green]\n"
            timing_text += f"[yellow]📊 Rate: ~{avg_time_per_file:.1f}s per file[/yellow]\n"
            timing_text += f"[blue]🔢 Indices per file: {indices_count}[/blue]"
            
            timing_panel = Panel(timing_text, title="Time Estimates", border_style="green")
            console.print(timing_panel)
        else:
            console.print("[bold red]⚠️  No indices configured - nothing would be processed![/bold red]")

    # Status panel
    status_text = "[red]💾 Database writes: DISABLED (dry-run mode)[/red]\n"
    status_text += "[green]🚀 Use without --dry-run to execute actual processing[/green]"
    
    status_panel = Panel(status_text, title="Dry-Run Status", border_style="yellow")
    console.print(status_panel)


def process_temporal_files(
    files: List[str],
    config: dict,
    target_name: str,
    force: bool = False,
    dry_run: bool = False,
) -> tuple:
    """Process temporal indices from WAV files"""
    # Get database path from config
    db_path = config.get("database_path")
    if not db_path:
        raise ValueError("❌ No database_path specified in config file")

    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"❌ Database file not found: {db_path}")

    processor = TemporalIndicesProcessor(config)
    db_manager = DatabaseManager(db_path, config=config)

    # Get the specific indices that would be created by this processor
    # Temporal indices typically use their cosmetic name as database name
    expected_indices = processor.get_enabled_indices()

    created = 0
    exists = 0
    errors = 0
    start_time = time.time()

    # Bulk preload existing indices for all target files (single database query)
    with console.status("[bold blue]🔍 Preloading existing indices..."):
        preload_start = time.time()
        existing_indices_bulk = db_manager.get_indices_for_files_bulk(
            files, "temporal", expected_indices
        )
        preload_time = time.time() - preload_start
    
    console.print(f"[green]✓ Preloaded in {preload_time:.1f}s - found indices for {len(existing_indices_bulk)} files[/green]")

    # Create progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        TextColumn("•"),
        TextColumn("{task.fields[status]}", style="green"),
        console=console
    ) as progress:
        task = progress.add_task(f"Processing {target_name}", total=len(files), status="Starting...")
        
        for i, wav_file in enumerate(files, 1):
            file_start_time = time.time()
            filename = os.path.basename(wav_file)
            progress.update(task, description=f"Processing: {filename[:30]}", status="Working...")

            # Try to acquire file lock - skip immediately if locked
            lock_path = f"{wav_file}.lock"
            try:
                with FileLock(lock_path, timeout=0):
                    # Check if the specific indices we want to create already exist (using preloaded data)
                    existing_indices = existing_indices_bulk.get(wav_file, {})
                    indices_exist = len(existing_indices) > 0

                    if indices_exist and not force:
                        exists += 1
                        file_duration = time.time() - file_start_time
                        existing_names = list(existing_indices.keys())
                        progress.update(task, status=f"Exists ({file_duration:.1f}s)")
                        progress.advance(task)
                        continue
                    elif indices_exist and force:
                        if not dry_run:
                            # Delete existing specific indices before reprocessing (only if not dry-run)
                            for index_name in expected_indices:
                                if index_name in existing_indices:
                                    # Note: delete_indices_for_file deletes ALL indices for file+type, not specific ones
                                    # This is a limitation of the current DatabaseManager API
                                    pass

                    if dry_run:
                        # Dry-run mode: just show what would be processed
                        created += 1
                        file_duration = time.time() - file_start_time
                        enabled_indices = processor.get_enabled_indices()
                        progress.update(task, status=f"[DRY-RUN] {len(enabled_indices)} indices ({file_duration:.1f}s)")
                    else:
                        # Normal processing mode
                        progress.update(task, status="Processing indices...")
                        # Process file
                        indices_data = processor.process_file(wav_file)

                        # Check if file was skipped (dict with _skipped flag returned)
                        if isinstance(indices_data, dict) and indices_data.get('_skipped'):
                            errors += 1
                            file_duration = time.time() - file_start_time
                            progress.update(task, status=f"⚠️  Skipped ({file_duration:.1f}s)")

                            # Mark file as skipped in database
                            try:
                                import sqlite3
                                db_path = config.get("database_path")
                                if db_path:
                                    conn = sqlite3.connect(db_path)
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        "UPDATE audio_files SET processing_status = 'skipped' WHERE filepath = ?",
                                        (wav_file,)
                                    )
                                    conn.commit()
                                    conn.close()
                            except Exception as e:
                                pass  # Don't fail processing if DB update fails
                        else:
                            timestamps = processor.get_chunk_timestamps()

                            progress.update(task, status="Storing to database...")
                            # Store in database
                            db_manager.store_indices(
                                wav_file, "temporal", indices_data, timestamps
                            )

                            created += 1
                            file_duration = time.time() - file_start_time
                            progress.update(task, status=f"✓ ({file_duration:.1f}s)")
                    
                    progress.advance(task)
            except Timeout:
                # File is locked by another process, skip it
                file_duration = time.time() - file_start_time
                progress.update(task, status=f"Locked ({file_duration:.3f}s)")
                progress.advance(task)
                continue

            # Cleanup every few files
            if i % 5 == 0:
                gc.collect()

    return created, exists, errors


def process_spectral_files(
    files: List[str],
    config: dict,
    device: torch.device,
    target_name: str,
    force: bool = False,
    dry_run: bool = False,
) -> tuple:
    """Process spectral indices from NPZ files"""
    # Get database path from config
    db_path = config.get("database_path")
    if not db_path:
        raise ValueError("❌ No database_path specified in config file")

    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"❌ Database file not found: {db_path}")

    processor = SpectralIndicesProcessor(config, device)
    db_manager = DatabaseManager(db_path, config=config)

    # Get the specific indices that would be created by this processor
    if hasattr(processor, "named_indices") and processor.named_indices:
        # New format: get database names for named indices
        expected_indices = []
        for name, idx_config in processor.named_indices.items():
            processor_name = idx_config["processor"]
            params = idx_config.get("params", {})
            db_name = processor._generate_database_name(name, processor_name, params)
            expected_indices.append(db_name)
    else:
        # Legacy format: get enabled indices with frequency encoding
        expected_indices = []
        for index_name in processor.enabled_indices:
            if index_name == "bioacoustics_index":
                db_name = f"standard_bai_{int(processor.bioacoustics_freq_min)}-{int(processor.bioacoustics_freq_max)}"
            elif index_name == "soundscape_index":
                db_name = f"standard_soundscape_{int(processor.bioacoustics_freq_min)}-{int(processor.bioacoustics_freq_max)}"
            else:
                db_name = index_name
            expected_indices.append(db_name)

    created = 0
    exists = 0
    errors = 0
    start_time = time.time()

    # Bulk preload existing indices for all target files (single database query)
    print(f"🔍 Preloading existing indices for {len(files)} files...")
    preload_start = time.time()
    existing_indices_bulk = db_manager.get_indices_for_files_bulk(
        files, "spectral", expected_indices
    )
    preload_time = time.time() - preload_start
    print(
        f"✓ Preloaded in {preload_time:.1f}s - found indices for {len(existing_indices_bulk)} files"
    )

    for i, npz_file in enumerate(files, 1):
        file_start_time = time.time()
        print(
            f"[{target_name}] [{i:4d}/{len(files)}] {os.path.basename(npz_file)}...",
            end=" ",
        )

        # Try to acquire file lock - skip immediately if locked
        lock_path = f"{npz_file}.lock"
        try:
            with FileLock(lock_path, timeout=0):
                # Check if the specific indices we want to create already exist (using preloaded data)
                existing_indices = existing_indices_bulk.get(npz_file, {})
                indices_exist = len(existing_indices) > 0

                if indices_exist and not force:
                    exists += 1
                    file_duration = time.time() - file_start_time
                    existing_names = list(existing_indices.keys())
                    print(f"(exists: {existing_names}) ({file_duration:.1f}s)")
                    continue
                elif indices_exist and force:
                    if not dry_run:
                        # Delete existing specific indices before reprocessing (only if not dry-run)
                        for index_name in expected_indices:
                            if index_name in existing_indices:
                                # Note: delete_indices_for_file deletes ALL indices for file+type, not specific ones
                                # This is a limitation of the current DatabaseManager API
                                pass

                if dry_run:
                    # Dry-run mode: just show what would be processed
                    created += 1
                    file_duration = time.time() - file_start_time
                    enabled_indices = processor.get_enabled_indices()
                    print(
                        f"[DRY-RUN] would process {len(enabled_indices)} indices ({file_duration:.1f}s)"
                    )
                else:
                    # Normal processing mode
                    # Process file
                    indices_data = processor.process_file(npz_file)

                    # Check if file was skipped (dict with _skipped flag returned)
                    if isinstance(indices_data, dict) and indices_data.get('_skipped'):
                        errors += 1
                        file_duration = time.time() - file_start_time
                        print(f"⚠️  Skipped ({file_duration:.1f}s)")

                        # Mark file as skipped in database
                        try:
                            import sqlite3
                            db_path = config.get("database_path")
                            if db_path:
                                conn = sqlite3.connect(db_path)
                                cursor = conn.cursor()
                                # Get wav filepath from npz filepath
                                wav_file = npz_file.replace('_spec.npz', '.WAV')
                                cursor.execute(
                                    "UPDATE audio_files SET processing_status = 'skipped' WHERE filepath = ?",
                                    (wav_file,)
                                )
                                conn.commit()
                                conn.close()
                        except Exception as e:
                            pass  # Don't fail processing if DB update fails
                    else:
                        timestamps = processor.get_chunk_timestamps()

                        # Store in database
                        db_manager.store_indices(
                            npz_file, "spectral", indices_data, timestamps
                        )

                        created += 1
                        file_duration = time.time() - file_start_time
                        print(f"✓ ({file_duration:.1f}s)")
        except Timeout:
            # File is locked by another process, skip it
            file_duration = time.time() - file_start_time
            print(f"(locked) ({file_duration:.3f}s)")
            continue

        # Progress reporting and cleanup
        if i % 5 == 0:
            elapsed_total = time.time() - start_time
            current_rate = i / elapsed_total if elapsed_total > 0 else 0

            # GPU cleanup for spectral processing
            if device.type == "cuda":
                torch.cuda.empty_cache()
            gc.collect()

            if i % 10 == 0:
                eta = (len(files) - i) / current_rate if current_rate > 0 else 0
                progress_pct = i / len(files) * 100
                print(
                    f"  [{target_name}] Rate: {current_rate:.2f} files/sec - Progress: {i}/{len(files)} ({progress_pct:.1f}%) - ETA: {eta/60:.1f}min"
                )

    return created, exists, errors


def main():
    """Main processing function"""
    args = parse_arguments()

    # Determine processing type
    processing_type = "temporal" if args.TEMPORAL else "spectral"

    # Setup
    config = load_config(args.config)

    # Determine input directory: use --input if provided, otherwise fall back to config
    if args.input:
        input_directory = args.input
        input_source = "command line"
    else:
        input_directory = config.get("input_directory")
        if not input_directory:
            console.print(
                "[bold red]❌ No input directory specified. Use --input or set input_directory in config file.[/bold red]"
            )
            return
        input_source = "config file"

    # Set target indices - default to all targets if not specified
    target_indices = args.target if args.target else list(range(10))

    # Create title panel
    dry_run_text = " [red](DRY-RUN MODE)[/red]" if args.dry_run else ""
    title_text = f"🎵 [bold blue]Acoustic Indices Processing Starting...[/bold blue]{dry_run_text}"
    
    setup_table = Table(show_header=False, box=box.MINIMAL)
    setup_table.add_row("Input directory:", f"{input_directory} [dim](from {input_source})[/dim]")
    setup_table.add_row("Configuration:", args.config)
    setup_table.add_row("Processing type:", processing_type.upper())
    setup_table.add_row("Target groups:", str(target_indices))
    
    if args.dry_run:
        setup_table.add_row("Mode:", "[red]🔍 Dry-run mode: No actual processing or database writes will occur[/red]")
    
    console.print(Panel(setup_table, title=title_text, border_style="blue"))
    
    device = setup_device()

    # Find and filter files
    console.rule(f"[bold green]File Discovery", style="green")
    all_files = find_files_by_type(input_directory, processing_type)

    if not all_files:
        console.print(f"[bold red]No {processing_type} files found![/bold red]")
        return

    # Apply target filtering
    target_files = filter_files_by_target(all_files, target_indices)

    target_str = "_".join(map(str, target_indices))
    target_name = f"{processing_type.upper()}_GROUP_{target_str}"

    console.print(f"[bold green]🎯 Processing {target_name}: {len(target_files)}/{len(all_files)} files[/bold green]")

    if not target_files:
        console.print("[bold red]No files to process![/bold red]")
        return

    # Show dry-run report if in dry-run mode
    if args.dry_run:
        create_dry_run_report(processing_type, config, target_files, all_files)

    # Process files based on type
    if processing_type == "temporal":
        created, exists, errors = process_temporal_files(
            target_files, config, target_name, args.force, args.dry_run
        )
    else:  # spectral
        created, exists, errors = process_spectral_files(
            target_files, config, device, target_name, args.force, args.dry_run
        )

    # Create results table
    console.print()
    console.rule("[bold green]Processing Complete", style="green")
    
    results_table = Table(title=f"🎉 {target_name} Results", box=box.ROUNDED)
    results_table.add_column("Metric", style="cyan", no_wrap=True)
    results_table.add_column("Count", style="magenta", justify="right")
    
    if args.dry_run:
        results_table.add_row("Would Create", str(created))
        results_table.add_row("Already Exists", str(exists))  
        results_table.add_row("Errors", str(errors))
        
        console.print(results_table)
        
        # Add dry-run reminder panel
        reminder_text = "[green]💡 Run without --dry-run to execute actual processing[/green]"
        reminder_panel = Panel(reminder_text, title="Next Steps", border_style="green")
        console.print(reminder_panel)
    else:
        results_table.add_row("Created", str(created))
        results_table.add_row("Already Existed", str(exists))
        results_table.add_row("Errors", str(errors))
        
        console.print(results_table)


if __name__ == "__main__":
    main()
