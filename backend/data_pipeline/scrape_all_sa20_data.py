"""Master script to scrape all SA20 data from official website."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_pipeline.scrape_sa20_teams_players import update_teams_and_players
from data_pipeline.scrape_sa20_stats import export_stats_to_csv, update_player_stats_from_scraper
from data_pipeline.scrape_sa20_fixtures import seed_fixtures_from_scraper
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Main function to scrape all SA20 data."""
    parser = argparse.ArgumentParser(
        description="Scrape all SA20 data from official website (teams, players, stats, fixtures)"
    )
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    parser.add_argument("--skip-teams", action="store_true", help="Skip scraping teams and players")
    parser.add_argument("--skip-stats", action="store_true", help="Skip scraping statistics")
    parser.add_argument("--skip-fixtures", action="store_true", help="Skip scraping fixtures")
    parser.add_argument("--export-stats-csv", action="store_true", help="Export stats to CSV files")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("=" * 70)
        print("SA20 Official Website Data Scraper")
        print("=" * 70)
        print(f"Season: {args.season}")
        print()

        # 1. Scrape teams and players
        if not args.skip_teams:
            print("\n[1/3] Scraping teams and players...")
            print("-" * 70)
            try:
                teams_updated, players_added = update_teams_and_players(db, update_roles_from_stats=True)
                print(f"✓ Updated {teams_updated} teams and {players_added} players")
            except Exception as e:
                logger.error(f"Error scraping teams/players: {e}")
                print(f"✗ Failed to scrape teams/players: {e}")
        else:
            print("\n[1/3] Skipping teams and players (--skip-teams)")

        # 2. Scrape player statistics
        if not args.skip_stats:
            print("\n[2/3] Scraping player statistics...")
            print("-" * 70)
            try:
                from data_pipeline.scrapers.sa20_stats_scraper import SA20StatsScraper
                scraper = SA20StatsScraper()
                
                # Scrape for current season and all-time
                all_stats = scraper.scrape_all_player_stats(season=args.season)
                
                if args.export_stats_csv:
                    output_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "sa20_stats"
                    export_stats_to_csv(all_stats, output_dir)
                    print(f"✓ Exported stats to CSV files")
                
                players_updated, stats_added = update_player_stats_from_scraper(db, season=args.season)
                print(f"✓ Updated stats for {players_updated} players")
                
                # Also scrape all-time stats
                alltime_stats = scraper.scrape_all_player_stats(season=None)
                if args.export_stats_csv:
                    alltime_stats["season"] = None
                    export_stats_to_csv(alltime_stats, output_dir)
                    print(f"✓ Exported all-time stats to CSV files")
                    
            except Exception as e:
                logger.error(f"Error scraping stats: {e}")
                print(f"✗ Failed to scrape stats: {e}")
        else:
            print("\n[2/3] Skipping statistics (--skip-stats)")

        # 3. Scrape fixtures
        if not args.skip_fixtures:
            print("\n[3/3] Scraping fixtures...")
            print("-" * 70)
            try:
                matches_added = seed_fixtures_from_scraper(db, season=args.season)
                if matches_added > 0:
                    print(f"✓ Scraped and seeded {matches_added} fixtures from SA20 website")
                else:
                    print("⚠ No fixtures found from scraper, using generated schedule")
            except Exception as e:
                logger.error(f"Error scraping fixtures: {e}")
                print(f"✗ Failed to scrape fixtures: {e}")
        else:
            print("\n[3/3] Skipping fixtures (--skip-fixtures)")

        print("\n" + "=" * 70)
        print("✓ Data scraping completed!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Review the scraped data in the database")
        print("  2. Run data aggregation: python data_pipeline/build_aggregates.py")
        print("  3. Train ML models: python app/ml/training/train_match_model.py")
        print("  4. Train player models: python app/ml/training/train_player_models.py")

    except Exception as e:
        db.rollback()
        logger.error(f"Error in scraping process: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

