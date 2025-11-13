"""Script to scrape and update SA20 match results from official website."""
from __future__ import annotations

import asyncio
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright, Browser, Page
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Season ID mapping
SEASON_IDS = {
    2023: 7625,
    2024: 8001,
    2025: 8387,
}


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    return name.strip().lower().replace("'", "").replace(" ", "_")


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    return name.strip().lower().replace("'", "").replace(" ", "_")


def get_player_by_name(db: Session, name: str, team_id: Optional[int] = None) -> models.Player | None:
    """Get player from database by name (with fuzzy matching)."""
    normalized = normalize_player_name(name)
    
    # Try exact match first
    query = db.query(models.Player).filter(models.Player.name == name)
    if team_id:
        query = query.filter(models.Player.team_id == team_id)
    player = query.first()
    if player:
        return player
    
    # Try normalized match
    all_players = db.query(models.Player).all()
    if team_id:
        all_players = [p for p in all_players if p.team_id == team_id]
    
    for p in all_players:
        if normalize_player_name(p.name) == normalized:
            return p
    
    return None


def get_team_by_name(db: Session, name: str) -> models.Team | None:
    """Get team from database by name (with fuzzy matching)."""
    normalized = normalize_team_name(name)
    
    # Try exact match first
    team = db.query(models.Team).filter(models.Team.name == name).first()
    if team:
        return team
    
    # Try short name
    team = db.query(models.Team).filter(models.Team.short_name == name).first()
    if team:
        return team
    
    # Try normalized match
    all_teams = db.query(models.Team).all()
    for t in all_teams:
        if normalize_team_name(t.name) == normalized or normalize_team_name(t.short_name or "") == normalized:
            return t
    
    return None


def parse_score(score_text: str) -> tuple[int, int, Optional[int]]:
    """
    Parse score text like '181/8(20/20 ov)' or '105 (18.4/20 ov, target: 182)'
    Returns: (runs, wickets, overs_used)
    """
    runs = 0
    wickets = 0
    overs = None
    
    # Extract runs/wickets
    match = re.search(r'(\d+)/(\d+)', score_text)
    if match:
        runs = int(match.group(1))
        wickets = int(match.group(2))
    
    # Extract overs (optional)
    overs_match = re.search(r'\((\d+(?:\.\d+)?)/(\d+)', score_text)
    if overs_match:
        overs = float(overs_match.group(1))
    
    return runs, wickets, overs


def parse_match_result(result_text: str) -> Dict:
    """
    Parse result text like 'MI Cape Town win by 76 runs' or 'Sunrisers Eastern Cape win by 8 wickets'
    Returns: {winner_name, margin_type, margin_value}
    """
    result = {
        "winner_name": None,
        "margin_type": None,
        "margin_value": None,
        "margin_text": result_text
    }
    
    # Pattern: "Team Name win by X runs/wickets"
    match = re.search(r'(.+?)\s+win\s+by\s+(\d+)\s+(runs?|wickets?)', result_text, re.IGNORECASE)
    if match:
        result["winner_name"] = match.group(1).strip()
        result["margin_value"] = int(match.group(2))
        margin_type = match.group(3).lower()
        result["margin_type"] = "runs" if "run" in margin_type else "wickets"
    
    # Pattern: "No result" or "Tied"
    elif "no result" in result_text.lower():
        result["margin_text"] = "No result"
    elif "tied" in result_text.lower() or "tie" in result_text.lower():
        result["margin_text"] = "Tied"
    
    return result


