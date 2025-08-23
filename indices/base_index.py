#!/usr/bin/env python3
"""
Base interface for acoustic indices processing
Defines common patterns for temporal and spectral indices
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Tuple
import numpy as np


class AcousticIndex(ABC):
    """Abstract base class for all acoustic indices"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize acoustic index processor
        
        Args:
            config: Configuration dictionary from YAML
        """
        self.config = config
        # Values will be set by subclass after calling super().__init__()
        self.chunk_duration_sec = None
        self.sample_rate = None
        self.file_duration_sec = None
        self.samples_per_chunk = None
        self.n_chunks = None
    
    def _setup_from_config(self, processing_type: str):
        """Setup parameters from config after subclass initialization"""
        indices_config = self.config['acoustic_indices'][processing_type]
        self.chunk_duration_sec = indices_config['chunk_duration_sec']
        self.sample_rate = self.config['sample_rate']
        self.file_duration_sec = self.config['file_duration_sec']
        
        # Calculate chunk parameters
        self.samples_per_chunk = int(self.sample_rate * self.chunk_duration_sec)
        self.n_chunks = int(self.file_duration_sec / self.chunk_duration_sec)
    
    @abstractmethod
    def get_processing_type(self) -> str:
        """
        Return processing type: 'temporal' or 'spectral'
        
        Returns:
            str: Processing type identifier
        """
        pass
    
    @abstractmethod
    def get_enabled_indices(self) -> List[str]:
        """
        Return list of enabled indices for this processor
        
        Returns:
            List[str]: Names of indices to compute
        """
        pass
    
    @abstractmethod
    def process_file(self, file_path: str) -> Dict[str, np.ndarray]:
        """
        Process a single file and compute all enabled indices
        
        Args:
            file_path: Path to input file (WAV or PNG)
            
        Returns:
            Dict[str, np.ndarray]: Mapping of index_name -> values array
        """
        pass
    
    def validate_file_duration(self, duration_sec: float) -> None:
        """
        Validate that file duration matches expected length
        
        Args:
            duration_sec: Actual file duration in seconds
            
        Raises:
            ValueError: If duration doesn't match expected 15 minutes
        """
        if abs(duration_sec - self.file_duration_sec) > 1.0:  # 1 second tolerance
            raise ValueError(f"File duration {duration_sec}s != expected {self.file_duration_sec}s")
    
    def get_chunk_timestamps(self) -> np.ndarray:
        """
        Generate timestamp array for all chunks
        
        Returns:
            np.ndarray: Start time in seconds for each chunk
        """
        return np.arange(self.n_chunks) * self.chunk_duration_sec
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Return metadata about this processor configuration
        
        Returns:
            Dict[str, Any]: Processor metadata
        """
        return {
            'processing_type': self.get_processing_type(),
            'enabled_indices': self.get_enabled_indices(),
            'chunk_duration_sec': self.chunk_duration_sec,
            'n_chunks': self.n_chunks,
            'sample_rate': self.sample_rate,
            'file_duration_sec': self.file_duration_sec
        }