#!/usr/bin/env python3
"""
AudioMoth Spectrogram Viewer - Clean Architecture Implementation
Main Flask application setup following the modern architecture specification
"""

import argparse
import os
import sys
from pathlib import Path

from flask import Flask, render_template

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent))

from config import load_config, setup_cli
from database import init_database
from api.files import files_bp
from api.spectrograms import spectrograms_bp
from api.audio import audio_bp
from api.indices import indices_bp


def create_app(config_path: str) -> Flask:
    """Application factory pattern"""
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # Load configuration
    config = load_config(config_path)
    app.config.update(config)
    
    # Initialize database with proper path handling
    db_path = config.get('database_path', 'audiomoth.db')
    # Handle paths with spaces and expand home directory
    db_path = os.path.expanduser(db_path.replace('\\ ', ' '))
    
    print(f"Initializing database at: {db_path}")
    
    # Check if database file exists
    if not os.path.exists(db_path):
        print(f"WARNING: Database file not found at {db_path}")
        print("Creating empty database...")
    
    init_database(db_path)
    
    # Store config in app for services to access
    app.config['DATABASE_PATH'] = db_path
    
    # Register blueprints
    app.register_blueprint(files_bp)
    app.register_blueprint(spectrograms_bp)
    app.register_blueprint(audio_bp)
    app.register_blueprint(indices_bp)
    
    # Main route
    @app.route('/')
    def index():
        return render_template('index.html')
    
    return app


if __name__ == '__main__':
    args = setup_cli()
    app = create_app(args.config)
    app.run(host='0.0.0.0', port=args.port, debug=True)