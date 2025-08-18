#!/usr/bin/env python3
"""
Spectrograms API endpoints for AudioMoth Spectrogram Viewer
Handles spectrogram image requests and processing
"""

from flask import Blueprint, request, send_file, jsonify
import io

from services.spectrogram_service import SpectrogramService
from services.colormap_service import ColormapService


spectrograms_bp = Blueprint('spectrograms', __name__)


def create_error_response(status_code: int, message: str) -> tuple:
    """Create standardized error response"""
    return jsonify({'success': False, 'error': message}), status_code


@spectrograms_bp.route('/api/spectrogram/<date>/<time>')
def get_spectrogram(date: str, time: str):
    """Get spectrogram image with optional colormap and gamma correction"""
    try:
        # Get query parameters
        colormap = request.args.get('colormap', 'viridis')
        gamma_str = request.args.get('gamma', '1.0')
        
        # Validate gamma parameter
        try:
            gamma = float(gamma_str)
            if gamma <= 0 or gamma > 10:
                return create_error_response(400, 'Gamma must be between 0 and 10')
        except ValueError:
            return create_error_response(400, 'Invalid gamma parameter')
        
        # Get processed spectrogram image
        image_data = SpectrogramService.get_spectrogram_with_processing(
            date, time, colormap, gamma
        )
        
        if not image_data:
            return create_error_response(404, f'No spectrogram found for {date} {time}')
        
        # Create file-like object and serve
        image_io = io.BytesIO(image_data)
        image_io.seek(0)
        
        return send_file(
            image_io,
            mimetype='image/png',
            as_attachment=False,
            download_name=f'spectrogram_{date}_{time}.png'
        )
        
    except ValueError as e:
        return create_error_response(400, str(e))
    except Exception as e:
        return create_error_response(500, f"Failed to get spectrogram: {str(e)}")


@spectrograms_bp.route('/api/colormap/<colormap_name>')
def get_colormap(colormap_name: str):
    """Get matplotlib colormap as JSON array"""
    try:
        colormap_data = ColormapService.get_colormap(colormap_name)
        
        if colormap_data is None:
            if colormap_name in ['gray', 'grayscale']:
                # Return empty array for grayscale (handled specially)
                return jsonify([])
            else:
                return create_error_response(404, f'Unknown colormap: {colormap_name}')
        
        return jsonify(colormap_data)
        
    except Exception as e:
        return create_error_response(500, f"Failed to get colormap: {str(e)}")


@spectrograms_bp.route('/api/colormaps')
def get_available_colormaps():
    """Get list of available colormap names"""
    try:
        colormaps = ColormapService.get_available_colormaps()
        return jsonify({'success': True, 'data': colormaps})
    except Exception as e:
        return create_error_response(500, f"Failed to get available colormaps: {str(e)}")


@spectrograms_bp.route('/api/mel_scale')
def get_mel_scale():
    """Get mel scale frequency mapping for spectrograms"""
    try:
        # Get query parameters with defaults
        sample_rate = int(request.args.get('sample_rate', 48000))
        n_mels = int(request.args.get('n_mels', 128))
        fmin = float(request.args.get('fmin', 0))
        fmax_str = request.args.get('fmax')
        fmax = float(fmax_str) if fmax_str else None
        
        # Validate parameters
        if sample_rate <= 0 or sample_rate > 192000:
            return create_error_response(400, 'Invalid sample rate')
        if n_mels <= 0 or n_mels > 1024:
            return create_error_response(400, 'Invalid n_mels')
        if fmin < 0:
            return create_error_response(400, 'fmin must be non-negative')
        if fmax is not None and fmax <= fmin:
            return create_error_response(400, 'fmax must be greater than fmin')
        
        # Get mel scale data
        mel_data = ColormapService.get_mel_scale_data(sample_rate, n_mels, fmin, fmax)
        
        return jsonify(mel_data)
        
    except ValueError as e:
        return create_error_response(400, f"Invalid parameter: {str(e)}")
    except Exception as e:
        return create_error_response(500, f"Failed to get mel scale: {str(e)}")