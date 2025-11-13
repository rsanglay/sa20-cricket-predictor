"""Seed the database with teams, venues, players, and matches from processed data."""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

# Add app directory to path for imports - in Docker, app is at /app
if Path("/app/app").exists():
    # Docker environment
    sys.path.insert(0, "/app")
else:
    # Local environment
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))

from app.db.session import SessionLocal
from app.db import models

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# SA20 Teams
SA20_TEAMS = [
    {"name": "MI Cape Town", "short_name": "MICT", "home_venue": "Newlands"},
    {"name": "Paarl Royals", "short_name": "PR", "home_venue": "Boland Park"},
    {"name": "Pretoria Capitals", "short_name": "PC", "home_venue": "Centurion"},
    {"name": "Durban's Super Giants", "short_name": "DSG", "home_venue": "Kingsmead"},
    {"name": "Joburg Super Kings", "short_name": "JSK", "home_venue": "Wanderers"},
    {"name": "Sunrisers Eastern Cape", "short_name": "SEC", "home_venue": "St George's Park"},
]

# SA20 Venues
SA20_VENUES = [
    {"name": "Newlands", "city": "Cape Town", "country": "South Africa", "capacity": 25000, "avg_first_innings_score": 165.0},
    {"name": "Boland Park", "city": "Paarl", "country": "South Africa", "capacity": 10000, "avg_first_innings_score": 160.0},
    {"name": "Centurion", "city": "Pretoria", "country": "South Africa", "capacity": 20000, "avg_first_innings_score": 170.0},
    {"name": "Kingsmead", "city": "Durban", "country": "South Africa", "capacity": 25000, "avg_first_innings_score": 155.0},
    {"name": "Wanderers", "city": "Johannesburg", "country": "South Africa", "capacity": 34000, "avg_first_innings_score": 175.0},
    {"name": "St George's Park", "city": "Gqeberha", "country": "South Africa", "capacity": 19000, "avg_first_innings_score": 160.0},
]


def seed_teams(db: Session) -> dict[int, models.Team]:
    """Seed teams and return mapping of team name to team object."""
    print("Seeding teams...")
    team_map = {}
    
    for team_data in SA20_TEAMS:
        # Check if team already exists
        existing = db.query(models.Team).filter(models.Team.name == team_data["name"]).first()
        if existing:
            team_map[team_data["name"]] = existing
            continue
            
        team = models.Team(
            name=team_data["name"],
            short_name=team_data["short_name"],
            home_venue=team_data["home_venue"],
            founded_year=2023,
        )
        db.add(team)
        db.flush()
        team_map[team_data["name"]] = team
    
    db.commit()
    print(f"  ✓ Seeded {len(team_map)} teams")
    return team_map


def seed_venues(db: Session) -> dict[str, models.Venue]:
    """Seed venues and return mapping of venue name to venue object."""
    print("Seeding venues...")
    venue_map = {}
    
    for venue_data in SA20_VENUES:
        # Check if venue already exists
        existing = db.query(models.Venue).filter(models.Venue.name == venue_data["name"]).first()
        if existing:
            venue_map[venue_data["name"]] = existing
            continue
            
        venue = models.Venue(
            name=venue_data["name"],
            city=venue_data["city"],
            country=venue_data["country"],
            capacity=venue_data["capacity"],
            avg_first_innings_score=venue_data["avg_first_innings_score"],
        )
        db.add(venue)
        db.flush()
        venue_map[venue_data["name"]] = venue
    
    db.commit()
    print(f"  ✓ Seeded {len(venue_map)} venues")
    return venue_map


