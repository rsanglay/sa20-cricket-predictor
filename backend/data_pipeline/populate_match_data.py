"""Populate missing match data: toss results, UTC times, match stage info."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import models
from app.db.session import SessionLocal
from data_pipeline.scrapers.cricsheet_api import CricsheetAPI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "cricsheet"


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    return name.strip().lower().replace("'", "").replace(" ", "_")


def get_team_by_name(db: Session, name: str) -> Optional[models.Team]:
    """Get team from database by name (with fuzzy matching)."""
    if not name:
        return None
    
    # Try exact match first
    team = db.query(models.Team).filter(models.Team.name == name).first()
    if team:
        return team
    
    # Try short name
    team = db.query(models.Team).filter(models.Team.short_name == name).first()
    if team:
        return team
    
    # Try normalized match
    normalized = normalize_team_name(name)
    all_teams = db.query(models.Team).all()
    for t in all_teams:
        if normalize_team_name(t.name) == normalized or normalize_team_name(t.short_name or "") == normalized:
            return t
    
    return None


def determine_match_stage(match_number: Optional[int], season: int) -> Optional[str]:
    """Determine match stage from match number and season."""
    if match_number is None:
        return None
    
    # SA20 typically has:
    # - Group stage: matches 1-30 (approximately)
    # - Qualifier 1: match 31
    # - Eliminator: match 32
    # - Qualifier 2: match 33
    # - Final: match 34
    
    # This is a simplified heuristic - adjust based on actual SA20 structure
    if match_number >= 30:
        if match_number == 34 or match_number == 35:
            return "final"
        elif match_number == 33 or match_number == 34:
            return "qualifier_2"
        elif match_number == 32 or match_number == 33:
            return "eliminator"
        elif match_number == 31 or match_number == 32:
            return "qualifier_1"
    
    return "group"


def convert_to_utc(match_date: datetime, timezone: str = "Africa/Johannesburg") -> Optional[datetime]:
    """Convert match date to UTC."""
    from datetime import timedelta, timezone as dt_tz
    
    try:
        from dateutil import tz
        from dateutil.tz import gettz
        
        # Assume SA20 matches are in South Africa timezone (SAST - UTC+2)
        sa_timezone = gettz(timezone)
        if sa_timezone is None:
            # Fallback: use UTC+2 offset
            sa_timezone = dt_tz(timedelta(hours=2))
        
        # If match_date is naive, assume it's in SA timezone
        if match_date.tzinfo is None:
            # Create a timezone-aware datetime in SA timezone
            # Assume match is at 18:00 SAST (typical T20 match time) if no time info
            if match_date.hour == 0 and match_date.minute == 0:
                # If only date is provided, set to 18:00 SAST
                match_date = match_date.replace(hour=18, minute=0)
            
            # Make timezone-aware
            if isinstance(sa_timezone, dt_tz):
                local_dt = match_date.replace(tzinfo=sa_timezone)
            else:
                local_dt = match_date.replace(tzinfo=sa_timezone)
        else:
            local_dt = match_date.astimezone(sa_timezone)
        
        # Convert to UTC
        utc_timezone = tz.UTC
        utc_dt = local_dt.astimezone(utc_timezone)
        return utc_dt
    except (ImportError, AttributeError):
        # If dateutil is not available, use simple offset (SAST is UTC+2)
        if match_date.tzinfo is None:
            # Assume match is at 18:00 SAST (typical T20 match time)
            # Set time if not set
            if match_date.hour == 0 and match_date.minute == 0:
                match_date = match_date.replace(hour=18, minute=0)
            # Convert to UTC by subtracting 2 hours
            sa_tz = dt_tz(timedelta(hours=2))
            local_dt = match_date.replace(tzinfo=sa_tz)
            utc_dt = local_dt.astimezone(dt_tz.utc)
            return utc_dt
    except Exception as e:
        # Fallback: simple offset
        try:
            if match_date.tzinfo is None:
                if match_date.hour == 0 and match_date.minute == 0:
                    match_date = match_date.replace(hour=18, minute=0)
                sa_tz = dt_tz(timedelta(hours=2))
                local_dt = match_date.replace(tzinfo=sa_tz)
                utc_dt = local_dt.astimezone(dt_tz.utc)
                return utc_dt
        except Exception as inner_e:
            print(f"Error in fallback UTC conversion: {inner_e}")
            return None
    return None


def extract_toss_from_cricsheet(db: Session, overwrite: bool = False) -> Dict[str, int]:
    """Extract toss information from Cricsheet JSON files and populate database."""
    print("Extracting toss information from Cricsheet data...")
    
    stats = {
        "matches_processed": 0,
        "toss_updated": 0,
        "toss_already_exists": 0,
        "toss_not_found": 0,
        "team_not_found": 0,
    }
    
    # Find all SA20 JSON files
    sa20_dir = RAW_DIR / "sa20"
    if not sa20_dir.exists():
        print(f"SA20 data directory not found: {sa20_dir}")
        print("Please run: python -m backend.data_pipeline.ingest_cricsheet --competitions sa20")
        return stats
    
    # Get all JSON files
    json_files = list(sa20_dir.rglob("*.json"))
    print(f"Found {len(json_files)} JSON files to process")
    
    # Process each JSON file and find matching match in database
    for json_file in json_files:
        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            info = data.get("info", {})
            if not info:
                continue
            
            # Extract match information
            season = info.get("season")
            match_number = info.get("event", {}).get("match_number")
            dates = info.get("dates", [])
            teams = info.get("teams", [])
            
            if not dates or not teams or len(teams) < 2:
                stats["matches_processed"] += 1
                continue
            
            # Parse match date
            match_date = None
            try:
                match_date = datetime.fromisoformat(dates[0]).date()
            except (ValueError, IndexError):
                stats["matches_processed"] += 1
                continue
            
            # Find matching match in database by date and teams
            team1 = get_team_by_name(db, teams[0])
            team2 = get_team_by_name(db, teams[1])
            
            if not team1 or not team2:
                stats["team_not_found"] += 1
                stats["matches_processed"] += 1
                continue
            
            # Find match by date and teams
            match = db.query(models.Match).filter(
                and_(
                    models.Match.match_date == match_date,
                    or_(
                        and_(
                            models.Match.home_team_id == team1.id,
                            models.Match.away_team_id == team2.id
                        ),
                        and_(
                            models.Match.home_team_id == team2.id,
                            models.Match.away_team_id == team1.id
                        )
                    )
                )
            ).first()
            
            # Also try by season and match_number if available
            if not match and season and match_number:
                match = db.query(models.Match).filter(
                    and_(
                        models.Match.season == int(str(season).split('/')[0]) if season else True,
                        models.Match.match_number == match_number
                    )
                ).first()
            
            if not match:
                stats["matches_processed"] += 1
                continue
            
            # Extract toss information
            toss = info.get("toss", {})
            if not toss:
                stats["toss_not_found"] += 1
                stats["matches_processed"] += 1
                continue
            
            toss_winner_name = toss.get("winner")
            toss_decision = toss.get("decision")  # 'bat' or 'field'
            
            if not toss_winner_name or not toss_decision:
                stats["toss_not_found"] += 1
                stats["matches_processed"] += 1
                continue
            
            # Check if toss data already exists
            if match.toss_winner_id and match.toss_decision and not overwrite:
                stats["toss_already_exists"] += 1
                stats["matches_processed"] += 1
                continue
            
            # Get toss winner team
            toss_winner_team = get_team_by_name(db, toss_winner_name)
            if not toss_winner_team:
                stats["team_not_found"] += 1
                print(f"  Team not found: {toss_winner_name}")
                stats["matches_processed"] += 1
                continue
            
            # Update match with toss data
            match.toss_winner_id = toss_winner_team.id
            match.toss_decision = toss_decision
            stats["toss_updated"] += 1
            stats["matches_processed"] += 1
            
            if stats["toss_updated"] % 10 == 0:
                db.commit()
                print(f"  Updated {stats['toss_updated']} matches...")
        
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue
    
    db.commit()
    print(f"\nToss extraction complete:")
    print(f"  Matches processed: {stats['matches_processed']}")
    print(f"  Toss updated: {stats['toss_updated']}")
    print(f"  Toss already exists: {stats['toss_already_exists']}")
    print(f"  Toss not found: {stats['toss_not_found']}")
    print(f"  Team not found: {stats['team_not_found']}")
    
    return stats


def populate_utc_times(db: Session, overwrite: bool = False) -> Dict[str, int]:
    """Populate UTC times for all matches."""
    print("Populating UTC times for matches...")
    
    stats = {
        "matches_processed": 0,
        "utc_updated": 0,
        "utc_already_exists": 0,
        "utc_conversion_failed": 0,
    }
    
    # Get all matches that need UTC times
    matches = db.query(models.Match).filter(
        models.Match.date_utc.is_(None) if not overwrite else True
    ).all()
    
    print(f"Found {len(matches)} matches that need UTC times")
    
    for match in matches:
        try:
            # Check if UTC time already exists
            if match.date_utc and not overwrite:
                stats["utc_already_exists"] += 1
                continue
            
            # Convert match_date to UTC
            if match.match_date:
                utc_time = convert_to_utc(match.match_date)
                if utc_time:
                    match.date_utc = utc_time
                    stats["utc_updated"] += 1
                else:
                    stats["utc_conversion_failed"] += 1
            else:
                stats["utc_conversion_failed"] += 1
            
            stats["matches_processed"] += 1
            
            if stats["utc_updated"] % 50 == 0:
                db.commit()
                print(f"  Updated {stats['utc_updated']} matches...")
        
        except Exception as e:
            print(f"Error processing match {match.id}: {e}")
            stats["utc_conversion_failed"] += 1
            continue
    
    db.commit()
    print(f"\nUTC time population complete:")
    print(f"  Matches processed: {stats['matches_processed']}")
    print(f"  UTC updated: {stats['utc_updated']}")
    print(f"  UTC already exists: {stats['utc_already_exists']}")
    print(f"  UTC conversion failed: {stats['utc_conversion_failed']}")
    
    return stats


def populate_match_stages(db: Session, overwrite: bool = False) -> Dict[str, int]:
    """Populate match stage info for all matches."""
    print("Populating match stage info...")
    
    stats = {
        "matches_processed": 0,
        "stage_updated": 0,
        "stage_already_exists": 0,
        "stage_could_not_determine": 0,
    }
    
    # Get all matches that need stage info
    matches = db.query(models.Match).filter(
        models.Match.match_stage.is_(None) if not overwrite else True
    ).all()
    
    print(f"Found {len(matches)} matches that need stage info")
    
    for match in matches:
        try:
            # Check if stage already exists
            if match.match_stage and not overwrite:
                stats["stage_already_exists"] += 1
                continue
            
            # Determine match stage from match_number
            stage = determine_match_stage(match.match_number, match.season)
            if stage:
                match.match_stage = stage
                stats["stage_updated"] += 1
            else:
                stats["stage_could_not_determine"] += 1
                # Default to 'group' if we can't determine
                match.match_stage = "group"
                stats["stage_updated"] += 1
            
            stats["matches_processed"] += 1
            
            if stats["stage_updated"] % 50 == 0:
                db.commit()
                print(f"  Updated {stats['stage_updated']} matches...")
        
        except Exception as e:
            print(f"Error processing match {match.id}: {e}")
            stats["stage_could_not_determine"] += 1
            continue
    
    db.commit()
    print(f"\nMatch stage population complete:")
    print(f"  Matches processed: {stats['matches_processed']}")
    print(f"  Stage updated: {stats['stage_updated']}")
    print(f"  Stage already exists: {stats['stage_already_exists']}")
    print(f"  Stage could not determine: {stats['stage_could_not_determine']}")
    
    return stats


def main() -> None:
    """Main function to populate all match data."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate missing match data")
    parser.add_argument("--toss", action="store_true", help="Extract and populate toss data")
    parser.add_argument("--utc", action="store_true", help="Populate UTC times")
    parser.add_argument("--stage", action="store_true", help="Populate match stage info")
    parser.add_argument("--all", action="store_true", help="Populate all data")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing data")
    
    args = parser.parse_args()
    
    if not any([args.toss, args.utc, args.stage, args.all]):
        parser.print_help()
        return
    
    db = SessionLocal()
    try:
        if args.all or args.toss:
            extract_toss_from_cricsheet(db, overwrite=args.overwrite)
        
        if args.all or args.utc:
            populate_utc_times(db, overwrite=args.overwrite)
        
        if args.all or args.stage:
            populate_match_stages(db, overwrite=args.overwrite)
    
    except Exception as e:
        print(f"Error: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()

