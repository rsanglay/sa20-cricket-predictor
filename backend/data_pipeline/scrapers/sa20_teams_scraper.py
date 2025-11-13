"""Scraper for SA20 teams and players from official website."""
from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Role mappings from website to our enum
ROLE_MAPPING = {
    "batsman": "batsman",
    "batter": "batsman",
    "bowler": "bowler",
    "all-rounder": "all_rounder",
    "allrounder": "all_rounder",
    "wicket-keeper": "wicket_keeper",
    "wicketkeeper": "wicket_keeper",
    "wk": "wicket_keeper",
    "wk-batsman": "wicket_keeper",
    "wk-batter": "wicket_keeper",
}


class SA20TeamsScraper:
    """Scraper for SA20 teams and players from official website."""

    base_url = "https://www.sa20.co.za"
    teams_url = "https://www.sa20.co.za/teams"

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

    def scrape_all_teams(self) -> List[Dict]:
        """Scrape all teams from the teams page."""
        try:
            response = self.session.get(self.teams_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            teams = []
            # Find team links/cards
            team_elements = soup.find_all(
                ["a", "div"],
                href=re.compile(r"/teams/", re.I),
                class_=re.compile(r"team", re.I),
            )

            # Also look for team names in various structures
            if not team_elements:
                team_elements = soup.find_all(["div", "article"], class_=re.compile(r"team", re.I))

            for element in team_elements:
                team = self._extract_team_info(element, soup)
                if team:
                    teams.append(team)

            # If no teams found, try to extract from text
            if not teams:
                teams = self._extract_teams_from_text(soup)

            logger.info(f"Found {len(teams)} teams")
            return teams

        except requests.RequestException as exc:
            logger.error(f"Failed to scrape teams: {exc}")
            return []

    def scrape_team_players(self, team_slug: str) -> List[Dict]:
        """Scrape players from a specific team page."""
        team_url = f"{self.base_url}/teams/{team_slug}"
        try:
            response = self.session.get(team_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            players = []
            # Look for player cards/listings
            player_elements = soup.find_all(
                ["div", "article", "li"],
                class_=re.compile(r"player|squad", re.I),
            )

            for element in player_elements:
                player = self._extract_player_info(element)
                if player:
                    players.append(player)

            # If no players found, try alternative structure
            if not players:
                players = self._extract_players_alternative(soup)

            logger.info(f"Found {len(players)} players for team {team_slug}")
            time.sleep(self.rate_limit_seconds)
            return players

        except requests.RequestException as exc:
            logger.error(f"Failed to scrape team {team_slug}: {exc}")
            return []

    def _extract_team_info(self, element, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract team information from an element."""
        try:
            # Get team name
            name_elem = element.find(["h2", "h3", "span", "div"], class_=re.compile(r"name|title", re.I))
            if not name_elem:
                name_elem = element.find("a")
            
            name = name_elem.get_text(strip=True) if name_elem else None
            if not name:
                return None

            # Get team link/slug
            link_elem = element.find("a", href=re.compile(r"/teams/"))
            slug = None
            if link_elem:
                href = link_elem.get("href", "")
                slug_match = re.search(r"/teams/([^/]+)", href)
                if slug_match:
                    slug = slug_match.group(1)

            # Get logo/image
            img_elem = element.find("img")
            logo_url = None
            if img_elem:
                logo_url = img_elem.get("src") or img_elem.get("data-src")
                if logo_url and not logo_url.startswith("http"):
                    logo_url = f"{self.base_url}{logo_url}"

            return {
                "name": name.strip(),
                "slug": slug or self._name_to_slug(name),
                "logo_url": logo_url,
            }
        except Exception as e:
            logger.warning(f"Error extracting team info: {e}")
            return None

    def _extract_teams_from_text(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract team names from page text as fallback."""
        teams = []
        # Known SA20 teams
        known_teams = [
            "Durban's Super Giants",
            "Joburg Super Kings",
            "MI Cape Town",
            "Paarl Royals",
            "Pretoria Capitals",
            "Sunrisers Eastern Cape",
        ]

        for team_name in known_teams:
            if team_name.lower() in soup.get_text().lower():
                teams.append({
                    "name": team_name,
                    "slug": self._name_to_slug(team_name),
                    "logo_url": None,
                })

        return teams

    def _extract_player_info(self, element) -> Optional[Dict]:
        """Extract player information from an element."""
        try:
            # Get player name
            name_elem = element.find(["h3", "h4", "span", "div"], class_=re.compile(r"name|player-name", re.I))
            if not name_elem:
                name_elem = element.find("a")

            name = name_elem.get_text(strip=True) if name_elem else None
            if not name:
                return None

            # Get player image
            img_elem = element.find("img")
            image_url = None
            if img_elem:
                image_url = img_elem.get("src") or img_elem.get("data-src") or img_elem.get("data-lazy-src")
                if image_url and not image_url.startswith("http"):
                    image_url = f"{self.base_url}{image_url}"

            # Get role
            role_elem = element.find(["span", "div"], class_=re.compile(r"role|position|type", re.I))
            role = None
            if role_elem:
                role_text = role_elem.get_text(strip=True).lower()
                role = self._normalize_role(role_text)

            # Get country/nationality
            country_elem = element.find(["span", "div"], class_=re.compile(r"country|nationality|flag", re.I))
            country = country_elem.get_text(strip=True) if country_elem else None

            return {
                "name": name.strip(),
                "role": role,
                "country": country or "South Africa",
                "image_url": image_url,
            }
        except Exception as e:
            logger.warning(f"Error extracting player info: {e}")
            return None

    def _extract_players_alternative(self, soup: BeautifulSoup) -> List[Dict]:
        """Alternative method to extract players if standard method fails."""
        players = []
        
        # Look for player names in various structures
        player_sections = soup.find_all(["section", "div"], class_=re.compile(r"squad|players|roster", re.I))
        
        for section in player_sections:
            player_items = section.find_all(["div", "li", "article"])
            for item in player_items:
                player = self._extract_player_info(item)
                if player:
                    players.append(player)

        return players

    def _normalize_role(self, role_text: str) -> str:
        """Normalize role text to our enum values."""
        role_lower = role_text.lower().strip()
        for key, value in ROLE_MAPPING.items():
            if key in role_lower:
                return value
        return "batsman"  # Default

    def _name_to_slug(self, name: str) -> str:
        """Convert team name to URL slug."""
        # Known team slugs
        slug_map = {
            "Durban's Super Giants": "durans-super-giants",
            "Joburg Super Kings": "joburg-super-kings",
            "MI Cape Town": "mi-cape-town",
            "Paarl Royals": "paarl-royals",
            "Pretoria Capitals": "pretoria-capitals",
            "Sunrisers Eastern Cape": "sunrisers-eastern-cape",
        }
        return slug_map.get(name, name.lower().replace(" ", "-").replace("'", ""))