def seed_players(db: Session, team_map: dict) -> None:
    """Seed players from processed rosters."""
    print("Seeding players...")
    
    rosters_path = PROCESSED_DIR / "sa20_team_rosters.csv"
    if not rosters_path.exists():
        print(f"  ✗ Roster file not found: {rosters_path}")
        return
    
    rosters_df = pd.read_csv(rosters_path)
    
    # Get unique players
    unique_players = rosters_df[["player_name", "team_name"]].drop_duplicates()
    
    # Map player roles from roster data if available
    role_mapping = {
        "batsman": models.PlayerRole.BATSMAN,
        "bowler": models.PlayerRole.BOWLER,
        "all-rounder": models.PlayerRole.ALL_ROUNDER,
        "all_rounder": models.PlayerRole.ALL_ROUNDER,
        "wicket-keeper": models.PlayerRole.WICKET_KEEPER,
        "wicket_keeper": models.PlayerRole.WICKET_KEEPER,
        "keeper": models.PlayerRole.WICKET_KEEPER,
    }
    
    players_added = 0
    for _, row in unique_players.iterrows():
        player_name = row["player_name"]
        team_name = row["team_name"]
        
        if team_name not in team_map:
            continue
            
        team = team_map[team_name]
        
        # Check if player already exists
        existing = db.query(models.Player).filter(
            models.Player.name == player_name,
            models.Player.team_id == team.id
        ).first()
        
        if existing:
            continue
        
        # Try to get role from roster data if available
        role = models.PlayerRole.BATSMAN  # Default fallback
        if "role" in rosters_df.columns:
            role_str = str(row.get("role", "")).lower().strip() if pd.notna(row.get("role")) else ""
            if role_str:
                role = role_mapping.get(role_str, models.PlayerRole.BATSMAN)
        
        # Default role and styles
        player = models.Player(
            name=player_name,
            role=role,
            batting_style=models.BattingStyle.RIGHT_HAND,  # Default
            team_id=team.id,
            country="South Africa",
            age=25,  # Default
        )
        db.add(player)
        players_added += 1
    
    db.commit()
    print(f"  ✓ Seeded {players_added} players")
    print(f"  ⚠ Note: Run 'python -m data_pipeline.infer_player_roles' to update roles from performance data")
    return players_added


