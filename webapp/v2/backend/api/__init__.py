"""
API blueprints for AudioMoth Spectrogram Viewer
Clean separation of API endpoints
"""

# Import blueprints for registration in main app
from .files import files_bp
from .spectrograms import spectrograms_bp
from .audio import audio_bp

__all__ = ['files_bp', 'spectrograms_bp', 'audio_bp']