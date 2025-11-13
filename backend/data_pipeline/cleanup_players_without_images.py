"""Script to remove players without valid images from the database.

Players without images are from previous seasons and should be removed
to keep only current season players.
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.session import SessionLocal
from app.db import models

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_valid_image_url(image_url: str | None) -> bool:
    """Check if an image URL is valid (same logic as player_service.py)."""
    if not image_url:
        return False
    
    url_lower = image_url.lower().strip()
    
    # UI patterns to exclude
    ui_patterns = [
        'instagram', 'logo', 'search', 'hamburger', 'chevron', 'icon', 
        'button', 'menu', 'arrow', 'svg', 'facebook', 'twitter', 'youtube',
        'linkedin', 'placeholder', 'default'
    ]
    
    # Skip if URL contains UI element patterns
    if any(pattern in url_lower for pattern in ui_patterns):
        return False
    
    # Skip if URL is too short (likely invalid)
    if len(url_lower) < 10:
        return False
    
    # Image-related keywords
    image_keywords = ['player', 'squad', 'team', 'photo', 'image', 'picture', 'portrait', 'headshot']
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    
    # Check for image extensions
    if any(ext in url_lower for ext in image_extensions):
        return True
    
    # Check for image-related keywords
    if any(keyword in url_lower for keyword in image_keywords):
        return True
    
    # Check if it starts with http/https (valid URL)
    if url_lower.startswith('http://') or url_lower.startswith('https://'):
        # Additional check: should not be a social media or UI URL
        bad_patterns = ['facebook', 'twitter', 'instagram', 'linkedin', 'youtube', 'google', 'cdn']
        if not any(bad_pattern in url_lower for bad_pattern in bad_patterns):
            return True
    
    return False


def get_players_without_valid_images(db: Session) -> list[models.Player]:
    """Get all players without valid images."""
    all_players = db.query(models.Player).all()
    players_without_images = []
    
    for player in all_players:
        if not is_valid_image_url(player.image_url):
            players_without_images.append(player)
    
    return players_without_images


def delete_player_and_related_data(db: Session, player: models.Player) -> bool:
    """Delete a player and all related data.
    
    Related data includes:
    - PlayerPerformance records
    - AggPlayerSeason records
    - SimPlayerSummary records
    - StrategyContext references (striker_id, non_striker_id, current_bowler_id) - set to None
    - FantasyProjection records
    """
    try:
        player_id = player.id
        player_name = player.name
        
        # Count related records before deletion (for logging)
        perf_count_before = db.query(models.PlayerPerformance).filter(
            models.PlayerPerformance.player_id == player_id
        ).count()
        
        # Delete PlayerPerformance records
        perf_count = db.query(models.PlayerPerformance).filter(
            models.PlayerPerformance.player_id == player_id
        ).delete(synchronize_session=False)
        if perf_count > 0:
            logger.debug(f"  Deleted {perf_count} PlayerPerformance records for {player_name}")
        
        # Delete AggPlayerSeason records
        agg_count = db.query(models.AggPlayerSeason).filter(
            models.AggPlayerSeason.player_id == player_id
        ).delete(synchronize_session=False)
        if agg_count > 0:
            logger.debug(f"  Deleted {agg_count} AggPlayerSeason records for {player_name}")
        
        # Delete SimPlayerSummary records
        sim_count = db.query(models.SimPlayerSummary).filter(
            models.SimPlayerSummary.player_id == player_id
        ).delete(synchronize_session=False)
        if sim_count > 0:
            logger.debug(f"  Deleted {sim_count} SimPlayerSummary records for {player_name}")
        
        # Delete FantasyProjection records
        fantasy_count = db.query(models.FantasyProjection).filter(
            models.FantasyProjection.player_id == player_id
        ).delete(synchronize_session=False)
        if fantasy_count > 0:
            logger.debug(f"  Deleted {fantasy_count} FantasyProjection records for {player_name}")
        
        # Update StrategyContext records to set player references to None
        # (These are nullable, so we can just set them to None)
        # We need to update each field separately to avoid SQLAlchemy issues
        strategy_updates = 0
        
        # Update striker_id
        striker_count = db.query(models.StrategyContext).filter(
            models.StrategyContext.striker_id == player_id
        ).update({models.StrategyContext.striker_id: None}, synchronize_session=False)
        strategy_updates += striker_count
        
        # Update non_striker_id
        non_striker_count = db.query(models.StrategyContext).filter(
            models.StrategyContext.non_striker_id == player_id
        ).update({models.StrategyContext.non_striker_id: None}, synchronize_session=False)
        strategy_updates += non_striker_count
        
        # Update current_bowler_id
        bowler_count = db.query(models.StrategyContext).filter(
            models.StrategyContext.current_bowler_id == player_id
        ).update({models.StrategyContext.current_bowler_id: None}, synchronize_session=False)
        strategy_updates += bowler_count
        
        if strategy_updates > 0:
            logger.debug(f"  Updated {strategy_updates} StrategyContext records for {player_name}")
        
        # Finally, delete the player
        db.delete(player)
        
        if perf_count_before > 0:
            logger.info(f"  ✓ Deleted player: {player_name} (ID: {player_id}) - had {perf_count_before} performances")
        else:
            logger.info(f"  ✓ Deleted player: {player_name} (ID: {player_id})")
        
        return True
    except Exception as e:
        logger.error(f"  ✗ Error deleting player {player.name}: {e}", exc_info=True)
        db.rollback()
        return False


def cleanup_players_without_images(dry_run: bool = True) -> dict:
    """Remove players without valid images from the database.
    
    Args:
        dry_run: If True, only report what would be deleted without actually deleting.
    
    Returns:
        Dictionary with cleanup statistics.
    """
    db = SessionLocal()
    
    try:
        # Get all players without valid images
        players_to_delete = get_players_without_valid_images(db)
        
        logger.info(f"Found {len(players_to_delete)} players without valid images")
        
        if dry_run:
            logger.info("DRY RUN MODE - No players will be deleted")
            logger.info("\nPlayers that would be deleted:")
            for player in players_to_delete[:20]:  # Show first 20
                logger.info(f"  - {player.name} (ID: {player.id}, Team: {player.team_id}, Image: {player.image_url[:50] if player.image_url else 'None'})")
            if len(players_to_delete) > 20:
                logger.info(f"  ... and {len(players_to_delete) - 20} more players")
            
            return {
                "total_players": len(players_to_delete),
                "deleted": 0,
                "failed": 0,
                "dry_run": True
            }
        
        # Delete players and their related data
        deleted_count = 0
        failed_count = 0
        
        for i, player in enumerate(players_to_delete, 1):
            logger.info(f"[{i}/{len(players_to_delete)}] Deleting {player.name}...")
            if delete_player_and_related_data(db, player):
                deleted_count += 1
                # Commit after each player to avoid large transactions
                db.commit()
            else:
                failed_count += 1
                db.rollback()
        
        logger.info(f"\n=== Cleanup Summary ===")
        logger.info(f"Total players without images: {len(players_to_delete)}")
        logger.info(f"Successfully deleted: {deleted_count}")
        logger.info(f"Failed: {failed_count}")
        
        return {
            "total_players": len(players_to_delete),
            "deleted": deleted_count,
            "failed": failed_count,
            "dry_run": False
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_players_without_images: {e}", exc_info=True)
        db.rollback()
        return {
            "total_players": 0,
            "deleted": 0,
            "failed": 0,
            "error": str(e)
        }
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up players without valid images")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete the players (default is dry-run)"
    )
    
    args = parser.parse_args()
    
    # Default to dry-run unless --execute is explicitly provided
    dry_run = not args.execute
    
    if dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN MODE - No players will be deleted")
        logger.info("Use --execute to actually delete players")
        logger.info("=" * 60)
    else:
        logger.warning("=" * 60)
        logger.warning("EXECUTION MODE - Players will be PERMANENTLY DELETED")
        logger.warning("=" * 60)
        response = input("Are you sure you want to delete players? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Operation cancelled")
            sys.exit(0)
    
    results = cleanup_players_without_images(dry_run=dry_run)
    
    if results.get("dry_run"):
        logger.info(f"\nTo delete these {results['total_players']} players, run:")
        logger.info("  python data_pipeline/cleanup_players_without_images.py --execute")

