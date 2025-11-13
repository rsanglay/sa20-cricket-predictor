"""Generate player stats from deliveries data for players without scraped stats."""
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import json

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

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
    PROCESSED_DIR = Path("/app/data/processed")
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DELIVERIES_FILE = PROCESSED_DIR / "sa20_deliveries.csv"


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    if not name:
        return ""
    return " ".join(name.strip().split())


def find_player_by_name(db: Session, player_name: str) -> Optional[models.Player]:
    """Find a player in the database by name with flexible matching."""
    if not player_name:
        return None
    
    normalized_search = normalize_player_name(player_name).lower()
    
    # Try exact match
    player = db.query(models.Player).filter(
        func.lower(models.Player.name) == normalized_search
    ).first()
    
    if player:
        return player
    
    # Try partial match
    players = db.query(models.Player).filter(
        func.lower(models.Player.name).contains(normalized_search)
    ).all()
    
    if len(players) == 1:
        return players[0]
    
    # Try reverse (search name in player name)
    if len(players) > 1:
        for p in players:
            if normalized_search in p.name.lower():
                return p
    
    return None


def normalize_name_for_matching(name: str) -> str:
    """Normalize name for matching."""
    if not name or pd.isna(name):
        return ""
    # Remove special characters, convert to lowercase
    name = str(name).strip().lower()
    # Remove common prefixes/suffixes
    name = name.replace(" (c)", "").replace(" (wk)", "").replace(" *", "")
    return name


def find_player_in_deliveries(player_name: str, deliveries_df: pd.DataFrame) -> Optional[str]:
    """Find player name in deliveries data with flexible matching."""
    normalized_player = normalize_name_for_matching(player_name)
    
    # Get all unique player names from deliveries
    all_batters = deliveries_df['batter'].dropna().unique()
    all_bowlers = deliveries_df['bowler'].dropna().unique()
    all_players = pd.concat([pd.Series(all_batters), pd.Series(all_bowlers)]).unique()
    
    # Try exact match first
    for delivery_name in all_players:
        if normalize_name_for_matching(delivery_name) == normalized_player:
            return delivery_name
    
    # Try partial match
    player_parts = normalized_player.split()
    if len(player_parts) >= 2:
        # Try matching last name
        last_name = player_parts[-1]
        last_name_matches = []
        for delivery_name in all_players:
            delivery_normalized = normalize_name_for_matching(delivery_name)
            if last_name in delivery_normalized and len(last_name) > 3:
                last_name_matches.append(delivery_name)
        
        # If only one match by last name, return it
        if len(last_name_matches) == 1:
            return last_name_matches[0]
        
        # Try matching first and last name
        first_name = player_parts[0]
        for delivery_name in all_players:
            delivery_normalized = normalize_name_for_matching(delivery_name)
            delivery_parts = delivery_normalized.split()
            if len(delivery_parts) >= 2:
                # Check if first initial matches (for names like "Andre Russell" -> "AD Russell")
                first_initial_match = first_name[0] == delivery_parts[0][0] if first_name and delivery_parts[0] else False
                last_name_match = last_name in delivery_parts[-1] or delivery_parts[-1] in last_name
                
                if (first_initial_match and last_name_match) or \
                   (first_name in delivery_parts[0] or delivery_parts[0] in first_name) and last_name_match:
                    return delivery_name
        
        # If multiple last name matches, try to find best match
        if last_name_matches:
            # Prefer matches that contain parts of the first name
            for match in last_name_matches:
                match_normalized = normalize_name_for_matching(match)
                match_parts = match_normalized.split()
                if len(match_parts) >= 2:
                    # Check if first initial matches
                    if first_name and match_parts[0] and first_name[0] == match_parts[0][0]:
                        return match
            # Return first match if no better match found
            return last_name_matches[0]
    
    # Try single word match (for players with single name)
    if len(player_parts) == 1:
        single_name = player_parts[0]
        for delivery_name in all_players:
            delivery_normalized = normalize_name_for_matching(delivery_name)
            if single_name in delivery_normalized and len(single_name) > 4:
                return delivery_name
    
    return None


