"""Monitor player scraping progress and send notification when complete."""
import sys
import time
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.db import models


def send_notification(title: str, message: str):
    """Send a macOS notification."""
    try:
        # macOS notification using osascript
        script = f'''
        display notification "{message}" with title "{title}"
        '''
        subprocess.run(['osascript', '-e', script], check=False, capture_output=True)
        print(f"✓ Notification sent: {title} - {message}")
    except Exception as e:
        print(f"Could not send notification: {e}")


def check_progress():
    """Check scraping progress."""
    db = SessionLocal()
    try:
        total = db.query(models.Player).count()
        with_birth_date = db.query(models.Player).filter(
            models.Player.birth_date.isnot(None)
        ).count()
        with_batting_style = db.query(models.Player).filter(
            models.Player.batting_style.isnot(None)
        ).count()
        with_bowling_style = db.query(models.Player).filter(
            models.Player.bowling_style.isnot(None)
        ).count()
        
        return {
            'total': total,
            'with_birth_date': with_birth_date,
            'with_batting_style': with_batting_style,
            'with_bowling_style': with_bowling_style,
            'progress': with_birth_date / total * 100 if total > 0 else 0
        }
    finally:
        db.close()


def monitor_scraping(check_interval: int = 30, expected_total: int = 113):
    """Monitor scraping progress and notify when complete."""
    print("=" * 60)
    print("Player Scraping Monitor")
    print("=" * 60)
    print(f"Monitoring scraping progress (checking every {check_interval} seconds)")
    print(f"Expected total players: {expected_total}")
    print("Press Ctrl+C to stop monitoring")
    print("=" * 60)
    print()
    
    last_progress = 0
    start_time = time.time()
    notified_complete = False
    
    try:
        while True:
            stats = check_progress()
            
            # Print current status
            elapsed = time.time() - start_time
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            
            print(f"\r[{elapsed_min:02d}:{elapsed_sec:02d}] Progress: {stats['with_birth_date']}/{stats['total']} "
                  f"({stats['progress']:.1f}%) | "
                  f"Birth dates: {stats['with_birth_date']} | "
                  f"Bowling styles: {stats['with_bowling_style']}", end='', flush=True)
            
            # Check if scraping is complete
            # Consider complete when all players have birth dates (main indicator)
            if stats['with_birth_date'] >= expected_total and not notified_complete:
                print("\n")
                print("=" * 60)
                print("🎉 SCRAPING COMPLETE! 🎉")
                print("=" * 60)
                print(f"Total players: {stats['total']}")
                print(f"Players with birth dates: {stats['with_birth_date']}")
                print(f"Players with batting styles: {stats['with_batting_style']}")
                print(f"Players with bowling styles: {stats['with_bowling_style']}")
                print(f"Time elapsed: {elapsed_min} minutes {elapsed_sec} seconds")
                print("=" * 60)
                
                # Send notification
                message = (f"Scraped {stats['with_birth_date']}/{stats['total']} players. "
                          f"Birth dates: {stats['with_birth_date']}, "
                          f"Bowling styles: {stats['with_bowling_style']}")
                send_notification("Player Scraping Complete", message)
                
                notified_complete = True
                break
            
            # Check if progress is stuck (no change in last 5 minutes)
            if stats['with_birth_date'] == last_progress and elapsed > 300:
                print("\n")
                print("⚠️  WARNING: No progress detected in the last 5 minutes")
                print("   The scraper may have stopped or encountered an error")
                print("   Check the log file: /tmp/player_scraping.log")
                send_notification(
                    "Scraping Stalled",
                    f"No progress in 5 minutes. Current: {stats['with_birth_date']}/{stats['total']}"
                )
                # Don't break, keep monitoring
            
            last_progress = stats['with_birth_date']
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
        stats = check_progress()
        print(f"Final progress: {stats['with_birth_date']}/{stats['total']} ({stats['progress']:.1f}%)")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor player scraping progress")
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