def seed_matches(db: Session, team_map: dict, venue_map: dict) -> None:
    """Seed SA20 2026 fixture schedule: group stage + playoffs + final."""
    print("Seeding matches...")
    
    teams = list(team_map.values())
    matches_added = 0
    
    # SA20 2026 Schedule: January 10 - February 8, 2026
    # Group Stage: Jan 10 - Feb 2 (30 matches: each team plays each other twice)
    # Playoffs: Feb 4-8
    
    # Clear existing 2026 matches
    db.query(models.Match).filter(models.Match.season == 2026).delete()
    db.commit()
    
    # Group Stage Matches (Jan 10 - Feb 2)
    match_date = datetime(2026, 1, 10)
    match_number = 1
    
    # Map city to venue name
    city_to_venue = {
        "Cape Town": "Newlands",
        "Johannesburg": "Wanderers",
        "Paarl": "Boland Park",
        "Pretoria": "Centurion",
        "Durban": "Kingsmead",
        "Gqeberha": "St George's Park",
    }
    
    # First round: each team plays each other once (15 matches)
    for i, home_team in enumerate(teams):
        for away_team in teams[i+1:]:
            # Get venue from team's city
            venue_name = None
            if hasattr(home_team, 'city') and home_team.city:
                venue_name = city_to_venue.get(home_team.city)
            # Fallback: try to find venue by team name pattern
            if not venue_name:
                # Try to match team name to venue
                team_venue_map = {
                    "MI Cape Town": "Newlands",
                    "Paarl Royals": "Boland Park",
                    "Pretoria Capitals": "Centurion",
                    "Durban's Super Giants": "Kingsmead",
                    "Joburg Super Kings": "Wanderers",
                    "Sunrisers Eastern Cape": "St George's Park",
                }
                venue_name = team_venue_map.get(home_team.name)
            
            if not venue_name or venue_name not in venue_map:
                # Use first available venue as fallback
                venue = list(venue_map.values())[0] if venue_map else None
            else:
                venue = venue_map[venue_name]
            
            if not venue:
                continue
            
            match = models.Match(
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                venue_id=venue.id,
                match_date=match_date,
                season=2026,
                match_no=match_number,  # Use match_no instead of match_number
            )
            db.add(match)
            matches_added += 1
            match_number += 1
            match_date = datetime.fromordinal(match_date.toordinal() + 1)
    
    # Second round: reverse fixtures (15 matches)
    for i, away_team in enumerate(teams):
        for home_team in teams[i+1:]:
            # Get venue from team's city
            venue_name = None
            if hasattr(home_team, 'city') and home_team.city:
                venue_name = city_to_venue.get(home_team.city)
            # Fallback: try to find venue by team name pattern
            if not venue_name:
                team_venue_map = {
                    "MI Cape Town": "Newlands",
                    "Paarl Royals": "Boland Park",
                    "Pretoria Capitals": "Centurion",
                    "Durban's Super Giants": "Kingsmead",
                    "Joburg Super Kings": "Wanderers",
                    "Sunrisers Eastern Cape": "St George's Park",
                }
                venue_name = team_venue_map.get(home_team.name)
            
            if not venue_name or venue_name not in venue_map:
                venue = list(venue_map.values())[0] if venue_map else None
            else:
                venue = venue_map[venue_name]
            
            if not venue:
                continue
            
            match = models.Match(
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                venue_id=venue.id,
                match_date=match_date,
                season=2026,
                match_no=match_number,  # Use match_no instead of match_number
            )
            db.add(match)
            matches_added += 1
            match_number += 1
            match_date = datetime.fromordinal(match_date.toordinal() + 1)
    
    # Playoffs (Feb 4-8)
    # Note: We'll use placeholder teams for playoffs - they'll be determined by standings
    # Qualifier 1: 1st vs 2nd (Feb 4)
    # Eliminator: 3rd vs 4th (Feb 5)
    # Qualifier 2: Loser Q1 vs Winner Eliminator (Feb 7)
    # Final: Winner Q1 vs Winner Q2 (Feb 8)
    
    # Use a neutral venue for playoffs (Wanderers - largest capacity)
    playoff_venue = venue_map.get("Wanderers", list(venue_map.values())[0])
    
    # Placeholder playoff matches - will be updated based on standings
    playoff_matches = [
        {"type": "Qualifier 1", "date": datetime(2026, 2, 4), "match_num": 31},
        {"type": "Eliminator", "date": datetime(2026, 2, 5), "match_num": 32},
        {"type": "Qualifier 2", "date": datetime(2026, 2, 7), "match_num": 33},
        {"type": "Final", "date": datetime(2026, 2, 8), "match_num": 34},
    ]
    
    # Create playoff matches with placeholder teams (will be determined by simulation)
    for playoff in playoff_matches:
        # Use first two teams as placeholders - actual teams determined by standings
        match = models.Match(
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            venue_id=playoff_venue.id,
            match_date=playoff["date"],
            season=2026,
            match_no=playoff["match_num"],  # Use match_no instead of match_number
        )
        db.add(match)
        matches_added += 1
    
    db.commit()
    print(f"  ✓ Seeded {matches_added} matches (30 group stage + 4 playoffs)")
    return matches_added


def main():
    """Main seeding function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed SA20 database")
    parser.add_argument(
        "--use-scraper",
        action="store_true",
        help="Try to scrape fixtures from SA20 official website first"
    )
    parser.add_argument(
        "--season",
        type=int,
        default=2026,
        help="Season year (default: 2026)"
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("Seeding SA20 Database")
    print("=" * 60)
    
    db: Session = SessionLocal()
    try:
        team_map = seed_teams(db)
        venue_map = seed_venues(db)
        seed_players(db, team_map)
        
        # Try to scrape fixtures from website if requested
        if args.use_scraper:
            try:
                from data_pipeline.scrape_sa20_fixtures import seed_fixtures_from_scraper
                matches_added = seed_fixtures_from_scraper(db, season=args.season)
                if matches_added > 0:
                    print(f"\n✓ Successfully scraped and seeded {matches_added} fixtures from SA20 website")
                else:
                    print("\n⚠ No fixtures found from scraper, using generated schedule...")
                    seed_matches(db, team_map, venue_map)
            except Exception as e:
                print(f"\n⚠ Error scraping fixtures: {e}")
                print("Falling back to generated schedule...")
                seed_matches(db, team_map, venue_map)
        else:
            seed_matches(db, team_map, venue_map)
        
        print("\n" + "=" * 60)
        print("✓ Database seeding completed successfully!")
        print("=" * 60)
    except Exception as e:
        db.rollback()
        print(f"\n✗ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

