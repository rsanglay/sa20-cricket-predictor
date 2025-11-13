#!/usr/bin/env python3
"""Setup script to populate all missing features."""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """Main setup function."""
    print("🚀 Setting up missing features for SA20 Cricket Predictor")
    print("")
    
    # Step 1: Run database migration
    print("📦 Step 1: Running database migration...")
    try:
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("✅ Migration complete")
    except Exception as e:
        print(f"⚠️  Warning: Could not run migration: {e}")
        print("   Please run manually: alembic upgrade head")
    print("")
    
    # Step 2: Populate match data
    print("📊 Step 2: Populating match data (toss, UTC times, match stages)...")
    try:
        from data_pipeline.populate_match_data import (
            extract_toss_from_cricsheet,
            populate_utc_times,
            populate_match_stages,
        )
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        try:
            # Extract toss data
            toss_stats = extract_toss_from_cricsheet(db, overwrite=False)
            print(f"   Toss: {toss_stats['toss_updated']} matches updated")
            
            # Populate UTC times
            utc_stats = populate_utc_times(db, overwrite=False)
            print(f"   UTC: {utc_stats['utc_updated']} matches updated")
            
            # Populate match stages
            stage_stats = populate_match_stages(db, overwrite=False)
            print(f"   Stage: {stage_stats['stage_updated']} matches updated")
            
            print("✅ Match data populated")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  Warning: Could not populate match data: {e}")
        print("   Please run manually: python -m data_pipeline.populate_match_data --all")
    print("")
    
    # Step 3: Calculate player form trends
    print("👤 Step 3: Calculating player form trends...")
    try:
        from data_pipeline.calculate_player_form import calculate_all_player_forms
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        try:
            form_stats = calculate_all_player_forms(db, window=5)
            print(f"   Form: {form_stats['players_with_form']} players with form data")
            print("✅ Player form trends calculated")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  Warning: Could not calculate player form trends: {e}")
        print("   Please run manually: python -m data_pipeline.calculate_player_form")
    print("")
    
    # Step 4: Calculate venue statistics
    print("🏟️  Step 4: Calculating venue statistics (including toss bias)...")
    try:
        from data_pipeline.calculate_venue_stats import calculate_venue_stats_from_matches
        from app.db.session import SessionLocal
        
        db = SessionLocal()
        try:
            calculate_venue_stats_from_matches(db)
            print("✅ Venue statistics calculated")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  Warning: Could not calculate venue statistics: {e}")
        print("   Please run manually: python -m data_pipeline.calculate_venue_stats")
    print("")
    
    print("✅ Setup complete!")
    print("")
    print("📝 Next steps:")
    print("   1. Verify data was populated correctly")
    print("   2. Check the database for updated records")
    print("   3. Update ML models to use new features")
    print("   4. Test predictions with new data")
    print("")


if __name__ == "__main__":
    main()