async def scrape_match_results(season: Optional[int] = None) -> List[Dict]:
    """Scrape match results from SA20 website."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Capture API responses
        api_responses = []
        
        async def handle_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')
            if content_type.startswith('application/json') or 'json' in url.lower():
                try:
                    data = await response.json()
                    api_responses.append({
                        'url': url,
                        'data': data,
                        'content_type': content_type
                    })
                except Exception:
                    pass
        
        page.on('response', handle_response)
        
        try:
            url = "https://www.sa20.co.za/matches/results"
            logger.info(f"Scraping match results from {url}")
            logger.info("Loading page...")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                logger.info("Page loaded, waiting for content...")
                await page.wait_for_timeout(3000)  # Wait for content to load
            except Exception as e:
                logger.warning(f"Page load issue: {e}, continuing anyway...")
                try:
                    await page.goto(url, wait_until="load", timeout=20000)
                    await page.wait_for_timeout(2000)
                except Exception as e2:
                    logger.error(f"Failed to load page: {e2}")
                    raise
            
            # Scroll to load all matches
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(3000)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(3000)
            
            # Try to find season filter and select it if needed
            if season:
                try:
                    # Look for season filter dropdown or buttons
                    season_selectors = [
                        f"button:has-text('{season}')",
                        f"select option:has-text('{season}')",
                        f"[data-season='{season}']",
                        f".season-filter:has-text('{season}')"
                    ]
                    for selector in season_selectors:
                        try:
                            element = await page.query_selector(selector)
                            if element:
                                await element.click()
                                await page.wait_for_timeout(3000)
                                logger.info(f"Selected season {season}")
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"Could not select season {season}: {e}")
            
            # Check API responses for match data
            matches = []
            for resp in api_responses:
                data = resp.get('data', {})
                if isinstance(data, dict) and ('match' in str(data).lower() or 'result' in str(data).lower()):
                    extracted = extract_matches_from_json(data)
                    if extracted:
                        matches.extend(extracted)
            
            # If no matches from API, extract from page
            if not matches:
                # Look for match cards/containers
                match_cards = await page.query_selector_all(
                    '[class*="match"], [class*="result"], article, .match-card, .result-card, [data-testid*="match"]'
                )
                
                if not match_cards:
                    # Try alternative selectors
                    match_cards = await page.query_selector_all('div:has-text("MATCH"), div:has-text("win by")')
                
                logger.info(f"Found {len(match_cards)} potential match elements")
                
                if match_cards and len(match_cards) >= 5:
                    matches = await extract_matches_from_cards(page, match_cards)
                else:
                    matches = await extract_matches_from_page_text(page)
            
            # Filter by season if specified
            if season and matches:
                filtered_matches = []
                for match in matches:
                    date_str = match.get("date_text") or match.get("date")
                    if date_str:
                        match_date = parse_date(date_str, year=season)
                        if match_date and match_date.year == season:
                            filtered_matches.append(match)
                    else:
                        # If no date, include it (might be from the right season)
                        filtered_matches.append(match)
                matches = filtered_matches
            
            await browser.close()
            logger.info(f"Extracted {len(matches)} matches")
            return matches
            
        except Exception as e:
            logger.error(f"Error scraping match results: {e}", exc_info=True)
            await browser.close()
            return []


async def extract_matches_from_page_text(page: Page) -> List[Dict]:
    """Extract match information from page text content."""
    matches = []
    
    try:
        # Get all text content
        content = await page.content()
        
        # Look for match patterns in the HTML
        # Pattern: MATCH X, date, teams, scores, result
        match_pattern = re.compile(
            r'MATCH\s+(\d+).*?'
            r'(\w+day,\s+\d+\s+\w+\s+\d{4})|(\d{1,2}\s+\w+\s+\d{4})|(\w+day,\s+\d+\s+\w+)'
            r'.*?'
            r'([A-Z][a-zA-Z\s\']+?)\s+(?:\d+/\d+.*?)?\s*(?:vs|v\.?)\s*([A-Z][a-zA-Z\s\']+?)(?:\s+\d+/\d+.*?)?'
            r'.*?'
            r'(\d+/\d+.*?\(.*?\))'
            r'.*?'
            r'(\d+/\d+.*?\(.*?\))'
            r'.*?'
            r'([A-Z][a-zA-Z\s\']+?)\s+win\s+by\s+(\d+)\s+(runs?|wickets?)',
            re.DOTALL | re.IGNORECASE
        )
        
        matches_found = match_pattern.findall(content)
        logger.info(f"Found {len(matches_found)} matches via regex")
        
        # Alternative: Extract from structured data if available
        # Try to find JSON data in script tags
        script_tags = await page.query_selector_all('script[type="application/json"], script:not([src])')
        for script in script_tags:
            try:
                script_content = await script.inner_text()
                if 'match' in script_content.lower() and 'result' in script_content.lower():
                    import json
                    data = json.loads(script_content)
                    # Process JSON data structure
                    matches.extend(extract_matches_from_json(data))
            except Exception:
                pass
        
    except Exception as e:
        logger.error(f"Error extracting matches from page text: {e}")
    
    return matches


async def extract_matches_from_cards(page: Page, cards: List) -> List[Dict]:
    """Extract match information from match card elements, including Match Centre links."""
    matches = []
    
    # Known team names for validation
    known_teams = [
        "MI Cape Town", "Paarl Royals", "Pretoria Capitals", 
        "Durban's Super Giants", "Joburg Super Kings", "Sunrisers Eastern Cape"
    ]
    
    for card in cards[:100]:  # Limit to first 100 to avoid timeout
        try:
            card_text = await card.inner_text()
            
            # Skip if card doesn't contain match-related keywords
            if not any(keyword in card_text.lower() for keyword in ['match', 'win', 'runs', 'wickets', 'vs']):
                continue
            
            # Extract match number
            match_no_match = re.search(r'MATCH\s+(\d+)', card_text, re.IGNORECASE)
            match_number = int(match_no_match.group(1)) if match_no_match else None
            
            # Extract date - look for date patterns
            date_patterns = [
                r'(\w+day,\s+\d+\s+\w+\s+\d{4})',  # Friday, 31 January 2025
                r'(\d{1,2}\s+\w+\s+\d{4})',        # 31 January 2025
                r'(\w+day,\s+\d+\s+\w+)',          # Friday, 31 January
            ]
            date_str = None
            for pattern in date_patterns:
                date_match = re.search(pattern, card_text)
                if date_match:
                    date_str = date_match.group(1)
                    break
            
            # Extract result line first (e.g., "MI Cape Town win by 76 runs")
            result_match = re.search(
                r'([A-Z][a-zA-Z\s\']+?)\s+win\s+by\s+(\d+)\s+(runs?|wickets?)',
                card_text,
                re.IGNORECASE
            )
            
            # Remove result line from card text to avoid confusion
            card_text_clean = card_text
            if result_match:
                # Remove the result line from the text
                result_line = result_match.group(0)
                card_text_clean = card_text_clean.replace(result_line, "")
            
            # Extract team names and scores more carefully
            # Look for patterns like: "Team Name\n181/8(20/20 ov)"
            lines = card_text_clean.split('\n')
            team1_name = None
            team1_score = None
            team2_name = None
            team2_score = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Skip lines that contain result text
                if "win by" in line.lower() or "runs" in line.lower() and "wickets" not in line.lower():
                    continue
                
                # Check if line contains a score pattern
                score_match = re.search(r'(\d+/\d+.*?\([^)]+\))', line)
                if score_match:
                    score_text = score_match.group(1)
                    # Look backwards for team name (up to 5 lines back)
                    for j in range(max(0, i-5), i):
                        potential_team = lines[j].strip()
                        # Skip if it contains result text
                        if "win by" in potential_team.lower():
                            continue
                        # Validate it's a known team (exact match or contains team name)
                        for known_team in known_teams:
                            # Check if the line is exactly the team name or starts with it
                            if potential_team == known_team or potential_team.startswith(known_team):
                                # Make sure it's not part of a longer sentence
                                if len(potential_team) <= len(known_team) + 5:  # Allow small variations
                                    if not team1_name:
                                        team1_name = known_team  # Use the known team name, not the extracted one
                                        team1_score = score_text
                                        break
                                    elif not team2_name and known_team != team1_name:
                                        team2_name = known_team
                                        team2_score = score_text
                                        break
                        if team1_name and (team2_name or potential_team == team1_name):
                            break
                
                # Also check if line itself is a team name with score
                for known_team in known_teams:
                    if known_team in line and re.search(r'\d+/\d+', line):
                        # Extract just the team name part before the score
                        parts = re.split(r'(\d+/\d+.*?\([^)]+\))', line)
                        if len(parts) >= 2:
                            team_part = parts[0].strip()
                            score_part = parts[1]
                            # Check if team_part contains the known team name
                            if known_team in team_part:
                                if not team1_name:
                                    team1_name = known_team
                                    team1_score = score_part
                                elif not team2_name and known_team != team1_name:
                                    team2_name = known_team
                                    team2_score = score_part
                                break
            
            # Look for "Match Centre" link and extract match_id
            match_centre_link = None
            match_id = None
            try:
                link_elements = await card.query_selector_all("a:has-text('Match Centre'), a[href*='match'], a[href*='scorecard']")
                for link in link_elements:
                    href = await link.get_attribute("href")
                    if href:
                        if not href.startswith("http"):
                            href = f"https://www.sa20.co.za{href}"
                        match_centre_link = href
                        
                        # Extract match_id from URL pattern: /matches/{season_id}/{match_id}
                        # Pattern: /matches/7625/214819 or /matches/8001/217697
                        match_url_pattern = re.search(r'/matches/(\d+)/(\d+)', href)
                        if match_url_pattern:
                            match_id = int(match_url_pattern.group(2))
                            logger.debug(f"Extracted match_id {match_id} from URL: {href}")
                        break
            except Exception as e:
                logger.debug(f"Error extracting match centre link: {e}")
                pass
            
            # If we found both teams and scores, create match data
            if team1_name and team1_score and team2_name and team2_score:
                match_data = {
                    "match_number": match_number,
                    "date_text": date_str,
                    "team1_name": team1_name,
                    "team1_score": team1_score,
                    "team2_name": team2_name,
                    "team2_score": team2_score,
                    "match_centre_url": match_centre_link,
                    "match_id": match_id,  # The unique match ID from the URL
                }
                
                if result_match:
                    winner_text = result_match.group(1).strip()
                    # Find the matching known team name
                    winner_team = None
                    for known_team in known_teams:
                        if known_team in winner_text or winner_text in known_team:
                            winner_team = known_team
                            break
                    
                    if winner_team:
                        match_data["winner"] = winner_team
                        match_data["margin"] = f"{result_match.group(2)} {result_match.group(3)}"
                    elif "no result" in card_text.lower():
                        match_data["result"] = "No result"
                    elif "tied" in card_text.lower():
                        match_data["result"] = "Tied"
                
                matches.append(match_data)
                logger.debug(f"Extracted match: {team1_name} vs {team2_name}")
        
        except Exception as e:
            logger.debug(f"Error extracting from card: {e}")
            continue
    
    return matches


def extract_matches_from_json(data: Dict) -> List[Dict]:
    """Extract matches from JSON data structure."""
    matches = []
    
    def extract_recursive(obj, path=""):
        """Recursively search for match data in JSON."""
        if isinstance(obj, dict):
            # Check if this looks like a match object
            if all(key in obj for key in ['home_team', 'away_team', 'score']):
                matches.append(obj)
            elif 'matches' in obj:
                if isinstance(obj['matches'], list):
                    matches.extend(obj['matches'])
                else:
                    extract_recursive(obj['matches'], f"{path}.matches")
            elif 'results' in obj:
                if isinstance(obj['results'], list):
                    matches.extend(obj['results'])
                else:
                    extract_recursive(obj['results'], f"{path}.results")
            else:
                for key, value in obj.items():
                    extract_recursive(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for item in obj:
                extract_recursive(item, path)
    
    extract_recursive(data)
    return matches


def parse_date(date_str: str, year: Optional[int] = None) -> Optional[datetime]:
    """Parse date string to datetime."""
    if not date_str:
        return None
    
    # Common date formats
    date_formats = [
        "%A, %d %B %Y",  # Friday, 31 January 2025
        "%d %B %Y",      # 31 January 2025
        "%A, %d %B",     # Friday, 31 January (needs year)
        "%B %d, %Y",     # January 31, 2025
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if year and dt.year == 1900:  # Year not parsed
                dt = dt.replace(year=year)
            return dt
        except ValueError:
            continue
    
    # Try fuzzy parsing
    try:
        from dateutil import parser
        dt = parser.parse(date_str)
        if year:
            dt = dt.replace(year=year)
        return dt
    except Exception:
        pass
    
    return None


async def scrape_match_scorecard(page: Page, match_centre_url: str) -> List[Dict]:
    """Scrape player performance data from match scorecard."""
    performances = []
    
    try:
        # Ensure URL has tab=1 parameter for scorecard
        if "?tab=" not in match_centre_url:
            if "?" in match_centre_url:
                match_centre_url = f"{match_centre_url}&tab=1"
            else:
                match_centre_url = f"{match_centre_url}?tab=1"
        
        logger.info(f"Navigating to scorecard: {match_centre_url}")
        try:
            response = await page.goto(match_centre_url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status >= 400:
                logger.warning(f"Page returned status {response.status} for {match_centre_url}")
                return []
        except Exception as e:
            logger.warning(f"Failed to load page {match_centre_url}: {e}")
            return []
        
        await page.wait_for_timeout(3000)  # Wait for content to load
        
        # Check if we're on the right page
        page_title = await page.title()
        page_url = page.url
        logger.debug(f"Page title: {page_title}, URL: {page_url}")
        
        # Check if page contains scorecard content
        page_text = await page.inner_text("body")
        if "scorecard" not in page_text.lower() and "runs" not in page_text.lower():
            logger.warning(f"Page doesn't seem to contain scorecard data: {match_centre_url}")
            # Try without tab parameter first, then add it
            if "?tab=1" in match_centre_url:
                base_url = match_centre_url.split("?")[0]
                logger.info(f"Trying base URL: {base_url}")
                try:
                    await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    # Now try to click scorecard tab
                except:
                    pass
        
        # If tab=1 is in URL, scorecard should already be visible
        # But try clicking the tab if it exists to ensure it's loaded
        scorecard_selectors = [
            "button:has-text('Scorecard')",
            "a:has-text('Scorecard')",
            "[data-tab='1']",
            "[data-tab='scorecard']",
            ".tab:has-text('Scorecard')",
            "li:has-text('Scorecard')",
            "div[role='tab']:has-text('Scorecard')",
        ]
        
        scorecard_clicked = False
        for selector in scorecard_selectors:
            try:
                scorecard_tab = await page.query_selector(selector)
                if scorecard_tab:
                    await scorecard_tab.click()
                    await page.wait_for_timeout(3000)  # Wait longer for content to load
                    scorecard_clicked = True
                    logger.debug("Clicked Scorecard tab")
                    break
            except Exception as e:
                logger.debug(f"Could not click scorecard tab with selector {selector}: {e}")
                continue
        
        # Wait for scorecard content to load (might be loaded via API)
        await page.wait_for_timeout(3000)
        
        # Try waiting for specific elements that indicate scorecard is loaded
        try:
            # Wait for batting or bowling table to appear
            await page.wait_for_selector("table", timeout=10000)
        except Exception:
            logger.debug("No tables found after waiting")
        
        # Extract batting and bowling stats
        # Wait a bit more for tables to render
        await page.wait_for_timeout(2000)
        
        # Scroll to ensure content is loaded
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)
        
        # Look for scorecard sections (they use divs, not tables)
        scorecard_sections = await page.query_selector_all(
            "[class*='scorecard'], [class*='batting'], [class*='bowling'], section, div[class*='innings']"
        )
        logger.info(f"Found {len(scorecard_sections)} scorecard sections")
        
        # Also get tables as fallback
        all_tables = await page.query_selector_all("table")
        logger.debug(f"Found {len(all_tables)} tables on the page")
        
        # Process scorecard sections first (div-based)
        for section in scorecard_sections:
            try:
                section_text = await section.inner_text()
                
                # Check if this is a batting section
                if "batting" in section_text.lower()[:50] or ("runs" in section_text.lower() and "balls" in section_text.lower() and "batter" not in section_text.lower()[:100]):
                    logger.debug(f"Found batting section")
                    
                    # The section contains all text with newlines - parse it line by line
                    lines = [l.strip() for l in section_text.split('\n') if l.strip()]
                    
                    # Skip header lines
                    header_keywords = ["batting", "r", "b", "4s", "6s", "sr", "runs", "balls", "strike rate"]
                    skip_until_data = True
                    
                    i = 0
                    while i < len(lines):
                        line = lines[i]
                        
                        # Skip header
                        if skip_until_data and any(kw in line.lower() for kw in header_keywords):
                            i += 1
                            continue
                        skip_until_data = False
                        
                        # Check if this line looks like a player name (starts with capital letter, has at least 2 words)
                        if re.match(r'^[A-Z][a-zA-Z\s]+$', line) and len(line.split()) >= 2:
                            # This is a player name
                            player_name = line
                            
                            # Pattern: name, dismissal, [optional: C/WK], runs, balls, 4s, 6s, SR
                            # Check next lines for stats
                            if i + 1 < len(lines):
                                # Next line is dismissal (skip it)
                                dismissal_line = lines[i + 1]
                                
                                # Find the first numeric line after dismissal (skipping optional C/WK/etc)
                                stats_start_idx = i + 2
                                while stats_start_idx < len(lines) and not re.match(r'^\d+$', lines[stats_start_idx]):
                                    stats_start_idx += 1
                                
                                if stats_start_idx + 3 < len(lines):
                                    # Lines after optional indicators: runs, balls, 4s, 6s
                                    runs_line = lines[stats_start_idx] if stats_start_idx < len(lines) else ""
                                    balls_line = lines[stats_start_idx + 1] if stats_start_idx + 1 < len(lines) else ""
                                    fours_line = lines[stats_start_idx + 2] if stats_start_idx + 2 < len(lines) else ""
                                    sixes_line = lines[stats_start_idx + 3] if stats_start_idx + 3 < len(lines) else ""
                                    
                                    # Extract numbers
                                    runs = 0
                                    balls = 0
                                    fours = 0
                                    sixes = 0
                                    
                                    # Runs
                                    runs_match = re.search(r'^\d+$', runs_line)
                                    if runs_match:
                                        runs = int(runs_match.group(0))
                                    
                                    # Balls
                                    balls_match = re.search(r'^\d+$', balls_line)
                                    if balls_match:
                                        balls = int(balls_match.group(0))
                                    
                                    # Fours
                                    fours_match = re.search(r'^\d+$', fours_line)
                                    if fours_match:
                                        fours = int(fours_match.group(0))
                                    
                                    # Sixes
                                    sixes_match = re.search(r'^\d+$', sixes_line)
                                    if sixes_match:
                                        sixes = int(sixes_match.group(0))
                                    
                                    # Only add if we found valid stats (runs or balls)
                                    if runs > 0 or balls > 0:
                                        existing = next((p for p in performances if p.get("player_name") == player_name), None)
                                        if not existing:
                                            performances.append({
                                                "player_name": player_name,
                                                "runs_scored": runs,
                                                "balls_faced": balls,
                                                "fours": fours,
                                                "sixes": sixes,
                                                "type": "batting"
                                            })
                                            logger.debug(f"Extracted batting: {player_name} - {runs}({balls})")
                                        # Move past this player's stats (name, dismissal, optional, runs, balls, 4s, 6s, SR)
                                        i = stats_start_idx + 5  # Skip to after SR
                                        continue
                        
                        i += 1
                
                # Check if this is a bowling section
                elif "bowling" in section_text.lower()[:50] or ("overs" in section_text.lower() and "wickets" in section_text.lower()):
                    logger.debug(f"Found bowling section")
                    
                    # Parse line by line similar to batting
                    lines = [l.strip() for l in section_text.split('\n') if l.strip()]
                    
                    header_keywords = ["bowling", "o", "m", "r", "w", "econ", "overs", "wickets", "economy", "maidens"]
                    skip_until_data = True
                    
                    i = 0
                    while i < len(lines):
                        line = lines[i]
                        
                        # Skip header
                        if skip_until_data and any(kw in line.lower() for kw in header_keywords):
                            i += 1
                            continue
                        skip_until_data = False
                        
                        # Check if this line looks like a player name
                        if re.match(r'^[A-Z][a-zA-Z\s]+$', line) and len(line.split()) >= 2:
                            player_name = line
                            
                            # Pattern: name, O, M, R, W, ECON, NB, WD
                            # Check next lines for stats
                            if i + 6 < len(lines):
                                overs_line = lines[i + 1] if i + 1 < len(lines) else ""
                                maidens_line = lines[i + 2] if i + 2 < len(lines) else ""
                                runs_line = lines[i + 3] if i + 3 < len(lines) else ""
                                wickets_line = lines[i + 4] if i + 4 < len(lines) else ""
                                
                                overs = 0.0
                                runs_conceded = 0
                                wickets = 0
                                
                                # Overs (decimal)
                                overs_match = re.search(r'^\d+\.?\d*$', overs_line)
                                if overs_match:
                                    overs = float(overs_match.group(0))
                                
                                # Runs conceded
                                runs_match = re.search(r'^\d+$', runs_line)
                                if runs_match:
                                    runs_conceded = int(runs_match.group(0))
                                
                                # Wickets
                                wickets_match = re.search(r'^\d+$', wickets_line)
                                if wickets_match:
                                    wickets = int(wickets_match.group(0))
                                
                                # Only add if we found valid stats
                                if overs > 0 or wickets > 0:
                                    perf = next((p for p in performances if p.get("player_name") == player_name), None)
                                    if perf:
                                        perf["overs_bowled"] = overs
                                        perf["runs_conceded"] = runs_conceded
                                        perf["wickets_taken"] = wickets
                                        perf["type"] = "all_rounder"
                                        logger.debug(f"Updated with bowling: {player_name} - {wickets}/{runs_conceded} ({overs}ov)")
                                    else:
                                        performances.append({
                                            "player_name": player_name,
                                            "overs_bowled": overs,
                                            "runs_conceded": runs_conceded,
                                            "wickets_taken": wickets,
                                            "type": "bowling"
                                        })
                                        logger.debug(f"Extracted bowling: {player_name} - {wickets}/{runs_conceded} ({overs}ov)")
                                    # Move past this player's stats (O, M, R, W, ECON, NB, WD = 7 lines)
                                    i += 7
                                    continue
                        
                        i += 1
            except Exception as e:
                logger.debug(f"Error extracting from section: {e}")
                continue
        
        # Also try tables as fallback
        for table in all_tables:
            try:
                table_text = await table.inner_text()
                
                # Skip if we already processed this in sections
                if any(keyword in table_text.lower() for keyword in ["date", "venue", "toss", "umpire"]):
                    continue
                
                # Check if this is a batting or bowling table
                if any(keyword in table_text.lower() for keyword in ["runs", "balls", "batter"]):
                    rows = await table.query_selector_all("tr")
                    for row in rows:
                        try:
                            cells = await row.query_selector_all("td, th")
                            if len(cells) >= 3:
                                cell_texts = [await c.inner_text() for c in cells]
                                player_name = cell_texts[0].strip()
                                if player_name and player_name.lower() not in ["batting", "r", "b", "4s", "6s", "sr"]:
                                    # Similar extraction logic as above
                                    pass  # Will be handled by section extraction
                        except:
                            continue
            except Exception as e:
                logger.debug(f"Error extracting from table: {e}")
                continue
        
        logger.info(f"Extracted {len(performances)} player performances from scorecard")
        
    except Exception as e:
        logger.warning(f"Error scraping scorecard from {match_centre_url}: {e}")
    
    return performances


async def update_match_results(db: Session, season: Optional[int] = None, scrape_scorecards: bool = True) -> int:
    """Scrape and update match results in database."""
    logger.info(f"Scraping match results for season {season or 'all'}")
    
    matches = await scrape_match_results(season=season)
    
    if not matches:
        logger.warning("No matches found from scraper")
        return 0
    
    logger.info(f"Found {len(matches)} match results")
    
    updated_count = 0
    created_count = 0
    skipped_count = 0
    
    # Store match_id mapping for scorecard scraping: {match_db_id: match_id_from_url}
    match_id_map = {}
    
    for match_data in matches:
        try:
            # Parse teams - clean the names first
            team1_name = match_data.get("team1_name") or match_data.get("home_team")
            team2_name = match_data.get("team2_name") or match_data.get("away_team")
            
            if not team1_name or not team2_name:
                logger.warning(f"Skipping match with missing team names: {match_data}")
                skipped_count += 1
                continue
            
            # Clean team names - remove any result text that might have been included
            team1_name = team1_name.split(" win by")[0].strip()
            team2_name = team2_name.split(" win by")[0].strip()
            team1_name = team1_name.split(" vs ")[0].strip()
            team2_name = team2_name.split(" vs ")[0].strip()
            
            team1 = get_team_by_name(db, team1_name)
            team2 = get_team_by_name(db, team2_name)
            
            if not team1 or not team2:
                logger.warning(f"Teams not found: {team1_name} vs {team2_name}")
                skipped_count += 1
                continue
            
            # Parse date
            date_str = match_data.get("date_text") or match_data.get("date")
            match_date = parse_date(date_str, year=season)
            
            if not match_date:
                # Try to infer from match number and season
                if season:
                    # SA20 typically runs Jan-Feb, so assume matches are in that range
                    match_date = datetime(season, 1, 10)  # Default to mid-January
                else:
                    logger.warning(f"Could not parse date for match: {match_data}")
                    skipped_count += 1
                    continue
            
            # Find or create match
            match_number = match_data.get("match_number")
            existing_match = None
            
            if match_number:
                existing_match = db.query(models.Match).filter(
                    models.Match.season == (season or match_date.year),
                    models.Match.match_number == match_number
                ).first()
            
            if not existing_match:
                # Try to find by teams and date
                existing_match = db.query(models.Match).filter(
                    ((models.Match.home_team_id == team1.id) & (models.Match.away_team_id == team2.id)) |
                    ((models.Match.home_team_id == team2.id) & (models.Match.away_team_id == team1.id)),
                    models.Match.match_date == match_date
                ).first()
            
            if not existing_match:
                # Create new match
                # Determine home/away (use team1 as home for now)
                existing_match = models.Match(
                    home_team_id=team1.id,
                    away_team_id=team2.id,
                    venue_id=1,  # Default venue, should be updated
                    match_date=match_date,
                    season=season or match_date.year,
                    match_number=match_number,
                )
                db.add(existing_match)
                db.flush()
                created_count += 1
                logger.info(f"Created match: {team1.name} vs {team2.name} on {match_date}")
            
            # Update match result
            winner_name = match_data.get("winner")
            if winner_name:
                winner = get_team_by_name(db, winner_name)
                if winner:
                    existing_match.winner_id = winner.id
                    existing_match.winner_team_id = winner.id
            
            # Parse scores
            team1_score_text = match_data.get("team1_score") or ""
            team2_score_text = match_data.get("team2_score") or ""
            
            if team1_score_text:
                runs1, wickets1, _ = parse_score(team1_score_text)
            if team2_score_text:
                runs2, wickets2, _ = parse_score(team2_score_text)
            
            # Update margin
            margin = match_data.get("margin") or match_data.get("result")
            if margin:
                existing_match.margin = margin
                existing_match.margin_text = margin
            
            result = match_data.get("result")
            if result:
                existing_match.result = result
            
            # Determine status
            if winner_name:
                existing_match.status = "completed"
            elif "no result" in (result or "").lower():
                existing_match.status = "no_result"
            elif "tied" in (result or "").lower():
                existing_match.status = "tied"
            
            updated_count += 1
            
            # Store match_id for scorecard scraping
            match_id_from_data = match_data.get("match_id")
            if match_id_from_data and existing_match:
                # Map database match ID to the URL match_id for scorecard scraping
                match_id_map[existing_match.id] = {
                    "match_id": match_id_from_data,
                    "season": season or existing_match.season,
                }
            
        except Exception as e:
            logger.error(f"Error processing match result: {e}", exc_info=True)
            skipped_count += 1
            continue
    
    db.commit()
    logger.info(f"✓ Updated {updated_count} matches, created {created_count}, skipped {skipped_count}")
    
    # Scrape scorecards in a separate pass if requested
    if scrape_scorecards and match_id_map:
        logger.info(f"Scraping player scorecards for completed matches (found {len(match_id_map)} match IDs)...")
        scorecard_count = await scrape_all_scorecards(db, season=season, match_id_map=match_id_map)
        logger.info(f"✓ Scraped scorecards for {scorecard_count} matches")
    elif scrape_scorecards:
        logger.warning("No match IDs found, cannot scrape scorecards. Re-running results scraper may help.")
    
    return updated_count + created_count


async def scrape_all_scorecards(db: Session, season: Optional[int] = None, match_id_map: Optional[Dict[int, Dict]] = None) -> int:
    """Scrape player performance data from scorecards for all completed matches."""
    from playwright.async_api import async_playwright
    
    # Get all completed matches for the season
    query = db.query(models.Match).filter(
        models.Match.status == "completed",
        models.Match.winner_id.isnot(None)
    )
    if season:
        query = query.filter(models.Match.season == season)
    
    matches = query.all()
    logger.info(f"Found {len(matches)} completed matches to scrape scorecards for")
    
    if not matches:
        return 0
    
    scorecard_count = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        for match in matches:
            try:
                # Get season_id for this match's season
                season_id = SEASON_IDS.get(match.season)
                if not season_id:
                    logger.warning(f"No season_id mapping for season {match.season}, skipping match {match.id}")
                    continue
                
                # Get match_id from the map if available
                match_id = None
                if match_id_map and match.id in match_id_map:
                    match_id = match_id_map[match.id]["match_id"]
                    logger.debug(f"Using stored match_id {match_id} for match {match.id}")
                else:
                    # Try to find match_id by going to results page
                    logger.info(f"Match ID not found in map for match {match.id}, searching results page...")
                    try:
                        results_url = "https://www.sa20.co.za/matches/results"
                        await page.goto(results_url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(3000)
                        
                        # Select the season
                        if match.season in SEASON_IDS:
                            season_selectors = [
                                f"button:has-text('{match.season}')",
                                f"select option:has-text('{match.season}')",
                                f"[data-season='{match.season}']",
                            ]
                            for selector in season_selectors:
                                try:
                                    element = await page.query_selector(selector)
                                    if element:
                                        await element.click()
                                        await page.wait_for_timeout(2000)
                                        break
                                except:
                                    continue
                        
                        # Look for the match by match number
                        if match.match_number:
                            # Search for match card with this match number
                            all_cards = await page.query_selector_all("div, article, section, [class*='match'], [class*='card']")
                            for card in all_cards[:200]:  # Limit search
                                try:
                                    card_text = await card.inner_text()
                                    if f"MATCH {match.match_number}" in card_text.upper():
                                        # Found the match card, extract the match centre link
                                        link = await card.query_selector("a[href*='match'], a:has-text('Match Centre')")
                                        if link:
                                            href = await link.get_attribute("href")
                                            if href:
                                                if not href.startswith("http"):
                                                    href = f"https://www.sa20.co.za{href}"
                                                # Extract match_id from URL
                                                match_url_pattern = re.search(r'/matches/(\d+)/(\d+)', href)
                                                if match_url_pattern:
                                                    match_id = int(match_url_pattern.group(2))
                                                    logger.info(f"Found match_id {match_id} for match {match.match_number}")
                                                    break
                                except:
                                    continue
                    except Exception as e:
                        logger.debug(f"Could not find match_id from results page: {e}")
                
                # Construct scorecard URL using season_id and match_id
                if match_id:
                    match_centre_url = f"https://www.sa20.co.za/matches/{season_id}/{match_id}?tab=1"
                else:
                    # Fallback: try using match.id as match_id (unlikely to work)
                    logger.warning(f"Could not find match_id for match {match.id}, using match.id as fallback")
                    match_centre_url = f"https://www.sa20.co.za/matches/{season_id}/{match.id}?tab=1"
                
                logger.info(f"Scraping scorecard for match {match.id} (Match {match.match_number}, season {match.season}): {match_centre_url}")
                
                # Scrape scorecard
                performances = await scrape_match_scorecard(page, match_centre_url)
                
                if not performances:
                    logger.warning(f"No performances found for match {match.id}")
                    continue
                
                # Save player performances
                saved_count = 0
                for perf_data in performances:
                    player_name = perf_data.get("player_name")
                    if not player_name:
                        continue
                    
                    # Determine which team the player belongs to
                    # For now, try to find player in either team
                    player = get_player_by_name(db, player_name, team_id=match.home_team_id)
                    if not player:
                        player = get_player_by_name(db, player_name, team_id=match.away_team_id)
                    if not player:
                        # Try without team filter
                        player = get_player_by_name(db, player_name)
                    
                    if not player:
                        logger.debug(f"Player not found: {player_name}")
                        continue
                    
                    # Determine team_id
                    team_id = player.team_id
                    if not team_id:
                        # Default to home team if player has no team
                        team_id = match.home_team_id
                    
                    # Check if performance already exists
                    existing_perf = db.query(models.PlayerPerformance).filter(
                        models.PlayerPerformance.player_id == player.id,
                        models.PlayerPerformance.match_id == match.id
                    ).first()
                    
                    if existing_perf:
                        # Update existing performance
                        existing_perf.runs_scored = perf_data.get("runs_scored", 0)
                        existing_perf.balls_faced = perf_data.get("balls_faced", 0)
                        existing_perf.fours = perf_data.get("fours", 0)
                        existing_perf.sixes = perf_data.get("sixes", 0)
                        existing_perf.overs_bowled = perf_data.get("overs_bowled", 0.0)
                        existing_perf.runs_conceded = perf_data.get("runs_conceded", 0)
                        existing_perf.wickets_taken = perf_data.get("wickets_taken", 0)
                        existing_perf.team_id = team_id
                    else:
                        # Create new performance
                        new_perf = models.PlayerPerformance(
                            player_id=player.id,
                            match_id=match.id,
                            team_id=team_id,
                            runs_scored=perf_data.get("runs_scored", 0),
                            balls_faced=perf_data.get("balls_faced", 0),
                            fours=perf_data.get("fours", 0),
                            sixes=perf_data.get("sixes", 0),
                            overs_bowled=perf_data.get("overs_bowled", 0.0),
                            runs_conceded=perf_data.get("runs_conceded", 0),
                            wickets_taken=perf_data.get("wickets_taken", 0),
                        )
                        db.add(new_perf)
                    
                    saved_count += 1
                
                if saved_count > 0:
                    db.commit()
                    scorecard_count += 1
                    logger.info(f"Saved {saved_count} performances for match {match.id}")
                
                # Small delay between matches
                await page.wait_for_timeout(1000)
                
            except Exception as e:
                logger.warning(f"Error scraping scorecard for match {match.id}: {e}")
                continue
        
        await browser.close()
    
    return scorecard_count


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape and update SA20 match results")
    parser.add_argument("--season", type=int, help="Season year (2023, 2024, or 2025)")
    parser.add_argument("--all-seasons", action="store_true", help="Scrape all seasons (2023-2025)")
    parser.add_argument("--scorecards", action="store_true", default=True, help="Also scrape player scorecards (default: True)")
    parser.add_argument("--no-scorecards", dest="scorecards", action="store_false", help="Skip scraping player scorecards")
    args = parser.parse_args()
    
    db: Session = SessionLocal()
    try:
        if args.all_seasons:
            total_updated = 0
            for season in [2023, 2024, 2025]:
                logger.info(f"\n=== Scraping season {season} ===")
                updated = asyncio.run(update_match_results(db, season=season, scrape_scorecards=args.scorecards))
                total_updated += updated
            logger.info(f"\n✓ Total matches updated: {total_updated}")
        else:
            season = args.season
            asyncio.run(update_match_results(db, season=season, scrape_scorecards=args.scorecards))
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating match results: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

