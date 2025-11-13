"""Load player performances from deliveries data into the database."""
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Add app directory to path
if Path("/app/app").exists():
    sys.path.insert(0, "/app")
else:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal
from app.db import models

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Determine paths based on environment
if Path("/app/data/processed").exists():
    # Docker environment
    PROCESSED_DIR = Path("/app/data/processed")
else:
    # Local environment
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DELIVERIES_FILE = PROCESSED_DIR / "sa20_deliveries.csv"
ROSTERS_FILE = PROCESSED_DIR / "sa20_team_rosters.csv"


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    if not name:
        return ""
    # Remove extra spaces, convert to title case
    return " ".join(name.strip().split())


def find_player_by_name(db: Session, player_name: str, team_name: Optional[str] = None) -> Optional[models.Player]:
    """Find a player in the database by name with flexible matching."""
    normalized_name = normalize_player_name(player_name)
    
    # Try exact match first
    query = db.query(models.Player).filter(models.Player.name == normalized_name)
    if team_name:
        team = db.query(models.Team).filter(models.Team.name == team_name).first()
        if team:
            query = query.filter(models.Player.team_id == team.id)
    
    player = query.first()
    if player:
        return player
    
    # Try case-insensitive exact match
    query = db.query(models.Player).filter(models.Player.name.ilike(normalized_name))
    if team_name:
        team = db.query(models.Team).filter(models.Team.name == team_name).first()
        if team:
            query = query.filter(models.Player.team_id == team.id)
    
    player = query.first()
    if player:
        return player
    
    # Try matching by last name (most reliable)
    name_parts = normalized_name.split()
    if len(name_parts) >= 2:
        last_name = name_parts[-1]
        # Match if last name appears in player name
        query = db.query(models.Player).filter(
            models.Player.name.ilike(f"%{last_name}%")
        )
        if team_name:
            team = db.query(models.Team).filter(models.Team.name == team_name).first()
            if team:
                query = query.filter(models.Player.team_id == team.id)
        
        # If multiple matches, prefer ones that also match first initial or first name
        candidates = query.all()
        if len(candidates) == 1:
            return candidates[0]
        elif len(candidates) > 1:
            # Try to match first name/initial
            first_part = name_parts[0]
            for candidate in candidates:
                candidate_parts = candidate.name.split()
                if candidate_parts and (
                    candidate_parts[0].startswith(first_part) or 
                    first_part.startswith(candidate_parts[0][0]) or
                    candidate_parts[0].startswith(first_part[0])
                ):
                    return candidate
            # Return first match if no better match
            return candidates[0]
    
    # Try matching by initials (e.g., "D Brevis" -> "Dewald Brevis")
    if len(name_parts) == 2 and len(name_parts[0]) <= 3:
        # First part looks like initials
        last_name = name_parts[-1]
        query = db.query(models.Player).filter(
            models.Player.name.ilike(f"%{last_name}%")
        )
        candidates = query.all()
        if candidates:
            # Prefer matches where first initial matches
            first_initial = name_parts[0][0].upper()
            for candidate in candidates:
                candidate_parts = candidate.name.split()
                if candidate_parts and candidate_parts[0][0].upper() == first_initial:
                    return candidate
            # Return first match if no initial match
            return candidates[0]
    
    # Try substring match as last resort
    query = db.query(models.Player).filter(
        models.Player.name.ilike(f"%{normalized_name}%")
    )
    if team_name:
        team = db.query(models.Team).filter(models.Team.name == team_name).first()
        if team:
            query = query.filter(models.Player.team_id == team.id)
    
    player = query.first()
    return player


def find_match_by_season_date(db: Session, season: int, match_date: str, home_team_name: str, away_team_name: str) -> Optional[models.Match]:
    """Find a match in the database by season, date, and teams."""
    try:
        match_date_obj = datetime.strptime(match_date, "%Y-%m-%d").date()
    except:
        return None
    
    # Find teams
    home_team = db.query(models.Team).filter(models.Team.name == home_team_name).first()
    away_team = db.query(models.Team).filter(models.Team.name == away_team_name).first()
    
    if not home_team or not away_team:
        return None
    
    # Find match
    match = db.query(models.Match).filter(
        and_(
            models.Match.season == season,
            models.Match.match_date == match_date_obj,
            models.Match.home_team_id == home_team.id,
            models.Match.away_team_id == away_team.id
        )
    ).first()
    
    if match:
        return match
    
    # Try with swapped teams
    match = db.query(models.Match).filter(
        and_(
            models.Match.season == season,
            models.Match.match_date == match_date_obj,
            models.Match.home_team_id == away_team.id,
            models.Match.away_team_id == home_team.id
        )
    ).first()
    
    return match


