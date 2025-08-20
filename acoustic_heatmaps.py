#!/usr/bin/env python3
"""
Acoustic Indices Heatmap Generator

Generates heatmaps from acoustic indices stored in the database.
Supports single/multiple indices, false-color RGB composites, and various matplotlib colormaps.

Usage:
    python acoustic_heatmaps.py --config config_mac.yaml
    python acoustic_heatmaps.py --config config_mac.yaml --indices acoustic_diversity_index
    python acoustic_heatmaps.py --config config_mac.yaml --indices adi,aei,te --false-color
    python acoustic_heatmaps.py --config config_mac.yaml --colormap plasma --output ./heatmaps/
"""

import argparse
import os
import sys
import yaml
import sqlite3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from pathlib import Path
from audio_database import AudioDatabase

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich import box

# Initialize Rich console
console = Console()


class ConfigLoader:
    """Load and parse configuration from YAML file."""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load config from {self.config_path}: {e}")
    
    @property
    def database_path(self):
        """Get database path from config."""
        return self.config.get('database_path', 'audiomoth.db')
    
    @property
    def available_indices(self):
        """Get list of available indices from config."""
        indices = []
        acoustic_config = self.config.get('acoustic_indices', {})
        
        # Temporal indices
        temporal = acoustic_config.get('temporal', {})
        for key in temporal.keys():
            if key != 'chunk_duration_sec':
                indices.append(key)
        
        # Spectral indices  
        spectral = acoustic_config.get('spectral', {})
        for key in spectral.keys():
            if key != 'chunk_duration_sec':
                indices.append(key)
                
        return indices


class DataProcessor:
    """Process acoustic indices data for heatmap generation."""
    
    def __init__(self, database_path):
        self.database_path = database_path
        self.db = AudioDatabase(database_path)
    
    def get_available_indices(self):
        """Get all available index names from database."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT index_name FROM acoustic_indices ORDER BY index_name")
        indices = [row[0] for row in cursor.fetchall()]
        conn.close()
        return indices
    
    def get_date_range(self):
        """Get the date range of available data."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                MIN(DATE(recording_datetime)) as start_date,
                MAX(DATE(recording_datetime)) as end_date
            FROM acoustic_indices
        """)
        result = cursor.fetchone()
        conn.close()
        return result[0], result[1]
    
    def extract_hourly_data(self, index_names, start_date=None, end_date=None):
        """Extract and aggregate acoustic indices data to hourly resolution."""
        if isinstance(index_names, str):
            index_names = [index_names]
        
        conn = sqlite3.connect(self.database_path)
        
        # Build query conditions
        conditions = ["index_name IN ({})".format(','.join(['?' for _ in index_names]))]
        params = list(index_names)
        
        if start_date:
            conditions.append("DATE(recording_datetime) >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("DATE(recording_datetime) <= ?")
            params.append(end_date)
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
        SELECT 
            index_name,
            DATE(recording_datetime) as date,
            CAST(strftime('%H', recording_datetime) as INTEGER) as hour,
            AVG(value) as mean_value,
            COUNT(value) as value_count,
            MIN(value) as min_value,
            MAX(value) as max_value,
            processing_type
        FROM acoustic_indices
        WHERE {where_clause}
        GROUP BY index_name, DATE(recording_datetime), CAST(strftime('%H', recording_datetime) as INTEGER)
        ORDER BY date, hour, index_name
        """
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
    
    def create_heatmap_matrix(self, df, index_name):
        """Create a 2D matrix (hours x days) for heatmap visualization."""
        index_data = df[df['index_name'] == index_name].copy()
        
        if index_data.empty:
            return None, None, None
        
        # Convert date strings to datetime
        index_data['date'] = pd.to_datetime(index_data['date'])
        
        # Get date range
        start_date = index_data['date'].min()
        end_date = index_data['date'].max()
        
        # Create complete date range
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Create pivot table with hours as rows, dates as columns
        pivot_data = index_data.pivot_table(
            index='hour',
            columns='date', 
            values='mean_value',
            fill_value=np.nan
        )
        
        # Ensure we have all 24 hours
        full_hours = pd.RangeIndex(0, 24, name='hour')
        pivot_data = pivot_data.reindex(index=full_hours, columns=date_range, fill_value=np.nan)
        
        return pivot_data, start_date, end_date


