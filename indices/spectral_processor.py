#!/usr/bin/env python3
"""
Spectral Indices Processor
Processes NPZ spectrogram files to compute spectral domain acoustic indices
"""

import os
import torch
import numpy as np
from typing import Dict, List, Any
from maad import features

from .base_index import AcousticIndex


class SpectralIndicesProcessor(AcousticIndex):
    """Processor for spectral domain acoustic indices from NPZ spectrograms"""
    
    def __init__(self, config: Dict[str, Any], device: torch.device):
        """
        Initialize spectral indices processor
        
        Args:
            config: Configuration dictionary with spectral settings
            device: PyTorch device for GPU processing
        """
        super().__init__(config)
        self.device = device
        
        # Setup base parameters from config
        self._setup_from_config("spectral")
        
        # Get spectral-specific config
        spectral_config = config.get('acoustic_indices', {}).get('spectral', {})
        
        # Support both old and new config formats
        if 'enabled' in spectral_config:
            # Old format: list of enabled indices with global parameters
            self.enabled_indices = spectral_config.get('enabled', ['acoustic_complexity_index', 'acoustic_diversity_index'])
            self.named_indices = {}
            # Convert old format to named indices for backward compatibility
            self.bioacoustics_freq_min = spectral_config.get('bioacoustics_freq_min', 2000)
            self.bioacoustics_freq_max = spectral_config.get('bioacoustics_freq_max', 8000)
        else:
            # New format: named indices with processor + params
            self.named_indices = {k: v for k, v in spectral_config.items() 
                                if isinstance(v, dict) and 'processor' in v}
            self.enabled_indices = list(self.named_indices.keys())
            # Legacy parameters for backward compatibility
            self.bioacoustics_freq_min = 2000
            self.bioacoustics_freq_max = 8000
        
        # NPZ spectrogram parameters (dynamic sizing)
        self.pixels_per_chunk = None  # Will be calculated per file
        
        print(f"Spectral Indices Processor initialized:")
        print(f"  Device: {self.device}")
        print(f"  Enabled indices: {self.enabled_indices}")
        print(f"  Chunk duration: {self.chunk_duration_sec}s")
        print(f"  Chunks per file: {self.n_chunks}")
        if self.named_indices:
            print(f"  Using generalized named indices format")
            for name, config in self.named_indices.items():
                params = config.get('params', {})
                print(f"    {name}: {config['processor']} {params}")
        else:
            print(f"  Using legacy format - Bioacoustics index frequency range: {self.bioacoustics_freq_min}-{self.bioacoustics_freq_max} Hz")
    
    def get_processing_type(self) -> str:
        """Return processing type identifier"""
        return "spectral"
    
    def get_enabled_indices(self) -> List[str]:
        """Return list of enabled spectral indices"""
        return self.enabled_indices
    
    def process_file(self, npz_file: str) -> Dict[str, np.ndarray]:
        """
        Process a single NPZ spectrogram file to compute spectral indices
        
        Args:
            npz_file: Path to NPZ spectrogram file
            
        Returns:
            Dict[str, np.ndarray]: Mapping of index_name -> values array
        """
        # Validate file exists and has correct extension
        if not os.path.exists(npz_file):
            raise FileNotFoundError(f"NPZ file not found: {npz_file}")
        
        if not npz_file.lower().endswith('.npz'):
            raise ValueError(f"File is not a NPZ file: {npz_file}")
        
        # Load NPZ spectrogram data
        npz_data = np.load(npz_file)
        
        # Extract spectrogram array and frequency information
        spectrogram_array = npz_data['spec']  # Shape: (freq_bins, time_bins)
        self.frequency_array = npz_data['fn']  # Frequency array for this file
        
        # Move to GPU tensor
        spectrogram_tensor = torch.from_numpy(spectrogram_array).float().to(self.device)
        
        npz_data.close()
        
        # Validate spectrogram has reasonable dimensions (NPZ files have variable time length)
        freq_bins, time_bins = spectrogram_tensor.shape
        print(f"Loaded NPZ spectrogram: {freq_bins} freq bins x {time_bins} time bins")
        
        # Compute indices by chunks
        results = {}
        
        # Calculate chunk size based on NPZ time dimensions
        time_bins = spectrogram_tensor.shape[1]
        self.pixels_per_chunk = time_bins // self.n_chunks
        
        print(f"Processing with {self.n_chunks} chunks of {self.pixels_per_chunk} time bins each")
        
        for index_name in self.enabled_indices:
            if self.named_indices and index_name in self.named_indices:
                # New format: use processor and params from named index
                index_config = self.named_indices[index_name]
                processor_name = index_config['processor']
                params = index_config.get('params', {})
                
                # Generate database name with frequency encoding for frequency-dependent indices
                db_name = self._generate_database_name(index_name, processor_name, params)
                index_values = self._compute_named_index_chunks(spectrogram_tensor, index_name, processor_name, params)
                results[db_name] = index_values
            else:
                # Legacy format: use original method but generate proper database names
                index_values = self._compute_index_chunks(spectrogram_tensor, index_name)
                
                # Generate database name with frequency encoding for legacy frequency-dependent indices
                if index_name == 'bioacoustics_index':
                    db_name = f"standard_bai_{int(self.bioacoustics_freq_min)}-{int(self.bioacoustics_freq_max)}"
                elif index_name == 'soundscape_index':
                    db_name = f"standard_soundscape_{int(self.bioacoustics_freq_min)}-{int(self.bioacoustics_freq_max)}"
                else:
                    db_name = index_name  # Non-frequency-dependent indices keep original name
                
                results[db_name] = index_values
        
        return results
    
    def _generate_database_name(self, cosmetic_name: str, processor_name: str, params: Dict[str, Any]) -> str:
        """
        Generate database-friendly name with frequency encoding for frequency-dependent indices
        
        Args:
            cosmetic_name: User-friendly name from config
            processor_name: Underlying processor method
            params: Parameters dict
            
        Returns:
            str: Database name with frequency encoding where applicable
        """
        # For frequency-dependent indices, encode frequency range in name
        freq_dependent_processors = ['bioacoustics_index', 'soundscape_index']
        
        if processor_name in freq_dependent_processors:
            freq_min = params.get('freq_min', params.get('bioacoustic_freq_min', 0))
            freq_max = params.get('freq_max', params.get('bioacoustic_freq_max', 0))
            
            if freq_min and freq_max:
                # Check if cosmetic name already includes frequency range
                freq_pattern = f"{int(freq_min)}-{int(freq_max)}"
                if freq_pattern in cosmetic_name:
                    # Name already includes frequency range, use as-is
                    return cosmetic_name
                else:
                    # Add frequency range to name
                    return f"{cosmetic_name}_{freq_pattern}"
        
        # For non-frequency-dependent indices, use cosmetic name as-is
        return cosmetic_name
    
    def _compute_named_index_chunks(self, spectrogram_tensor: torch.Tensor, 
                                   cosmetic_name: str, processor_name: str, 
                                   params: Dict[str, Any]) -> np.ndarray:
        """
        Compute a named index for all chunks using specified processor and parameters
        
        Args:
            spectrogram_tensor: 2D tensor (height, width) on device
            cosmetic_name: User-friendly name from config
            processor_name: Underlying processor method
            params: Parameters dict
            
        Returns:
            np.ndarray: Index values for each chunk
        """
        height, width = spectrogram_tensor.shape
        values = []
        
        # Process spectrogram in time chunks (columns)
        for i in range(self.n_chunks):
            start_col = i * self.pixels_per_chunk
            end_col = start_col + self.pixels_per_chunk
            
            # Strict bounds checking
            if end_col > width:
                raise ValueError(f"Chunk {i} extends beyond spectrogram width: {end_col} > {width}")
            
            # Extract spectrogram chunk (all frequencies, time slice) on GPU
            chunk_tensor = spectrogram_tensor[:, start_col:end_col]
            
            # Validate chunk size
            if chunk_tensor.shape[1] != self.pixels_per_chunk:
                raise ValueError(f"Chunk {i} has unexpected width: {chunk_tensor.shape[1]} != {self.pixels_per_chunk}")
            
            # Convert to CPU numpy for maad processing (maad is CPU-only)
            chunk_cpu = chunk_tensor.cpu().numpy()
            
            # Compute the specific spectral index with parameters
            value = self._compute_single_named_index(chunk_cpu, processor_name, params)
            if not isinstance(value, (int, float, np.number)):
                # Handle tuple returns by taking the first element
                if isinstance(value, tuple):
                    value = value[0]
                else:
                    value = 0.0
            values.append(float(value))
        
        return np.array(values)
    
    def _compute_index_chunks(self, spectrogram_tensor: torch.Tensor, index_name: str) -> np.ndarray:
        """
        Compute a specific spectral index for all chunks
        
        Args:
            spectrogram_tensor: 2D tensor (height, width) on device
            index_name: Name of spectral index to compute
            
        Returns:
            np.ndarray: Index values for each chunk
        """
        height, width = spectrogram_tensor.shape
        
        values = []
        
        # Process spectrogram in time chunks (columns)
        for i in range(self.n_chunks):
            start_col = i * self.pixels_per_chunk
            end_col = start_col + self.pixels_per_chunk
            
            # Strict bounds checking
            if end_col > width:
                raise ValueError(f"Chunk {i} extends beyond spectrogram width: {end_col} > {width}")
            
            # Extract spectrogram chunk (all frequencies, time slice) on GPU
            chunk_tensor = spectrogram_tensor[:, start_col:end_col]
            
            # Validate chunk size
            if chunk_tensor.shape[1] != self.pixels_per_chunk:
                raise ValueError(f"Chunk {i} has unexpected width: {chunk_tensor.shape[1]} != {self.pixels_per_chunk}")
            
            # Convert to CPU numpy for maad processing (maad is CPU-only)
            # NPZ files are already in proper spectrogram format (dB scale)
            chunk_cpu = chunk_tensor.cpu().numpy()
            
            # Compute the specific spectral index
            value = self._compute_single_spectral_index(chunk_cpu, index_name)
            if not isinstance(value, (int, float, np.number)):
                # Handle tuple returns by taking the first element
                if isinstance(value, tuple):
                    value = value[0]
                else:
                    value = 0.0
            values.append(float(value))
        
        return np.array(values)
    
    def _compute_single_spectral_index(self, chunk: np.ndarray, index_name: str) -> float:
        """
        Compute a single spectral index value for one spectrogram chunk
        
        Args:
            chunk: Spectrogram chunk (2D array: frequency x time)
            index_name: Name of index to compute
            
        Returns:
            float: Computed index value
        """
        # Use the actual frequency array from the NPZ file
        fn = self.frequency_array
        
        # Map index names to maad functions
        if index_name == 'acoustic_complexity_index':
            # Convert dB to linear power scale for correct ACI calculation
            chunk_linear = 10**(chunk / 10)
            _, _, aci_sum = features.acoustic_complexity_index(chunk_linear)
            return float(aci_sum)
        
        elif index_name == 'acoustic_diversity_index':
            return float(features.acoustic_diversity_index(chunk, fn))
        
        elif index_name == 'acoustic_eveness_index':
            return float(features.acoustic_eveness_index(chunk, fn))
        
        elif index_name == 'bioacoustics_index':
            # CRITICAL FIX: Let BAI handle frequency filtering internally to avoid double-filtering bug
            # Convert dB to linear power scale as BAI expects
            chunk_linear = 10**(chunk / 10)
            
            # Use BAI's internal frequency filtering with our target range (500-2000Hz for frogs)
            return float(features.bioacoustics_index(
                chunk_linear, fn, 
                flim=(self.bioacoustics_freq_min, self.bioacoustics_freq_max)
            ))
        
        elif index_name == 'frequency_entropy':
            # CRITICAL FIX: frequency_entropy returns (nan, array) - extract valid values from array
            result = features.frequency_entropy(chunk)
            if isinstance(result, tuple) and len(result) > 1:
                # Use mean of valid entropy values from the array (element 1)
                entropy_array = result[1]
                valid_values = entropy_array[~np.isnan(entropy_array)]
                return float(np.mean(valid_values)) if len(valid_values) > 0 else 0.0
            return 0.0
        
        elif index_name == 'spectral_entropy':
            # CRITICAL FIX: spectral_entropy returns (nan, valid_entropy, ...) - extract element 1
            result = features.spectral_entropy(chunk, fn)
            if isinstance(result, tuple) and len(result) > 1:
                # Element 1 contains the valid entropy value (element 0 is nan)
                return float(result[1]) if not np.isnan(result[1]) else 0.0
            return result[0] if isinstance(result, tuple) else result
        
        elif index_name == 'number_of_peaks':
            peaks = features.number_of_peaks(chunk)
            return float(peaks) if peaks is not None else 0.0
        
        elif index_name == 'spectral_activity':
            return features.spectral_activity(chunk)
        
        elif index_name == 'spectral_events':
            events = features.spectral_events(chunk)
            # Return count of events as the index value
            return float(len(events)) if events is not None else 0.0
        
        elif index_name == 'spectral_cover':
            return features.spectral_cover(chunk)
        
        elif index_name == 'soundscape_index':
            # Returns tuple: (NDSI, ndsi_bioacoustic, ndsi_anthropogenic, ...)
            # We want the main NDSI value (first element)
            # Custom frequency bands for urban frog detection:
            # - Bioacoustic (frogs): 500-2000Hz 
            # - Anthropogenic (heavy traffic): 0-500Hz
            result = features.soundscape_index(
                chunk, fn,
                flim_bioPh=(self.bioacoustics_freq_min, self.bioacoustics_freq_max),  # 500-2000Hz frogs
                flim_antroPh=(0, self.bioacoustics_freq_min)  # 0-500Hz heavy traffic
            )
            return result[0] if isinstance(result, tuple) else result
        
        elif index_name == 'acoustic_gradient_index':
            return features.acoustic_gradient_index(chunk)
        
        elif index_name == 'spectral_leq':
            # Create dummy time and frequency vectors for spectral_leq
            tn = np.linspace(0, self.chunk_duration_sec, chunk.shape[1])
            fn = np.linspace(0, self.sample_rate/2, chunk.shape[0])
            return features.spectral_leq(chunk, tn, fn)
        
        else:
            raise ValueError(f"Unsupported spectral index: {index_name}")
    
    def _compute_single_named_index(self, chunk: np.ndarray, processor_name: str, params: Dict[str, Any]) -> float:
        """
        Compute a single spectral index value for one spectrogram chunk using named processor and parameters
        
        Args:
            chunk: Spectrogram chunk (2D array: frequency x time)
            processor_name: Name of processor method to use
            params: Parameters dict for the processor
            
        Returns:
            float: Computed index value
        """
        # Use the actual frequency array from the NPZ file
        fn = self.frequency_array
        
        # Map processor names to maad functions with parameters
        if processor_name == 'acoustic_complexity_index':
            # Convert dB to linear power scale for correct ACI calculation
            chunk_linear = 10**(chunk / 10)
            _, _, aci_sum = features.acoustic_complexity_index(chunk_linear)
            return float(aci_sum)
        
        elif processor_name == 'acoustic_diversity_index':
            return float(features.acoustic_diversity_index(chunk, fn))
        
        elif processor_name == 'acoustic_eveness_index':
            return float(features.acoustic_eveness_index(chunk, fn))
        
        elif processor_name == 'bioacoustics_index':
            # Get frequency parameters from params dict
            freq_min = params.get('freq_min', 2000)
            freq_max = params.get('freq_max', 8000)
            
            # Convert dB to linear power scale as BAI expects
            chunk_linear = 10**(chunk / 10)
            
            # Use BAI's internal frequency filtering with specified range
            return float(features.bioacoustics_index(
                chunk_linear, fn, 
                flim=(freq_min, freq_max)
            ))
        
        elif processor_name == 'frequency_entropy':
            # frequency_entropy returns (nan, array) - extract valid values from array
            result = features.frequency_entropy(chunk)
            if isinstance(result, tuple) and len(result) > 1:
                # Use mean of valid entropy values from the array (element 1)
                entropy_array = result[1]
                valid_values = entropy_array[~np.isnan(entropy_array)]
                return float(np.mean(valid_values)) if len(valid_values) > 0 else 0.0
            return 0.0
        
        elif processor_name == 'spectral_entropy':
            # spectral_entropy returns (nan, valid_entropy, ...) - extract element 1
            result = features.spectral_entropy(chunk, fn)
            if isinstance(result, tuple) and len(result) > 1:
                # Element 1 contains the valid entropy value (element 0 is nan)
                return float(result[1]) if not np.isnan(result[1]) else 0.0
            return result[0] if isinstance(result, tuple) else result
        
        elif processor_name == 'number_of_peaks':
            peaks = features.number_of_peaks(chunk)
            return float(peaks) if peaks is not None else 0.0
        
        elif processor_name == 'spectral_activity':
            return features.spectral_activity(chunk)
        
        elif processor_name == 'spectral_events':
            events = features.spectral_events(chunk)
            # Return count of events as the index value
            return float(len(events)) if events is not None else 0.0
        
        elif processor_name == 'spectral_cover':
            return features.spectral_cover(chunk)
        
        elif processor_name == 'soundscape_index':
            # Get frequency parameters from params dict
            bio_freq_min = params.get('bioacoustic_freq_min', params.get('freq_min', 2000))
            bio_freq_max = params.get('bioacoustic_freq_max', params.get('freq_max', 8000))
            anthro_freq_min = params.get('anthropogenic_freq_min', 0)
            anthro_freq_max = params.get('anthropogenic_freq_max', bio_freq_min)
            
            # Returns tuple: (NDSI, ndsi_bioacoustic, ndsi_anthropogenic, ...)
            # We want the main NDSI value (first element)
            result = features.soundscape_index(
                chunk, fn,
                flim_bioPh=(bio_freq_min, bio_freq_max),
                flim_antroPh=(anthro_freq_min, anthro_freq_max)
            )
            return result[0] if isinstance(result, tuple) else result
        
        elif processor_name == 'acoustic_gradient_index':
            return features.acoustic_gradient_index(chunk)
        
        elif processor_name == 'spectral_leq':
            # Create dummy time and frequency vectors for spectral_leq
            tn = np.linspace(0, self.chunk_duration_sec, chunk.shape[1])
            fn_local = np.linspace(0, self.sample_rate/2, chunk.shape[0])
            return features.spectral_leq(chunk, tn, fn_local)
        
        elif processor_name == 'maad_spectral_activity':
            # MAAD spectral activity index (AAI spectral component)
            # This is the spectral component of the Audio Activity Index
            # Get frequency parameters from params dict if provided
            freq_min = params.get('freq_min')
            freq_max = params.get('freq_max')
            
            if freq_min is not None and freq_max is not None:
                # Apply frequency filtering by creating a mask for the desired frequency range
                freq_mask = (fn >= freq_min) & (fn <= freq_max)
                if np.any(freq_mask):
                    # Extract frequency band and compute spectral activity
                    band_chunk = chunk[freq_mask, :]
                    return float(features.spectral_activity(band_chunk))
                else:
                    return 0.0
            else:
                # No frequency filtering, use full spectrum
                return float(features.spectral_activity(chunk))
        
        else:
            raise ValueError(f"Unsupported processor: {processor_name}")
    
    def get_supported_indices(self) -> List[str]:
        """
        Return list of all supported spectral indices
        
        Returns:
            List[str]: All available spectral index names
        """
        return [
            'acoustic_complexity_index',
            'acoustic_diversity_index',
            'acoustic_eveness_index',
            'bioacoustics_index',
            'frequency_entropy',
            'spectral_entropy',
            'number_of_peaks',
            'spectral_activity',
            'spectral_events',
            'spectral_cover',
            'soundscape_index',
            'acoustic_gradient_index',
            'spectral_leq'
        ]