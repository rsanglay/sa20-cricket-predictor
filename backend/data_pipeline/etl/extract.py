"""Data extraction logic for the SA20 platform."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.data_pipeline.scrapers.cricinfo_scraper import CricinfoScraper
from backend.data_pipeline.scrapers.cricsheet_api import CricsheetAPI


@dataclass
class DataExtractor:
    cricinfo_scraper: CricinfoScraper = CricinfoScraper()
    cricsheet_api: CricsheetAPI = CricsheetAPI()

    def extract_historical_matches(self, match_ids: list[str]) -> pd.DataFrame:
        rows = []
        for match_id in match_ids:
            data = self.cricinfo_scraper.scrape_match(match_id)
            if data:
                rows.append(data)
        return pd.DataFrame(rows)

    def extract_player_data(self, player_ids: list[str]) -> pd.DataFrame:
        rows = []
        for player_id in player_ids:
            data = self.cricinfo_scraper.scrape_player_profile(player_id)
            if data:
                rows.append(data)
        return pd.DataFrame(rows)

    def extract_venue_data(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"id": 1, "name": "Newlands", "city": "Cape Town", "country": "South Africa"},
                {"id": 2, "name": "Wanderers", "city": "Johannesburg", "country": "South Africa"},
            ]
        )
