# Cross-Platform Configuration Guide

## Current Configuration - WSL

All configuration files have been updated for WSL environment:

```yaml
input_directory : "/mnt/n/AudioWalks/H3-VC/2025-6-20_to_7-31/"
database_path : "/mnt/n/AudioWalks/H3-VC/2025-6-20_to_7-31/audiomoth.db"
```

## Cross-Platform Usage

### For WSL (Current Setup):
```yaml
input_directory : "/mnt/n/AudioWalks/H3-VC/2025-6-20_to_7-31/"
database_path : "/mnt/n/AudioWalks/H3-VC/2025-6-20_to_7-31/audiomoth.db"
```

### For macOS:
```yaml
input_directory : "/Volumes/Extreme SSD/2025-6-20_to_7-31/"
database_path : "/Volumes/Extreme SSD/2025-6-20_to_7-31/audiomoth.db"
```

## Updated Configuration Files

All of these files now have correct WSL paths:

- ✅ `config.yaml`
- ✅ `config_aci_only.yaml`
- ✅ `config_aai_maad.yaml`
- ✅ `config_eastern_froglet.yaml`
- ✅ `config_generalized_indices.yaml`
- ✅ `config_multi_species_frogs.yaml`

## Database Cross-Platform Compatibility

The database has been migrated to support cross-platform operation:
- Files are stored with both `volume_prefix` and `relative_path`
- Scripts automatically resolve paths based on config `input_directory`
- Same database works on both macOS and WSL with appropriate config

## Usage Notes

1. **When switching platforms**: Update the config files with the appropriate volume paths
2. **When copying database**: Database will automatically work with new volume paths
3. **For processing**: All scripts use the `input_directory` to resolve cross-platform paths