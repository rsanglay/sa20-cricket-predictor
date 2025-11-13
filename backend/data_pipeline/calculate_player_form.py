"""Calculate and store player form trends (last 5 innings)."""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import models
from app.db.session import SessionLocal


def calculate_player_form(db: Session, player_id: int, window: int = 5) -> Dict[str, float]:
    """Calculate form trends for a player based on last N performances."""
    # Get player performances ordered by match date
    performances = db.query(models.PlayerPerformance).filter(
        models.PlayerPerformance.player_id == player_id
    ).join(
        models.Match
    ).order_by(
        desc(models.Match.match_date)
    ).limit(window).all()
    
    if not performances:
        return {
            "avg_runs": 0.0,
            "avg_wickets": 0.0,
            "avg_strike_rate": 0.0,
            "avg_economy": 0.0,
            "matches_played": 0,
            "form_score": 0.0,
        }
    
    # Calculate averages over the window
    total_runs = sum(p.runs_scored or 0 for p in performances)
    total_balls = sum(p.balls_faced or 0 for p in performances)
    total_wickets = sum(p.wickets_taken or 0 for p in performances)
    total_overs = sum(p.overs_bowled or 0.0 for p in performances)
    total_runs_conceded = sum(p.runs_conceded or 0 for p in performances)
    
    avg_runs = total_runs / len(performances) if performances else 0.0
    avg_wickets = total_wickets / len(performances) if performances else 0.0
    avg_strike_rate = (total_runs / total_balls * 100) if total_balls > 0 else 0.0
    avg_economy = (total_runs_conceded / total_overs) if total_overs > 0 else 0.0
    
    # Calculate form score (weighted combination)
    # Higher is better
    form_score = (avg_runs * 0.4) + (avg_wickets * 20) + (avg_strike_rate * 0.2) - (avg_economy * 2)
    
    return {
        "avg_runs": round(avg_runs, 2),
        "avg_wickets": round(avg_wickets, 2),
        "avg_strike_rate": round(avg_strike_rate, 2),
        "avg_economy": round(avg_economy, 2),
        "matches_played": len(performances),
        "form_score": round(form_score, 2),
    }


def calculate_all_player_forms(db: Session, window: int = 5) -> Dict[str, int]:
    """Calculate form trends for all players."""
    print(f"Calculating player form trends (last {window} innings)...")
    
    stats = {
        "players_processed": 0,
        "players_with_form": 0,
        "players_without_performances": 0,
    }
    
    # Get all players
    players = db.query(models.Player).all()
    print(f"Found {len(players)} players")
    
    # Store form data (could be stored in a new table or cached)
    # For now, we'll calculate on-demand and could store in a JSONB field
    # or create a separate PlayerForm table
    
    for player in players:
        try:
            form = calculate_player_form(db, player.id, window=window)
            
            if form["matches_played"] > 0:
                stats["players_with_form"] += 1
                
                # Optionally store in a JSONB field on Player model
                # For now, we'll just calculate and can store later
                # player.recent_form = form  # Would need to add this field
            else:
                stats["players_without_performances"] += 1
            
            stats["players_processed"] += 1
            
            if stats["players_processed"] % 50 == 0:
                print(f"  Processed {stats['players_processed']} players...")
        
        except Exception as e:
            print(f"Error processing player {player.id}: {e}")
            continue
    
    print(f"\nPlayer form calculation complete:")
    print(f"  Players processed: {stats['players_processed']}")
    print(f"  Players with form: {stats['players_with_form']}")
    print(f"  Players without performances: {stats['players_without_performances']}")
    
    return stats


def get_player_form_dataframe(db: Session, window: int = 5) -> pd.DataFrame:
    """Get player form data as a DataFrame."""
    players = db.query(models.Player).all()
    rows = []
    
    for player in players:
        form = calculate_player_form(db, player.id, window=window)
        if form["matches_played"] > 0:
            rows.append({
                "player_id": player.id,
                "player_name": player.name,
                "team_id": player.team_id,
                **form
            })
    
    return pd.DataFrame(rows)


def main() -> None:
    """Main function to calculate player forms."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Calculate player form trends")
    parser.add_argument("--window", type=int, default=5, help="Number of recent matches to consider")
    parser.add_argument("--export", type=str, help="Export to CSV file")
    
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        stats = calculate_all_player_forms(db, window=args.window)
        
        if args.export:
            df = get_player_form_dataframe(db, window=args.window)
            df.to_csv(args.export, index=False)
            print(f"\nExported player form data to {args.export}")
    
    except Exception as e:
        print(f"Error: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()

