#!/usr/bin/env python3
"""
Temporal Indices Processor
Processes WAV files to compute temporal domain acoustic indices
"""

import torchaudio
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
from maad import features

from .base_index import AcousticIndex


class TemporalIndicesProcessor(AcousticIndex):
    """Processor for temporal domain acoustic indices from WAV files"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize temporal indices processor
        
        Args:
            config: Configuration dictionary with temporal settings
        """
        super().__init__(config)
        self._setup_from_config("temporal")
        
        # Get temporal-specific config
        temporal_config = config.get('acoustic_indices', {}).get('temporal', {})
        
        # Support both old and new config formats
        if 'enabled' in temporal_config:
            # Old format: list of enabled indices
            self.enabled_indices = temporal_config.get('enabled', ['temporal_entropy', 'temporal_activity', 'temporal_median'])
            self.named_indices = {}
        else:
            # New format: named indices with processor + params
            self.named_indices = {k: v for k, v in temporal_config.items() 
                                if isinstance(v, dict) and 'processor' in v}
            self.enabled_indices = list(self.named_indices.keys())
        
        print(f"Temporal Indices Processor initialized:")
        print(f"  Enabled indices: {self.enabled_indices}")
        print(f"  Chunk duration: {self.chunk_duration_sec}s")
        print(f"  Chunks per file: {self.n_chunks}")
        if self.named_indices:
            print(f"  Using generalized named indices format")
            for name, config in self.named_indices.items():
                params = config.get('params', {})
                print(f"    {name}: {config['processor']} {params}")
        else:
            print(f"  Using legacy format")
    
    def get_processing_type(self) -> str:
        """Return processing type identifier"""
        return "temporal"
    
    def get_enabled_indices(self) -> List[str]:
        """Return list of enabled temporal indices"""
        return self.enabled_indices
    
    def process_file(self, wav_file: str) -> Dict[str, np.ndarray]:
        """
        Process a single WAV file to compute temporal indices
        
        Args:
            wav_file: Path to WAV file
            
        Returns:
            Dict[str, np.ndarray]: Mapping of index_name -> values array
        """
        # Validate file exists and has correct extension
        wav_path = Path(wav_file)
        if not wav_path.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_file}")
        
        if wav_path.suffix.upper() != '.WAV':
            raise ValueError(f"File is not a WAV file: {wav_file}")
        
        # Load audio and validate properties
        waveform, sample_rate = torchaudio.load(wav_file)
        
        if sample_rate != self.sample_rate:
            raise ValueError(f"Sample rate mismatch: {sample_rate} != {self.sample_rate}")
        
        # Convert to mono if needed
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        
        audio = waveform.squeeze().numpy()
        
        # Validate duration with tolerance
        duration_sec = len(audio) / sample_rate
        tolerance_sec = 2.0
        if abs(duration_sec - self.file_duration_sec) > tolerance_sec:
            print(f"  ⚠️  Skipping file: duration {duration_sec}s outside tolerance ±{tolerance_sec}s of expected {self.file_duration_sec}s")
            # Return special marker to indicate file should be marked as skipped
            return {'_skipped': True, 'reason': f'duration_{duration_sec}s', 'filepath': str(wav_path)}
        
        # Adjust chunk count for shorter files within tolerance
        max_chunks = len(audio) // self.samples_per_chunk
        actual_chunks = min(self.n_chunks, max_chunks)
        
        if actual_chunks < self.n_chunks:
            print(f"  Using {actual_chunks} chunks instead of {self.n_chunks} due to file length")
        
        # Store actual chunk count for timestamp generation
        self._last_processed_chunks = actual_chunks
        
        # Compute indices by chunks
        results = {}
        
        for index_name in self.enabled_indices:
            if self.named_indices and index_name in self.named_indices:
                # New format: use processor and params from named index
                index_config = self.named_indices[index_name]
                processor_name = index_config['processor']
                params = index_config.get('params', {})
                
                # For temporal indices, database name is usually the same as cosmetic name
                # since temporal indices typically don't have frequency-dependent parameters
                db_name = index_name
                index_values = self._compute_named_index_chunks(audio, sample_rate, processor_name, params, actual_chunks)
                results[db_name] = index_values
            else:
                # Legacy format: use original method
                index_values = self._compute_index_chunks(audio, sample_rate, index_name, actual_chunks)
                results[index_name] = index_values
        
        return results
    
    def get_chunk_timestamps(self, n_chunks: int = None) -> np.ndarray:
        """
        Generate timestamp array for chunks
        
        Args:
            n_chunks: Number of chunks (uses default if None)
            
        Returns:
            np.ndarray: Start time in seconds for each chunk
        """
        if n_chunks is None:
            # Use actual chunks from last processing if available
            chunks = getattr(self, '_last_processed_chunks', self.n_chunks)
        else:
            chunks = n_chunks
        return np.arange(chunks) * self.chunk_duration_sec
    
    def _compute_index_chunks(self, audio: np.ndarray, sample_rate: int, index_name: str, n_chunks: int) -> np.ndarray:
        """
        Compute a specific temporal index for all chunks
        
        Args:
            audio: Audio waveform
            sample_rate: Audio sample rate
            index_name: Name of temporal index to compute
            
        Returns:
            np.ndarray: Index values for each chunk
        """
        values = []
        
        for i in range(n_chunks):
            start = i * self.samples_per_chunk
            end = start + self.samples_per_chunk
            
            # Strict bounds checking
            if end > len(audio):
                raise ValueError(f"Chunk {i} extends beyond audio length: {end} > {len(audio)}")
            
            chunk = audio[start:end]
            
            # Validate chunk length
            if len(chunk) != self.samples_per_chunk:
                raise ValueError(f"Chunk {i} has unexpected length: {len(chunk)} != {self.samples_per_chunk}")
            
            # Compute the specific temporal index
            value = self._compute_single_temporal_index(chunk, sample_rate, index_name)
            values.append(float(value))
        
        return np.array(values)
    
    def _compute_named_index_chunks(self, audio: np.ndarray, sample_rate: int, 
                                   processor_name: str, params: Dict[str, Any], n_chunks: int) -> np.ndarray:
        """
        Compute a named temporal index for all chunks using specified processor and parameters
        
        Args:
            audio: Audio waveform
            sample_rate: Audio sample rate
            processor_name: Name of processor method to use
            params: Parameters dict for the processor
            n_chunks: Number of chunks to process
            
        Returns:
            np.ndarray: Index values for each chunk
        """
        values = []
        
        for i in range(n_chunks):
            start = i * self.samples_per_chunk
            end = start + self.samples_per_chunk
            
            # Strict bounds checking
            if end > len(audio):
                raise ValueError(f"Chunk {i} extends beyond audio length: {end} > {len(audio)}")
            
            chunk = audio[start:end]
            
            # Validate chunk length
            if len(chunk) != self.samples_per_chunk:
                raise ValueError(f"Chunk {i} has unexpected length: {len(chunk)} != {self.samples_per_chunk}")
            
            # Compute the specific temporal index with parameters
            value = self._compute_single_named_index(chunk, sample_rate, processor_name, params)
            values.append(float(value))
        
        return np.array(values)
    
    def _compute_single_temporal_index(self, chunk: np.ndarray, sample_rate: int, index_name: str) -> float:
        """
        Compute a single temporal index value for one chunk
        
        Args:
            chunk: Audio chunk (1D array)
            sample_rate: Audio sample rate
            index_name: Name of index to compute
            
        Returns:
            float: Computed index value
        """
        # Map index names to maad functions with correct signatures
        if index_name == 'temporal_entropy':
            return float(features.temporal_entropy(chunk))
        
        elif index_name == 'temporal_activity':
            # temporal_activity returns (activity, count, mean_db)
            activity, count, mean_db = features.temporal_activity(chunk)
            return float(activity)  # Use the activity value
        
        elif index_name == 'temporal_median':
            return float(features.temporal_median(chunk))
        
        else:
            raise ValueError(f"Unsupported temporal index: {index_name}")
    
    def _compute_single_named_index(self, chunk: np.ndarray, sample_rate: int, 
                                   processor_name: str, params: Dict[str, Any]) -> float:
        """
        Compute a single temporal index value for one chunk using named processor and parameters
        
        Args:
            chunk: Audio chunk (1D array)
            sample_rate: Audio sample rate
            processor_name: Name of processor method to use
            params: Parameters dict for the processor
            
        Returns:
            float: Computed index value
        """
        # Map processor names to maad functions with parameters
        if processor_name == 'temporal_entropy':
            return float(features.temporal_entropy(chunk))
        
        elif processor_name == 'temporal_activity':
            # temporal_activity returns (activity, count, mean_db)
            activity, count, mean_db = features.temporal_activity(chunk)
            # Use params to select which value to return (default: activity)
            return_value = params.get('return_value', 'activity')
            if return_value == 'activity':
                return float(activity)
            elif return_value == 'count':
                return float(count)
            elif return_value == 'mean_db':
                return float(mean_db)
            else:
                return float(activity)  # Default fallback
        
        elif processor_name == 'temporal_median':
            return float(features.temporal_median(chunk))
        
        elif processor_name == 'maad_temporal_activity':
            # MAAD temporal activity index (AAI temporal component)
            # This is the temporal component of the Audio Activity Index
            activity, count, mean_db = features.temporal_activity(chunk)
            return float(activity)
        
        else:
            raise ValueError(f"Unsupported temporal processor: {processor_name}")
    
    def get_supported_indices(self) -> List[str]:
        """
        Return list of all supported temporal indices
        
        Returns:
            List[str]: All available temporal index names
        """
        return [
            'temporal_entropy',
            'temporal_activity', 
            'temporal_median'
        ]