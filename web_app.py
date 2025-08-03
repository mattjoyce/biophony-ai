#!/usr/bin/env python3
"""
AudioMoth Web Interface
"""

from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import os
from datetime import datetime, date, time
import json
from audio_database import AudioDatabase

app = Flask(__name__)
db = AudioDatabase("audiomoth.db")

@app.route('/')
def index():
    """Main page with search interface."""
    return render_template('index.html')

@app.route('/api/files')
def api_files():
    """API endpoint to search for audio files."""
    # Get query parameters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    time_from = request.args.get('time_from')
    time_to = request.args.get('time_to')
    limit = int(request.args.get('limit', 100))
    
    # Search files
    files = db.search_files(
        date_from=date_from,
        date_to=date_to,
        time_from=time_from,
        time_to=time_to,
        limit=limit
    )
    
    return jsonify(files)

@app.route('/api/grid')
def api_grid():
    """API endpoint for grid view data."""
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all files in date range
    query = """
    SELECT 
        DATE(recording_datetime) as recording_date,
        TIME(recording_datetime) as recording_time,
        filename,
        filepath,
        duration_seconds
    FROM audio_files
    WHERE 1=1
    """
    params = []
    
    if date_from:
        query += " AND DATE(recording_datetime) >= ?"
        params.append(date_from)
    
    if date_to:
        query += " AND DATE(recording_datetime) <= ?"
        params.append(date_to)
    
    query += " ORDER BY recording_datetime"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    
    # Organize data by date and time slots
    grid_data = {}
    for row in results:
        recording_date = row['recording_date']
        recording_time = row['recording_time']
        
        if recording_date not in grid_data:
            grid_data[recording_date] = {}
        
        # Convert to 30-minute time slots
        hour, minute, second = recording_time.split(':')
        slot_minute = '00' if int(minute) < 30 else '30'
        time_slot = f"{hour}:{slot_minute}"
        
        grid_data[recording_date][time_slot] = {
            'filename': row['filename'],
            'filepath': row['filepath'],
            'duration': row['duration_seconds']
        }
    
    return jsonify(grid_data)

@app.route('/api/stats')
def api_stats():
    """Get database statistics."""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Get basic stats
    cursor.execute("SELECT COUNT(*) FROM audio_files")
    total_files = cursor.fetchone()[0]
    
    cursor.execute("SELECT MIN(recording_datetime), MAX(recording_datetime) FROM audio_files")
    date_range = cursor.fetchone()
    
    cursor.execute("SELECT SUM(duration_seconds) FROM audio_files")
    total_duration = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(DISTINCT audiomoth_id) FROM audio_files")
    unique_devices = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM annotations")
    total_annotations = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_files': total_files,
        'date_range': date_range,
        'total_duration_hours': round(total_duration / 3600, 2),
        'unique_devices': unique_devices,
        'total_annotations': total_annotations
    })

@app.route('/api/annotations/<int:file_id>')
def api_annotations(file_id):
    """Get annotations for a specific file."""
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT * FROM annotations 
    WHERE audio_file_id = ? 
    ORDER BY start_time
    """, (file_id,))
    
    annotations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(annotations)

@app.route('/api/spectrogram')
def api_spectrogram():
    """Serve actual spectrogram image for given date and time."""
    import sqlite3
    from pathlib import Path
    
    date = request.args.get('date', '2025-06-20')
    time = request.args.get('time', '00:00')
    
    # Query database for audio file matching date and time
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Convert time format (HH:MM to HHMMSS)
    time_formatted = f"{time.replace(':', '')}00"
    
    cursor.execute("""
        SELECT filepath, filename FROM audio_files 
        WHERE DATE(recording_datetime) = ? 
        AND TIME(recording_datetime) = ?
        LIMIT 1
    """, (date, f"{time}:00"))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return jsonify({'error': f'No audio file found for {date} {time}'}), 404
    
    filepath, filename = result
    
    # Look for corresponding spectrogram PNG
    audio_dir = Path(filepath).parent
    base_name = Path(filename).stem
    
    # Try different spectrogram filename patterns
    patterns = [
        f"{base_name}_spec.png",
        f"{base_name}_aci_overlay.png",
        f"{base_name}.png"
    ]
    
    image_file = None
    for pattern in patterns:
        potential_file = audio_dir / pattern
        if potential_file.exists():
            image_file = potential_file
            break
    
    if not image_file:
        return jsonify({'error': f'No spectrogram found for {filename}'}), 404
    
    return send_file(str(image_file), mimetype='image/png')

@app.route('/api/file_info')
def api_file_info():
    """Get file path info for given date and time."""
    import sqlite3
    
    date = request.args.get('date', '2025-06-20')
    time = request.args.get('time', '00:00')
    
    # Query database for audio file matching date and time
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT filepath, filename FROM audio_files 
        WHERE DATE(recording_datetime) = ? 
        AND TIME(recording_datetime) = ?
        LIMIT 1
    """, (date, f"{time}:00"))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return jsonify({'error': f'No audio file found for {date} {time}'}), 404
    
    filepath, filename = result
    
    return jsonify({
        'filepath': filepath,
        'filename': filename
    })