def create_matches_from_deliveries(db: Session, deliveries_df: pd.DataFrame) -> Dict[str, models.Match]:
    """Create Match records from deliveries data and return mapping of match_id to Match."""
    logger.info("Creating matches from deliveries data...")
    
    # Get unique matches
    unique_matches = deliveries_df[['match_id', 'season', 'match_date', 'innings_team']].drop_duplicates()
    
    # Group by match_id to get teams
    match_teams = deliveries_df.groupby('match_id')['innings_team'].apply(lambda x: list(x.unique())).to_dict()
    
    match_map = {}
    matches_created = 0
    
    for match_id_str, teams in match_teams.items():
        if len(teams) < 2:
            continue
        
        # Get match info
        match_data = deliveries_df[deliveries_df['match_id'] == match_id_str].iloc[0]
        season_raw = match_data['season']
        match_date_str = match_data['match_date']
        
        # Parse season
        if pd.notna(season_raw):
            season_str = str(season_raw)
            if '/' in season_str:
                season = int(season_str.split('/')[0])
            else:
                try:
                    season = int(season_str)
                except:
                    season = 2023  # Default
        else:
            season = 2023
        
        # Parse date
        try:
            match_date = datetime.strptime(match_date_str, "%Y-%m-%d").date()
        except:
            continue
        
        # Check if match already exists
        home_team_name = teams[0]
        away_team_name = teams[1]
        
        home_team = db.query(models.Team).filter(models.Team.name == home_team_name).first()
        away_team = db.query(models.Team).filter(models.Team.name == away_team_name).first()
        
        if not home_team or not away_team:
            continue
        
        # Check if match exists
        existing = db.query(models.Match).filter(
            and_(
                models.Match.season == season,
                models.Match.match_date == match_date,
                models.Match.home_team_id == home_team.id,
                models.Match.away_team_id == away_team.id
            )
        ).first()
        
        if existing:
            match_map[match_id_str] = existing
            continue
        
        # Get venue (use home team's venue or first available)
        venue = None
        if hasattr(home_team, 'city') and home_team.city:
            # Try to find venue by city
            venue = db.query(models.Venue).filter(models.Venue.city == home_team.city).first()
        
        if not venue:
            # Use first available venue
            venue = db.query(models.Venue).first()
        
        if not venue:
            continue
        
        # Create match
        match = models.Match(
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            venue_id=venue.id,
            match_date=match_date,
            season=season,
        )
        db.add(match)
        db.flush()
        match_map[match_id_str] = match
        matches_created += 1
    
    db.commit()
    logger.info(f"  ✓ Created {matches_created} matches")
    return match_map


