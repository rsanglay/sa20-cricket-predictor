"""Scraper for SA20 website using direct API calls and improved HTML parsing."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SA20APIScraper:
    """Improved scraper that tries multiple methods to extract data."""

    base_url = "https://www.sa20.co.za"
    api_base = "https://api.sa20.co.za"  # Potential API base

    def __init__(self, rate_limit_seconds: float = 2.0) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                ),
                "Accept": "application/json, text/html, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.sa20.co.za/",
            }
        )
        self.rate_limit_seconds = rate_limit_seconds

    def scrape_teams(self) -> List[Dict]:
        """Scrape teams using multiple methods."""
        teams = []

        # Method 1: Try API endpoint
        api_teams = self._try_teams_api()
        if api_teams:
            return api_teams

        # Method 2: Parse HTML with better selectors
        html_teams = self._scrape_teams_from_html()
        if html_teams:
            teams.extend(html_teams)

        # Method 3: Known teams as fallback
        if not teams:
            teams = self._get_known_teams()

        return teams

    def scrape_team_players(self, team_slug: str) -> List[Dict]:
        """Scrape players for a team."""
        # Try API first
        api_players = self._try_players_api(team_slug)
        if api_players:
            return api_players

        # Try HTML
        return self._scrape_players_from_html(team_slug)

    def scrape_stats(self, stat_type: str = "batting", season: Optional[int] = None) -> List[Dict]:
        """Scrape statistics."""
        # Try API
        api_stats = self._try_stats_api(stat_type, season)
        if api_stats:
            return api_stats

        # Try HTML
        return self._scrape_stats_from_html(stat_type, season)

    def scrape_fixtures(self, season: int = 2026) -> List[Dict]:
        """Scrape fixtures."""
        # Try API
        api_fixtures = self._try_fixtures_api(season)
        if api_fixtures:
            return api_fixtures

        # Try HTML
        return self._scrape_fixtures_from_html(season)

    def _try_teams_api(self) -> List[Dict]:
        """Try to get teams from API endpoints."""
        api_endpoints = [
            f"{self.base_url}/api/teams",
            f"{self.api_base}/teams",
            f"{self.base_url}/api/v1/teams",
        ]

        for endpoint in api_endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return [self._normalize_team(t) for t in data]
                    elif isinstance(data, dict) and "teams" in data:
                        return [self._normalize_team(t) for t in data["teams"]]
            except Exception as e:
                logger.debug(f"API endpoint {endpoint} failed: {e}")
                continue

        return []

    def _scrape_teams_from_html(self) -> List[Dict]:
        """Scrape teams from HTML page."""
        try:
            response = self.session.get(f"{self.base_url}/teams", timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            teams = []

            # Look for team links in various formats
            team_links = soup.find_all("a", href=re.compile(r"/teams/"))
            for link in team_links:
                href = link.get("href", "")
                name = link.get_text(strip=True)
                if name and "/teams/" in href:
                    slug = href.split("/teams/")[-1].strip("/")
                    teams.append({
                        "name": name,
                        "slug": slug,
                        "url": f"{self.base_url}{href}" if href.startswith("/") else href,
                    })

            # Also look in script tags for JSON data
            for script in soup.find_all("script"):
                if script.string:
                    # Look for team data in JSON
                    json_matches = re.findall(
                        r'\{[^{}]*"(?:name|team|slug)"[^{}]*\}', script.string, re.DOTALL
                    )
                    for match in json_matches[:10]:  # Limit to avoid too many
                        try:
                            data = json.loads(match)
                            if "name" in data or "team" in data:
                                teams.append(self._normalize_team(data))
                        except json.JSONDecodeError:
                            continue

            return teams

        except Exception as e:
            logger.error(f"Failed to scrape teams from HTML: {e}")
            return []

    def _scrape_players_from_html(self, team_slug: str) -> List[Dict]:
        """Scrape players from team page HTML."""
        try:
            # Try different URL formats
            urls = [
                f"{self.base_url}/teams/{team_slug}",
                f"{self.base_url}/team/{team_slug}",
            ]

            for url in urls:
                try:
                    response = self.session.get(url, timeout=30)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, "html.parser")
                        players = self._extract_players_from_soup(soup)
                        if players:
                            return players
                except Exception:
                    continue

            return []

        except Exception as e:
            logger.error(f"Failed to scrape players for {team_slug}: {e}")
            return []

    def _extract_players_from_soup(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract players from BeautifulSoup object."""
        players = []

        # Look for player elements
        player_elements = soup.find_all(
            ["div", "article", "li"],
            class_=re.compile(r"player|squad|roster", re.I),
        )

        for element in player_elements:
            player = self._parse_player_element(element)
            if player:
                players.append(player)

        # Also check script tags for JSON data
        for script in soup.find_all("script"):
            if script.string and "player" in script.string.lower():
                json_data = self._extract_json_from_script(script.string)
                if json_data:
                    players.extend([self._normalize_player(p) for p in json_data if isinstance(p, dict)])

        return players

    def _scrape_stats_from_html(self, stat_type: str, season: Optional[int]) -> List[Dict]:
        """Scrape stats from HTML."""
        try:
            url = f"{self.base_url}/stats"
            if season:
                url += f"?season={season}"

            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            stats = []

            # Look for stats tables
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")[1:]  # Skip header
                for row in rows:
                    if stat_type == "batting":
                        stat = self._parse_batting_row(row)
                    else:
                        stat = self._parse_bowling_row(row)
                    if stat:
                        stats.append(stat)

            # Check script tags for JSON
            for script in soup.find_all("script"):
                if script.string:
                    json_data = self._extract_json_from_script(script.string)
                    if json_data:
                        stats.extend([s for s in json_data if isinstance(s, dict)])

            return stats

        except Exception as e:
            logger.error(f"Failed to scrape stats from HTML: {e}")
            return []

    def _scrape_fixtures_from_html(self, season: int) -> List[Dict]:
        """Scrape fixtures from HTML."""
        try:
            response = self.session.get(f"{self.base_url}/matches", timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            fixtures = []

            # Look for fixture elements
            fixture_elements = soup.find_all(
                ["div", "article"],
                class_=re.compile(r"match|fixture", re.I),
            )

            for element in fixture_elements:
                fixture = self._parse_fixture_element(element, season)
                if fixture:
                    fixtures.append(fixture)

            return fixtures

        except Exception as e:
            logger.error(f"Failed to scrape fixtures from HTML: {e}")
            return []

    def _parse_player_element(self, element) -> Optional[Dict]:
        """Parse a player element."""
        try:
            name_elem = element.find(["h3", "h4", "span", "a"], class_=re.compile(r"name", re.I))
            if not name_elem:
                name_elem = element.find("a")

            name = name_elem.get_text(strip=True) if name_elem else None
            if not name:
                return None

            img_elem = element.find("img")
            image_url = None
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src")

            role_elem = element.find(["span", "div"], class_=re.compile(r"role", re.I))
            role = None
            if role_elem:
                role = self._normalize_role(role_elem.get_text(strip=True))

            return {
                "name": name,
                "role": role,
                "image_url": image_url,
                "country": "South Africa",  # Default
            }
        except Exception:
            return None

    def _parse_batting_row(self, row) -> Optional[Dict]:
        """Parse a batting stats row."""
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                return None

            name = cells[0].get_text(strip=True)
            if not name:
                return None

            # Try to extract runs (usually in 2nd or 3rd column)
            runs = None
            for cell in cells[1:4]:
                text = cell.get_text(strip=True)
                if text.isdigit():
                    runs = int(text)
                    break

            return {
                "player_name": name,
                "runs": runs,
            }
        except Exception:
            return None

    def _parse_bowling_row(self, row) -> Optional[Dict]:
        """Parse a bowling stats row."""
        try:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                return None

            name = cells[0].get_text(strip=True)
            if not name:
                return None

            wickets = None
            for cell in cells[1:4]:
                text = cell.get_text(strip=True)
                if text.isdigit():
                    wickets = int(text)
                    break

            return {
                "player_name": name,
                "wickets": wickets,
            }
        except Exception:
            return None

    def _parse_fixture_element(self, element, season: int) -> Optional[Dict]:
        """Parse a fixture element."""
        # Simplified - would need more specific parsing
        text = element.get_text(strip=True)
        if not text or len(text) < 10:
            return None

        return {
            "season": season,
            "raw_text": text,
        }

    def _try_players_api(self, team_slug: str) -> List[Dict]:
        """Try API for players."""
        endpoints = [
            f"{self.base_url}/api/teams/{team_slug}/players",
            f"{self.api_base}/teams/{team_slug}/players",
        ]
        for endpoint in endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return [self._normalize_player(p) for p in data]
            except Exception:
                continue
        return []

    def _try_stats_api(self, stat_type: str, season: Optional[int]) -> List[Dict]:
        """Try API for stats."""
        endpoints = [
            f"{self.base_url}/api/stats/{stat_type}",
            f"{self.api_base}/stats/{stat_type}",
        ]
        if season:
            endpoints = [f"{e}?season={season}" for e in endpoints]

        for endpoint in endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "data" in data:
                        return data["data"]
            except Exception:
                continue
        return []

    def _try_fixtures_api(self, season: int) -> List[Dict]:
        """Try API for fixtures."""
        endpoints = [
            f"{self.base_url}/api/matches?season={season}",
            f"{self.api_base}/matches?season={season}",
        ]
        for endpoint in endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
            except Exception:
                continue
        return []

    def _extract_json_from_script(self, script_text: str) -> List[Dict]:
        """Extract JSON data from script text."""
        results = []
        # Look for JSON objects
        json_patterns = [
            r'\{[^{}]*"(?:player|team|match|stat)"[^{}]*\}',
            r'\[[^\]]*\{[^{}]*"(?:player|team|match|stat)"[^{}]*\}[^\]]*\]',
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, script_text, re.DOTALL)
            for match in matches[:20]:  # Limit matches
                try:
                    data = json.loads(match)
                    if isinstance(data, dict):
                        results.append(data)
                    elif isinstance(data, list):
                        results.extend([d for d in data if isinstance(d, dict)])
                except json.JSONDecodeError:
                    continue

        return results

    def _normalize_team(self, data: Dict) -> Dict:
        """Normalize team data."""
        if isinstance(data, str):
            return {"name": data, "slug": self._name_to_slug(data)}
        name = data.get("name") or data.get("team") or data.get("teamName")
        slug = data.get("slug") or self._name_to_slug(name) if name else None
        return {
            "name": name or "Unknown",
            "slug": slug or "unknown",
            "url": data.get("url") or f"{self.base_url}/teams/{slug}",
        }

    def _normalize_player(self, data: Dict) -> Dict:
        """Normalize player data."""
        if isinstance(data, str):
            return {"name": data}
        return {
            "name": data.get("name") or data.get("playerName") or "Unknown",
            "role": self._normalize_role(data.get("role") or data.get("position")),
            "image_url": data.get("image") or data.get("imageUrl") or data.get("photo"),
            "country": data.get("country") or data.get("nationality") or "South Africa",
        }

    def _normalize_role(self, role_text: Optional[str]) -> Optional[str]:
        """Normalize role."""
        if not role_text:
            return None
        role_lower = role_text.lower().strip()
        role_map = {
            "batsman": "batsman",
            "batter": "batsman",
            "bowler": "bowler",
            "all-rounder": "all_rounder",
            "allrounder": "all_rounder",
            "wicket-keeper": "wicket_keeper",
            "wicketkeeper": "wicket_keeper",
            "wk": "wicket_keeper",
        }
        for key, value in role_map.items():
            if key in role_lower:
                return value
        return "batsman"

    def _name_to_slug(self, name: str) -> str:
        """Convert name to slug."""
        slug_map = {
            "Durban's Super Giants": "durans-super-giants",
            "Joburg Super Kings": "joburg-super-kings",
            "MI Cape Town": "mi-cape-town",
            "Paarl Royals": "paarl-royals",
            "Pretoria Capitals": "pretoria-capitals",
            "Sunrisers Eastern Cape": "sunrisers-eastern-cape",
        }
        return slug_map.get(name, name.lower().replace(" ", "-").replace("'", ""))

    def _get_known_teams(self) -> List[Dict]:
        """Return known SA20 teams."""
        teams = [
            "Durban's Super Giants",
            "Joburg Super Kings",
            "MI Cape Town",
            "Paarl Royals",
            "Pretoria Capitals",
            "Sunrisers Eastern Cape",
        ]
        return [{"name": t, "slug": self._name_to_slug(t), "url": f"{self.base_url}/teams/{self._name_to_slug(t)}"} for t in teams]

