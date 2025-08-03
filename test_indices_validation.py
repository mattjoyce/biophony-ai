#!/usr/bin/env python3
"""
Scientific validation test for spectral indices computation
Tests actual maad function returns and identifies implementation issues
"""

import numpy as np
from maad import features

# Load sample NPZ file
npz_file = 'test_audio/20250620/243B1F0663FAA6CC_20250620_000000_spec.npz'
data = np.load(npz_file)
spec = data['spec']
fn = data['fn']

# Take a small chunk for testing
chunk = spec[:, 1000:1100]  # 100 time bins
print(f"Test chunk shape: {chunk.shape}")
print(f"Frequency range: {fn.min():.1f} - {fn.max():.1f} Hz")

# Test 1: Bioacoustics Index
print("\n=== BIOACOUSTICS INDEX TEST ===")
freq_mask = (fn >= 500) & (fn <= 2000)
filtered_chunk = chunk[freq_mask, :]
filtered_fn = fn[freq_mask]

print(f"Filtered chunk shape: {filtered_chunk.shape}")
print(f"Filtered frequency range: {filtered_fn.min():.1f} - {filtered_fn.max():.1f} Hz")
print(f"Chunk energy statistics:")
print(f"  Min: {filtered_chunk.min():.3f}")
print(f"  Max: {filtered_chunk.max():.3f}")
print(f"  Mean: {filtered_chunk.mean():.3f}")
print(f"  Non-zero values: {np.sum(filtered_chunk != 0)}")

try:
    bai_result = features.bioacoustics_index(filtered_chunk, filtered_fn)
    print(f"BAI result: {bai_result}")
    print(f"BAI type: {type(bai_result)}")
except Exception as e:
    print(f"BAI computation failed: {e}")

# Test 2: Frequency Entropy
print("\n=== FREQUENCY ENTROPY TEST ===")
try:
    freq_ent_result = features.frequency_entropy(chunk)
    print(f"Frequency entropy result: {freq_ent_result}")
    print(f"Frequency entropy type: {type(freq_ent_result)}")
except Exception as e:
    print(f"Frequency entropy computation failed: {e}")

# Test 3: Spectral Entropy
print("\n=== SPECTRAL ENTROPY TEST ===")
try:
    spec_ent_result = features.spectral_entropy(chunk, fn)
    print(f"Spectral entropy result: {spec_ent_result}")
    print(f"Spectral entropy type: {type(spec_ent_result)}")
except Exception as e:
    print(f"Spectral entropy computation failed: {e}")

# Test 4: ACI
print("\n=== ACI TEST ===")
try:
    aci_result = features.acoustic_complexity_index(chunk)
    print(f"ACI result: {aci_result}")
    print(f"ACI type: {type(aci_result)}")
    if isinstance(aci_result, tuple):
        print(f"ACI tuple elements: {[type(x) for x in aci_result]}")
        print(f"ACI sum (element 2): {aci_result[2]}")
except Exception as e:
    print(f"ACI computation failed: {e}")

# Test 5: NDSI
print("\n=== NDSI TEST ===")
try:
    ndsi_result = features.soundscape_index(
        chunk, fn,
        flim_bioPh=(500, 2000),
        flim_antroPh=(0, 500)
    )
    print(f"NDSI result: {ndsi_result}")
    print(f"NDSI type: {type(ndsi_result)}")
    if isinstance(ndsi_result, tuple):
        print(f"NDSI tuple elements: {[type(x) for x in ndsi_result]}")
        print(f"NDSI main value (element 0): {ndsi_result[0]}")
except Exception as e:
    print(f"NDSI computation failed: {e}")

data.close()