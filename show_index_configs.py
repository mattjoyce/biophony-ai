#!/usr/bin/env python3
"""
Configuration Lookup Utility
Show stored acoustic index configurations from database
"""

import sys
import argparse
from indices.database_manager import DatabaseManager
import json


def main():
    parser = argparse.ArgumentParser(description="Show stored acoustic index configurations")
    parser.add_argument("--config", help="Filter by config file name")
    parser.add_argument("--index", help="Show specific index configuration")
    parser.add_argument("--list", action="store_true", help="List all configurations")
    parser.add_argument("--db", default="audiomoth.db", help="Database path")
    
    args = parser.parse_args()
    
    db = DatabaseManager(args.db)
    
    if args.index:
        # Show specific index configuration
        config = db.get_index_configuration(args.index, args.config)
        if config:
            print(f"Configuration for '{args.index}':")
            print(f"  Config file: {config['config_name']}")
            print(f"  Processor: {config['processor_name']}")
            print(f"  Created: {config['created_at']}")
            print(f"  Parameters:")
            fragment = config['config_fragment']
            print(f"    Processing type: {fragment['processing_type']}")
            if fragment['params']:
                for key, value in fragment['params'].items():
                    print(f"    {key}: {value}")
            else:
                print(f"    No parameters")
        else:
            print(f"Configuration for '{args.index}' not found")
            
    elif args.list:
        # List all configurations
        configs = db.get_all_configurations(args.config)
        
        if not configs:
            print("No configurations found")
            return
            
        print(f"Found {len(configs)} stored configurations:")
        print()
        
        current_config = None
        for config in configs:
            if config['config_name'] != current_config:
                current_config = config['config_name']
                print(f"📄 {current_config}:")
            
            fragment = config['config_fragment']
            params_str = ""
            if fragment['params']:
                params_list = [f"{k}={v}" for k, v in fragment['params'].items()]
                params_str = f" ({', '.join(params_list)})"
            
            print(f"  🔍 {config['index_name']}: {config['processor_name']}{params_str}")
            
    else:
        print("Use --list to show all configurations or --index <name> to show specific configuration")
        print("Example: python3 show_index_configs.py --list")
        print("Example: python3 show_index_configs.py --index eastern_froglet_bai_2500-3500")


if __name__ == "__main__":
    main()