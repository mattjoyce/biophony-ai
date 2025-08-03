#!/usr/bin/env python3
"""
Test the fixed spectral indices implementation
"""

import numpy as np
from maad import features

# Load sample NPZ file
npz_file = 'test_audio/20250620/243B1F0663FAA6CC_20250620_000000_spec.npz'
data = np.load(npz_file)
spec = data['spec']
fn = data['fn']

# Take a small chunk for testing
chunk = spec[:, 1000:1100]
print(f"Test chunk shape: {chunk.shape}")

# Test FIXED Bioacoustics Index
print("\n=== FIXED BIOACOUSTICS INDEX TEST ===")
freq_mask = (fn >= 500) & (fn <= 2000)
filtered_chunk = chunk[freq_mask, :]
filtered_fn = fn[freq_mask]

# FIXED: Convert dB to linear scale
filtered_chunk_linear = 10**(filtered_chunk / 10)
print(f"Linear chunk statistics:")
print(f"  Min: {filtered_chunk_linear.min():.6f}")
print(f"  Max: {filtered_chunk_linear.max():.6f}")
print(f"  Mean: {filtered_chunk_linear.mean():.6f}")

bai_result = features.bioacoustics_index(filtered_chunk_linear, filtered_fn)
print(f"FIXED BAI result: {bai_result}")

# Test FIXED Frequency Entropy
print("\n=== FIXED FREQUENCY ENTROPY TEST ===")
freq_ent_result = features.frequency_entropy(chunk)
if isinstance(freq_ent_result, tuple) and len(freq_ent_result) > 1:
    entropy_array = freq_ent_result[1]
    valid_values = entropy_array[~np.isnan(entropy_array)]
    fixed_freq_ent = float(np.mean(valid_values)) if len(valid_values) > 0 else 0.0
    print(f"FIXED Frequency entropy: {fixed_freq_ent}")
    print(f"Valid values count: {len(valid_values)}")

# Test FIXED Spectral Entropy
print("\n=== FIXED SPECTRAL ENTROPY TEST ===")
spec_ent_result = features.spectral_entropy(chunk, fn)
if isinstance(spec_ent_result, tuple) and len(spec_ent_result) > 1:
    fixed_spec_ent = float(spec_ent_result[1]) if not np.isnan(spec_ent_result[1]) else 0.0
    print(f"FIXED Spectral entropy: {fixed_spec_ent}")

data.close()