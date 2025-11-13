"""Scraper for ESPN Cricinfo data."""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class CricinfoScraper:
    base_url = "https://www.espncricinfo.com"

    def __init__(self, rate_limit_seconds: float = 2.0) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36"
                )
            }
        )
        self.rate_limit_seconds = rate_limit_seconds

    def scrape_match(self, match_id: str) -> Optional[Dict]:
        url = f"{self.base_url}/series/sa20/match/{match_id}"
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            data = {
                "match_id": match_id,
                "teams": self._extract_teams(soup),
                "venue": self._extract_venue(soup),
                "result": self._extract_result(soup),
                "scorecard": self._extract_scorecard(soup),
            }
            time.sleep(self.rate_limit_seconds)
            return data
        except requests.RequestException as exc:
            logger.error("Failed to scrape match %s: %s", match_id, exc)
            return None

    def scrape_player_profile(self, player_id: str) -> Optional[Dict]:
        url = f"{self.base_url}/player/{player_id}"
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            data = {
                "player_id": player_id,
                "name": self._text_or_none(soup.select_one("h1")),
                "country": self._extract_meta_value(soup, "country"),
                "role": self._extract_meta_value(soup, "playing_role"),
            }
            time.sleep(self.rate_limit_seconds)
            return data
        except requests.RequestException as exc:
            logger.error("Failed to scrape player %s: %s", player_id, exc)
            return None

    def _extract_teams(self, soup: BeautifulSoup) -> List[str]:
        teams = [tag.get_text(strip=True) for tag in soup.select(".ci-team-score div.name")]
        return teams

    def _extract_venue(self, soup: BeautifulSoup) -> Optional[str]:
        venue_tag = soup.select_one(".match-info-strip .text a")
        return venue_tag.get_text(strip=True) if venue_tag else None

    def _extract_result(self, soup: BeautifulSoup) -> Dict:
        result_tag = soup.select_one(".match-result")
        return {"summary": result_tag.get_text(strip=True) if result_tag else ""}

    def _extract_scorecard(self, soup: BeautifulSoup) -> Dict:
        return {"raw_html": str(soup.select_one("#main-container"))}

    def _extract_meta_value(self, soup: BeautifulSoup, key: str) -> Optional[str]:
        meta = soup.select_one(f".player-card .player-card-padding [data-field='{key}']")
        return meta.get_text(strip=True) if meta else None

    def _text_or_none(self, element) -> Optional[str]:
        return element.get_text(strip=True) if element else None