@app.route('/api/colormap/<colormap_name>')
def api_colormap(colormap_name):
    """Get matplotlib colormap as JSON array."""
    import matplotlib.pyplot as plt
    import numpy as np
    
    try:
        # Get the colormap
        cmap = plt.get_cmap(colormap_name)
        
        # Sample 256 colors from the colormap
        colors = []
        for i in range(256):
            rgba = cmap(i / 255.0)
            # Convert to RGB (0-255)
            rgb = [int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)]
            colors.append(rgb)
        
        return jsonify(colors)
    except ValueError:
        return jsonify({'error': f'Unknown colormap: {colormap_name}'}), 404

@app.route('/api/available_times')
def api_available_times():
    """Get available dates and times from the database."""
    import sqlite3
    
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT 
            DATE(recording_datetime) as date,
            TIME(recording_datetime) as time
        FROM audio_files 
        ORDER BY recording_datetime
    """)
    
    results = cursor.fetchall()
    conn.close()
    
    # Group by date
    data = {}
    for date, time in results:
        if date not in data:
            data[date] = []
        # Convert time to HH:MM format
        time_short = time[:5]  # Remove seconds
        data[date].append(time_short)
    
    return jsonify(data)

@app.route('/api/mel_scale')
def api_mel_scale():
    """Get mel scale frequency mapping for spectrograms."""
    import numpy as np
    
    # Default AudioMoth sampling rate is 48kHz
    sample_rate = int(request.args.get('sample_rate', 48000))
    n_mels = int(request.args.get('n_mels', 128))
    fmin = float(request.args.get('fmin', 0))
    fmax = float(request.args.get('fmax', sample_rate // 2))
    
    # Convert Hz to mel scale
    def hz_to_mel(hz):
        return 2595 * np.log10(1 + hz / 700)
    
    # Convert mel scale to Hz
    def mel_to_hz(mel):
        return 700 * (10**(mel / 2595) - 1)
    
    # Create mel scale points
    mel_min = hz_to_mel(fmin)
    mel_max = hz_to_mel(fmax)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 1)
    
    # Convert back to Hz
    freq_points = [mel_to_hz(mel) for mel in mel_points]
    
    # Create mapping for pixel positions (assuming spectrogram height matches n_mels)
    scale_data = []
    for i, freq in enumerate(freq_points):
        pixel_y = i  # Y position from bottom of spectrogram
        scale_data.append({
            'pixel_y': pixel_y,
            'frequency_hz': round(freq, 1),
            'frequency_khz': round(freq / 1000, 2)
        })
    
    return jsonify({
        'scale_data': scale_data,
        'sample_rate': sample_rate,
        'n_mels': n_mels,
        'fmin': fmin,
        'fmax': fmax
    })

@app.route('/api/upload_labels', methods=['POST'])
def upload_labels():
    """Upload Audacity label file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    audio_filepath = request.form.get('audio_filepath')
    
    if not audio_filepath:
        return jsonify({'error': 'No audio file path provided'}), 400
    
    # Save uploaded file temporarily
    temp_path = f"/tmp/{file.filename}"
    file.save(temp_path)
    
    try:
        # Import labels
        success = db.import_audacity_labels(temp_path, audio_filepath)
        os.remove(temp_path)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to import labels'}), 500
    
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    app.run(host='0.0.0.0', port=8000, debug=True)