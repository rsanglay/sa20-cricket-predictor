#!/usr/bin/env python3
"""Monitor player scraping progress from host machine and send macOS notifications."""
import sys
import time
import subprocess
import json
from pathlib import Path


def send_notification(title: str, message: str):
    """Send a macOS notification."""
    try:
        # Escape quotes in message
        message_escaped = message.replace('"', '\\"')
        script = f'display notification "{message_escaped}" with title "{title}"'
        subprocess.run(['osascript', '-e', script], check=False, capture_output=True)
        print(f"✓ Notification sent: {title}")
        return True
    except Exception as e:
        print(f"Could not send notification: {e}")
        return False


def check_progress_via_docker():
    """Check scraping progress by querying database through Docker."""
    try:
        # Run the check script in Docker
        result = subprocess.run(
            ['docker-compose', 'exec', '-T', 'backend', 'python', 
             'data_pipeline/check_scraping_progress.py'],
            cwd=Path(__file__).parent.parent.parent,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print(f"Error checking progress: {result.stderr}")
            return None
        
        # Parse output
        output = result.stdout
        stats = {}
        for line in output.split('\n'):
            if 'Total players:' in line:
                stats['total'] = int(line.split(':')[1].strip())
            elif 'Players with birth_date:' in line:
                parts = line.split(':')[1].strip().split()
                stats['with_birth_date'] = int(parts[0])
                if '(' in parts[1]:
                    stats['progress_pct'] = float(parts[1].replace('(', '').replace('%)', ''))
            elif 'Players with bowling_style:' in line:
                parts = line.split(':')[1].strip().split()
                stats['with_bowling_style'] = int(parts[0])
        
        return stats
    except Exception as e:
        print(f"Error checking progress: {e}")
        return None


def monitor_scraping(check_interval: int = 30, expected_total: int = 113):
    """Monitor scraping progress and notify when complete."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    
    print("=" * 60)
    print("Player Scraping Monitor (Host)")
    print("=" * 60)
    print(f"Monitoring scraping progress (checking every {check_interval} seconds)")
    print(f"Expected total players: {expected_total}")
    print("Press Ctrl+C to stop monitoring")
    print("=" * 60)
    print()
    
    last_progress = 0
    start_time = time.time()
    notified_complete = False
    last_notification_time = 0
    
    try:
        while True:
            stats = check_progress_via_docker()
            
            if stats is None:
                print("Could not check progress, retrying in 10 seconds...")
                time.sleep(10)
                continue
            
            # Print current status
            elapsed = time.time() - start_time
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            
            progress = stats.get('with_birth_date', 0)
            total = stats.get('total', expected_total)
            progress_pct = (progress / total * 100) if total > 0 else 0
            
            print(f"\r[{elapsed_min:02d}:{elapsed_sec:02d}] Progress: {progress}/{total} "
                  f"({progress_pct:.1f}%) | "
                  f"Birth dates: {progress} | "
                  f"Bowling styles: {stats.get('with_bowling_style', 0)}", end='', flush=True)
            
            # Check if scraping is complete
            if progress >= expected_total and not notified_complete:
                print("\n")
                print("=" * 60)
                print("🎉 SCRAPING COMPLETE! 🎉")
                print("=" * 60)
                print(f"Total players: {total}")
                print(f"Players with birth dates: {progress}")
                print(f"Players with bowling styles: {stats.get('with_bowling_style', 0)}")
                print(f"Time elapsed: {elapsed_min} minutes {elapsed_sec} seconds")
                print("=" * 60)
                
                # Send notification
                message = (f"Scraped {progress}/{total} players. "
                          f"Birth dates: {progress}, "
                          f"Bowling styles: {stats.get('with_bowling_style', 0)}")
                send_notification("🎉 Player Scraping Complete", message)
                
                notified_complete = True
                print("\nMonitor will continue running. Press Ctrl+C to stop.")
                # Don't break, keep monitoring in case more players are added
            
            # Progress notification every 25% (optional)
            elif progress > last_progress:
                progress_25 = (progress // (expected_total // 4)) * 25
                last_progress_25 = (last_progress // (expected_total // 4)) * 25
                
                if progress_25 > last_progress_25 and progress_25 > 0:
                    current_time = time.time()
                    # Only notify if at least 5 minutes have passed since last notification
                    if current_time - last_notification_time > 300:
                        message = f"Progress: {progress}/{total} players ({progress_pct:.1f}%)"
                        send_notification(f"Scraping Progress: {progress_25}%", message)
                        last_notification_time = current_time
            
            # Check if progress is stuck (no change in last 10 minutes)
            if progress == last_progress and elapsed > 600 and not notified_complete:
                print("\n")
                print("⚠️  WARNING: No progress detected in the last 10 minutes")
                print("   The scraper may have stopped or encountered an error")
                print("   Check the log file: /tmp/player_scraping.log")
                send_notification(
                    "⚠️ Scraping Stalled",
                    f"No progress in 10 minutes. Current: {progress}/{total}"
                )
                # Reset check time
                start_time = time.time() - 300  # Give it 5 more minutes
            
            last_progress = progress
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        stats = check_progress_via_docker()
        if stats:
            progress = stats.get('with_birth_date', 0)
            total = stats.get('total', expected_total)
            progress_pct = (progress / total * 100) if total > 0 else 0
            print(f"Final progress: {progress}/{total} ({progress_pct:.1f}%)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor player scraping progress from host")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Check interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--expected",
        type=int,
        default=113,
        help="Expected total number of players (default: 113)"
    )
    
    args = parser.parse_args()
    
    monitor_scraping(check_interval=args.interval, expected_total=args.expected)

