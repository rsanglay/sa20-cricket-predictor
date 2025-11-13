#!/usr/bin/env python3
"""
Wait for scraper to complete and then import the data.
This script monitors the players.json file and imports when all 113 players are scraped.
"""
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_pipeline.import_player_profiles import import_player_profiles

JSON_FILE = "/players.json"
TARGET_COUNT = 113
CHECK_INTERVAL = 60  # Check every minute

print(f"Monitoring {JSON_FILE} for scraper completion...")
print(f"Target: {TARGET_COUNT} players")
print("Press Ctrl+C to stop monitoring\n")

try:
    while True:
        try:
            with open(JSON_FILE, 'r') as f:
                data = json.load(f)
                count = len(data)
                
                print(f"{time.strftime('%H:%M:%S')} - Progress: {count}/{TARGET_COUNT} players ({count*100//TARGET_COUNT}%)")
                
                if count >= TARGET_COUNT:
                    print(f"\n✓ Scraping complete! Found {count} players.")
                    print("Starting import...\n")
                    result = import_player_profiles(JSON_FILE)
                    print(f"\n✓ Import complete!")
                    print(f"  - Updated: {result['success']}")
                    print(f"  - Skipped: {result['skipped']}")
                    print(f"  - Not found: {result['not_found']}")
                    break
        except FileNotFoundError:
            print(f"{time.strftime('%H:%M:%S')} - Waiting for {JSON_FILE} to be created...")
        except json.JSONDecodeError:
            print(f"{time.strftime('%H:%M:%S')} - File exists but not valid JSON yet, waiting...")
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} - Error: {e}")
        
        time.sleep(CHECK_INTERVAL)
        
except KeyboardInterrupt:
    print("\n\nMonitoring stopped by user.")
    print("To import manually, run:")
    print(f"  docker-compose exec backend python /app/data_pipeline/import_player_profiles.py --file {JSON_FILE}")

