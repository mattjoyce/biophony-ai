#!/usr/bin/env python3
"""
Show what database values would be stored for the test file
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

    # Calculate statistics that would be stored in database
    aci_min = float(np.min(aci_values))
    aci_max = float(np.max(aci_values))
    aci_mean = float(np.mean(aci_values))

    print('📊 Database Values that would be stored:')
    print('')
    print('Table: audio_files')
    print('Column additions for this file:')
    print(f'  filepath: {audio_file}')
    print(f'  aci_min: {aci_min:.6f}')
    print(f'  aci_max: {aci_max:.6f}')
    print(f'  aci_mean: {aci_mean:.6f}')
    print('')
    print('SQL UPDATE statement:')
    print('UPDATE audio_files')
    print(f'SET aci_min = {aci_min:.6f},')
    print(f'    aci_max = {aci_max:.6f},')
    print(f'    aci_mean = {aci_mean:.6f}')
    print(f'WHERE filepath = "{audio_file}"')
    print('')
    print('Table: global_stats (would be updated after batch processing)')
    print('  stat_name: aci_global_min')
    print('  stat_value: [calculated from all files using 2nd percentile]')
    print('  stat_name: aci_global_max') 
    print('  stat_value: [calculated from all files using 98th percentile]')
    print('')
    print('Schema changes needed:')
    print('ALTER TABLE audio_files ADD COLUMN aci_min REAL;')
    print('ALTER TABLE audio_files ADD COLUMN aci_max REAL;')
    print('ALTER TABLE audio_files ADD COLUMN aci_mean REAL;')


if __name__ == "__main__":
    main()