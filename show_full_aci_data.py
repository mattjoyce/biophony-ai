#!/usr/bin/env python3
"""
Show the full ACI dataset - all 200 chunk values that could be stored
"""

from aci_processor import ACIProcessor
import yaml
import torch
import numpy as np
from PIL import Image


def main():
    # Load config and setup
    with open('config_medium.yaml', 'r') as f:
        config = yaml.safe_load(f)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    processor = ACIProcessor(config, device)

    # Load and process spectrogram
    audio_file = 'test_audio/20250620/243B1F0663FAA6CC_20250620_000000.WAV'
    spectrogram_file = audio_file.replace('.WAV', '.png')

    spectrogram_img = Image.open(spectrogram_file)
    if spectrogram_img.mode != 'L':
        spectrogram_img = spectrogram_img.convert('L')

    spectrogram_array = np.array(spectrogram_img)
    spectrogram_tensor = torch.from_numpy(spectrogram_array).float().to(device)

    # Compute ACI values
    aci_values = processor.compute_aci_from_spectrogram(spectrogram_tensor)

    print('📊 Full ACI Dataset - All 200 Chunk Values')
    print('='*80)
    print(f'File: {audio_file}')
    print(f'Total chunks: {len(aci_values)}')
    print(f'Chunk duration: 4.5 seconds each')
    print(f'Total time covered: {len(aci_values) * 4.5 / 60:.1f} minutes')
    print('')

    print('Chunk-by-chunk ACI values:')
    print('Chunk | Time (mm:ss) | ACI Value')
    print('-' * 40)
    
    for i, aci in enumerate(aci_values):
        # Calculate time position for this chunk
        start_seconds = i * 4.5
        minutes = int(start_seconds // 60)
        seconds = int(start_seconds % 60)
        print(f'{i:5d} | {minutes:2d}:{seconds:02d}       | {aci:9.6f}')
    
    print('')
    print('Statistical Summary:')
    print(f'  Min: {np.min(aci_values):.6f} (chunk {np.argmin(aci_values)})')
    print(f'  Max: {np.max(aci_values):.6f} (chunk {np.argmax(aci_values)})')
    print(f'  Mean: {np.mean(aci_values):.6f}')
    print(f'  Std: {np.std(aci_values):.6f}')
    print(f'  Median: {np.median(aci_values):.6f}')
    
    print('')
    print('Potential Database Storage Options:')
    print('1. Full temporal data table:')
    print('   CREATE TABLE aci_temporal (')
    print('     file_id INTEGER,')
    print('     chunk_index INTEGER,')
    print('     start_time_sec REAL,')
    print('     aci_value REAL,')
    print('     PRIMARY KEY (file_id, chunk_index)')
    print('   );')
    print('')
    print('2. JSON column in audio_files:')
    print('   ALTER TABLE audio_files ADD COLUMN aci_values JSON;')
    print(f'   -- Would store: {list(aci_values[:5])} ... (200 values total)')


if __name__ == "__main__":
    main()