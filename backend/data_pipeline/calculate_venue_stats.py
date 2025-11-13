"""Calculate venue statistics from historical match data."""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Dict

from app.db import models
from app.db.session import SessionLocal

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def calculate_toss_bias(db: Session, venue_id: int) -> Dict[str, float]:
    """Calculate toss bias for a venue (bat first vs chase win %)."""
    matches = db.query(models.Match).filter(
        models.Match.venue_id == venue_id,
        models.Match.toss_winner_id.isnot(None),
        models.Match.toss_decision.isnot(None),
        models.Match.winner_id.isnot(None),
    ).all()
    
    bat_first_wins = 0
    bat_first_total = 0
    chase_wins = 0
    chase_total = 0
    
    for match in matches:
        # Determine if toss winner batted first
        toss_decision = match.toss_decision.lower() if match.toss_decision else ""
        bat_first = "bat" in toss_decision or "field" not in toss_decision
        
        if bat_first:
            bat_first_total += 1
            # Check if toss winner won
            if match.winner_id == match.toss_winner_id:
                bat_first_wins += 1
        else:
            chase_total += 1
            # Check if toss winner won (they chased)
            if match.winner_id == match.toss_winner_id:
                chase_wins += 1
    
    bat_first_win_pct = (bat_first_wins / bat_first_total * 100) if bat_first_total > 0 else 0.0
    chase_win_pct = (chase_wins / chase_total * 100) if chase_total > 0 else 0.0
    
    return {
        "bat_first_wins": bat_first_wins,
        "bat_first_total": bat_first_total,
        "bat_first_win_pct": round(bat_first_win_pct, 2),
        "chase_wins": chase_wins,
        "chase_total": chase_total,
        "chase_win_pct": round(chase_win_pct, 2),
    }


def calculate_venue_stats_from_matches(db: Session) -> None:
    """Calculate venue statistics from historical match data in database."""
    print("Calculating venue statistics from match data...")
    
    venues = db.query(models.Venue).all()
    
    for venue in venues:
        print(f"\nProcessing venue: {venue.name}")
        
        # Get all matches at this venue
        matches = db.query(models.Match).filter(models.Match.venue_id == venue.id).all()
        
        if not matches:
            print(f"  No matches found for {venue.name}")
            continue
        
        print(f"  Found {len(matches)} matches")
        
        # Calculate first innings averages from match scorecards
        # Use match_scorecards.csv if available, otherwise calculate from performances
        first_innings_scores = []
        second_innings_scores = []
        
        # Try to get from match_scorecards.csv
        scorecards_path = PROCESSED_DIR / "match_scorecards.csv"
        if scorecards_path.exists():
            try:
                scorecards = pd.read_csv(scorecards_path)
                # Filter for SA20 and this venue (would need venue matching)
                # For now, calculate from database
                pass
            except Exception:
                pass
        
        # Calculate from player performances
        for match in matches:
            # Get innings scores from performances
            performances = db.query(models.PlayerPerformance).filter(
                models.PlayerPerformance.match_id == match.id
            ).all()
            
            if not performances:
                continue
            
            # Group by team to get innings scores
            team_scores = {}
            for perf in performances:
                if perf.team_id not in team_scores:
                    team_scores[perf.team_id] = 0
                team_scores[perf.team_id] += perf.runs_scored or 0
            
            # Get scores in order
            scores = list(team_scores.values())
            if len(scores) >= 2:
                first_innings_scores.append(scores[0])
                second_innings_scores.append(scores[1])
        
        # Calculate averages
        if first_innings_scores:
            avg_first = sum(first_innings_scores) / len(first_innings_scores)
            venue.avg_first_innings_score = round(avg_first, 2)
            print(f"  Average first innings score: {avg_first:.2f}")
        
        if second_innings_scores:
            avg_second = sum(second_innings_scores) / len(second_innings_scores)
            venue.avg_second_innings_score = round(avg_second, 2)
            print(f"  Average second innings score: {avg_second:.2f}")
        
        # Calculate toss bias
        toss_bias = calculate_toss_bias(db, venue.id)
        if toss_bias["bat_first_total"] > 0 or toss_bias["chase_total"] > 0:
            print(f"  Toss bias:")
            print(f"    Bat first: {toss_bias['bat_first_wins']}/{toss_bias['bat_first_total']} ({toss_bias['bat_first_win_pct']}%)")
            print(f"    Chase: {toss_bias['chase_wins']}/{toss_bias['chase_total']} ({toss_bias['chase_win_pct']}%)")
            # Store in a JSONB field if we add it to Venue model
            # For now, we'll calculate on-demand
        
        db.commit()
        print(f"  ✓ Updated {venue.name}")


def calculate_venue_stats_from_csv(db: Session) -> None:
    """Calculate venue statistics from CSV match scorecards."""
    print("Calculating venue statistics from CSV data...")
    
    scorecards_path = PROCESSED_DIR / "match_scorecards.csv"
    if not scorecards_path.exists():
        print(f"  Scorecards file not found: {scorecards_path}")
        return
    
    scorecards = pd.read_csv(scorecards_path)
    
    # Filter for SA20 only
    sa20_scorecards = scorecards[scorecards['competition'] == 'sa20'].copy()
    
    if sa20_scorecards.empty:
        print("  No SA20 scorecards found")
        return
    
    print(f"  Found {len(sa20_scorecards)} SA20 match scorecards")
    
    # We need to match venues by name from match data
    # For now, we'll calculate from the scorecards and update manually
    # This is a simplified version - full implementation would need venue mapping
    
    venues = db.query(models.Venue).all()
    venue_map = {v.name.lower(): v for v in venues}
    
    # Calculate stats per venue
    for venue_name, venue in venue_map.items():
        # Match venue names (this is simplified - actual matching would be more complex)
        # We'd need to join match_scorecards with matches table to get venue_id
        print(f"\n  Venue: {venue.name}")
        print(f"  (Full implementation would calculate from matches table)")


def main() -> None:
    """Main function to calculate venue statistics."""
    db = SessionLocal()
    try:
        # Option 1: Calculate from database matches
        calculate_venue_stats_from_matches(db)
        
        # Option 2: Calculate from CSV (for reference)
        # calculate_venue_stats_from_csv(db)
        
    except Exception as e:
        print(f"Error calculating venue stats: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()

