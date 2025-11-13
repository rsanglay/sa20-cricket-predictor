"""Update player roles from official SA20 website scraper."""
from __future__ import annotations

import sys
import logging
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from data_pipeline.scrapers.sa20_api_scraper import SA20APIScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_role_from_scraper(role_text: str | None) -> models.PlayerRole | None:
    """Normalize role text from scraper to PlayerRole enum."""
    if not role_text:
        return None
    
    role_lower = str(role_text).lower().strip()
    
    # Check for wicket keeper first (including variations like "wicket keeper batter")
    # Wicket keeper takes priority over other roles
    if "wicket" in role_lower and ("keeper" in role_lower or "keep" in role_lower):
        return models.PlayerRole.WICKET_KEEPER
    if "wk" in role_lower and len(role_lower) <= 3:  # "wk" as standalone
        return models.PlayerRole.WICKET_KEEPER
    
    # Map various role strings to enum values
    role_map = {
        "batsman": models.PlayerRole.BATSMAN,
        "batter": models.PlayerRole.BATSMAN,
        "bowler": models.PlayerRole.BOWLER,
        "all-rounder": models.PlayerRole.ALL_ROUNDER,
        "allrounder": models.PlayerRole.ALL_ROUNDER,
        "all rounder": models.PlayerRole.ALL_ROUNDER,
    }
    
    # Check for exact matches first
    if role_lower in role_map:
        return role_map[role_lower]
    
    # Check for partial matches
    for key, value in role_map.items():
        if key in role_lower:
            return value
    
    return None


def update_roles_from_sa20_scraper(db: Session, dry_run: bool = False) -> dict:
    """Update player roles by scraping SA20 official website."""
    logger.info("=" * 70)
    logger.info("Updating Player Roles from SA20 Official Website")
    logger.info("=" * 70)
    
    scraper = SA20APIScraper()
    
    # Get all teams first
    logger.info("Fetching teams from SA20 website...")
    teams_data = scraper.scrape_teams()
    logger.info(f"Found {len(teams_data)} teams")
    
    # Build a map of team name to team slug
    team_slug_map = {}
    for team_data in teams_data:
        team_name = team_data.get("name", "")
        team_slug = team_data.get("slug", "")
        if team_name and team_slug:
            team_slug_map[team_name.lower()] = team_slug
    
    # Get all players from database, grouped by team
    players_by_team = {}
    all_players = db.query(models.Player).all()
    
    for player in all_players:
        team_name = player.team.name.lower() if player.team else None
        if team_name:
            if team_name not in players_by_team:
                players_by_team[team_name] = []
            players_by_team[team_name].append(player)
    
    stats = {
        "total_players": len(all_players),
        "updated": 0,
        "unchanged": 0,
        "not_found": 0,
        "no_role_data": 0,
        "changes": [],
    }
    
    # Scrape each team's players
    for team_name, players in players_by_team.items():
        team_slug = team_slug_map.get(team_name)
        if not team_slug:
            logger.warning(f"Could not find slug for team: {team_name}")
            stats["not_found"] += len(players)
            continue
        
        logger.info(f"\nScraping players for {team_name} (slug: {team_slug})...")
        try:
            players_data = scraper.scrape_team_players(team_slug)
            logger.info(f"  Found {len(players_data)} players on website")
            
            # Create a lookup by name (normalized)
            def normalize_name(name: str) -> str:
                return name.lower().strip().replace("'", "").replace(" ", "")
            
            players_lookup = {}
            for p_data in players_data:
                name = p_data.get("name", "")
                if name:
                    normalized = normalize_name(name)
                    players_lookup[normalized] = p_data
            
            # Match database players with scraped data
            for player in players:
                player_normalized = normalize_name(player.name)
                
                # Try exact match first
                player_data = players_lookup.get(player_normalized)
                
                # Try partial match if exact match fails
                if not player_data:
                    for key, p_data in players_lookup.items():
                        if player_normalized in key or key in player_normalized:
                            player_data = p_data
                            break
                
                if player_data and player_data.get("role"):
                    # Normalize and update role
                    new_role = normalize_role_from_scraper(player_data["role"])
                    
                    if new_role and player.role != new_role:
                        old_role = player.role.value if hasattr(player.role, "value") else str(player.role)
                        new_role_str = new_role.value if hasattr(new_role, "value") else str(new_role)
                        
                        stats["changes"].append({
                            "player_id": player.id,
                            "name": player.name,
                            "old_role": old_role,
                            "new_role": new_role_str,
                            "source": "SA20 Website",
                        })
                        
                        if not dry_run:
                            player.role = new_role
                            stats["updated"] += 1
                        else:
                            stats["updated"] += 1
                    elif new_role and player.role == new_role:
                        stats["unchanged"] += 1
                    else:
                        stats["no_role_data"] += 1
                else:
                    stats["not_found"] += 1
            
            # Rate limiting
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error scraping team {team_name}: {e}")
            stats["not_found"] += len(players)
    
    if not dry_run:
        db.commit()
        logger.info(f"✓ Committed {stats['updated']} role updates")
    else:
        logger.info(f"✓ Dry run: Would update {stats['updated']} roles")
    
    logger.info(f"\nSummary:")
    logger.info(f"  Total players: {stats['total_players']}")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Unchanged: {stats['unchanged']}")
    logger.info(f"  Not found on website: {stats['not_found']}")
    logger.info(f"  No role data: {stats['no_role_data']}")
    
    if stats["changes"]:
        logger.info(f"\nFirst 20 changes:")
        for change in stats["changes"][:20]:
            logger.info(
                f"  {change['name']}: {change['old_role']} → {change['new_role']} ({change['source']})"
            )
    
    return stats


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update player roles from SA20 official website")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without actually updating the database",
    )
    args = parser.parse_args()
    
    db: Session = SessionLocal()
    try:
        stats = update_roles_from_sa20_scraper(db, dry_run=args.dry_run)
        
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

