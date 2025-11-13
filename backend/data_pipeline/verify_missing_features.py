#!/usr/bin/env python3
"""Verify that missing features were populated correctly."""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import models
from app.db.session import SessionLocal


def verify_toss_data(db):
    """Verify toss data was populated."""
    total_matches = db.query(models.Match).count()
    matches_with_toss = db.query(models.Match).filter(
        models.Match.toss_winner_id.isnot(None),
        models.Match.toss_decision.isnot(None)
    ).count()
    
    print(f"📊 Toss Data:")
    print(f"   Matches with toss data: {matches_with_toss}/{total_matches} ({matches_with_toss/total_matches*100:.1f}%)")
    return matches_with_toss, total_matches


def verify_utc_times(db):
    """Verify UTC times were populated."""
    total_matches = db.query(models.Match).count()
    matches_with_utc = db.query(models.Match).filter(
        models.Match.date_utc.isnot(None)
    ).count()
    
    print(f"🕐 UTC Times:")
    print(f"   Matches with UTC times: {matches_with_utc}/{total_matches} ({matches_with_utc/total_matches*100:.1f}%)")
    return matches_with_utc, total_matches


def verify_match_stages(db):
    """Verify match stages were populated."""
    total_matches = db.query(models.Match).count()
    matches_with_stage = db.query(models.Match).filter(
        models.Match.match_stage.isnot(None)
    ).count()
    
    # Count by stage
    from sqlalchemy import func
    stage_results = db.query(models.Match.match_stage, func.count(models.Match.id)).group_by(models.Match.match_stage).all()
    stage_counts = {}
    for stage, count in stage_results:
        if stage:
            stage_counts[stage] = count
    
    print(f"🎯 Match Stages:")
    print(f"   Matches with stage info: {matches_with_stage}/{total_matches} ({matches_with_stage/total_matches*100:.1f}%)")
    if stage_counts:
        print(f"   Stage breakdown:")
        for stage, count in sorted(stage_counts.items()):
            print(f"      {stage}: {count}")
    return matches_with_stage, total_matches


def verify_player_form(db):
    """Verify player form can be calculated."""
    from data_pipeline.calculate_player_form import calculate_player_form
    
    players = db.query(models.Player).limit(10).all()
    players_with_form = 0
    
    for player in players:
        form = calculate_player_form(db, player.id, window=5)
        if form["matches_played"] > 0:
            players_with_form += 1
    
    total_players = db.query(models.Player).count()
    print(f"👤 Player Form:")
    print(f"   Sample: {players_with_form}/10 players have form data")
    print(f"   (Total players: {total_players})")
    return players_with_form, 10


def verify_venue_stats(db):
    """Verify venue statistics."""
    from data_pipeline.calculate_venue_stats import calculate_toss_bias
    
    venues = db.query(models.Venue).all()
    venues_with_stats = 0
    
    print(f"🏟️  Venue Statistics:")
    for venue in venues:
        matches = db.query(models.Match).filter(models.Match.venue_id == venue.id).count()
        if matches > 0:
            venues_with_stats += 1
            toss_bias = calculate_toss_bias(db, venue.id)
            if toss_bias["bat_first_total"] > 0 or toss_bias["chase_total"] > 0:
                print(f"   {venue.name}: {matches} matches, "
                      f"Bat first: {toss_bias['bat_first_win_pct']:.1f}%, "
                      f"Chase: {toss_bias['chase_win_pct']:.1f}%")
            else:
                print(f"   {venue.name}: {matches} matches (no toss data)")
    
    return venues_with_stats, len(venues)


def main():
    """Main verification function."""
    print("🔍 Verifying missing features were populated correctly")
    print("")
    
    db = SessionLocal()
    try:
        # Verify each feature
        verify_toss_data(db)
        print("")
        
        verify_utc_times(db)
        print("")
        
        verify_match_stages(db)
        print("")
        
        verify_player_form(db)
        print("")
        
        verify_venue_stats(db)
        print("")
        
        print("✅ Verification complete!")
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