class HeatmapGenerator:
    """Generate heatmap visualizations using seaborn."""
    
    def __init__(self, colormap='viridis', figsize_per_week=(12, 8)):
        self.colormap = colormap
        self.figsize_per_week = figsize_per_week
    
    def create_single_heatmap(self, data_matrix, index_name, output_path):
        """Create a single heatmap for one acoustic index."""
        if data_matrix is None or data_matrix.empty:
            return False
        
        # Calculate figure size based on number of days
        n_days = data_matrix.shape[1]
        n_weeks = max(1, n_days / 7)
        figsize = (self.figsize_per_week[0] * (n_weeks / 4), self.figsize_per_week[1])
        
        plt.figure(figsize=figsize)
        
        # Create column labels (dates)
        date_labels = [col.strftime('%m-%d') for col in data_matrix.columns]
        
        # Create heatmap
        ax = sns.heatmap(
            data_matrix,
            cmap=self.colormap,
            cbar_kws={'label': f'{index_name}'},
            xticklabels=date_labels,
            yticklabels=True,
            linewidths=0.1,
            linecolor='white'
        )
        
        # Customize appearance
        ax.set_xlabel('Date')
        ax.set_ylabel('Hour of Day')
        ax.set_title(f'Acoustic Index Heatmap: {index_name}', fontsize=14, fontweight='bold')
        
        # Rotate x-axis labels for better readability
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        
        # Set y-axis to show every 4 hours
        ax.set_yticks(range(0, 24, 4))
        ax.set_yticklabels([f'{h:02d}:00' for h in range(0, 24, 4)])
        
        # Set x-axis to show every 7th day (weekly)
        n_dates = len(date_labels)
        step = max(1, n_dates // 20)  # Show roughly 20 date labels max
        ax.set_xticks(range(0, n_dates, step))
        ax.set_xticklabels([date_labels[i] for i in range(0, n_dates, step)])
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return True
    
    def create_multi_panel_heatmap(self, data_matrices, index_names, output_path):
        """Create a multi-panel figure with multiple heatmaps."""
        n_indices = len(index_names)
        if n_indices == 0:
            return False
        
        # Calculate subplot layout
        n_cols = min(2, n_indices)
        n_rows = (n_indices + n_cols - 1) // n_cols
        
        # Calculate figure size
        sample_matrix = next(iter(data_matrices.values()))
        n_days = sample_matrix.shape[1] if sample_matrix is not None else 30
        n_weeks = max(1, n_days / 7)
        
        figsize = (self.figsize_per_week[0] * n_cols * (n_weeks / 4), 
                   self.figsize_per_week[1] * n_rows)
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        if n_indices == 1:
            axes = [axes]
        elif n_rows == 1 and n_cols == 1:
            axes = [axes]
        else:
            axes = axes.flatten()
        
        for i, index_name in enumerate(index_names):
            data_matrix = data_matrices.get(index_name)
            
            if data_matrix is None or data_matrix.empty:
                axes[i].text(0.5, 0.5, f'No data\n{index_name}', 
                           ha='center', va='center', transform=axes[i].transAxes)
                axes[i].set_xticks([])
                axes[i].set_yticks([])
                continue
            
            # Create date labels
            date_labels = [col.strftime('%m-%d') for col in data_matrix.columns]
            
            # Create heatmap
            sns.heatmap(
                data_matrix,
                cmap=self.colormap,
                ax=axes[i],
                cbar_kws={'label': index_name} if i == 0 else None,
                cbar=i == 0,  # Only show colorbar for first subplot
                xticklabels=False,  # Simplified for multi-panel
                yticklabels=True if i % n_cols == 0 else False,  # Y-labels only for leftmost
                linewidths=0.05,
                linecolor='white'
            )
            
            axes[i].set_title(index_name, fontsize=10, fontweight='bold')
            
            if i >= (n_rows - 1) * n_cols:  # Bottom row
                axes[i].set_xlabel('Date')
            if i % n_cols == 0:  # Left column
                axes[i].set_ylabel('Hour')
        
        # Hide empty subplots
        for i in range(n_indices, len(axes)):
            axes[i].set_visible(False)
        
        plt.suptitle('Acoustic Indices Heatmaps', fontsize=16, fontweight='bold')
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return True


class FalseColorGenerator:
    """Generate false-color RGB composites from multiple acoustic indices."""
    
    def __init__(self):
        pass
    
    def normalize_data(self, data_matrix):
        """Normalize data matrix to 0-1 range for RGB mapping."""
        if data_matrix is None or data_matrix.empty:
            return None
        
        # Handle NaN values
        valid_data = data_matrix.values[~np.isnan(data_matrix.values)]
        if len(valid_data) == 0:
            return None
        
        # Normalize to 0-1 using percentile-based scaling to handle outliers
        p1, p99 = np.percentile(valid_data, [1, 99])
        normalized = np.clip((data_matrix.values - p1) / (p99 - p1), 0, 1)
        
        return normalized
    
    def create_false_color_image(self, data_matrices, index_names, output_path):
        """Create false-color RGB composite from 2-3 acoustic indices."""
        if len(index_names) < 2 or len(index_names) > 3:
            raise ValueError("False-color requires 2-3 indices")
        
        # Get data matrices
        matrices = []
        valid_names = []
        
        for name in index_names:
            if name in data_matrices:
                normalized = self.normalize_data(data_matrices[name])
                if normalized is not None:
                    matrices.append(normalized)
                    valid_names.append(name)
        
        if len(matrices) < 2:
            return False
        
        # Ensure all matrices have same shape
        shape = matrices[0].shape
        for i, matrix in enumerate(matrices[1:], 1):
            if matrix.shape != shape:
                return False
        
        # Create RGB channels
        if len(matrices) == 2:
            # 2 indices: R=index1, G=index2, B=mean(index1,index2)
            rgb_array = np.zeros((shape[0], shape[1], 3))
            rgb_array[:, :, 0] = matrices[0]  # Red
            rgb_array[:, :, 1] = matrices[1]  # Green
            rgb_array[:, :, 2] = (matrices[0] + matrices[1]) / 2  # Blue
            channel_names = [f'R={valid_names[0]}', f'G={valid_names[1]}', 'B=Mean(R,G)']
        else:
            # 3 indices: R=index1, G=index2, B=index3
            rgb_array = np.zeros((shape[0], shape[1], 3))
            rgb_array[:, :, 0] = matrices[0]  # Red
            rgb_array[:, :, 1] = matrices[1]  # Green
            rgb_array[:, :, 2] = matrices[2]  # Blue
            channel_names = [f'R={valid_names[0]}', f'G={valid_names[1]}', f'B={valid_names[2]}']
        
        # Handle NaN values by setting them to black
        nan_mask = np.isnan(rgb_array)
        rgb_array[nan_mask] = 0
        
        # Create the plot
        sample_matrix = data_matrices[valid_names[0]]
        n_days = sample_matrix.shape[1]
        n_weeks = max(1, n_days / 7)
        figsize = (12 * (n_weeks / 4), 8)
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # Display the false-color image
        im = ax.imshow(rgb_array, aspect='auto', origin='upper')
        
        # Create date labels
        date_labels = [col.strftime('%m-%d') for col in sample_matrix.columns]
        
        # Set ticks and labels
        ax.set_xticks(range(0, len(date_labels), max(1, len(date_labels) // 20)))
        ax.set_xticklabels([date_labels[i] for i in range(0, len(date_labels), max(1, len(date_labels) // 20))])
        ax.set_yticks(range(0, 24, 4))
        ax.set_yticklabels([f'{h:02d}:00' for h in range(0, 24, 4)])
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Hour of Day')
        ax.set_title(f'False-Color Composite\n{" | ".join(channel_names)}', 
                    fontsize=14, fontweight='bold')
        
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return True


def list_indices_and_exit(available_indices):
    """Display numbered list of available indices and exit."""
    console.print()
    console.print(Panel.fit(
        "[bold blue]📋 Available Acoustic Indices[/bold blue]\n"
        "[dim]Use these numbers or names with --indices[/dim]",
        border_style="blue"
    ))
    console.print()
    
    # Create numbered indices table
    indices_table = Table(title="🔢 Numbered Index List", box=box.ROUNDED, show_header=True)
    indices_table.add_column("#", style="bold magenta", width=3)
    indices_table.add_column("Index Name", style="cyan", no_wrap=True)
    indices_table.add_column("Type", style="green", width=15)
    indices_table.add_column("Abbreviation", style="yellow", width=12)
    
    for i, idx in enumerate(available_indices, 1):
        # Categorize indices
        if 'temporal' in idx.lower():
            idx_type = "Temporal"
            abbrev = "te" if 'entropy' in idx else "ta" if 'activity' in idx else "tm"
        elif any(x in idx.lower() for x in ['bai', 'soundscape', 'frog']):
            idx_type = "Species-specific"
            abbrev = idx.split('_')[0][:3].upper() if '_' in idx else idx[:3].upper()
        elif any(x in idx.lower() for x in ['diversity', 'eveness']):
            idx_type = "Diversity"
            abbrev = "ADI" if 'diversity' in idx else "AEI"
        else:
            idx_type = "Spectral"
            abbrev = idx[:3].upper()
        
        indices_table.add_row(str(i), idx, idx_type, abbrev)
    
    console.print(indices_table)
    console.print()
    
    # Usage examples
    examples_panel = Panel.fit(
        "[bold green]Usage Examples:[/bold green]\n"
        "[dim]# Select by numbers:[/dim]\n"
        "python acoustic_heatmaps.py --config config.yaml --indices 1,2,3\n\n"
        "[dim]# Select by names:[/dim]\n"
        "python acoustic_heatmaps.py --config config.yaml --indices temporal_entropy,ADI\n\n"
        "[dim]# Mix numbers and names:[/dim]\n"
        "python acoustic_heatmaps.py --config config.yaml --indices 1,temporal_entropy,3\n\n"
        "[dim]# False-color with numbers:[/dim]\n"
        "python acoustic_heatmaps.py --config config.yaml --indices 1,2,3 --false-color",
        title="💡 Examples",
        border_style="green"
    )
    console.print(examples_panel)
    console.print()
    sys.exit(0)


def resolve_indices(indices_input, available_indices):
    """Convert mixed number/name input to actual index names."""
    if not indices_input:
        return available_indices
    
    requested_items = [item.strip() for item in indices_input.split(',')]
    resolved_indices = []
    
    for item in requested_items:
        # Try to parse as number first
        try:
            index_num = int(item)
            if 1 <= index_num <= len(available_indices):
                resolved_indices.append(available_indices[index_num - 1])
            else:
                console.print(f"❌ [red]Invalid index number:[/red] {index_num} (valid range: 1-{len(available_indices)})")
                sys.exit(1)
        except ValueError:
            # Not a number, treat as index name
            if item in available_indices:
                resolved_indices.append(item)
            else:
                # Check for abbreviations or partial matches
                matches = [idx for idx in available_indices if item.lower() in idx.lower()]
                if len(matches) == 1:
                    resolved_indices.append(matches[0])
                elif len(matches) > 1:
                    console.print(f"❌ [red]Ambiguous index name:[/red] '{item}' matches multiple indices:")
                    for match in matches:
                        console.print(f"  - {match}")
                    sys.exit(1)
                else:
                    console.print(f"❌ [red]Unknown index:[/red] '{item}'")
                    console.print(f"[yellow]Use --list to see available indices[/yellow]")
                    sys.exit(1)
    
    return resolved_indices


def main():
    # Print header
    console.print()
    console.print(Panel.fit(
        "[bold blue]🎵 Acoustic Indices Heatmap Generator[/bold blue]\n"
        "[dim]Generate beautiful heatmaps from bioacoustic data[/dim]",
        border_style="blue"
    ))
    console.print()

    parser = argparse.ArgumentParser(description='Generate acoustic indices heatmaps')
    parser.add_argument('--config', required=True, help='Path to configuration YAML file')
    parser.add_argument('--list', action='store_true', help='List available indices with numbers and exit')
    parser.add_argument('--indices', help='Comma-separated list of indices (names or numbers) to process (default: all)')
    parser.add_argument('--colormap', default='viridis', help='Matplotlib colormap name (default: viridis)')
    parser.add_argument('--false-color', action='store_true', help='Generate false-color RGB composite (requires 2-3 indices)')
    parser.add_argument('--output', default='.', help='Output directory for PNG files (default: current directory)')
    parser.add_argument('--start-date', help='Start date for analysis (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date for analysis (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # Load configuration
    with console.status("[bold green]Loading configuration...") as status:
        try:
            config_loader = ConfigLoader(args.config)
            console.print(f"✅ [green]Configuration loaded:[/green] {args.config}")
        except Exception as e:
            console.print(f"❌ [red]Configuration error:[/red] {e}")
            sys.exit(1)
    
    # Initialize data processor
    with console.status("[bold green]Connecting to database...") as status:
        try:
            processor = DataProcessor(config_loader.database_path)
            console.print(f"✅ [green]Database connected:[/green] {config_loader.database_path}")
        except Exception as e:
            console.print(f"❌ [red]Database error:[/red] {e}")
            sys.exit(1)
    
    # Get available indices
    with console.status("[bold green]Scanning available indices..."):
        available_indices = processor.get_available_indices()
    
    # Handle --list option
    if args.list:
        list_indices_and_exit(available_indices)
    
    # Create indices table
    indices_table = Table(title="📊 Available Acoustic Indices", box=box.ROUNDED)
    indices_table.add_column("Index", style="cyan", no_wrap=True)
    indices_table.add_column("Type", style="magenta")
    
    for idx in available_indices:
        # Categorize indices
        if 'temporal' in idx.lower():
            idx_type = "Temporal"
        elif any(x in idx.lower() for x in ['bai', 'soundscape', 'frog']):
            idx_type = "Species-specific"
        elif any(x in idx.lower() for x in ['diversity', 'eveness']):
            idx_type = "Diversity"
        else:
            idx_type = "Spectral"
        
        indices_table.add_row(idx, idx_type)
    
    console.print(indices_table)
    console.print()
    
    # Determine indices to process (resolve numbers/names/abbreviations)
    indices_to_process = resolve_indices(args.indices, available_indices)
    
    # Create processing summary
    summary_table = Table(title="🔄 Processing Summary", box=box.SIMPLE)
    summary_table.add_column("Parameter", style="bold cyan")
    summary_table.add_column("Value", style="white")
    
    # Get date range
    db_start, db_end = processor.get_date_range()
    start_date = args.start_date or db_start
    end_date = args.end_date or db_end
    
    summary_table.add_row("Indices to process", str(len(indices_to_process)))
    summary_table.add_row("Date range", f"{start_date} → {end_date}")
    summary_table.add_row("Colormap", args.colormap)
    summary_table.add_row("Output directory", str(args.output))
    summary_table.add_row("Mode", "False-color RGB" if args.false_color else "Standard heatmap")
    
    console.print(summary_table)
    console.print()
    
    # Extract data with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        # Data extraction
        task1 = progress.add_task("Extracting hourly data...", total=1)
        df = processor.extract_hourly_data(indices_to_process, start_date, end_date)
        progress.update(task1, completed=1)
        console.print(f"✅ [green]Extracted[/green] {len(df):,} hourly data points")
        
        # Create data matrices
        task2 = progress.add_task("Creating data matrices...", total=len(indices_to_process))
        data_matrices = {}
        matrix_stats = []
        
        for index_name in indices_to_process:
            matrix, _, _ = processor.create_heatmap_matrix(df, index_name)
            data_matrices[index_name] = matrix
            if matrix is not None:
                rows, cols = matrix.shape
                valid_points = (~matrix.isna()).sum().sum()
                total_points = rows * cols
                completeness = (valid_points / total_points) * 100
                matrix_stats.append({
                    "index": index_name,
                    "shape": f"{rows}×{cols}",
                    "completeness": f"{completeness:.1f}%"
                })
            else:
                matrix_stats.append({
                    "index": index_name,
                    "shape": "No data",
                    "completeness": "0%"
                })
            progress.update(task2, advance=1)
    
    # Show matrix statistics
    matrix_table = Table(title="📈 Data Matrix Statistics", box=box.ROUNDED)
    matrix_table.add_column("Index", style="cyan")
    matrix_table.add_column("Dimensions", style="yellow")
    matrix_table.add_column("Completeness", style="green")
    
    for stat in matrix_stats:
        matrix_table.add_row(stat["index"], stat["shape"], stat["completeness"])
    
    console.print(matrix_table)
    console.print()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"📁 [blue]Output directory:[/blue] {output_dir.absolute()}")
    
    # Generate visualizations with progress
    heatmap_gen = HeatmapGenerator(colormap=args.colormap)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        if args.false_color:
            # Generate false-color composite
            if len(indices_to_process) < 2 or len(indices_to_process) > 3:
                console.print("❌ [red]False-color mode requires 2-3 indices[/red]")
                sys.exit(1)
            
            task = progress.add_task("Creating false-color composite...", total=1)
            false_color_gen = FalseColorGenerator()
            output_path = output_dir / f"false_color_{'_'.join(indices_to_process[:3])}.png"
            false_color_gen.create_false_color_image(data_matrices, indices_to_process, output_path)
            progress.update(task, completed=1)
            
            console.print(f"🎨 [magenta]False-color composite saved:[/magenta] {output_path.name}")
        
        elif len(indices_to_process) == 1:
            # Single heatmap
            task = progress.add_task("Creating single heatmap...", total=1)
            index_name = indices_to_process[0]
            output_path = output_dir / f"{index_name}_heatmap.png"
            heatmap_gen.create_single_heatmap(data_matrices[index_name], index_name, output_path)
            progress.update(task, completed=1)
            
            console.print(f"🔥 [yellow]Single heatmap saved:[/yellow] {output_path.name}")
        
        elif len(indices_to_process) <= 6:
            # Multi-panel heatmap
            task = progress.add_task("Creating multi-panel heatmap...", total=1)
            output_path = output_dir / f"multi_indices_heatmap.png"
            heatmap_gen.create_multi_panel_heatmap(data_matrices, indices_to_process, output_path)
            progress.update(task, completed=1)
            
            console.print(f"📊 [cyan]Multi-panel heatmap saved:[/cyan] {output_path.name}")
        
        else:
            # Individual heatmaps for many indices
            task = progress.add_task("Creating individual heatmaps...", total=len(indices_to_process))
            saved_files = []
            for index_name in indices_to_process:
                output_path = output_dir / f"{index_name}_heatmap.png"
                heatmap_gen.create_single_heatmap(data_matrices[index_name], index_name, output_path)
                saved_files.append(output_path.name)
                progress.update(task, advance=1)
            
            console.print(f"🔥 [yellow]Individual heatmaps saved:[/yellow] {len(saved_files)} files")
    
    # Success message
    console.print()
    console.print(Panel.fit(
        "[bold green]✅ Heatmap generation complete![/bold green]\n"
        f"[dim]Files saved to: {output_dir.absolute()}[/dim]",
        border_style="green"
    ))
    console.print()


if __name__ == '__main__':
    main()