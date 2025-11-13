"""Script to scrape and update SA20 teams and players from official website."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from data_pipeline.scrapers.sa20_teams_scraper import SA20TeamsScraper
from data_pipeline.scrapers.sa20_stats_scraper import SA20StatsScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Normalize name for matching."""
    return name.strip().lower().replace("'", "").replace(" ", "_")


def get_team_by_name(db: Session, name: str) -> models.Team | None:
    """Get team from database by name."""
    # Try exact match
    team = db.query(models.Team).filter(models.Team.name == name).first()
    if team:
        return team
    
    # Try short name
    team = db.query(models.Team).filter(models.Team.short_name == name).first()
    if team:
        return team
    
    # Try normalized match
    normalized = normalize_name(name)
    all_teams = db.query(models.Team).all()
    for t in all_teams:
        if normalize_name(t.name) == normalized or normalize_name(t.short_name or "") == normalized:
            return t
    
    return None


def update_teams_and_players(db: Session, update_roles_from_stats: bool = True) -> tuple[int, int]:
    """Scrape and update teams and players from SA20 website."""
    logger.info("Scraping SA20 teams and players from official website...")
    
    teams_scraper = SA20TeamsScraper()
    teams_data = teams_scraper.scrape_all_teams()
    
    if not teams_data:
        logger.warning("No teams found from scraper")
        return 0, 0
    
    teams_updated = 0
    players_added = 0
    
    # Optionally scrape stats to get accurate roles
    stats_scraper = None
    if update_roles_from_stats:
        try:
            stats_scraper = SA20StatsScraper()
            logger.info("Stats scraper initialized for role verification")
        except Exception as e:
            logger.warning(f"Could not initialize stats scraper: {e}")
    
    for team_data in teams_data:
        team = get_team_by_name(db, team_data["name"])
        if not team:
            logger.warning(f"Team not found in database: {team_data['name']}")
            continue
        
        # Update team logo if available
        if team_data.get("logo_url"):
            logger.info(f"Found logo for {team.name}: {team_data['logo_url']}")
        
        # Scrape players for this team
        slug = team_data.get("slug")
        if slug:
            players_data = teams_scraper.scrape_team_players(slug)
            
            for player_data in players_data:
                # Check if player exists
                existing = db.query(models.Player).filter(
                    models.Player.name == player_data["name"],
                    models.Player.team_id == team.id
                ).first()
                
                # Try to get role from stats if available
                inferred_role = player_data.get("role")
                if stats_scraper and not inferred_role:
                    # Could cross-reference with stats to infer role
                    pass
                
                # Normalize role string
                role_map = {
                    "batsman": models.PlayerRole.BATSMAN,
                    "batter": models.PlayerRole.BATSMAN,
                    "bowler": models.PlayerRole.BOWLER,
                    "all-rounder": models.PlayerRole.ALL_ROUNDER,
                    "all_rounder": models.PlayerRole.ALL_ROUNDER,
                    "wicket-keeper": models.PlayerRole.WICKET_KEEPER,
                    "wicket_keeper": models.PlayerRole.WICKET_KEEPER,
                    "keeper": models.PlayerRole.WICKET_KEEPER,
                    "wk": models.PlayerRole.WICKET_KEEPER,
                }
                
                # Try to get role from scraped data
                role = models.PlayerRole.BATSMAN  # Default fallback
                if inferred_role:
                    role_str = str(inferred_role).lower().strip()
                    role = role_map.get(role_str, models.PlayerRole.BATSMAN)
                
                if existing:
                    # Update existing player
                    if existing.role != role:
                        existing.role = role
                        logger.info(f"Updated role for {player_data['name']}: {existing.role.value} → {role.value}")
                    
                    if player_data.get("image_url"):
                        existing.image_url = player_data["image_url"]
                    
                    if player_data.get("country"):
                        existing.country = player_data["country"]
                    
                    logger.debug(f"Updated player: {player_data['name']}")
                else:
                    # Create new player
                    player = models.Player(
                        name=player_data["name"],
                        role=role,
                        batting_style=models.BattingStyle.RIGHT_HAND,  # Default
                        team_id=team.id,
                        country=player_data.get("country", "South Africa"),
                        age=25,  # Default, could be scraped if available
                        image_url=player_data.get("image_url"),
                    )
                    db.add(player)
                    players_added += 1
                    logger.info(f"Added player: {player_data['name']} ({role.value})")
        
        teams_updated += 1
    
    db.commit()
    logger.info(f"✓ Updated {teams_updated} teams, added/updated {players_added} players")
    return teams_updated, players_added


def main():
    """Main function."""
    db: Session = SessionLocal()
    try:
        teams_updated, players_added = update_teams_and_players(db)
        print(f"\n✓ Successfully updated {teams_updated} teams and {players_added} players")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating teams/players: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

