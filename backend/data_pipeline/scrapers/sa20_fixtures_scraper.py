"""Scraper for SA20 official website fixtures."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Team name mappings from SA20 website to our database
TEAM_NAME_MAPPING = {
    "MI Cape Town": "MI Cape Town",
    "Paarl Royals": "Paarl Royals",
    "Pretoria Capitals": "Pretoria Capitals",
    "Durban's Super Giants": "Durban's Super Giants",
    "Joburg Super Kings": "Joburg Super Kings",
    "Sunrisers Eastern Cape": "Sunrisers Eastern Cape",
}

# Venue name mappings
VENUE_MAPPING = {
    "Newlands": "Newlands",
    "Wanderers": "Wanderers",
    "Boland Park": "Boland Park",
    "SuperSport Park": "SuperSport Park",
    "Kingsmead": "Kingsmead",
    "St George's Park": "St George's Park",
}


class SA20FixturesScraper:
    """Scraper for SA20 official website fixtures page."""

    base_url = "https://www.sa20.co.za"
    fixtures_url = "https://www.sa20.co.za/matches"

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

    def scrape_fixtures(self, season: int = 2026) -> List[Dict]:
        """
        Scrape fixtures from SA20 website.
        
        The website loads fixtures via JavaScript, so we use Playwright for dynamic content.
        Falls back to API/HTML parsing if Playwright is not available.
        """
        # Try Playwright first for JavaScript-rendered content
        fixtures = self._scrape_with_playwright(season)
        if fixtures:
            logger.info(f"Found {len(fixtures)} fixtures using Playwright")
            return fixtures
        
        # Fallback to API/HTML methods
        try:
            response = self.session.get(self.fixtures_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Try to find JSON data in script tags (common pattern for JS apps)
            fixtures = self._extract_from_scripts(soup)
            if fixtures:
                logger.info(f"Found {len(fixtures)} fixtures from script tags")
                return fixtures

            # Try to parse HTML structure
            fixtures = self._extract_from_html(soup)
            if fixtures:
                logger.info(f"Found {len(fixtures)} fixtures from HTML")
                return fixtures

            # Try to find API endpoint
            fixtures = self._try_api_endpoint(season)
            if fixtures:
                logger.info(f"Found {len(fixtures)} fixtures from API")
                return fixtures

            logger.warning("Could not extract fixtures from SA20 website")
            return []

        except requests.RequestException as exc:
            logger.error(f"Failed to scrape fixtures: {exc}")
            return []
    
    def _scrape_with_playwright(self, season: int = 2026) -> List[Dict]:
        """Scrape fixtures using Playwright to handle JavaScript-rendered content."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright not available, skipping JavaScript rendering")
            return []
        
        fixtures = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Navigate to fixtures page
                logger.info(f"Loading {self.fixtures_url} with Playwright...")
                page.goto(self.fixtures_url, wait_until="networkidle", timeout=60000)
                
                # Wait for fixtures to load (adjust selector based on actual page)
                try:
                    page.wait_for_selector('[class*="fixture"], [class*="match"], [data-testid*="fixture"]', timeout=10000)
                except Exception:
                    logger.warning("Fixture elements not found, trying to extract from page content")
                
                # Try to intercept API calls
                fixtures_from_api = self._intercept_api_calls(page)
                if fixtures_from_api:
                    browser.close()
                    return fixtures_from_api
                
                # Extract from rendered HTML
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                # Look for fixture elements in various formats
                fixture_elements = (
                    soup.find_all("div", class_=re.compile(r"fixture|match", re.I)) +
                    soup.find_all("article", class_=re.compile(r"fixture|match", re.I)) +
                    soup.find_all("li", class_=re.compile(r"fixture|match", re.I))
                )
                
                for elem in fixture_elements:
                    fixture = self._parse_fixture_element(elem)
                    if fixture:
                        fixtures.append(fixture)
                
                # Also check for JSON data in the page
                fixtures_from_json = self._extract_from_scripts(soup)
                if fixtures_from_json and len(fixtures_from_json) > len(fixtures):
                    fixtures = fixtures_from_json
                
                browser.close()
                
        except Exception as e:
            logger.error(f"Error scraping with Playwright: {e}")
            return []
        
        return fixtures
    
    def _intercept_api_calls(self, page) -> List[Dict]:
        """Intercept API calls to find fixture data."""
        fixtures = []
        try:
            # Listen for API responses
            def handle_response(response):
                url = response.url
                if "api" in url.lower() and ("fixture" in url.lower() or "match" in url.lower()):
                    try:
                        data = response.json()
                        parsed = self._parse_json_data(data)
                        if parsed:
                            fixtures.extend(parsed)
                    except Exception:
                        pass
            
            page.on("response", handle_response)
            # Wait a bit for API calls to complete
            page.wait_for_timeout(5000)
        except Exception as e:
            logger.debug(f"Could not intercept API calls: {e}")
        
        return fixtures
    
    def _parse_fixture_element(self, elem) -> Optional[Dict]:
        """Parse fixture from a rendered HTML element."""
        try:
            # Extract team names - look for common patterns
            team_selectors = [
                elem.find_all(["span", "div", "p"], class_=re.compile(r"team.*name|team.*title", re.I)),
                elem.find_all(["h3", "h4"], class_=re.compile(r"team", re.I)),
                elem.find_all("img", alt=True),  # Team logos with alt text
            ]
            
            teams = []
            for selector_list in team_selectors:
                if selector_list:
                    for sel in selector_list:
                        text = sel.get_text(strip=True) or sel.get("alt", "")
                        if text and len(text) > 2:
                            teams.append(text)
                    if len(teams) >= 2:
                        break
            
            if len(teams) < 2:
                return None
            
            # Extract date
            date_elem = (
                elem.find("time") or
                elem.find(["span", "div"], class_=re.compile(r"date|time", re.I)) or
                elem.find(["span", "div"], {"data-date": True})
            )
            date_str = None
            if date_elem:
                date_str = date_elem.get("datetime") or date_elem.get("data-date") or date_elem.get_text(strip=True)
            
            # Extract venue
            venue_elem = elem.find(["span", "div"], class_=re.compile(r"venue|stadium|location", re.I))
            venue = venue_elem.get_text(strip=True) if venue_elem else None
            
            # Extract match number
            match_num_elem = elem.find(["span", "div"], class_=re.compile(r"match.*number|number", re.I))
            match_number = match_num_elem.get_text(strip=True) if match_num_elem else None
            if match_number:
                # Extract numeric part
                match_number = re.search(r'\d+', match_number)
                match_number = int(match_number.group()) if match_number else None
            
            match_date = self._parse_date(date_str) if date_str else None
            
            return {
                "home_team": teams[0].strip(),
                "away_team": teams[1].strip(),
                "venue": venue.strip() if venue else None,
                "match_date": match_date,
                "match_number": match_number,
                "season": 2026,
            }
        except Exception as e:
            logger.debug(f"Error parsing fixture element: {e}")
            return None

    def _extract_from_scripts(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract fixture data from JavaScript/JSON in script tags."""
        fixtures = []
        
        # Look for JSON data in script tags
        for script in soup.find_all("script", type="application/json"):
            try:
                data = json.loads(script.string)
                fixtures.extend(self._parse_json_data(data))
            except (json.JSONDecodeError, AttributeError):
                continue

        # Look for window.__INITIAL_STATE__ or similar patterns
        for script in soup.find_all("script"):
            if not script.string:
                continue
            # Try to find JSON objects in script content
            json_matches = re.findall(r'\{[^{}]*"fixtures"[^{}]*\}', script.string, re.DOTALL)
            for match in json_matches:
                try:
                    data = json.loads(match)
                    fixtures.extend(self._parse_json_data(data))
                except json.JSONDecodeError:
                    continue

        return fixtures

    def _extract_from_html(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract fixtures from HTML structure."""
        fixtures = []
        
        # Common patterns for fixture cards/listings
        # Adjust selectors based on actual website structure
        fixture_cards = soup.find_all(
            ["div", "article", "li"],
            class_=re.compile(r"fixture|match|game", re.I)
        )
        
        for card in fixture_cards:
            fixture = self._parse_fixture_card(card)
            if fixture:
                fixtures.append(fixture)

        return fixtures

    def _try_api_endpoint(self, season: int) -> List[Dict]:
        """Try to find and call API endpoints for fixtures."""
        # Common API endpoint patterns
        api_endpoints = [
            f"{self.base_url}/api/fixtures",
            f"{self.base_url}/api/matches",
            f"{self.base_url}/api/v1/fixtures",
            f"{self.base_url}/api/v1/matches",
            f"{self.base_url}/api/fixtures/{season}",
        ]

        for endpoint in api_endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    fixtures = self._parse_json_data(data)
                    if fixtures:
                        return fixtures
            except (requests.RequestException, json.JSONDecodeError):
                continue

        return []

    def _parse_json_data(self, data: dict | list) -> List[Dict]:
        """Parse fixture data from JSON structure."""
        fixtures = []
        
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Look for common keys
            items = (
                data.get("fixtures", [])
                or data.get("matches", [])
                or data.get("data", [])
                or data.get("results", [])
                or [data]
            )
        else:
            return fixtures

        for item in items:
            if isinstance(item, dict):
                fixture = self._parse_fixture_dict(item)
                if fixture:
                    fixtures.append(fixture)

        return fixtures

    def _parse_fixture_dict(self, data: Dict) -> Optional[Dict]:
        """Parse a single fixture from dictionary."""
        try:
            # Extract date
            date_str = (
                data.get("date")
                or data.get("matchDate")
                or data.get("scheduledDate")
                or data.get("startTime")
            )
            if date_str:
                match_date = self._parse_date(date_str)
            else:
                return None

            # Extract teams
            home_team = (
                data.get("homeTeam", {}).get("name")
                if isinstance(data.get("homeTeam"), dict)
                else data.get("homeTeam")
                or data.get("team1")
            )
            away_team = (
                data.get("awayTeam", {}).get("name")
                if isinstance(data.get("awayTeam"), dict)
                else data.get("awayTeam")
                or data.get("team2")
            )

            if not home_team or not away_team:
                return None

            # Extract venue
            venue = (
                data.get("venue", {}).get("name")
                if isinstance(data.get("venue"), dict)
                else data.get("venue")
                or data.get("stadium")
            )

            # Extract match number
            match_number = data.get("matchNumber") or data.get("match_number") or data.get("number")

            return {
                "home_team": home_team.strip(),
                "away_team": away_team.strip(),
                "venue": venue.strip() if venue else None,
                "match_date": match_date,
                "match_number": match_number,
                "season": data.get("season", 2026),
            }
        except Exception as e:
            logger.warning(f"Error parsing fixture dict: {e}")
            return None

    def _parse_fixture_card(self, card) -> Optional[Dict]:
        """Parse fixture from HTML card element."""
        try:
            # This is a placeholder - adjust based on actual HTML structure
            teams = card.find_all(["span", "div"], class_=re.compile(r"team", re.I))
            if len(teams) < 2:
                return None

            date_elem = card.find(["time", "span", "div"], class_=re.compile(r"date|time", re.I))
            venue_elem = card.find(["span", "div"], class_=re.compile(r"venue|stadium", re.I))

            return {
                "home_team": teams[0].get_text(strip=True),
                "away_team": teams[1].get_text(strip=True),
                "venue": venue_elem.get_text(strip=True) if venue_elem else None,
                "match_date": self._parse_date(date_elem.get_text(strip=True)) if date_elem else None,
                "match_number": None,
                "season": 2026,
            }
        except Exception as e:
            logger.warning(f"Error parsing fixture card: {e}")
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None

        # Common date formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%d %B %Y",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        # Try ISO format with timezone
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except (ImportError, ValueError, TypeError):
            pass

        logger.warning(f"Could not parse date: {date_str}")
        return None

