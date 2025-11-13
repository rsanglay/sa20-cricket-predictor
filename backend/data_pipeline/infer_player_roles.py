"""Utility to infer player roles from performance statistics."""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal

logger = __import__("logging").getLogger(__name__)

# Manual overrides for known players (name -> role)
# Use this for players where statistics don't accurately reflect their primary role
KNOWN_PLAYER_ROLES = {
    "Aiden Markram": models.PlayerRole.BATSMAN,  # Batsman who bowls occasionally
    "Imran Tahir": models.PlayerRole.BOWLER,  # Specialist leg-spinner
    # Add more known players as needed
}


def infer_role_from_stats(
    total_runs: int,
    total_balls: int,
    total_wickets: int,
    total_overs: float,
    total_catches: int,
    total_stumpings: int,
) -> models.PlayerRole:
    """
    Infer player role from career statistics.
    
    Logic (prioritizes primary role):
    - Wicket keeper: Has significant catches/stumpings (>= 5)
    - All-rounder: Has BOTH significant batting (>= 150 runs OR >= 100 balls) AND significant bowling (>= 8 wickets OR >= 15 overs)
    - Bowler: Primary contribution is bowling - either:
      * Has 10+ wickets AND runs < 100 (clearly a bowler)
      * Has 15+ overs AND wickets significantly outweigh runs (wickets > runs/20 AND runs < 150)
      * Has 8+ wickets AND very few runs (< 30) - specialist bowler
    - Batsman: Default/primary contribution is batting (if they have 50+ runs or 30+ balls, they're a batsman unless clearly a bowler)
    """
    # Check for wicket keeper first (catches + stumpings)
    if total_catches + total_stumpings >= 5:
        # But if they also have significant bowling, they might be an all-rounder who keeps
        if total_wickets >= 8 and total_runs >= 150:
            return models.PlayerRole.ALL_ROUNDER
        # If they have significant batting but not bowling, they're a wicket keeper
        if total_runs >= 100:
            return models.PlayerRole.WICKET_KEEPER
    
    # Check for all-rounder: BOTH significant batting AND significant bowling
    has_significant_batting = total_runs >= 150 or total_balls >= 100
    has_significant_bowling = total_wickets >= 8 or total_overs >= 15
    
    if has_significant_batting and has_significant_bowling:
        return models.PlayerRole.ALL_ROUNDER
    
    # Check for bowler: primary contribution must be clearly bowling
    # Rule 1: Specialist bowler - 10+ wickets with limited batting (< 100 runs)
    if total_wickets >= 10 and total_runs < 100:
        return models.PlayerRole.BOWLER
    
    # Rule 2: Significant overs (15+) with wickets clearly outweighing runs
    if total_overs >= 15:
        # Wickets should be much more significant than runs
        if total_wickets > (total_runs / 20) and total_runs < 150:
            return models.PlayerRole.BOWLER
    
    # Rule 3: Specialist bowler with 8+ wickets and very few runs
    if total_wickets >= 8 and total_runs < 30:
        return models.PlayerRole.BOWLER
    
    # Rule 4: If they have ANY batting contribution (runs or balls), they're likely a batsman
    # unless bowling is clearly dominant. A batsman who bowls occasionally should stay batsman.
    if total_runs > 0 or total_balls > 0:
        # Only classify as bowler if wickets are MUCH more significant than runs
        # For example: 10+ wickets with very few runs (< 30), or wickets >> runs/15
        if total_wickets >= 10 and total_runs < 30:
            return models.PlayerRole.BOWLER
        # If they have significant batting (30+ runs or 20+ balls), definitely a batsman
        if total_runs >= 30 or total_balls >= 20:
            return models.PlayerRole.BATSMAN
        # If they have some runs/balls but also wickets, check ratio
        # If wickets are less than 3x runs, they're a batsman
        if total_runs > 0 and total_wickets > 0:
            if total_runs >= total_wickets * 3:
                return models.PlayerRole.BATSMAN
            # If wickets are much more than runs, might be bowler
            if total_wickets >= 8 and total_runs < 20:
                return models.PlayerRole.BOWLER
    
    # Rule 5: If they have wickets but no batting at all, they're a bowler
    if total_wickets >= 3 and total_runs == 0 and total_balls == 0:
        return models.PlayerRole.BOWLER
    
    # Default to batsman
    return models.PlayerRole.BATSMAN