def load_player_performances(dry_run: bool = False, limit: Optional[int] = None):
    """Load player performances from deliveries data."""
    if not DELIVERIES_FILE.exists():
        logger.error(f"Deliveries file not found: {DELIVERIES_FILE}")
        return
    
    logger.info(f"Loading player performances from {DELIVERIES_FILE}")
    
    # Read deliveries data
    logger.info("Reading deliveries data...")
    deliveries_df = pd.read_csv(DELIVERIES_FILE)
    
    if limit:
        deliveries_df = deliveries_df.head(limit * 1000)  # Rough estimate
    
    logger.info(f"Loaded {len(deliveries_df)} delivery records")
    
    # Read rosters for team mapping
    rosters_df = None
    if ROSTERS_FILE.exists():
        rosters_df = pd.read_csv(ROSTERS_FILE)
        logger.info(f"Loaded {len(rosters_df)} roster records")
    
    db = SessionLocal()
    
    try:
        # First, create matches from deliveries data
        match_map = create_matches_from_deliveries(db, deliveries_df)
        
        # Group deliveries by match, player, and team
        logger.info("Aggregating player performances...")
        
        # Aggregate batting stats
        batting_stats = deliveries_df.groupby([
            'match_id', 'season', 'match_date', 'innings_team', 'batter'
        ]).agg({
            'runs_batter': 'sum',
            'runs_batter': lambda x: (x > 0).sum(),  # balls faced = count of deliveries
            'runs_batter': lambda x: (x == 4).sum(),  # fours
            'runs_batter': lambda x: (x == 6).sum(),   # sixes
        }).reset_index()
        
        # Fix the aggregation - pandas groupby with multiple lambdas doesn't work as expected
        batting_stats = deliveries_df.groupby([
            'match_id', 'season', 'match_date', 'innings_team', 'batter'
        ]).agg({
            'runs_batter': ['sum', 'count', lambda x: (x == 4).sum(), lambda x: (x == 6).sum()]
        }).reset_index()
        
        batting_stats.columns = ['match_id', 'season', 'match_date', 'team_name', 'player_name', 'runs', 'balls', 'fours', 'sixes']
        
        # Aggregate bowling stats
        bowling_stats = deliveries_df.groupby([
            'match_id', 'season', 'match_date', 'bowler'
        ]).agg({
            'runs_total': 'sum',  # runs conceded
            'runs_total': 'count',  # deliveries bowled
            'wicket': 'sum',  # wickets taken
        }).reset_index()
        
        # Fix bowling aggregation too
        bowling_stats = deliveries_df.groupby([
            'match_id', 'season', 'match_date', 'bowler'
        ]).agg({
            'runs_total': ['sum', 'count'],
            'wicket': 'sum'
        }).reset_index()
        
        bowling_stats.columns = ['match_id', 'season', 'match_date', 'player_name', 'runs_conceded', 'deliveries', 'wickets']
        
        # Get unique matches to find match IDs
        unique_matches = deliveries_df[['match_id', 'season', 'match_date', 'innings_team']].drop_duplicates()
        
        performances_created = 0
        performances_skipped = 0
        players_not_found = set()
        matches_not_found = set()
        
        # Process batting performances
        logger.info("Processing batting performances...")
        for idx, row in batting_stats.iterrows():
            if dry_run and idx >= 10:
                break
            
            player_name = normalize_player_name(row['player_name'])
            team_name = row['team_name']
            match_id_str = str(row['match_id'])
            # Parse season (could be "2022/23" or 2023)
            season_raw = row['season']
            if pd.notna(season_raw):
                season_str = str(season_raw)
                if '/' in season_str:
                    # Extract first year from "2022/23" -> 2022
                    season = int(season_str.split('/')[0])
                else:
                    try:
                        season = int(season_str)
                    except:
                        season = None
            else:
                season = None
            match_date = row['match_date']
            
            # Find player
            player = find_player_by_name(db, player_name, team_name)
            if not player:
                players_not_found.add(player_name)
                performances_skipped += 1
                continue
            
            # Find match - we need to get teams from the match data
            # For now, try to find match by season and date
            # We'll need to get team names from the deliveries data
            match_teams = deliveries_df[deliveries_df['match_id'] == match_id_str]['innings_team'].unique()
            if len(match_teams) < 2:
                matches_not_found.add(match_id_str)
                performances_skipped += 1
                continue
            
            # Use match_map instead of searching
            match = match_map.get(match_id_str)
            if not match:
                matches_not_found.add(match_id_str)
                performances_skipped += 1
                continue
            
            # Find team
            team = db.query(models.Team).filter(models.Team.name == team_name).first()
            if not team:
                performances_skipped += 1
                continue
            
            # Check if performance already exists
            existing = db.query(models.PlayerPerformance).filter(
                and_(
                    models.PlayerPerformance.player_id == player.id,
                    models.PlayerPerformance.match_id == match.id
                )
            ).first()
            
            if existing:
                # Update existing
                existing.runs_scored = int(row['runs'])
                existing.balls_faced = int(row['balls'])
                existing.fours = int(row['fours'])
                existing.sixes = int(row['sixes'])
                existing.team_id = team.id
                performances_created += 1
            else:
                # Create new
                perf = models.PlayerPerformance(
                    player_id=player.id,
                    match_id=match.id,
                    team_id=team.id,
                    runs_scored=int(row['runs']),
                    balls_faced=int(row['balls']),
                    fours=int(row['fours']),
                    sixes=int(row['sixes']),
                )
                db.add(perf)
                performances_created += 1
            
            if idx % 100 == 0:
                logger.info(f"  Processed {idx} batting performances...")
                if not dry_run:
                    db.commit()
        
        # Process bowling performances
        logger.info("Processing bowling performances...")
        for idx, row in bowling_stats.iterrows():
            if dry_run and idx >= 10:
                break
            
            player_name = normalize_player_name(row['player_name'])
            match_id_str = str(row['match_id'])
            # Parse season (could be "2022/23" or 2023)
            season_raw = row['season']
            if pd.notna(season_raw):
                season_str = str(season_raw)
                if '/' in season_str:
                    # Extract first year from "2022/23" -> 2022
                    season = int(season_str.split('/')[0])
                else:
                    try:
                        season = int(season_str)
                    except:
                        season = None
            else:
                season = None
            match_date = row['match_date']
            
            # Find player (no team filter for bowling - bowler could be from either team)
            player = find_player_by_name(db, player_name)
            if not player:
                players_not_found.add(player_name)
                performances_skipped += 1
                continue
            
            # Find match
            match_teams = deliveries_df[deliveries_df['match_id'] == match_id_str]['innings_team'].unique()
            if len(match_teams) < 2:
                matches_not_found.add(match_id_str)
                performances_skipped += 1
                continue
            
            # Use match_map instead of searching
            match = match_map.get(match_id_str)
            if not match:
                matches_not_found.add(match_id_str)
                performances_skipped += 1
                continue
            
            # Get bowler's team from deliveries (which team did they bowl for?)
            bowler_deliveries = deliveries_df[
                (deliveries_df['match_id'] == match_id_str) & 
                (deliveries_df['bowler'] == row['player_name'])
            ]
            if bowler_deliveries.empty:
                performances_skipped += 1
                continue
            
            # Bowler's team is the opposite of the innings_team
            innings_teams = bowler_deliveries['innings_team'].unique()
            # The bowler bowls for the team that is NOT batting
            # We need to find which team the bowler belongs to from rosters
            team = None
            if rosters_df is not None:
                player_rosters = rosters_df[
                    (rosters_df['match_id'] == match_id_str) &
                    (rosters_df['player_name'] == row['player_name'])
                ]
                if not player_rosters.empty:
                    team_name = player_rosters.iloc[0]['team_name']
                    team = db.query(models.Team).filter(models.Team.name == team_name).first()
            
            # Calculate overs (deliveries / 6)
            deliveries_count = int(row['deliveries'])
            overs = deliveries_count / 6.0
            
            # Check if performance already exists
            existing = db.query(models.PlayerPerformance).filter(
                and_(
                    models.PlayerPerformance.player_id == player.id,
                    models.PlayerPerformance.match_id == match.id
                )
            ).first()
            
            if existing:
                # Update existing
                existing.wickets_taken = int(row['wickets'])
                existing.runs_conceded = int(row['runs_conceded'])
                existing.overs_bowled = overs
                if team:
                    existing.team_id = team.id
                performances_created += 1
            else:
                # Create new or update if batting perf exists
                perf = models.PlayerPerformance(
                    player_id=player.id,
                    match_id=match.id,
                    team_id=team.id if team else None,
                    wickets_taken=int(row['wickets']),
                    runs_conceded=int(row['runs_conceded']),
                    overs_bowled=overs,
                )
                db.add(perf)
                performances_created += 1
            
            if idx % 100 == 0:
                logger.info(f"  Processed {idx} bowling performances...")
                if not dry_run:
                    db.commit()
        
        if not dry_run:
            db.commit()
        
        logger.info(f"\n=== Summary ===")
        logger.info(f"Performances created/updated: {performances_created}")
        logger.info(f"Performances skipped: {performances_skipped}")
        logger.info(f"Players not found: {len(players_not_found)}")
        if players_not_found:
            logger.info(f"  Sample: {list(players_not_found)[:10]}")
        logger.info(f"Matches not found: {len(matches_not_found)}")
        if matches_not_found:
            logger.info(f"  Sample: {list(matches_not_found)[:10]}")
        
    except Exception as e:
        logger.error(f"Error loading player performances: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Load player performances from deliveries data")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (process first 10 only)")
    parser.add_argument("--limit", type=int, help="Limit number of matches to process")
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN MODE - Only processing first 10 performances")
        logger.info("=" * 60)
    
    load_player_performances(dry_run=args.dry_run, limit=args.limit)

