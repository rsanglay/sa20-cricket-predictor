"""Scraper for SA20 official website statistics page."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SA20StatsScraper:
    """Scraper for SA20 official website stats page."""

    base_url = "https://www.sa20.co.za"
    stats_url = "https://www.sa20.co.za/stats"

    def __init__(self, rate_limit_seconds: float = 2.0) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
        self.rate_limit_seconds = rate_limit_seconds

    def scrape_batting_leaders(
        self, season: Optional[int] = None, limit: int = 100
    ) -> List[Dict]:
        """Scrape batting leaders from stats page."""
        try:
            url = self.stats_url
            if season:
                url = f"{url}?season={season}"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Try to find JSON data in script tags
            stats = self._extract_from_scripts(soup, "batting")
            if stats:
                logger.info(f"Found {len(stats)} batting stats from script tags")
                return stats[:limit]

            # Try to parse HTML structure
            stats = self._extract_batting_from_html(soup)
            if stats:
                logger.info(f"Found {len(stats)} batting stats from HTML")
                return stats[:limit]

            # Try API endpoint
            stats = self._try_stats_api("batting", season)
            if stats:
                logger.info(f"Found {len(stats)} batting stats from API")
                return stats[:limit]

            logger.warning("Could not extract batting stats from SA20 website")
            return []

        except requests.RequestException as exc:
            logger.error(f"Failed to scrape batting stats: {exc}")
            return []

    def scrape_bowling_leaders(
        self, season: Optional[int] = None, limit: int = 100
    ) -> List[Dict]:
        """Scrape bowling leaders from stats page."""
        try:
            url = self.stats_url
            if season:
                url = f"{url}?season={season}"
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Try to find JSON data
            stats = self._extract_from_scripts(soup, "bowling")
            if stats:
                return stats[:limit]

            # Try to parse HTML
            stats = self._extract_bowling_from_html(soup)
            if stats:
                return stats[:limit]

            # Try API
            stats = self._try_stats_api("bowling", season)
            if stats:
                return stats[:limit]

            return []

        except requests.RequestException as exc:
            logger.error(f"Failed to scrape bowling stats: {exc}")
            return []

    def scrape_all_player_stats(
        self, season: Optional[int] = None
    ) -> Dict[str, List[Dict]]:
        """Scrape all player statistics (batting, bowling, fielding)."""
        batting = self.scrape_batting_leaders(season=season, limit=500)
        time.sleep(self.rate_limit_seconds)
        
        bowling = self.scrape_bowling_leaders(season=season, limit=500)
        time.sleep(self.rate_limit_seconds)

        return {
            "batting": batting,
            "bowling": bowling,
            "season": season,
        }

    def _extract_from_scripts(self, soup: BeautifulSoup, stat_type: str) -> List[Dict]:
        """Extract stats from JavaScript/JSON in script tags."""
        stats = []

        # Look for JSON data in script tags
        for script in soup.find_all("script", type="application/json"):
            try:
                data = json.loads(script.string)
                stats.extend(self._parse_stats_json(data, stat_type))
            except (json.JSONDecodeError, AttributeError):
                continue

        # Look for window.__INITIAL_STATE__ or similar
        for script in soup.find_all("script"):
            if not script.string:
                continue
            # Try to find stats objects
            json_matches = re.findall(
                r'\{[^{}]*"(?:batting|bowling|stats|leaders)"[^{}]*\}', script.string, re.DOTALL
            )
            for match in json_matches:
                try:
                    data = json.loads(match)
                    stats.extend(self._parse_stats_json(data, stat_type))
                except json.JSONDecodeError:
                    continue

        return stats

    def _extract_batting_from_html(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract batting stats from HTML structure."""
        stats = []

        # Look for batting leaderboard/table
        tables = soup.find_all(["table", "div"], class_=re.compile(r"batting|leader|stats", re.I))
        
        for table in tables:
            rows = table.find_all(["tr", "div"], class_=re.compile(r"row|item|player", re.I))
            
            for row in rows:
                stat = self._parse_batting_row(row)
                if stat:
                    stats.append(stat)

        return stats

    def _extract_bowling_from_html(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract bowling stats from HTML structure."""
        stats = []

        # Look for bowling leaderboard/table
        tables = soup.find_all(["table", "div"], class_=re.compile(r"bowling|leader|stats", re.I))
        
        for table in tables:
            rows = table.find_all(["tr", "div"], class_=re.compile(r"row|item|player", re.I))
            
            for row in rows:
                stat = self._parse_bowling_row(row)
                if stat:
                    stats.append(stat)

        return stats

    def _parse_batting_row(self, row) -> Optional[Dict]:
        """Parse a single batting stats row."""
        try:
            # Extract player name
            name_elem = row.find(["a", "span", "div"], class_=re.compile(r"name|player", re.I))
            if not name_elem:
                name_elem = row.find("a")
            
            name = name_elem.get_text(strip=True) if name_elem else None
            if not name:
                return None

            # Extract team
            team_elem = row.find(["span", "div"], class_=re.compile(r"team", re.I))
            team = team_elem.get_text(strip=True) if team_elem else None

            # Extract stats - look for common stat labels
            cells = row.find_all(["td", "div"], class_=re.compile(r"stat|value|number", re.I))
            
            # Try to extract runs, matches, strike rate, etc.
            runs = self._extract_stat_value(row, ["runs", "r"])
            matches = self._extract_stat_value(row, ["matches", "m", "inn"])
            strike_rate = self._extract_stat_value(row, ["strike", "sr", "strike_rate"])
            high_score = self._extract_stat_value(row, ["high", "hs", "best"])
            fours = self._extract_stat_value(row, ["4s", "fours"])
            sixes = self._extract_stat_value(row, ["6s", "sixes"])
            fifties = self._extract_stat_value(row, ["50", "fifties"])
            hundreds = self._extract_stat_value(row, ["100", "hundreds"])

            return {
                "player_name": name.strip(),
                "team": team.strip() if team else None,
                "matches": matches,
                "runs": runs,
                "high_score": high_score,
                "strike_rate": strike_rate,
                "fours": fours,
                "sixes": sixes,
                "fifties": fifties,
                "hundreds": hundreds,
            }
        except Exception as e:
            logger.warning(f"Error parsing batting row: {e}")
            return None

    def _parse_bowling_row(self, row) -> Optional[Dict]:
        """Parse a single bowling stats row."""
        try:
            name_elem = row.find(["a", "span", "div"], class_=re.compile(r"name|player", re.I))
            if not name_elem:
                name_elem = row.find("a")
            
            name = name_elem.get_text(strip=True) if name_elem else None
            if not name:
                return None

            team_elem = row.find(["span", "div"], class_=re.compile(r"team", re.I))
            team = team_elem.get_text(strip=True) if team_elem else None

            wickets = self._extract_stat_value(row, ["wickets", "wkts", "w"])
            matches = self._extract_stat_value(row, ["matches", "m", "inn"])
            economy = self._extract_stat_value(row, ["economy", "econ", "eco"])
            average = self._extract_stat_value(row, ["average", "avg"])
            best_figures = self._extract_stat_value(row, ["best", "bb", "figures"])

            return {
                "player_name": name.strip(),
                "team": team.strip() if team else None,
                "matches": matches,
                "wickets": wickets,
                "economy": economy,
                "average": average,
                "best_figures": best_figures,
            }
        except Exception as e:
            logger.warning(f"Error parsing bowling row: {e}")
            return None

    def _extract_stat_value(self, row, keys: List[str]) -> Optional[float]:
        """Extract a stat value by looking for labels."""
        for key in keys:
            # Look for label with value
            label = row.find(["span", "div", "td"], string=re.compile(key, re.I))
            if label:
                # Find adjacent value
                value_elem = label.find_next(["span", "div", "td"])
                if value_elem:
                    try:
                        text = value_elem.get_text(strip=True)
                        # Remove non-numeric characters except decimal point
                        cleaned = re.sub(r'[^\d.]', '', text)
                        if cleaned:
                            return float(cleaned)
                    except (ValueError, AttributeError):
                        continue
        return None

    def _parse_stats_json(self, data: dict | list, stat_type: str) -> List[Dict]:
        """Parse stats from JSON structure."""
        stats = []

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = (
                data.get("batting", []) if stat_type == "batting" else data.get("bowling", [])
                or data.get("stats", [])
                or data.get("leaders", [])
                or data.get("data", [])
                or [data]
            )
        else:
            return stats

        for item in items:
            if isinstance(item, dict):
                if stat_type == "batting":
                    stat = self._parse_batting_dict(item)
                else:
                    stat = self._parse_bowling_dict(item)
                if stat:
                    stats.append(stat)

        return stats

    def _parse_batting_dict(self, data: Dict) -> Optional[Dict]:
        """Parse batting stats from dictionary."""
        try:
            player_name = (
                data.get("player", {}).get("name")
                if isinstance(data.get("player"), dict)
                else data.get("player")
                or data.get("playerName")
                or data.get("name")
            )

            if not player_name:
                return None

            return {
                "player_name": str(player_name).strip(),
                "team": (
                    data.get("team", {}).get("name")
                    if isinstance(data.get("team"), dict)
                    else data.get("team")
                    or data.get("teamName")
                ),
                "matches": self._safe_float(data.get("matches") or data.get("m") or data.get("innings")),
                "runs": self._safe_float(data.get("runs") or data.get("r")),
                "high_score": self._safe_float(data.get("highScore") or data.get("hs") or data.get("best")),
                "strike_rate": self._safe_float(data.get("strikeRate") or data.get("sr") or data.get("strike_rate")),
                "fours": self._safe_int(data.get("fours") or data.get("4s")),
                "sixes": self._safe_int(data.get("sixes") or data.get("6s")),
                "fifties": self._safe_int(data.get("fifties") or data.get("50s")),
                "hundreds": self._safe_int(data.get("hundreds") or data.get("100s")),
            }
        except Exception as e:
            logger.warning(f"Error parsing batting dict: {e}")
            return None

    def _parse_bowling_dict(self, data: Dict) -> Optional[Dict]:
        """Parse bowling stats from dictionary."""
        try:
            player_name = (
                data.get("player", {}).get("name")
                if isinstance(data.get("player"), dict)
                else data.get("player")
                or data.get("playerName")
                or data.get("name")
            )

            if not player_name:
                return None

            return {
                "player_name": str(player_name).strip(),
                "team": (
                    data.get("team", {}).get("name")
                    if isinstance(data.get("team"), dict)
                    else data.get("team")
                    or data.get("teamName")
                ),
                "matches": self._safe_float(data.get("matches") or data.get("m") or data.get("innings")),
                "wickets": self._safe_float(data.get("wickets") or data.get("wkts") or data.get("w")),
                "economy": self._safe_float(data.get("economy") or data.get("econ") or data.get("eco")),
                "average": self._safe_float(data.get("average") or data.get("avg")),
                "best_figures": data.get("bestFigures") or data.get("bb") or data.get("best"),
            }
        except Exception as e:
            logger.warning(f"Error parsing bowling dict: {e}")
            return None

    def _try_stats_api(self, stat_type: str, season: Optional[int]) -> List[Dict]:
        """Try to find and call API endpoints for stats."""
        api_endpoints = [
            f"{self.base_url}/api/stats/{stat_type}",
            f"{self.base_url}/api/v1/stats/{stat_type}",
            f"{self.base_url}/api/stats",
        ]

        if season:
            api_endpoints.extend([
                f"{self.base_url}/api/stats/{stat_type}?season={season}",
                f"{self.base_url}/api/v1/stats/{stat_type}?season={season}",
            ])

        for endpoint in api_endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    stats = self._parse_stats_json(data, stat_type)
                    if stats:
                        return stats
            except (requests.RequestException, json.JSONDecodeError):
                continue

        return []

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            if isinstance(value, str):
                # Remove non-numeric characters except decimal point
                cleaned = re.sub(r'[^\d.]', '', value)
                if not cleaned:
                    return None
                return float(cleaned)
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to int."""
        if value is None:
            return None
        try:
            if isinstance(value, str):
                cleaned = re.sub(r'[^\d]', '', value)
                if not cleaned:
                    return None
                return int(cleaned)
            return int(value)
        except (ValueError, TypeError):
            return None