def update_player_roles_from_performances(db: Session, dry_run: bool = False) -> dict:
    """Update player roles based on their performance statistics."""
    logger.info("=" * 70)
    logger.info("Updating Player Roles from Performance Statistics")
    logger.info("=" * 70)
    
    # Get all players
    players = db.query(models.Player).all()
    
    stats = {
        "total_players": len(players),
        "updated": 0,
        "unchanged": 0,
        "no_data": 0,
        "changes": [],
    }
    
    for player in players:
        # Check for manual override first
        if player.name in KNOWN_PLAYER_ROLES:
            inferred_role = KNOWN_PLAYER_ROLES[player.name]
            if player.role != inferred_role:
                old_role = player.role.value if hasattr(player.role, "value") else str(player.role)
                new_role = inferred_role.value if hasattr(inferred_role, "value") else str(inferred_role)
                
                stats["changes"].append({
                    "player_id": player.id,
                    "name": player.name,
                    "old_role": old_role,
                    "new_role": new_role,
                    "stats": {"note": "Manual override"},
                })
                
                if not dry_run:
                    player.role = inferred_role
                    stats["updated"] += 1
                else:
                    stats["updated"] += 1
            else:
                stats["unchanged"] += 1
            continue
        
        # Aggregate performance statistics
        result = db.query(
            func.sum(models.PlayerPerformance.runs_scored).label("total_runs"),
            func.sum(models.PlayerPerformance.balls_faced).label("total_balls"),
            func.sum(models.PlayerPerformance.wickets_taken).label("total_wickets"),
            func.sum(models.PlayerPerformance.overs_bowled).label("total_overs"),
            func.sum(models.PlayerPerformance.catches).label("total_catches"),
            func.sum(models.PlayerPerformance.stumpings).label("total_stumpings"),
        ).filter(models.PlayerPerformance.player_id == player.id).first()
        
        total_runs = result.total_runs or 0
        total_balls = result.total_balls or 0
        total_wickets = result.total_wickets or 0
        total_overs = result.total_overs or 0.0
        total_catches = result.total_catches or 0
        total_stumpings = result.total_stumpings or 0
        
        # If no performance data, skip
        if total_runs == 0 and total_balls == 0 and total_wickets == 0 and total_overs == 0:
            stats["no_data"] += 1
            continue
        
        # Infer role from stats
        inferred_role = infer_role_from_stats(
            total_runs=int(total_runs),
            total_balls=int(total_balls),
            total_wickets=int(total_wickets),
            total_overs=float(total_overs),
            total_catches=int(total_catches),
            total_stumpings=int(total_stumpings),
        )
        
        # Check if role needs updating
        if player.role != inferred_role:
            old_role = player.role.value if hasattr(player.role, "value") else str(player.role)
            new_role = inferred_role.value if hasattr(inferred_role, "value") else str(inferred_role)
            
            stats["changes"].append({
                "player_id": player.id,
                "name": player.name,
                "old_role": old_role,
                "new_role": new_role,
                "stats": {
                    "runs": total_runs,
                    "balls": total_balls,
                    "wickets": total_wickets,
                    "overs": total_overs,
                    "catches": total_catches,
                    "stumpings": total_stumpings,
                },
            })
            
            if not dry_run:
                player.role = inferred_role
                stats["updated"] += 1
            else:
                stats["updated"] += 1
        else:
            stats["unchanged"] += 1
    
    if not dry_run:
        db.commit()
        logger.info(f"✓ Committed {stats['updated']} role updates")
    else:
        logger.info(f"✓ Dry run: Would update {stats['updated']} roles")
    
    logger.info(f"\nSummary:")
    logger.info(f"  Total players: {stats['total_players']}")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Unchanged: {stats['unchanged']}")
    logger.info(f"  No performance data: {stats['no_data']}")
    
    if stats["changes"]:
        logger.info(f"\nFirst 10 changes:")
        for change in stats["changes"][:10]:
            stats_str = ""
            if "note" in change["stats"]:
                stats_str = f"({change['stats']['note']})"
            else:
                stats_str = (
                    f"(R:{change['stats'].get('runs', 0)}, "
                    f"W:{change['stats'].get('wickets', 0)}, "
                    f"O:{change['stats'].get('overs', 0):.1f})"
                )
            logger.info(
                f"  {change['name']}: {change['old_role']} → {change['new_role']} {stats_str}"
            )
    
    return stats


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update player roles from performance statistics")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without actually updating the database",
    )
    args = parser.parse_args()
    
    db: Session = SessionLocal()
    try:
        stats = update_player_roles_from_performances(db, dry_run=args.dry_run)
        
        if args.dry_run:
            print("\n" + "=" * 70)
            print("DRY RUN - No changes were made to the database")
            print("=" * 70)
            print(f"\nRun without --dry-run to apply {stats['updated']} role updates")
        else:
            print("\n" + "=" * 70)
            print("✓ Player roles updated successfully!")
            print("=" * 70)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating player roles: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

