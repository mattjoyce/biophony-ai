#!/usr/bin/env python3
"""
Test script for single file ACI processing
Processes one file and outputs debug information to screen
"""

import yaml
import torch
import numpy as np
from PIL import Image
from aci_processor import ACIProcessor


def main():
    # Configuration
    audio_file = 'test_audio/20250620/243B1F0663FAA6CC_20250620_000000.WAV'
    config_file = 'config_medium.yaml'
    
    print("🎵 Single File ACI Test")
    print(f"Audio file: {audio_file}")
    print(f"Config: {config_file}")
    
    # Load config
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    
    # Create processor (disable database updates by creating minimal processor)
    processor = ACIProcessor(config, device)
    
    # Load spectrogram image directly
    spectrogram_file = audio_file.replace('.WAV', '.png').replace('.wav', '.png')
    print(f"Spectrogram file: {spectrogram_file}")
    
    spectrogram_img = Image.open(spectrogram_file)
    if spectrogram_img.mode != 'L':
        spectrogram_img = spectrogram_img.convert('L')
    
    spectrogram_array = np.array(spectrogram_img)
    spectrogram_tensor = torch.from_numpy(spectrogram_array).float().to(device)
    
    print(f"\n📊 Spectrogram Analysis:")
    print(f"  Shape: {spectrogram_tensor.shape}")
    print(f"  Range: {spectrogram_tensor.min():.1f} to {spectrogram_tensor.max():.1f}")
    print(f"  Mean: {spectrogram_tensor.mean():.1f}")
    print(f"  Device: {spectrogram_tensor.device}")
    
    # Compute ACI values
    print(f"\n🔊 Computing ACI values...")
    aci_values = processor.compute_aci_from_spectrogram(spectrogram_tensor)
    
    print(f"\n📈 ACI Results:")
    print(f"  Shape: {aci_values.shape}")
    print(f"  Range: {aci_values.min():.6f} to {aci_values.max():.6f}")
    print(f"  Mean: {aci_values.mean():.6f}")
    print(f"  Std: {aci_values.std():.6f}")
    print(f"  Non-zero values: {np.count_nonzero(aci_values)}/{len(aci_values)}")
    
    print(f"\n🔍 Sample Values:")
    print(f"  First 10: {aci_values[:10]}")
    print(f"  Last 10: {aci_values[-10:]}")
    
    # Test normalization
    print(f"\n🎨 Normalization Test:")
    if processor.normalization_method == 'percentile':
        p2 = np.percentile(aci_values, 2)
        p98 = np.percentile(aci_values, 98)
        print(f"  2nd percentile: {p2:.6f}")
        print(f"  98th percentile: {p98:.6f}")
        print(f"  Percentile range: {p98 - p2:.6f}")
    else:
        print(f"  Min-max range: {aci_values.max() - aci_values.min():.6f}")
    
    # Generate overlay (without saving to test rendering)
    print(f"\n🖼️  Rendering Test:")
    output_file = audio_file.replace('.WAV', '_aci_overlay_test.png').replace('.wav', '_aci_overlay_test.png')
    processor.normalize_and_render(aci_values, output_file)
    print(f"  Overlay saved: {output_file}")
    
    print(f"\n✅ Single file test complete!")


if __name__ == "__main__":
    main()