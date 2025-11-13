"""Browser-based scraper for SA20 website using Playwright to handle JavaScript rendering."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


class SA20BrowserScraper:
    """Browser-based scraper for SA20 website using Playwright."""

    base_url = "https://www.sa20.co.za"

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        """Async context manager entry."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=self.headless)
        context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        )
        self.page = await context.new_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser:
            await self.browser.close()

    async def scrape_teams(self) -> List[Dict]:
        """Scrape all teams from the teams page."""
        if not self.page:
            raise RuntimeError("Browser not initialized. Use async context manager.")

        try:
            await self.page.goto(f"{self.base_url}/teams", wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)  # Wait for JS to render

            # Try to extract teams from the page
            teams = []

            # Method 1: Look for team cards/elements
            team_elements = await self.page.query_selector_all(
                "a[href*='/teams/'], div[class*='team'], article[class*='team']"
            )

            for element in team_elements:
                try:
                    name = await element.text_content()
                    href = await element.get_attribute("href")
                    if name and href and "/teams/" in href:
                        slug = href.split("/teams/")[-1].strip("/")
                        teams.append({
                            "name": name.strip(),
                            "slug": slug,
                            "url": f"{self.base_url}{href}" if href.startswith("/") else href,
                        })
                except Exception as e:
                    logger.debug(f"Error extracting team element: {e}")
                    continue

            # Method 2: Try to get data from JavaScript/API calls
            if not teams:
                # Listen for network requests
                api_data = await self._extract_from_api_calls()
                if api_data:
                    teams.extend(api_data)

            # Method 3: Extract from page text/known teams
            if not teams:
                page_text = await self.page.content()
                known_teams = [
                    "Durban's Super Giants",
                    "Joburg Super Kings",
                    "MI Cape Town",
                    "Paarl Royals",
                    "Pretoria Capitals",
                    "Sunrisers Eastern Cape",
                ]
                for team_name in known_teams:
                    if team_name.lower() in page_text.lower():
                        teams.append({
                            "name": team_name,
                            "slug": self._name_to_slug(team_name),
                            "url": f"{self.base_url}/teams/{self._name_to_slug(team_name)}",
                        })

            # Remove duplicates
            seen = set()
            unique_teams = []
            for team in teams:
                key = team["name"].lower()
                if key not in seen:
                    seen.add(key)
                    unique_teams.append(team)

            logger.info(f"Found {len(unique_teams)} teams")
            return unique_teams

        except Exception as e:
            logger.error(f"Failed to scrape teams: {e}")
            return []

    async def scrape_team_players(self, team_slug: str) -> List[Dict]:
        """Scrape players from a specific team page."""
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        try:
            url = f"{self.base_url}/teams/{team_slug}"
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)

            players = []

            # Look for player cards
            player_elements = await self.page.query_selector_all(
                "div[class*='player'], article[class*='player'], li[class*='player'], "
                "div[class*='squad'], div[class*='roster']"
            )

            for element in player_elements:
                try:
                    player = await self._extract_player_from_element(element)
                    if player:
                        players.append(player)
                except Exception as e:
                    logger.debug(f"Error extracting player: {e}")
                    continue

            # Try API method
            if not players:
                api_players = await self._extract_players_from_api(team_slug)
                players.extend(api_players)

            logger.info(f"Found {len(players)} players for team {team_slug}")
            return players

        except Exception as e:
            logger.error(f"Failed to scrape team {team_slug}: {e}")
            return []

    async def scrape_stats(
        self, stat_type: str = "batting", season: Optional[int] = None
    ) -> List[Dict]:
        """Scrape statistics from the stats page."""
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        try:
            url = f"{self.base_url}/stats"
            if season:
                url += f"?season={season}"

            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(5000)  # Wait for stats to load

            # Try to switch to the correct tab (batting/bowling)
            if stat_type == "bowling":
                try:
                    bowling_tab = await self.page.query_selector("button:has-text('Bowling'), a:has-text('Bowling')")
                    if bowling_tab:
                        await bowling_tab.click()
                        await self.page.wait_for_timeout(2000)
                except Exception:
                    pass

            stats = []

            # Extract from table/list
            rows = await self.page.query_selector_all(
                "tr, div[class*='row'], div[class*='stat'], div[class*='leader']"
            )

            for row in rows:
                try:
                    if stat_type == "batting":
                        stat = await self._extract_batting_stat(row)
                    else:
                        stat = await self._extract_bowling_stat(row)
                    if stat:
                        stats.append(stat)
                except Exception as e:
                    logger.debug(f"Error extracting stat row: {e}")
                    continue

            # Try API method
            if not stats:
                api_stats = await self._extract_stats_from_api(stat_type, season)
                stats.extend(api_stats)

            logger.info(f"Found {len(stats)} {stat_type} stats")
            return stats

        except Exception as e:
            logger.error(f"Failed to scrape {stat_type} stats: {e}")
            return []

    async def scrape_fixtures(self, season: int = 2026) -> List[Dict]:
        """Scrape fixtures from the matches page."""
        if not self.page:
            raise RuntimeError("Browser not initialized.")

        try:
            url = f"{self.base_url}/matches"
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(3000)

            fixtures = []

            # Extract match cards/elements
            match_elements = await self.page.query_selector_all(
                "div[class*='match'], article[class*='match'], div[class*='fixture']"
            )

            for element in match_elements:
                try:
                    fixture = await self._extract_fixture_from_element(element, season)
                    if fixture:
                        fixtures.append(fixture)
                except Exception as e:
                    logger.debug(f"Error extracting fixture: {e}")
                    continue

            # Try API method
            if not fixtures:
                api_fixtures = await self._extract_fixtures_from_api(season)
                fixtures.extend(api_fixtures)

            logger.info(f"Found {len(fixtures)} fixtures for season {season}")
            return fixtures

        except Exception as e:
            logger.error(f"Failed to scrape fixtures: {e}")
            return []

    async def _extract_player_from_element(self, element) -> Optional[Dict]:
        """Extract player information from a DOM element."""
        try:
            name_elem = await element.query_selector("h3, h4, span[class*='name'], a")
            name = await name_elem.text_content() if name_elem else None
            if not name:
                return None

            # Get image
            img_elem = await element.query_selector("img")
            image_url = None
            if img_elem:
                image_url = await img_elem.get_attribute("src") or await img_elem.get_attribute("data-src")

            # Get role
            role_elem = await element.query_selector("span[class*='role'], div[class*='role']")
            role_text = await role_elem.text_content() if role_elem else None
            role = self._normalize_role(role_text) if role_text else None

            # Get country
            country_elem = await element.query_selector("span[class*='country'], div[class*='country']")
            country = await country_elem.text_content() if country_elem else None

            return {
                "name": name.strip(),
                "role": role,
                "country": country.strip() if country else "South Africa",
                "image_url": image_url,
            }
        except Exception as e:
            logger.debug(f"Error in _extract_player_from_element: {e}")
            return None

    async def _extract_batting_stat(self, row) -> Optional[Dict]:
        """Extract batting statistics from a table row."""
        try:
            cells = await row.query_selector_all("td, div[class*='cell']")
            if len(cells) < 3:
                return None

            name = await cells[0].text_content()
            if not name or not name.strip():
                return None

            # Try to extract stats from cells
            stats_text = await row.text_content()
            # Use regex to extract numbers
            runs_match = re.search(r'(\d+)\s*runs?', stats_text, re.I)
            matches_match = re.search(r'(\d+)\s*m', stats_text, re.I)

            return {
                "player_name": name.strip(),
                "runs": int(runs_match.group(1)) if runs_match else None,
                "matches": int(matches_match.group(1)) if matches_match else None,
            }
        except Exception:
            return None

    async def _extract_bowling_stat(self, row) -> Optional[Dict]:
        """Extract bowling statistics from a table row."""
        try:
            cells = await row.query_selector_all("td, div[class*='cell']")
            if len(cells) < 3:
                return None

            name = await cells[0].text_content()
            if not name or not name.strip():
                return None

            stats_text = await row.text_content()
            wickets_match = re.search(r'(\d+)\s*w', stats_text, re.I)

            return {
                "player_name": name.strip(),
                "wickets": int(wickets_match.group(1)) if wickets_match else None,
            }
        except Exception:
            return None

    async def _extract_fixture_from_element(self, element, season: int) -> Optional[Dict]:
        """Extract fixture information from a DOM element."""
        try:
            text = await element.text_content()
            if not text:
                return None

            # Try to extract teams, date, venue from text
            # This is a simplified extraction - may need refinement
            return {
                "season": season,
                "raw_text": text.strip(),
            }
        except Exception:
            return None

    async def _extract_from_api_calls(self) -> List[Dict]:
        """Try to extract data from API calls made by the page."""
        # This would require intercepting network requests
        # For now, return empty
        return []

    async def _extract_players_from_api(self, team_slug: str) -> List[Dict]:
        """Try to extract players from API endpoints."""
        return []

    async def _extract_stats_from_api(self, stat_type: str, season: Optional[int]) -> List[Dict]:
        """Try to extract stats from API endpoints."""
        return []

    async def _extract_fixtures_from_api(self, season: int) -> List[Dict]:
        """Try to extract fixtures from API endpoints."""
        return []

    def _normalize_role(self, role_text: str) -> Optional[str]:
        """Normalize role text to our enum values."""
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
        return "batsman"  # Default

    def _name_to_slug(self, name: str) -> str:
        """Convert team name to URL slug."""
        slug_map = {
            "Durban's Super Giants": "durans-super-giants",
            "Joburg Super Kings": "joburg-super-kings",
            "MI Cape Town": "mi-cape-town",
            "Paarl Royals": "paarl-royals",
            "Pretoria Capitals": "pretoria-capitals",
            "Sunrisers Eastern Cape": "sunrisers-eastern-cape",
        }
        return slug_map.get(name, name.lower().replace(" ", "-").replace("'", ""))

