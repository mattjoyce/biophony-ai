from spectrogram_utils import find_all_wav_files
files = find_all_wav_files('/mnt/n/AudioWalks/H3-VC/2024-12-21/')
print(f'Found {len(files)} WAV files:')
for f in files[:5]:
    print(f'  {f}')
if len(files) > 5:
    print(f'  ... and {len(files)-5} more')