def generate_stats_from_deliveries(db: Session, limit: Optional[int] = None) -> Dict:
    """Generate stats from deliveries data for players without scraped stats."""
    if not DELIVERIES_FILE.exists():
        logger.error(f"Deliveries file not found: {DELIVERIES_FILE}")
        return {"success": 0, "failed": 0, "skipped": 0}
    
    logger.info(f"Loading deliveries from {DELIVERIES_FILE}")
    try:
        df = pd.read_csv(DELIVERIES_FILE, low_memory=False)
    except Exception as e:
        logger.error(f"Error loading deliveries file: {e}")
        return {"success": 0, "failed": 0, "skipped": 0}
    
    logger.info(f"Loaded {len(df)} delivery records")
    
    # Check required columns
    required_cols = ['batter', 'bowler', 'match_id']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}")
        logger.info(f"Available columns: {list(df.columns)}")
        return {"success": 0, "failed": 0, "skipped": 0}
    
    # Get all players without scraped stats
    players_without_stats = db.query(models.Player).filter(
        models.Player.scraped_season_stats.is_(None)
    ).all()
    
    logger.info(f"Found {len(players_without_stats)} players without scraped stats")
    
    if limit:
        players_without_stats = players_without_stats[:limit]
        logger.info(f"Processing first {limit} players")
    
    success = 0
    failed = 0
    skipped = 0
    
    # Get season and team columns if available
    has_season = 'season' in df.columns
    # Check for team columns - deliveries file uses 'innings_team' for batting, need to determine bowling team
    has_innings_team = 'innings_team' in df.columns
    
    for player in players_without_stats:
        try:
            # Find player name in deliveries data
            delivery_player_name = find_player_in_deliveries(player.name, df)
            if not delivery_player_name:
                logger.debug(f"No matching player found in deliveries for {player.name}")
                skipped += 1
                continue
            
            logger.info(f"Processing {player.name} (matched to '{delivery_player_name}' in deliveries)")
            
            # Get all deliveries for this player (batting and bowling)
            player_batting = df[df['batter'] == delivery_player_name].copy()
            player_bowling = df[df['bowler'] == delivery_player_name].copy()
            
            if player_batting.empty and player_bowling.empty:
                logger.debug(f"No deliveries found for {player.name}")
                skipped += 1
                continue
            
            # Group by season and team
            season_stats_dict = {}
            
            # Process batting stats
            if not player_batting.empty:
                # Determine grouping columns - deliveries file uses 'innings_team' for the team batting
                if has_season and has_innings_team:
                    group_cols = ['season', 'innings_team']
                elif has_season:
                    group_cols = ['season']
                    player_batting['innings_team'] = 'Unknown'
                else:
                    group_cols = []
                    player_batting['season'] = 2023  # Default season
                    player_batting['innings_team'] = 'Unknown'
                
                for (season, team), group in player_batting.groupby(group_cols if group_cols else []):
                    if not group_cols:
                        season, team = 2023, 'Unknown'
                    
                    # Parse season
                    if pd.notna(season):
                        if isinstance(season, str) and '/' in season:
                            season = int(season.split('/')[0])
                        else:
                            try:
                                season = int(season)
                            except:
                                season = 2023
                    else:
                        season = 2023
                    
                    team = str(team) if pd.notna(team) else 'Unknown'
                    
                    key = (season, team)
                    if key not in season_stats_dict:
                        season_stats_dict[key] = {
                            'season': season,
                            'team': team,
                            'batting': {},
                            'bowling': {}
                        }
                    
                    # Calculate batting stats - deliveries file uses 'runs_batter'
                    runs_col = 'runs_batter' if 'runs_batter' in group.columns else 'runs_total'
                    if runs_col not in group.columns:
                        runs = 0
                    else:
                        runs = int(group[runs_col].sum())
                    
                    balls = len(group)
                    matches = group['match_id'].nunique() if 'match_id' in group.columns else 1
                    
                    # Calculate fours and sixes
                    if runs_col in group.columns:
                        fours = int((group[runs_col] == 4).sum())
                        sixes = int((group[runs_col] == 6).sum())
                        # Calculate highest score per match
                        match_runs = group.groupby('match_id')[runs_col].sum()
                        highest = int(match_runs.max()) if not match_runs.empty else 0
                    else:
                        fours = 0
                        sixes = 0
                        highest = 0
                    
                    season_stats_dict[key]['batting'] = {
                        'season': season,
                        'team': team,
                        'matches': int(matches),
                        'runs': runs,
                        'balls_faced': int(balls),
                        'highest_score': highest,
                        'fours': fours,
                        'sixes': sixes,
                        'average': float(runs / matches) if matches > 0 else 0.0,
                        'strike_rate': float(runs / balls * 100) if balls > 0 else 0.0
                    }
            
            # Process bowling stats
            if not player_bowling.empty:
                # For bowling, we need to determine the bowler's team from match context
                # The bowler's team is the opposite of the team batting (innings_team)
                # We'll process by match to find the bowler's team, then group by season and team
                
                # Get unique matches for this bowler
                unique_matches = player_bowling['match_id'].unique() if 'match_id' in player_bowling.columns else []
                
                # Process each match to determine bowler's team
                bowling_by_season_team = {}  # (season, bowler_team) -> list of deliveries
                
                for match_id in unique_matches:
                    # Get all deliveries for this match
                    match_all = df[df['match_id'] == match_id]
                    match_teams = match_all['innings_team'].unique()
                    
                    if len(match_teams) < 2:
                        continue
                    
                    # Get bowler's deliveries in this match
                    bowler_match_deliveries = player_bowling[player_bowling['match_id'] == match_id]
                    
                    # For each innings this bowler bowled in
                    for innings_team in bowler_match_deliveries['innings_team'].unique():
                        # The bowler's team is the other team in the match
                        bowler_team = [t for t in match_teams if t != innings_team]
                        if not bowler_team:
                            continue
                        bowler_team = bowler_team[0]
                        
                        # Get season
                        season = bowler_match_deliveries['season'].iloc[0] if 'season' in bowler_match_deliveries.columns else 2023
                        if pd.notna(season):
                            if isinstance(season, str) and '/' in season:
                                season = int(season.split('/')[0])
                            else:
                                try:
                                    season = int(season)
                                except:
                                    season = 2023
                        else:
                            season = 2023
                        
                        # Get deliveries for this innings
                        innings_deliveries = bowler_match_deliveries[bowler_match_deliveries['innings_team'] == innings_team]
                        
                        # Store in dictionary
                        key = (season, bowler_team)
                        if key not in bowling_by_season_team:
                            bowling_by_season_team[key] = []
                        bowling_by_season_team[key].append(innings_deliveries)
                
                # Now aggregate by season and team
                for (season, bowler_team), delivery_list in bowling_by_season_team.items():
                    # Combine all deliveries for this season/team
                    all_deliveries = pd.concat(delivery_list)
                    
                    key = (season, bowler_team)
                    if key not in season_stats_dict:
                        season_stats_dict[key] = {
                            'season': season,
                            'team': bowler_team,
                            'batting': {},
                            'bowling': {}
                        }
                    
                    # Calculate bowling stats
                    runs_col = 'runs_total' if 'runs_total' in all_deliveries.columns else 'runs_batter'
                    if runs_col in all_deliveries.columns:
                        runs = int(all_deliveries[runs_col].sum())
                    else:
                        runs = 0
                    
                    balls = len(all_deliveries)
                    matches = all_deliveries['match_id'].nunique() if 'match_id' in all_deliveries.columns else 1
                    
                    # Calculate wickets
                    wickets_col = 'wicket' if 'wicket' in all_deliveries.columns else 'is_wicket'
                    if wickets_col in all_deliveries.columns:
                        wickets = int(all_deliveries[wickets_col].sum())
                    else:
                        wickets = 0
                    
                    season_stats_dict[key]['bowling'] = {
                        'season': season,
                        'team': bowler_team,
                        'matches': int(matches),
                        'runs': runs,
                        'balls': int(balls),
                        'wickets': wickets,
                        'average': float(runs / wickets) if wickets > 0 else 0.0,
                        'economy': float(runs / (balls / 6.0)) if balls > 0 else 0.0,
                        'strike_rate': float(balls / wickets) if wickets > 0 else 0.0,
                        'best_figures': None,  # Would need more detailed data
                        'five_wickets': 0
                    }
            
            if season_stats_dict:
                # Convert to list and sort by season
                season_stats = list(season_stats_dict.values())
                season_stats.sort(key=lambda x: x['season'], reverse=True)
                
                # Store in scraped_season_stats field
                player.scraped_season_stats = {"season_stats": season_stats}
                db.commit()
                logger.info(f"  ✓ Generated stats for {player.name}: {len(season_stats)} seasons")
                success += 1
            else:
                logger.debug(f"  - No stats generated for {player.name}")
                skipped += 1
                
        except Exception as e:
            logger.error(f"  ✗ Error processing {player.name}: {e}", exc_info=True)
            db.rollback()
            failed += 1
    
    return {
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "total": len(players_without_stats)
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate player stats from deliveries data")
    parser.add_argument("--limit", type=int, help="Limit number of players to process")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        result = generate_stats_from_deliveries(db, limit=args.limit)
        logger.info("")
        logger.info("=== Stats Generation Summary ===")
        logger.info(f"Total players: {result['total']}")
        logger.info(f"Success: {result['success']}")
        logger.info(f"Skipped: {result['skipped']}")
        logger.info(f"Failed: {result['failed']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

