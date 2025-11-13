"""Playwright-based scraper for SA20 website to handle JavaScript rendering."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


class SA20PlaywrightScraper:
    """Playwright-based scraper for JavaScript-rendered SA20 website."""

    base_url = "https://www.sa20.co.za"

    async def scrape_teams(self) -> List[Dict]:
        """Scrape all teams."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Capture network requests to find API endpoints
            api_responses = []
            
            async def handle_response(response):
                if response.url and ('api' in response.url.lower() or 'json' in response.url.lower() or response.headers.get('content-type', '').startswith('application/json')):
                    try:
                        api_responses.append({
                            'url': response.url,
                            'data': await response.json()
                        })
                    except Exception:
                        pass
            
            page.on('response', handle_response)
            
            try:
                await page.goto(f"{self.base_url}/teams", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(5000)  # Wait for JS to render
                
                # Check API responses first
                teams = []
                for resp in api_responses:
                    if 'team' in resp['url'].lower() or 'team' in str(resp.get('data', {})).lower():
                        data = resp['data']
                        if isinstance(data, list):
                            teams.extend([self._normalize_team(t) for t in data])
                        elif isinstance(data, dict):
                            if 'teams' in data:
                                teams.extend([self._normalize_team(t) for t in data['teams']])
                
                # Also try extracting from page
                if not teams:
                    teams = await self._extract_teams_from_page(page)
                
                # Fallback to known teams
                if not teams:
                    teams = self._get_known_teams()
                
                await browser.close()
                return teams
            except Exception as e:
                logger.error(f"Error scraping teams: {e}")
                await browser.close()
                return self._get_known_teams()  # Fallback

    async def scrape_team_players(self, team_slug: str) -> List[Dict]:
        """Scrape players from a team page."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Capture API responses - MUST set up handler BEFORE navigation
            api_responses = []
            
            async def handle_response(response):
                url = response.url
                content_type = response.headers.get('content-type', '')
                # Capture article-cms-api and any incrowd API that might have player data
                if url and (('article-cms-api' in url.lower()) or 
                           ('incrowd' in url.lower() and content_type.startswith('application/json'))):
                    try:
                        data = await response.json()
                        api_responses.append({
                            'url': url,
                            'data': data,
                            'content_type': content_type
                        })
                        logger.info(f"✓ Captured API: {url[:80]}... (has articles: {'articles' in str(data).lower()})")
                    except Exception as e:
                        logger.debug(f"Failed to parse JSON from {url}: {e}")
            
            # Set up response handler BEFORE navigation
            page.on('response', handle_response)
            
            try:
                # Try both URL formats
                urls = [
                    f"{self.base_url}/team/{team_slug}",  # Correct format (singular)
                    f"{self.base_url}/teams/{team_slug}",  # Fallback
                ]
                for url in urls:
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        # Wait for initial API calls
                        await page.wait_for_timeout(3000)
                        
                        # Scroll to trigger lazy-loaded content (player cards might be lazy-loaded)
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(2000)
                        await page.evaluate("window.scrollTo(0, 0)")
                        await page.wait_for_timeout(3000)
                        
                        # Wait a bit more for any delayed API calls
                        await page.wait_for_timeout(2000)
                        
                        if page.url != url and "404" not in await page.title():
                            break
                    except Exception:
                        continue
                
                logger.info(f"Captured {len(api_responses)} API responses")
                # Log which APIs were captured
                article_apis = [r['url'] for r in api_responses if 'article-cms-api' in r['url'].lower()]
                if article_apis:
                    logger.info(f"Found {len(article_apis)} article-cms-api responses")
                else:
                    logger.warning("No article-cms-api responses captured - trying to extract player IDs from page")
                    # Try to find player IDs in the page and call the API directly
                    try:
                        # Look for player IDs in script tags or data attributes
                        page_content = await page.content()
                        import re
                        # Look for CRICVIZ_CRICKET_PLAYER IDs in the page - try multiple patterns
                        # First, try to find the full API URL
                        url_pattern = r'https://article-cms-api[^\s\"\']+CRICVIZ_CRICKET_PLAYER[^\s\"\']+'
                        url_matches = re.findall(url_pattern, page_content)
                        if url_matches:
                            # Extract IDs from the URL
                            id_match = re.search(r'sourceSystemId=([\d,]+)', url_matches[0])
                            if id_match:
                                player_ids = id_match.group(1)
                                logger.info(f"Found player IDs from API URL: {player_ids[:100]}...")
                            else:
                                player_ids = None
                        else:
                            # Try other patterns
                            patterns = [
                                r'linkedId\.sourceSystemId=([\d,]+)',
                                r'sourceSystemId["\']?\s*[:=]\s*["\']?([\d,]+)',
                                r'CRICVIZ_CRICKET_PLAYER[^"]*["\']?\s*[:=]\s*["\']?([\d,]+)',
                            ]
                            player_ids = None
                            for pattern in patterns:
                                matches = re.findall(pattern, page_content)
                                if matches:
                                    # Filter out timestamps and other non-player IDs
                                    for match in matches:
                                        if ',' in match and len(match.split(',')) > 5:  # Player IDs are comma-separated lists
                                            player_ids = match
                                            logger.info(f"Found player IDs using pattern: {player_ids[:100]}...")
                                            break
                                    if player_ids:
                                        break
                        
                        if player_ids:
                            # Call the API directly
                            api_url = f"https://article-cms-api.incrowdsports.com/v2/articles?clientId=SA20&singlePage=true&linkedId.sourceSystem=CRICVIZ_CRICKET_PLAYER&linkedId.sourceSystemId={player_ids}&categorySlug=player"
                            logger.info(f"Calling API directly: {api_url[:150]}...")
                            try:
                                response = await page.request.get(api_url, timeout=10000)
                                if response.ok:
                                    data = await response.json()
                                    api_responses.append({
                                        'url': api_url,
                                        'data': data,
                                        'content_type': 'application/json'
                                    })
                                    logger.info("✓ Successfully fetched player data from API directly")
                                else:
                                    logger.warning(f"API call failed with status {response.status}")
                            except Exception as e:
                                logger.warning(f"Failed to fetch player data directly: {e}")
                        else:
                            logger.warning("Could not find player IDs in page content")
                    except Exception as e:
                        logger.warning(f"Error extracting player IDs: {e}")
                
                # Check API responses first - look for article/team data
                players = []
                for resp in api_responses:
                    resp_url = resp.get('url', '')
                    # Prioritize article-cms-api responses
                    if 'article-cms-api' in resp_url.lower():
                        logger.info(f"Processing article-cms-api response...")
                    data = resp.get('data', {})
                    url = resp.get('url', '')
                    
                    # Handle incrowdsports API structure
                    if isinstance(data, dict):
                        # Check for nested data structure (article-cms-api format)
                        if 'data' in data and isinstance(data['data'], dict):
                            nested = data['data']
                            # Look for articles/content that might contain team info
                            if 'articles' in nested:
                                logger.info(f"Found {len(nested['articles'])} articles in API response")
                                for article in nested['articles']:
                                    player = self._extract_player_from_article(article)
                                    if player:
                                        players.append(player)
                                        logger.debug(f"Extracted player: {player.get('name')}")
                            elif 'content' in nested:
                                content = nested['content']
                                if isinstance(content, list):
                                    for item in content:
                                        players.extend(self._extract_players_from_content(item))
                                elif isinstance(content, dict):
                                    players.extend(self._extract_players_from_content(content))
                        
                        # Direct player/squad data
                        if 'players' in data:
                            for item in data['players']:
                                player = self._normalize_player_data(item)
                                if player:
                                    players.append(player)
                        elif 'squad' in data:
                            for item in data['squad']:
                                player = self._normalize_player_data(item)
                                if player:
                                    players.append(player)
                        elif 'team' in data and isinstance(data['team'], dict):
                            team_data = data['team']
                            if 'players' in team_data:
                                for item in team_data['players']:
                                    player = self._normalize_player_data(item)
                                    if player:
                                        players.append(player)
                    
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                if 'player' in str(item).lower() or 'name' in str(item):
                                    player = self._normalize_player_data(item)
                                    if player:
                                        players.append(player)
                                # Check if it's an article with team data
                                players.extend(self._extract_players_from_article(item))
                
                # Only try HTML extraction if we got no players from API
                if not players:
                    players = await self._extract_players_from_page(page)
                
                await browser.close()
                return players
            except Exception as e:
                logger.error(f"Error scraping players for {team_slug}: {e}")
                await browser.close()
                return []

    async def scrape_stats(self, stat_type: str = "batting", season: Optional[int] = None) -> List[Dict]:
        """Scrape statistics."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                url = f"{self.base_url}/stats"
                if season:
                    url += f"?season={season}"
                
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(5000)  # Wait for stats to load
                
                # Switch to bowling tab if needed
                if stat_type == "bowling":
                    try:
                        bowling_btn = page.locator("button:has-text('Bowling'), a:has-text('Bowling')").first
                        if await bowling_btn.count() > 0:
                            await bowling_btn.click()
                            await page.wait_for_timeout(2000)
                    except Exception:
                        pass
                
                # Extract stats
                stats = await self._extract_stats_from_page(page, stat_type)
                
                await browser.close()
                return stats
            except Exception as e:
                logger.error(f"Error scraping {stat_type} stats: {e}")
                await browser.close()
                return []

    async def scrape_fixtures(self, season: int = 2026) -> List[Dict]:
        """Scrape fixtures."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Capture all API responses
            api_responses = []
            
            async def handle_response(response):
                url = response.url
                content_type = response.headers.get('content-type', '')
                # Capture any JSON response that might contain fixture/match data
                if content_type.startswith('application/json') or 'json' in url.lower():
                    try:
                        data = await response.json()
                        api_responses.append({
                            'url': url,
                            'data': data,
                            'content_type': content_type
                        })
                        logger.debug(f"Captured API response: {url[:100]}...")
                    except Exception:
                        pass
            
            page.on('response', handle_response)
            
            try:
                logger.info(f"Loading {self.base_url}/matches...")
                await page.goto(f"{self.base_url}/matches", wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)  # Wait for initial JS to render
                
                # Scroll to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(3000)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(3000)
                
                # Wait a bit more for any delayed API calls
                await page.wait_for_timeout(3000)
                
                logger.info(f"Captured {len(api_responses)} API responses")
                
                # Debug: Log first few API response URLs to understand structure
                if api_responses:
                    logger.info(f"Sample API URLs: {[r['url'][:100] for r in api_responses[:5]]}")
                    # Save a sample response for debugging
                    if len(api_responses) > 0:
                        sample = api_responses[0]
                        logger.debug(f"Sample API response structure (first 500 chars): {str(sample.get('data', {}))[:500]}")
                
                # First, try to extract from rendered HTML (more reliable for dates)
                logger.info("Attempting to extract fixtures from rendered HTML...")
                fixtures_from_html = await self._extract_fixtures_from_page(page, season)
                
                # Also try JavaScript extraction which is more reliable for modern JS sites
                js_fixtures = await self._extract_fixtures_with_javascript(page, season)
                if js_fixtures:
                    logger.info(f"JavaScript extraction found {len(js_fixtures)} fixtures")
                    fixtures_from_html.extend(js_fixtures)
                
                # Remove duplicates from combined results
                if fixtures_from_html:
                    seen = set()
                    unique_fixtures = []
                    for f in fixtures_from_html:
                        if f.get("home_team") and f.get("away_team") and f.get("match_date"):
                            key = (f.get("home_team"), f.get("away_team"), str(f.get("match_date")))
                            if key not in seen:
                                seen.add(key)
                                unique_fixtures.append(f)
                    fixtures_from_html = unique_fixtures
                
                if fixtures_from_html and all(f.get('match_date') for f in fixtures_from_html):
                    logger.info(f"Found {len(fixtures_from_html)} fixtures from HTML with dates")
                    await browser.close()
                    return fixtures_from_html
                
                # Fallback: Try API responses
                logger.info("Attempting to extract fixtures from API responses...")
                fixtures_from_api = []
                for resp in api_responses:
                    fixtures_from_api.extend(self._extract_fixtures_from_api_response(resp, season))
                
                if fixtures_from_api:
                    logger.info(f"Found {len(fixtures_from_api)} fixtures from API responses")
                    # Check if API fixtures have dates
                    fixtures_with_dates = [f for f in fixtures_from_api if f.get('match_date')]
                    if fixtures_with_dates:
                        logger.info(f"Found {len(fixtures_with_dates)} fixtures with dates from API")
                        # Remove duplicates
                        seen = set()
                        unique_fixtures = []
                        for fixture in fixtures_with_dates:
                            key = (fixture.get("home_team"), fixture.get("away_team"), str(fixture.get("match_date")))
                            if key not in seen and fixture.get("home_team") and fixture.get("away_team"):
                                seen.add(key)
                                unique_fixtures.append(fixture)
                        await browser.close()
                        return unique_fixtures
                    else:
                        # API fixtures don't have dates, try to enrich them from HTML
                        logger.info("API fixtures lack dates, attempting to enrich from HTML...")
                        if fixtures_from_html:
                            # Merge API fixtures with HTML fixtures (HTML has dates)
                            # Create a map of HTML fixtures by teams
                            html_fixture_map = {}
                            for f in fixtures_from_html:
                                if f.get('home_team') and f.get('away_team'):
                                    key = (f.get('home_team'), f.get('away_team'))
                                    html_fixture_map[key] = f
                            
                            # Enrich API fixtures with dates from HTML fixtures
                            enriched_fixtures = []
                            for api_fixture in fixtures_from_api:
                                key = (api_fixture.get('home_team'), api_fixture.get('away_team'))
                                if key in html_fixture_map:
                                    html_fixture = html_fixture_map[key]
                                    api_fixture['match_date'] = html_fixture.get('match_date')
                                    api_fixture['venue'] = api_fixture.get('venue') or html_fixture.get('venue')
                                    api_fixture['match_number'] = api_fixture.get('match_number') or html_fixture.get('match_number')
                                enriched_fixtures.append(api_fixture)
                            
                            if any(f.get('match_date') for f in enriched_fixtures):
                                logger.info(f"Enriched {len([f for f in enriched_fixtures if f.get('match_date')])} fixtures with dates from HTML")
                                await browser.close()
                                return enriched_fixtures
                
                # If we have HTML fixtures even without dates, return them
                if fixtures_from_html:
                    logger.info(f"Returning {len(fixtures_from_html)} fixtures from HTML (some may lack dates)")
                    await browser.close()
                    return fixtures_from_html
                
                await browser.close()
                return []
            except Exception as e:
                logger.error(f"Error scraping fixtures: {e}", exc_info=True)
                await browser.close()
                return []

    async def _extract_teams_from_page(self, page: Page) -> List[Dict]:
        """Extract teams from the teams page."""
        teams = []
        
        # Try multiple selectors - be more flexible
        selectors = [
            "a[href*='/teams/']",
            "a[href*='team']",
            "div[class*='team'] a",
            "article[class*='team'] a",
            "[data-team]",
            "h2, h3, h4",  # Team names might be in headings
        ]
        
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements:
                    try:
                        href = await elem.get_attribute("href")
                        name = await elem.inner_text()
                        if not name:
                            continue
                        
                        # Check if it's a team link
                        if href and ("/teams/" in href or "/team/" in href):
                            slug = (href.split("/teams/")[-1] or href.split("/team/")[-1]).strip("/")
                            if slug and name.strip():
                                teams.append({
                                    "name": name.strip(),
                                    "slug": slug,
                                    "url": f"{self.base_url}{href}" if href.startswith("/") else href,
                                })
                        # Or check if text matches known team names
                        elif name:
                            known_teams = [
                                "Durban's Super Giants",
                                "Joburg Super Kings",
                                "MI Cape Town",
                                "Paarl Royals",
                                "Pretoria Capitals",
                                "Sunrisers Eastern Cape",
                            ]
                            for known in known_teams:
                                if known.lower() in name.lower() or name.lower() in known.lower():
                                    teams.append({
                                        "name": known,
                                        "slug": self._name_to_slug(known),
                                        "url": f"{self.base_url}/teams/{self._name_to_slug(known)}",
                                    })
                    except Exception:
                        continue
            except Exception:
                continue
        
        # Also try to get from page content/JSON
        try:
            content = await page.content()
            # Look for team names in the HTML
            for known in ["Durban's Super Giants", "Joburg Super Kings", "MI Cape Town", 
                         "Paarl Royals", "Pretoria Capitals", "Sunrisers Eastern Cape"]:
                if known in content:
                    teams.append({
                        "name": known,
                        "slug": self._name_to_slug(known),
                        "url": f"{self.base_url}/teams/{self._name_to_slug(known)}",
                    })
        except Exception:
            pass
        
        # Remove duplicates
        seen = set()
        unique_teams = []
        for team in teams:
            key = team["name"].lower()
            if key not in seen:
                seen.add(key)
                unique_teams.append(team)
        
        return unique_teams

    async def _extract_players_from_page(self, page: Page) -> List[Dict]:
        """Extract players from a team page."""
        players = []
        
        # Try to find player cards - be very flexible
        player_selectors = [
            "div[class*='player']",
            "article[class*='player']",
            "li[class*='player']",
            "div[class*='squad'] > *",
            "div[class*='roster'] > *",
            "div[class*='member']",
            "[data-player]",
            "img[alt*='player']",  # Player images
            "div:has(img)",  # Any div with an image
        ]
        
        for selector in player_selectors:
            try:
                elements = await page.query_selector_all(selector)
                logger.debug(f"Found {len(elements)} elements with selector: {selector}")
                for elem in elements[:50]:  # Limit to avoid too many
                    try:
                        player = await self._parse_player_element(elem)
                        if player and player.get("name") and len(player["name"]) > 2:
                            players.append(player)
                    except Exception as e:
                        logger.debug(f"Error parsing element: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        # Try to get all images with alt text (player photos) - filter out UI elements
        try:
            images = await page.query_selector_all("img[alt]")
            ui_keywords = ['ticket', 'login', 'register', 'instagram', 'logo', 'search', 'hamburger', 'menu', 'icon', 'button', 'arrow', 'close']
            for img in images:
                alt = await img.get_attribute("alt")
                src = await img.get_attribute("src")
                if alt and len(alt.split()) >= 2:
                    # Filter out UI elements
                    alt_lower = alt.lower()
                    if any(keyword in alt_lower for keyword in ui_keywords):
                        continue
                    # Check if it looks like a player name (2-4 words, capitalized, not too long)
                    words = alt.split()
                    if 2 <= len(words) <= 4 and words[0] and words[0][0].isupper() and len(alt) < 50:
                        # Make sure it's not a common UI text
                        if not any(word.lower() in ['buy', 'click', 'here', 'more', 'view', 'see'] for word in words):
                            image_url = src if src and src.startswith("http") else f"{self.base_url}{src}" if src and src.startswith("/") else None
                            if image_url and ('player' in image_url.lower() or 'squad' in image_url.lower() or '/teams/' in image_url):
                                players.append({
                                    "name": alt.strip(),
                                    "image_url": image_url,
                                    "role": None,
                                    "country": "South Africa",
                                })
        except Exception:
            pass
        
        # Also try to get data from page content/JSON
        try:
            content = await page.content()
            # Look for JSON data in script tags
            json_data = self._extract_json_from_html(content)
            for item in json_data:
                if "player" in str(item).lower() or "name" in str(item):
                    player = self._normalize_player_data(item)
                    if player:
                        players.append(player)
        except Exception:
            pass
        
        # Remove duplicates
        seen = set()
        unique_players = []
        for player in players:
            key = player["name"].lower()
            if key not in seen and len(player["name"]) > 2:
                seen.add(key)
                unique_players.append(player)
        
        return unique_players

    async def _extract_stats_from_page(self, page: Page, stat_type: str) -> List[Dict]:
        """Extract statistics from the stats page."""
        stats = []
        
        # Try to find stats table
        try:
            # Look for table rows
            rows = await page.query_selector_all("table tr, div[class*='row']")
            for row in rows[1:]:  # Skip header
                if stat_type == "batting":
                    stat = await self._parse_batting_row(row)
                else:
                    stat = await self._parse_bowling_row(row)
                if stat:
                    stats.append(stat)
        except Exception:
            pass
        
        # Also try to get from page content
        try:
            content = await page.content()
            json_data = self._extract_json_from_html(content)
            for item in json_data:
                if stat_type in str(item).lower() or "runs" in str(item).lower() or "wickets" in str(item).lower():
                    stats.append(self._normalize_stat_data(item, stat_type))
        except Exception:
            pass
        
        return stats

    async def _extract_fixtures_from_page(self, page: Page, season: int) -> List[Dict]:
        """Extract fixtures from the matches page by parsing HTML structure."""
        fixtures = []
        
        # Wait for fixtures to load
        try:
            await page.wait_for_selector("body", timeout=10000)
            await page.wait_for_timeout(5000)  # Wait for JS to render
            
            # Extract fixtures by finding date headers and match cards
            fixtures = await self._extract_fixtures_by_date_headers(page, season)
            if fixtures:
                logger.info(f"Found {len(fixtures)} fixtures from HTML structure")
                return fixtures
            
            # Fallback: Try to extract from JSON in script tags
            try:
                content = await page.content()
                json_fixtures = self._extract_fixtures_from_json_scripts(content, season)
                if json_fixtures:
                    logger.info(f"Found {len(json_fixtures)} fixtures from JSON in script tags")
                    fixtures.extend(json_fixtures)
            except Exception as e:
                logger.debug(f"Error extracting from JSON scripts: {e}")
            
            # Fallback: Try multiple selectors for fixture elements
            selectors = [
                "div[class*='match']",
                "article[class*='match']",
                "div[class*='fixture']",
                "li[class*='match']",
                "li[class*='fixture']",
                "[data-testid*='match']",
                "[data-testid*='fixture']",
            ]
            
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    logger.info(f"Found {len(elements)} elements with selector: {selector}")
                    if elements:
                        for elem in elements:
                            fixture = await self._parse_fixture_element(elem, season)
                            if fixture and fixture.get("home_team") and fixture.get("away_team"):
                                fixtures.append(fixture)
                        if fixtures:
                            break
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            # Remove duplicates
            seen = set()
            unique_fixtures = []
            for fixture in fixtures:
                key = (fixture.get("home_team"), fixture.get("away_team"), str(fixture.get("match_date")))
                if key not in seen:
                    seen.add(key)
                    unique_fixtures.append(fixture)
            
            return unique_fixtures
        except Exception as e:
            logger.error(f"Error extracting fixtures from page: {e}", exc_info=True)
            return []
    
    async def _extract_fixtures_by_date_headers(self, page: Page, season: int) -> List[Dict]:
        """Extract fixtures by finding date headers and parsing match cards under each date."""
        fixtures = []
        
        try:
            # Wait for content to load
            await page.wait_for_timeout(3000)
            
            # Get page content
            html_content = await page.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all text that looks like date headers (e.g., "FRIDAY, 26 DECEMBER 2025")
            import re
            date_pattern = re.compile(r'([A-Z]+DAY),\s+(\d{1,2})\s+([A-Z]+)\s+(\d{4})', re.IGNORECASE)
            
            # Find all elements that might contain date headers
            all_text_elements = soup.find_all(text=date_pattern)
            
            current_date = None
            current_date_elem = None
            
            # Iterate through the page structure to find date headers and matches
            # Look for headings or divs that contain date text
            for elem in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span', 'p']):
                text = elem.get_text(strip=True)
                if not text:
                    continue
                
                # Check if this element contains a date
                date_match = date_pattern.search(text)
                if date_match:
                    # Parse the date
                    day_name = date_match.group(1)
                    day = int(date_match.group(2))
                    month_name = date_match.group(3)
                    year = int(date_match.group(4))
                    
                    # Convert month name to number
                    month_map = {
                        'january': 1, 'february': 2, 'march': 3, 'april': 4,
                        'may': 5, 'june': 6, 'july': 7, 'august': 8,
                        'september': 9, 'october': 10, 'november': 11, 'december': 12
                    }
                    month = month_map.get(month_name.lower())
                    if month:
                        from datetime import datetime
                        current_date = datetime(year, month, day)
                        current_date_elem = elem
                        logger.info(f"Found date header: {current_date.date()}")
                        continue
                
                # If we have a current date, look for match elements following it
                if current_date and current_date_elem:
                    # Check if this element is a match card (contains team names or "MATCH" text)
                    match_text = text.upper()
                    if 'MATCH' in match_text or any(team in match_text for team in [
                        'MI CAPE TOWN', 'PAARL ROYALS', 'PRETORIA CAPITALS',
                        "DURBAN'S SUPER GIANTS", 'DURBANS SUPER GIANTS',
                        'JOBURG SUPER KINGS', 'SUNRISERS EASTERN CAPE'
                    ]):
                        # Try to extract match details from this element or nearby elements
                        fixture = await self._parse_match_card_from_element(page, elem, current_date, season)
                        if fixture and fixture.get("home_team") and fixture.get("away_team"):
                            fixtures.append(fixture)
            
            # Always try JavaScript extraction (more reliable for modern JS sites)
            js_fixtures = await self._extract_fixtures_with_javascript(page, season)
            if js_fixtures:
                logger.info(f"JavaScript extraction found {len(js_fixtures)} fixtures")
                fixtures.extend(js_fixtures)
            
            # Remove duplicates
            seen = set()
            unique_fixtures = []
            for fixture in fixtures:
                if fixture.get("home_team") and fixture.get("away_team"):
                    key = (fixture.get("home_team"), fixture.get("away_team"), str(fixture.get("match_date")))
                    if key not in seen:
                        seen.add(key)
                        unique_fixtures.append(fixture)
            
            return unique_fixtures
            
        except Exception as e:
            logger.error(f"Error extracting fixtures by date headers: {e}", exc_info=True)
            return []
    
    async def _extract_fixtures_with_javascript(self, page: Page, season: int) -> List[Dict]:
        """Extract fixtures using JavaScript to query the DOM structure."""
        fixtures = []
        
        try:
            import re
            from datetime import datetime
            
            # Wait a bit more for page to fully render
            await page.wait_for_timeout(2000)
            
            # Execute JavaScript to extract fixtures using text-based parsing
            # This approach gets all page text and parses it with larger context windows
            fixture_data = await page.evaluate("""
                () => {
                    const fixtures = [];
                    const teamNames = [
                        'MI Cape Town', 'Paarl Royals', 'Pretoria Capitals',
                        "Durban's Super Giants", 'Durbans Super Giants',
                        'Joburg Super Kings', 'Sunrisers Eastern Cape'
                    ];
                    const venues = ['Newlands', 'Wanderers', 'Boland Park', 'SuperSport Park', 'SuperSport', 'Kingsmead', "St George's Park", "St Georges Park", 'Centurion', 'Centurion Park'];
                    
                    // Get all text content from the page
                    const bodyText = document.body.innerText || document.body.textContent || '';
                    const lines = bodyText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                    
                    let currentDate = null;
                    const dateSections = [];
                    
                    // First pass: identify date sections
                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];
                        const dateMatch = line.match(/([A-Z]+DAY),\\s+(\\d{1,2})\\s+([A-Z]+)\\s+(\\d{4})/i);
                        if (dateMatch) {
                            if (currentDate) {
                                // Save previous section
                                dateSections.push({
                                    date: currentDate,
                                    startLine: currentDate.startLine,
                                    endLine: i - 1
                                });
                            }
                            currentDate = {
                                day: parseInt(dateMatch[2]),
                                month: dateMatch[3],
                                year: parseInt(dateMatch[4]),
                                startLine: i
                            };
                        }
                    }
                    // Add last section
                    if (currentDate) {
                        dateSections.push({
                            date: currentDate,
                            startLine: currentDate.startLine,
                            endLine: lines.length - 1
                        });
                    }
                    
                    // Second pass: extract matches from each date section
                    // Strategy: Find match numbers first, then look for teams in the following lines
                    dateSections.forEach(section => {
                        const sectionLines = lines.slice(section.startLine, section.endLine + 1);
                        const processedMatches = new Set();
                        
                        // First, find all match numbers and their positions
                        const matchNumberPositions = [];
                        for (let i = 0; i < sectionLines.length; i++) {
                            const line = sectionLines[i];
                            const matchNumMatch = line.match(/MATCH\\s+(\\d+)/i);
                            if (matchNumMatch) {
                                const matchNum = parseInt(matchNumMatch[1]);
                                // Check if this is a playoff match with TBC teams
                                const lookAhead = sectionLines.slice(i, Math.min(i + 20, sectionLines.length)).join(' ');
                                const hasTBC = lookAhead.includes('TBC');
                                const isPlayoffMatch = matchNum >= 31 && matchNum <= 34;
                                
                                if (isPlayoffMatch && hasTBC) {
                                    // Skip playoff matches with TBC teams
                                    continue;
                                }
                                
                                matchNumberPositions.push({
                                    index: i,
                                    matchNum: matchNum,
                                    line: line
                                });
                            }
                        }
                        
                        // For each match number, find the associated teams, time, and venue
                        matchNumberPositions.forEach(matchInfo => {
                            const startIdx = matchInfo.index;
                            const endIdx = Math.min(startIdx + 25, sectionLines.length);
                            const matchWindow = sectionLines.slice(startIdx, endIdx).join(' ');
                            
                            // Find teams in this window
                            const foundTeams = [];
                            teamNames.forEach(teamName => {
                                if (matchWindow.includes(teamName)) {
                                    foundTeams.push(teamName);
                                }
                            });
                            
                            // Remove duplicates
                            const uniqueTeams = [...new Set(foundTeams)];
                            
                            // We need exactly 2 teams for a valid match
                            if (uniqueTeams.length !== 2) {
                                return; // Skip this match
                            }
                            
                            // Find time
                            const timeMatch = matchWindow.match(/(\\d{1,2}):(\\d{2})/);
                            const timeStr = timeMatch ? timeMatch[0] : null;
                            
                            // Find venue
                            let venue = null;
                            for (const v of venues) {
                                if (matchWindow.includes(v)) {
                                    venue = v;
                                    break;
                                }
                            }
                            
                            // Create fixture with match number as key
                            const matchKey = section.date.year + '-' + section.date.month + '-' + section.date.day + '-' + matchInfo.matchNum;
                            
                            // Check if we already have this fixture
                            if (!processedMatches.has(matchKey)) {
                                processedMatches.add(matchKey);
                                fixtures.push({
                                    date: {
                                        day: section.date.day,
                                        month: section.date.month,
                                        year: section.date.year
                                    },
                                    match_number: matchInfo.matchNum,
                                    home_team: uniqueTeams[0],
                                    away_team: uniqueTeams[1],
                                    time: timeStr,
                                    venue: venue,
                                    match_key: matchKey
                                });
                            }
                        });
                    });
                    
                    return fixtures;
                }
            """)
            
            # Convert JavaScript results to fixture dictionaries
            import re
            from datetime import datetime
            
            for data in fixture_data:
                try:
                    # Parse date
                    month_map = {
                        'january': 1, 'february': 2, 'march': 3, 'april': 4,
                        'may': 5, 'june': 6, 'july': 7, 'august': 8,
                        'september': 9, 'october': 10, 'november': 11, 'december': 12
                    }
                    month_name = data['date']['month'].lower()
                    month = month_map.get(month_name)
                    if not month:
                        logger.warning(f"Unknown month: {month_name}")
                        continue
                    
                    match_date = datetime(
                        data['date']['year'],
                        month,
                        data['date']['day']
                    )
                    
                    # Parse time if available (format: "17:30" or "17:30 (SAST)")
                    if data.get('time'):
                        time_str = data['time']
                        time_match = re.search(r'(\d{1,2}):(\d{2})', time_str)
                        if time_match:
                            hour = int(time_match.group(1))
                            minute = int(time_match.group(2))
                            match_date = match_date.replace(hour=hour, minute=minute)
                            logger.debug(f"Parsed time: {hour}:{minute} from {time_str}")
                    
                    fixture = {
                        "home_team": self._normalize_team_name(data['home_team']),
                        "away_team": self._normalize_team_name(data['away_team']),
                        "venue": data.get('venue'),
                        "match_date": match_date,
                        "match_number": data.get('match_number'),
                        "season": season,
                    }
                    fixtures.append(fixture)
                    logger.info(f"Extracted fixture: {fixture['home_team']} vs {fixture['away_team']} on {match_date}")
                except Exception as e:
                    logger.warning(f"Error parsing fixture data: {e}", exc_info=True)
                    continue
            
            logger.info(f"Successfully extracted {len(fixtures)} fixtures from JavaScript")
            return fixtures
            
        except Exception as e:
            logger.error(f"Error extracting fixtures with JavaScript: {e}", exc_info=True)
            return []
    
    async def _parse_match_card_from_element(self, page: Page, elem, date: datetime, season: int) -> Optional[Dict]:
        """Parse a match card element to extract fixture details."""
        try:
            # This is a placeholder - would need to traverse the DOM to find teams, time, venue
            # For now, return None to use the JavaScript approach
            return None
        except Exception as e:
            logger.debug(f"Error parsing match card: {e}")
            return None
    
    def _extract_fixtures_from_json_scripts(self, html: str, season: int) -> List[Dict]:
        """Extract fixtures from JSON data in script tags."""
        fixtures = []
        
        # Look for script tags with JSON data
        import re
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')
            
            for script in scripts:
                if not script.string:
                    continue
                
                script_text = script.string
                
                # Try to find JSON objects that might contain fixture data
                # Look for patterns like __NEXT_DATA__, window.__INITIAL_STATE__, etc.
                json_patterns = [
                    r'__NEXT_DATA__\s*=\s*({.+?});',
                    r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                    r'window\.__PRELOADED_STATE__\s*=\s*({.+?});',
                    r'"fixtures"\s*:\s*(\[.+?\])',
                    r'"matches"\s*:\s*(\[.+?\])',
                    r'\{[^{}]*"fixtures"[^{}]*\}',
                    r'\{[^{}]*"matches"[^{}]*\}',
                ]
                
                for pattern in json_patterns:
                    matches = re.findall(pattern, script_text, re.DOTALL)
                    for match in matches:
                        try:
                            # Clean up the match
                            if isinstance(match, tuple):
                                match = match[0] if match else ""
                            if not match:
                                continue
                            
                            # Try to parse as JSON
                            data = json.loads(match)
                            extracted = self._extract_fixtures_from_api_response(
                                {'url': '', 'data': data, 'content_type': 'application/json'}, 
                                season
                            )
                            fixtures.extend(extracted)
                        except (json.JSONDecodeError, ValueError):
                            continue
                
                # Also try to find script tags with type="application/json"
                if script.get('type') == 'application/json':
                    try:
                        data = json.loads(script_text)
                        extracted = self._extract_fixtures_from_api_response(
                            {'url': '', 'data': data, 'content_type': 'application/json'}, 
                            season
                        )
                        fixtures.extend(extracted)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"Error extracting from JSON scripts: {e}")
        
        return fixtures
    
    def _extract_fixtures_from_api_response(self, resp: Dict, season: int) -> List[Dict]:
        """Extract fixtures from an API response."""
        fixtures = []
        data = resp.get('data', {})
        url = resp.get('url', '')
        
        # Recursively search for fixture/match data
        def extract_from_obj(obj, depth=0):
            if depth > 5:  # Prevent infinite recursion
                return []
            found = []
            
            if isinstance(obj, dict):
                # Check if this dict looks like a fixture/match
                if self._is_fixture_dict(obj):
                    fixture = self._parse_fixture_from_api(obj, season)
                    if fixture:
                        found.append(fixture)
                # Recursively search nested structures
                for key, value in obj.items():
                    # Common keys that might contain fixtures
                    if key.lower() in ['fixtures', 'matches', 'data', 'results', 'items', 'events', 'schedule']:
                        found.extend(extract_from_obj(value, depth + 1))
                    elif isinstance(value, (dict, list)):
                        found.extend(extract_from_obj(value, depth + 1))
            elif isinstance(obj, list):
                for item in obj:
                    found.extend(extract_from_obj(item, depth + 1))
            
            return found
        
        fixtures.extend(extract_from_obj(data))
        return fixtures
    
    def _is_fixture_dict(self, obj: Dict) -> bool:
        """Check if a dictionary looks like a fixture/match object."""
        if not isinstance(obj, dict):
            return False
        
        # Check for common fixture/match fields
        team_fields = ['homeTeam', 'awayTeam', 'team1', 'team2', 'home', 'away', 'teamA', 'teamB']
        date_fields = ['date', 'matchDate', 'scheduledDate', 'startTime', 'start_date', 'fixtureDate']
        
        has_team = any(field in obj for field in team_fields)
        has_date = any(field in obj for field in date_fields)
        
        # Also check if values contain team names
        if not has_team:
            values_str = str(obj).lower()
            known_teams = ['cape town', 'paarl', 'pretoria', 'durban', 'joburg', 'sunrisers', 'eastern cape']
            has_team = any(team in values_str for team in known_teams)
        
        return has_team and (has_date or 'venue' in str(obj).lower() or 'stadium' in str(obj).lower())
    
    async def _intercept_fixture_api_calls(self, page: Page, season: int) -> List[Dict]:
        """Intercept API calls to find fixture data (legacy method, kept for compatibility)."""
        fixtures = []
        api_responses = []
        
        async def handle_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')
            if content_type.startswith('application/json'):
                try:
                    data = await response.json()
                    api_responses.append({
                        'url': url,
                        'data': data
                    })
                except Exception:
                    pass
        
        page.on('response', handle_response)
        await page.wait_for_timeout(5000)  # Wait for API calls
        
        # Parse API responses
        for resp in api_responses:
            fixtures.extend(self._extract_fixtures_from_api_response(resp, season))
        
        return fixtures
    
    def _parse_fixture_from_api(self, data: Dict, season: int) -> Optional[Dict]:
        """Parse fixture data from API response."""
        try:
            # Extract teams - try multiple field names and formats
            home_team = None
            away_team = None
            
            # Try various field names for home team
            home_team_fields = ['homeTeam', 'team1', 'home', 'teamA', 'homeTeamName', 'team1Name']
            for field in home_team_fields:
                if field in data:
                    value = data[field]
                    if isinstance(value, dict):
                        home_team = value.get('name') or value.get('teamName') or value.get('title') or str(value)
                    elif isinstance(value, str):
                        home_team = value
                    if home_team:
                        break
            
            # Try various field names for away team
            away_team_fields = ['awayTeam', 'team2', 'away', 'teamB', 'awayTeamName', 'team2Name']
            for field in away_team_fields:
                if field in data:
                    value = data[field]
                    if isinstance(value, dict):
                        away_team = value.get('name') or value.get('teamName') or value.get('title') or str(value)
                    elif isinstance(value, str):
                        away_team = value
                    if away_team:
                        break
            
            # If we still don't have teams, try to extract from string values
            if not home_team or not away_team:
                # Look for team names in the data
                known_teams = [
                    "MI Cape Town", "Paarl Royals", "Pretoria Capitals",
                    "Durban's Super Giants", "Joburg Super Kings", "Sunrisers Eastern Cape"
                ]
                values_str = str(data).lower()
                found_teams = [team for team in known_teams if team.lower() in values_str]
                if len(found_teams) >= 2 and (not home_team or not away_team):
                    if not home_team:
                        home_team = found_teams[0]
                    if not away_team and len(found_teams) > 1:
                        away_team = found_teams[1]
            
            if not home_team or not away_team:
                return None
            
            # Normalize team names
            home_team = self._normalize_team_name(str(home_team).strip())
            away_team = self._normalize_team_name(str(away_team).strip())
            
            # Extract date - try multiple field names and formats
            date_str = (
                data.get('date') or 
                data.get('matchDate') or 
                data.get('scheduledDate') or 
                data.get('startTime') or
                data.get('start_date') or
                data.get('fixtureDate') or
                data.get('datetime') or
                data.get('scheduledAt') or
                data.get('time') or
                data.get('start') or
                data.get('dateTime') or
                data.get('match_time') or
                data.get('fixture_time')
            )
            
            # Also check nested structures
            if not date_str:
                if 'schedule' in data and isinstance(data['schedule'], dict):
                    date_str = data['schedule'].get('date') or data['schedule'].get('time')
                if 'event' in data and isinstance(data['event'], dict):
                    date_str = data['event'].get('date') or data['event'].get('startTime')
                if 'matchInfo' in data and isinstance(data['matchInfo'], dict):
                    date_str = data['matchInfo'].get('date') or data['matchInfo'].get('matchDate')
            
            match_date = None
            if date_str:
                from dateutil import parser
                try:
                    # Try dateutil parser first (handles most formats including ISO, RFC, etc.)
                    match_date = parser.parse(str(date_str), fuzzy=False)
                    logger.debug(f"Parsed date using dateutil: {match_date} from {date_str}")
                except Exception as e:
                    logger.debug(f"Dateutil parser failed for '{date_str}': {e}")
                    # Try common formats manually
                    from datetime import datetime
                    formats = [
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S",
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%d",
                        "%d/%m/%Y %H:%M",
                        "%d %B %Y",
                        "%B %d, %Y",
                        "%d-%m-%Y",
                        "%Y/%m/%d",
                    ]
                    for fmt in formats:
                        try:
                            match_date = datetime.strptime(str(date_str).strip(), fmt)
                            logger.debug(f"Parsed date using format {fmt}: {match_date} from {date_str}")
                            break
                        except ValueError:
                            continue
                    
                    if not match_date:
                        logger.warning(f"Could not parse date: {date_str}")
            else:
                logger.debug(f"No date field found in fixture data: {list(data.keys())[:10]}")
            
            # Extract venue
            venue = None
            venue_fields = ['venue', 'stadium', 'ground', 'location', 'venueName']
            for field in venue_fields:
                if field in data:
                    value = data[field]
                    if isinstance(value, dict):
                        venue = value.get('name') or value.get('venueName') or str(value)
                    elif isinstance(value, str):
                        venue = value
                    if venue:
                        break
            
            # Extract match number
            match_number = (
                data.get('matchNumber') or 
                data.get('match_number') or 
                data.get('number') or
                data.get('matchNo') or
                data.get('fixtureNumber')
            )
            
            if match_number:
                try:
                    match_number = int(match_number)
                except (ValueError, TypeError):
                    match_number = None
            
            return {
                "home_team": home_team,
                "away_team": away_team,
                "venue": str(venue).strip() if venue else None,
                "match_date": match_date,
                "match_number": match_number,
                "season": season,
            }
        except Exception as e:
            logger.debug(f"Error parsing fixture from API: {e}")
            return None
    
    def _normalize_team_name(self, name: str) -> str:
        """Normalize team name to match database."""
        name = name.strip()
        # Map variations to standard names
        team_mapping = {
            "mi cape town": "MI Cape Town",
            "mumbai indians cape town": "MI Cape Town",
            "paarl royals": "Paarl Royals",
            "pretoria capitals": "Pretoria Capitals",
            "durban's super giants": "Durban's Super Giants",
            "durbans super giants": "Durban's Super Giants",
            "dsg": "Durban's Super Giants",
            "joburg super kings": "Joburg Super Kings",
            "jsk": "Joburg Super Kings",
            "sunrisers eastern cape": "Sunrisers Eastern Cape",
            "sec": "Sunrisers Eastern Cape",
        }
        name_lower = name.lower()
        return team_mapping.get(name_lower, name)

    async def _parse_player_element(self, elem) -> Optional[Dict]:
        """Parse a player element."""
        try:
            # Get name - try multiple methods
            name = None
            
            # Method 1: Direct text content
            text = await elem.inner_text()
            if text and len(text.strip()) > 2:
                # Filter out UI elements
                ui_keywords = ['ticket', 'login', 'register', 'instagram', 'logo', 'search', 'hamburger', 'menu', 'icon', 'button', 'arrow', 'close', 'buy', 'click']
                text_lower = text.lower()
                if not any(keyword in text_lower for keyword in ui_keywords):
                    words = text.strip().split()
                    if 2 <= len(words) <= 4 and words[0] and words[0][0].isupper() and len(text.strip()) < 50:
                        name = text.strip()
            
            # Method 2: From child elements
            if not name:
                name_elem = await elem.query_selector("h3, h4, h5, span[class*='name'], a, div[class*='name'], p")
                if name_elem:
                    name = await name_elem.inner_text()
            
            # Method 3: From alt text of image
            if not name:
                img_elem = await elem.query_selector("img")
                if img_elem:
                    name = await img_elem.get_attribute("alt")
            
            # Method 4: From title attribute
            if not name:
                name = await elem.get_attribute("title")
            
            if not name or len(name.strip()) < 2:
                return None
            
            name = name.strip()
            
            # Get image
            img_elem = await elem.query_selector("img")
            image_url = None
            if img_elem:
                image_url = await img_elem.get_attribute("src") or await img_elem.get_attribute("data-src") or await img_elem.get_attribute("data-lazy-src")
                if image_url:
                    if not image_url.startswith("http"):
                        image_url = f"{self.base_url}{image_url}" if image_url.startswith("/") else None
            
            # Get role
            role = None
            role_selectors = [
                "span[class*='role']",
                "div[class*='role']",
                "span[class*='position']",
                "div[class*='position']",
                "[data-role]",
            ]
            for selector in role_selectors:
                role_elem = await elem.query_selector(selector)
                if role_elem:
                    role_text = await role_elem.inner_text()
                    if role_text:
                        role = self._normalize_role(role_text)
                        break
            
            # Get country
            country = "South Africa"
            country_elem = await elem.query_selector("span[class*='country'], div[class*='country'], span[class*='flag'], [data-country]")
            if country_elem:
                country_text = await country_elem.inner_text()
                if country_text:
                    country = country_text.strip()
            
            return {
                "name": name,
                "role": role,
                "image_url": image_url,
                "country": country,
            }
        except Exception as e:
            logger.debug(f"Error parsing player element: {e}")
            return None

    async def _parse_batting_row(self, row) -> Optional[Dict]:
        """Parse a batting stats row."""
        try:
            cells = await row.query_selector_all("td, th, div[class*='cell']")
            if len(cells) < 2:
                return None
            
            name = await cells[0].inner_text()
            if not name or not name.strip():
                return None
            
            # Try to extract runs from cells
            runs = None
            for cell in cells[1:4]:
                text = await cell.inner_text()
                if text.strip().isdigit():
                    runs = int(text.strip())
                    break
            
            return {
                "player_name": name.strip(),
                "runs": runs,
            }
        except Exception:
            return None

    async def _parse_bowling_row(self, row) -> Optional[Dict]:
        """Parse a bowling stats row."""
        try:
            cells = await row.query_selector_all("td, th, div[class*='cell']")
            if len(cells) < 2:
                return None
            
            name = await cells[0].inner_text()
            if not name or not name.strip():
                return None
            
            wickets = None
            for cell in cells[1:4]:
                text = await cell.inner_text()
                if text.strip().isdigit():
                    wickets = int(text.strip())
                    break
            
            return {
                "player_name": name.strip(),
                "wickets": wickets,
            }
        except Exception:
            return None

    async def _parse_fixture_element(self, elem, season: int) -> Optional[Dict]:
        """Parse a fixture element from the matches page."""
        try:
            # Try to extract team names
            team_elements = await elem.query_selector_all("span[class*='team'], div[class*='team'], h3, h4")
            teams = []
            for team_elem in team_elements:
                text = await team_elem.inner_text()
                if text and len(text.strip()) > 2 and len(text.strip()) < 50:
                    # Filter out UI elements
                    if not any(word in text.lower() for word in ['vs', 'v', 'match', 'fixture', 'date', 'time', 'venue']):
                        teams.append(text.strip())
            
            # Also try to get from images (team logos)
            if len(teams) < 2:
                images = await elem.query_selector_all("img[alt]")
                for img in images:
                    alt = await img.get_attribute("alt")
                    if alt and len(alt) > 5 and len(alt) < 50:
                        # Check if it's a team name
                        known_teams = [
                            "MI Cape Town", "Paarl Royals", "Pretoria Capitals",
                            "Durban's Super Giants", "Joburg Super Kings", "Sunrisers Eastern Cape"
                        ]
                        for known_team in known_teams:
                            if known_team.lower() in alt.lower() or alt.lower() in known_team.lower():
                                if known_team not in teams:
                                    teams.append(known_team)
            
            if len(teams) < 2:
                return None
            
            # Extract date
            date_elem = await elem.query_selector("time, [datetime], [data-date], span[class*='date'], div[class*='date']")
            date_str = None
            if date_elem:
                date_str = await date_elem.get_attribute("datetime") or await date_elem.get_attribute("data-date") or await date_elem.inner_text()
            
            # Extract venue
            venue_elem = await elem.query_selector("span[class*='venue'], div[class*='venue'], span[class*='stadium'], div[class*='location']")
            venue = await venue_elem.inner_text() if venue_elem else None
            
            # Extract match number
            match_num_elem = await elem.query_selector("span[class*='match'], span[class*='number'], div[class*='match-number']")
            match_number = None
            if match_num_elem:
                match_text = await match_num_elem.inner_text()
                import re
                match_num_match = re.search(r'\d+', match_text)
                if match_num_match:
                    match_number = int(match_num_match.group())
            
            # Parse date
            match_date = None
            if date_str:
                from datetime import datetime
                from dateutil import parser
                try:
                    match_date = parser.parse(date_str)
                except Exception:
                    # Try common formats
                    formats = ["%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%Y-%m-%dT%H:%M:%S"]
                    for fmt in formats:
                        try:
                            match_date = datetime.strptime(date_str.strip(), fmt)
                            break
                        except ValueError:
                            continue
            
            return {
                "home_team": teams[0] if teams else None,
                "away_team": teams[1] if len(teams) > 1 else None,
                "venue": venue.strip() if venue else None,
                "match_date": match_date,
                "match_number": match_number,
                "season": season,
            }
        except Exception as e:
            logger.debug(f"Error parsing fixture element: {e}")
            return None

    def _extract_json_from_html(self, html: str) -> List[Dict]:
        """Extract JSON data from HTML."""
        results = []
        # Look for JSON in script tags
        json_patterns = [
            r'\{[^{}]*"(?:player|team|match|stat|batting|bowling)"[^{}]*\}',
            r'\[[^\]]*\{[^{}]*"(?:player|team|match|stat)"[^{}]*\}[^\]]*\]',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches[:20]:
                try:
                    data = json.loads(match)
                    if isinstance(data, dict):
                        results.append(data)
                    elif isinstance(data, list):
                        results.extend([d for d in data if isinstance(d, dict)])
                except json.JSONDecodeError:
                    continue
        
        return results

    def _normalize_player_data(self, data: Dict) -> Optional[Dict]:
        """Normalize player data from JSON."""
        if not isinstance(data, dict):
            return None
        name = data.get("name") or data.get("playerName") or data.get("player")
        if not name:
            return None
        return {
            "name": str(name).strip(),
            "role": self._normalize_role(data.get("role") or data.get("position")),
            "image_url": data.get("image") or data.get("imageUrl") or data.get("photo"),
            "country": data.get("country") or data.get("nationality") or "South Africa",
        }

    def _normalize_stat_data(self, data: Dict, stat_type: str) -> Dict:
        """Normalize stat data."""
        if stat_type == "batting":
            return {
                "player_name": data.get("player") or data.get("name") or "Unknown",
                "runs": data.get("runs") or data.get("r"),
            }
        else:
            return {
                "player_name": data.get("player") or data.get("name") or "Unknown",
                "wickets": data.get("wickets") or data.get("w") or data.get("wkts"),
            }

    def _normalize_role(self, role_text: Optional[str]) -> Optional[str]:
        """Normalize role."""
        if not role_text:
            return None
        role_lower = role_text.lower().strip()
        
        # Check for wicket keeper first (including variations like "wicket keeper batter")
        # Wicket keeper takes priority over other roles
        if "wicket" in role_lower and ("keeper" in role_lower or "keep" in role_lower):
            return "wicket_keeper"
        if "wk" in role_lower and len(role_lower) <= 3:  # "wk" as standalone
            return "wicket_keeper"
        
        # Check for other roles
        role_map = {
            "batsman": "batsman",
            "batter": "batsman",
            "bowler": "bowler",
            "all-rounder": "all_rounder",
            "allrounder": "all_rounder",
            "all rounder": "all_rounder",
        }
        for key, value in role_map.items():
            if key in role_lower:
                return value
        return "batsman"  # Default

    def _normalize_team(self, data: Dict) -> Dict:
        """Normalize team data."""
        if isinstance(data, str):
            return {"name": data, "slug": self._name_to_slug(data)}
        name = data.get("name") or data.get("team") or data.get("teamName") or "Unknown"
        slug = data.get("slug") or self._name_to_slug(name)
        return {
            "name": name,
            "slug": slug,
            "url": data.get("url") or f"{self.base_url}/teams/{slug}",
        }

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

    def _extract_player_from_article(self, article: Dict) -> Optional[Dict]:
        """Extract a single player from an article (incrowdsports format)."""
        if not isinstance(article, dict):
            return None
        
        # Extract player name from slug or heroMedia title
        player_name = None
        if 'slug' in article:
            # Slug is usually "firstname-lastname" format
            slug = article['slug']
            # Convert slug to proper name
            player_name = ' '.join(word.capitalize() for word in slug.split('-'))
        
        if not player_name and 'heroMedia' in article:
            hero = article['heroMedia']
            if isinstance(hero, dict) and 'title' in hero:
                player_name = hero['title']
        
        if not player_name:
            return None
        
        # Extract image URL
        image_url = None
        if 'heroMedia' in article:
            hero = article['heroMedia']
            if isinstance(hero, dict):
                if 'content' in hero and isinstance(hero['content'], dict):
                    content = hero['content']
                    if 'image' in content:
                        image_url = content['image']
                elif 'image' in hero:
                    image_url = hero['image']
        
        # Extract role from heroMedia summary, categories, or tags
        role = None
        
        # First, check heroMedia summary which often contains role info
        if 'heroMedia' in article:
            hero = article['heroMedia']
            if isinstance(hero, dict) and 'summary' in hero:
                summary = hero['summary'].lower()
                # Look for role keywords in summary
                role_keywords = {
                    'batter': 'batsman',
                    'batsman': 'batsman',
                    'bowler': 'bowler',
                    'all-rounder': 'all_rounder',
                    'allrounder': 'all_rounder',
                    'wicket-keeper': 'wicket_keeper',
                    'wicketkeeper': 'wicket_keeper',
                    'wicket keeper': 'wicket_keeper',
                }
                for keyword, role_value in role_keywords.items():
                    if keyword in summary:
                        role = role_value
                        break
        
        # Check categories
        if not role and 'categories' in article:
            for cat in article['categories']:
                if isinstance(cat, dict) and 'text' in cat:
                    cat_text = cat['text'].lower()
                    if 'player' not in cat_text:  # Skip "Player" category
                        role = self._normalize_role(cat_text)
                        if role:
                            break
        
        # Check tags for role information
        if not role and 'tags' in article:
            for tag in article['tags']:
                if isinstance(tag, str):
                    role = self._normalize_role(tag)
                    if role:
                        break
        
        # Extract country from linkedIds or tags
        country = "South Africa"  # Default
        if 'linkedIds' in article:
            for linked in article['linkedIds']:
                if isinstance(linked, dict) and 'sourceSystem' in linked:
                    # Could extract country info here if available
                    pass
        
        return {
            "name": player_name,
            "role": role,
            "image_url": image_url,
            "country": country,
        }

    def _extract_players_from_content(self, content: Dict) -> List[Dict]:
        """Extract players from content structure."""
        players = []
        if not isinstance(content, dict):
            return players
        
        # Recursively search for player data
        for key, value in content.items():
            if key.lower() in ['player', 'players', 'squad', 'roster', 'member']:
                if isinstance(value, list):
                    for item in value:
                        player = self._normalize_player_data(item)
                        if player:
                            players.append(player)
                elif isinstance(value, dict):
                    player = self._normalize_player_data(value)
                    if player:
                        players.append(player)
            elif isinstance(value, dict):
                players.extend(self._extract_players_from_content(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        players.extend(self._extract_players_from_content(item))
        
        return players

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
    
    def _player_name_to_slug(self, name: str) -> str:
        """Convert player name to URL slug format (e.g., 'Corbin Bosch' -> 'corbin-bosch')."""
        # Remove special characters and convert to lowercase
        slug = name.lower().strip()
        # Replace spaces with hyphens
        slug = slug.replace(" ", "-")
        # Remove special characters except hyphens
        import re
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        # Remove multiple consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        return slug
    
    async def scrape_player_profile(self, player_name: str) -> Optional[Dict]:
        """Scrape player profile page from SA20 website.
        
        Args:
            player_name: Player's full name (e.g., "Corbin Bosch")
            
        Returns:
            Dictionary with player data including:
            - birth_date: Date of birth (datetime or None)
            - birth_place: Birth location (str or None)
            - season_stats: List of season-by-season stats
            - batting_style: Batting style
            - bowling_style: Bowling style
        """
        player_slug = self._player_name_to_slug(player_name)
        url = f"{self.base_url}/player/{player_slug}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                logger.info(f"Scraping player profile: {url}")
                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Check if page loaded successfully
                if response and response.status == 404:
                    logger.warning(f"Player page not found (404): {url}")
                    await browser.close()
                    return None
                
                # Wait for content to load - try to wait for specific elements
                try:
                    # Wait for player name or stats sections to appear
                    await page.wait_for_selector("h1, h2, table, [class*='stats'], [class*='player']", timeout=10000)
                except PlaywrightTimeout:
                    logger.debug("Page elements not found, continuing anyway")
                
                await page.wait_for_timeout(3000)  # Additional wait for JavaScript to render
                
                # Scroll to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(2000)
                
                # Check if we're on the player page (look for player name in page title or content)
                page_title = await page.title()
                page_content = await page.content()
                
                # Check if page contains player-related content
                if "404" in page_title or "not found" in page_content.lower():
                    logger.warning(f"Player page not found: {url}")
                    await browser.close()
                    return None
                
                # Extract player data from the page
                player_data = await self._extract_player_profile_data(page, player_name)
                
                await browser.close()
                return player_data
            except PlaywrightTimeout:
                logger.error(f"Timeout loading player profile for {player_name} ({url})")
                await browser.close()
                return None
            except Exception as e:
                logger.error(f"Error scraping player profile for {player_name} ({url}): {e}", exc_info=True)
                await browser.close()
                return None
    
    async def _extract_player_profile_data(self, page: Page, player_name: str) -> Optional[Dict]:
        """Extract player profile data from the page."""
        try:
            data = {
                "name": player_name,
                "role": None,
                "birth_date": None,
                "birth_place": None,
                "batting_style": None,
                "bowling_style": None,
                "season_stats": [],
            }
            
            # Extract player role from the header section (appears under player name)
            # The role is typically displayed in the header box near the player's name
            role_extracted = await page.evaluate("""
                () => {
                    // Look for the player name header section first
                    const h1 = document.querySelector('h1');
                    const h3 = document.querySelector('h3');
                    
                    // Find the container that holds the player name and role
                    // The role typically appears in the same container as the name
                    let roleElement = null;
                    
                    // Strategy 1: Look for text that appears after h1/h3 in the same parent container
                    if (h1 || h3) {
                        const nameContainer = (h1 || h3).closest('div');
                        if (nameContainer) {
                            // Look for text nodes or elements that contain role keywords
                            const allText = nameContainer.textContent || '';
                            const roleKeywords = ['Allrounder', 'Batsman', 'Batter', 'Bowler', 'Wicket-keeper', 'Wicketkeeper', 'Wicket Keeper'];
                            
                            for (const keyword of roleKeywords) {
                                // Find element containing the keyword
                                const elements = Array.from(nameContainer.querySelectorAll('*'));
                                for (const el of elements) {
                                    const text = el.textContent || '';
                                    if (text.trim() === keyword || text.trim().toLowerCase() === keyword.toLowerCase()) {
                                        roleElement = el;
                                        break;
                                    }
                                }
                                if (roleElement) break;
                            }
                        }
                    }
                    
                    // Strategy 2: Look for common role text patterns in the header area
                    if (!roleElement) {
                        const headerSelectors = [
                            'div[class*="flex"][class*="justify-between"]',
                            'div[class*="bg-white"]',
                            'div:has(h1):has(h3)',
                        ];
                        
                        for (const selector of headerSelectors) {
                            try {
                                const containers = document.querySelectorAll(selector);
                                for (const container of containers) {
                                    const text = container.textContent || '';
                                    // Check if this container has both name and role-like text
                                    if ((h1 && container.contains(h1)) || (h3 && container.contains(h3))) {
                                        const roleKeywords = ['Allrounder', 'Batsman', 'Batter', 'Bowler', 'Wicket-keeper', 'Wicketkeeper', 'Wicket Keeper', 'All-rounder'];
                                        for (const keyword of roleKeywords) {
                                            const regex = new RegExp(`\\b${keyword}\\b`, 'i');
                                            if (regex.test(text)) {
                                                // Find the element containing this keyword
                                                const walker = document.createTreeWalker(
                                                    container,
                                                    NodeFilter.SHOW_TEXT,
                                                    null
                                                );
                                                let node;
                                                while (node = walker.nextNode()) {
                                                    if (regex.test(node.textContent)) {
                                                        roleElement = node.parentElement;
                                                        break;
                                                    }
                                                }
                                                if (roleElement) break;
                                            }
                                        }
                                        if (roleElement) break;
                                    }
                                }
                                if (roleElement) break;
                            } catch (e) {
                                // Selector might not be supported, continue
                            }
                        }
                    }
                    
                    // Strategy 3: Look for text that appears between name elements and other content
                    if (!roleElement) {
                        const bodyText = document.body.textContent || '';
                        // Look for role keywords near the player name
                        const rolePattern = /\\b(Allrounder|All-rounder|Batsman|Batter|Bowler|Wicket[-\\s]?[Kk]eeper|Wicketkeeper|Wicket Keeper)\\b/i;
                        const match = bodyText.match(rolePattern);
                        if (match) {
                            return match[1];
                        }
                    }
                    
                    if (roleElement) {
                        return roleElement.textContent.trim();
                    }
                    
                    return null;
                }
            """)
            
            if role_extracted:
                normalized_role = self._normalize_role(role_extracted)
                if normalized_role:
                    data["role"] = normalized_role
                    logger.info(f"  Found role: {role_extracted} -> {normalized_role}")
            
            # Extract date of birth and birth place
            # Look for text containing "Date of Birth" or similar
            page_content = await page.content()
            
            # Try to find date of birth in the page
            # The format appears to be: "Date of Birth10/9/1994 in Durban"
            # SA20 website uses DD/MM/YYYY format (South African format)
            import re
            from datetime import datetime
            
            dob_patterns = [
                r'Date of Birth[^\d]*(\d{1,2}/\d{1,2}/\d{4})\s*(?:in\s+)?([^<\n<]+)',
                r'(\d{1,2}/\d{1,2}/\d{4})\s*(?:in\s+)?([^<\n<]+)',
            ]
            
            for pattern in dob_patterns:
                matches = re.finditer(pattern, page_content, re.IGNORECASE)
                for match in matches:
                    dob_str = match.group(1).strip()
                    birth_place_raw = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else None
                    
                    # Parse date - SA20 uses DD/MM/YYYY format (South African format)
                    # Example: "10/9/1994" means October 9, 1994 (day=10, month=9)
                    try:
                        # Split the date to determine format
                        parts = dob_str.split('/')
                        if len(parts) == 3:
                            first, second, year = parts
                            first_int, second_int = int(first), int(second)
                            
                            # If first part > 12, it must be DD/MM format
                            if first_int > 12:
                                birth_date = datetime.strptime(dob_str, "%d/%m/%Y")
                            # If second part > 12, it must be MM/DD format, convert to DD/MM
                            elif second_int > 12:
                                birth_date = datetime.strptime(dob_str, "%m/%d/%Y")
                            else:
                                # Ambiguous - try DD/MM first (SA format), then MM/DD
                                try:
                                    birth_date = datetime.strptime(dob_str, "%d/%m/%Y")
                                except ValueError:
                                    birth_date = datetime.strptime(dob_str, "%m/%d/%Y")
                        else:
                            # Try DD/MM/YYYY first (South African format)
                            try:
                                birth_date = datetime.strptime(dob_str, "%d/%m/%Y")
                            except ValueError:
                                # Try MM/DD/YYYY as fallback
                                try:
                                    birth_date = datetime.strptime(dob_str, "%m/%d/%Y")
                                except ValueError:
                                    # Try YYYY-MM-DD
                                    birth_date = datetime.strptime(dob_str, "%Y-%m-%d")
                        
                        data["birth_date"] = birth_date
                        
                        if birth_place_raw:
                            # Extract birth place - look for "in <place>" pattern
                            birth_place_match = re.search(r'in\s+([^<\n,]+)', birth_place_raw, re.IGNORECASE)
                            if birth_place_match:
                                birth_place = birth_place_match.group(1).strip()
                                # Clean up birth place (remove extra characters)
                                birth_place = re.sub(r'[^a-zA-Z\s]', '', birth_place).strip()
                                data["birth_place"] = birth_place
                            else:
                                # Try to extract from the raw text
                                birth_place = re.sub(r'[^a-zA-Z\s]', '', birth_place_raw).strip()
                                if birth_place and len(birth_place) > 2:
                                    data["birth_place"] = birth_place
                        
                        logger.info(f"  Found birth date: {dob_str} -> {birth_date}, place: {data.get('birth_place')}")
                        break
                    except ValueError as e:
                        logger.debug(f"Could not parse date {dob_str}: {e}")
                        continue
                
                if data["birth_date"]:
                    break
            
            # Extract batting style and bowling style using JavaScript for more reliable extraction
            styles = await page.evaluate("""
                () => {
                    const bodyText = document.body.textContent || '';
                    const battingStyleMatch = bodyText.match(/Batting Style[^\\n]*?([^\\n<]+)/i);
                    const bowlingStyleMatch = bodyText.match(/Bowling Style[^\\n]*?([^\\n<]+)/i);
                    
                    return {
                        batting: battingStyleMatch ? battingStyleMatch[1].trim() : null,
                        bowling: bowlingStyleMatch ? bowlingStyleMatch[1].trim() : null
                    };
                }
            """)
            
            if styles.get("batting"):
                batting_style = styles["batting"]
                batting_style_lower = batting_style.lower()
                if 'right' in batting_style_lower and 'hand' in batting_style_lower:
                    data["batting_style"] = "right_hand"
                elif 'left' in batting_style_lower and 'hand' in batting_style_lower:
                    data["batting_style"] = "left_hand"
                elif 'right' in batting_style_lower:
                    data["batting_style"] = "right_hand"
                elif 'left' in batting_style_lower:
                    data["batting_style"] = "left_hand"
                logger.debug(f"  Found batting style: {batting_style} -> {data.get('batting_style')}")
            
            if styles.get("bowling"):
                bowling_style = styles["bowling"]
                bowling_style_lower = bowling_style.lower()
                if 'right arm fast' in bowling_style_lower or 'right-arm fast' in bowling_style_lower:
                    data["bowling_style"] = "right_arm_fast"
                elif 'left arm fast' in bowling_style_lower or 'left-arm fast' in bowling_style_lower:
                    data["bowling_style"] = "left_arm_fast"
                elif 'right arm medium' in bowling_style_lower or 'right-arm medium' in bowling_style_lower or ('right' in bowling_style_lower and 'medium' in bowling_style_lower):
                    data["bowling_style"] = "right_arm_medium"
                elif 'left arm medium' in bowling_style_lower or 'left-arm medium' in bowling_style_lower or ('left' in bowling_style_lower and 'medium' in bowling_style_lower):
                    data["bowling_style"] = "left_arm_medium"
                elif 'right arm spin' in bowling_style_lower or 'right-arm spin' in bowling_style_lower or ('right' in bowling_style_lower and 'spin' in bowling_style_lower):
                    data["bowling_style"] = "right_arm_spin"
                elif 'left arm spin' in bowling_style_lower or 'left-arm spin' in bowling_style_lower or ('left' in bowling_style_lower and 'spin' in bowling_style_lower):
                    data["bowling_style"] = "left_arm_spin"
                elif 'right' in bowling_style_lower and 'fast' in bowling_style_lower:
                    data["bowling_style"] = "right_arm_fast"
                elif 'left' in bowling_style_lower and 'fast' in bowling_style_lower:
                    data["bowling_style"] = "left_arm_fast"
                logger.debug(f"  Found bowling style: {bowling_style} -> {data.get('bowling_style')}")
            
            # Extract season stats from tables
            # Look for "Bowling Stats" and "Batting & Fielding Stats" tables
            season_stats = await self._extract_season_stats_from_page(page)
            data["season_stats"] = season_stats
            
            return data
        except Exception as e:
            logger.error(f"Error extracting player profile data: {e}", exc_info=True)
            return None
    
    async def _extract_season_stats_from_page(self, page: Page) -> List[Dict]:
        """Extract season-by-season stats from the player page."""
        season_stats = []
        
        try:
            # Wait longer for page to fully render - stats tables might load after initial render
            await page.wait_for_timeout(3000)
            
            # Wait for network to be idle (all resources loaded)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass
            
            # Scroll to find and trigger loading of stats sections
            # First, try to find the stats headings and scroll to them
            try:
                # Look for Bowling Stats heading with more flexible selectors
                bowling_selectors = [
                    "h2:has-text('Bowling Stats')",
                    "h2:has-text('Bowling')",
                    "h2",
                    "*:has-text('Bowling Stats')",
                ]
                bowling_heading = None
                for selector in bowling_selectors:
                    try:
                        bowling_heading = await page.query_selector(selector)
                        if bowling_heading:
                            heading_text = await bowling_heading.text_content()
                            if 'bowling' in heading_text.lower() and 'stats' in heading_text.lower():
                                break
                    except:
                        continue
                
                if bowling_heading:
                    await bowling_heading.scroll_into_view_if_needed()
                    await page.wait_for_timeout(3000)
                
                # Look for Batting Stats heading with more flexible selectors
                batting_selectors = [
                    "h2:has-text('Batting')",
                    "h2:has-text('Batting & Fielding')",
                    "h2",
                    "*:has-text('Batting')",
                ]
                batting_heading = None
                for selector in batting_selectors:
                    try:
                        batting_heading = await page.query_selector(selector)
                        if batting_heading:
                            heading_text = await batting_heading.text_content()
                            if 'batting' in heading_text.lower():
                                break
                    except:
                        continue
                
                if batting_heading:
                    await batting_heading.scroll_into_view_if_needed()
                    await page.wait_for_timeout(3000)
            except Exception as e:
                logger.debug(f"Could not scroll to stats headings: {e}")
            
            # Scroll through the page to trigger lazy loading - more aggressive scrolling
            scroll_height = await page.evaluate("document.body.scrollHeight")
            scroll_steps = 5
            step_size = scroll_height // scroll_steps
            
            for i in range(scroll_steps + 1):
                scroll_pos = i * step_size
                await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                await page.wait_for_timeout(1500)  # Wait longer between scrolls
            
            # Scroll back to top slowly
            for i in range(scroll_steps, -1, -1):
                scroll_pos = i * step_size
                await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                await page.wait_for_timeout(1000)
            
            # Final wait for any remaining content to load
            await page.wait_for_timeout(3000)
            
            # Try to wait for table elements to appear
            try:
                await page.wait_for_selector("div[role='table'], [class*='Table'], [class*='rdt_Table']", timeout=5000)
            except:
                logger.debug("No table elements found after waiting")
            
            # Check if stats sections exist
            stats_sections_exist = await page.evaluate("""
                () => {
                    const bodyText = document.body.textContent || '';
                    return bodyText.includes('Bowling Stats') || bodyText.includes('Batting');
                }
            """)
            
            if not stats_sections_exist:
                logger.warning("No stats sections found on page")
                return season_stats
            
            logger.info("Stats sections found, extracting div-based tables (react-data-table)")
            
            # Extract data from div-based tables (rdt_Table structure)
            # These are react-data-table components with role="table"
            # FIRST: Also check HTML tables, as they might be present
            html_tables_data = await page.evaluate("""
                () => {
                    const results = [];
                    const tables = Array.from(document.querySelectorAll('table'));
                    tables.forEach((table, idx) => {
                        const rows = Array.from(table.querySelectorAll('tr'));
                        const tableData = rows.map(row => {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            return cells.map(cell => cell.textContent.trim()).filter(cell => cell.length > 0);
                        }).filter(row => row.length >= 2);
                        if (tableData.length >= 2) {
                            results.push({
                                index: idx,
                                data: tableData,
                                rowCount: tableData.length,
                                colCount: tableData.length > 0 ? tableData[0].length : 0,
                                type: 'html'
                            });
                        }
                    });
                    return results;
                }
            """)
            
            all_tables_data = html_tables_data if html_tables_data else []
            if html_tables_data:
                logger.info(f"  Found {len(html_tables_data)} HTML tables")
            
            # NOW: Extract data from div-based tables (rdt_Table structure)
            # These are react-data-table components with role="table"
            # Debug: Check what we can find
            debug_info = await page.evaluate("""
                () => {
                    const divRoleTables = Array.from(document.querySelectorAll('div[role="table"]'));
                    const allRoleTables = Array.from(document.querySelectorAll('[role="table"]'));
                    const rdtTables = Array.from(document.querySelectorAll('[class*="rdt_Table"]'));
                    const tableElements = Array.from(document.querySelectorAll('table'));
                    
                    return {
                        divRoleTables: divRoleTables.length,
                        allRoleTables: allRoleTables.length,
                        rdtTables: rdtTables.length,
                        htmlTables: tableElements.length,
                        statsHeadings: Array.from(document.querySelectorAll('h2, h3')).filter(h => 
                            h.textContent.toLowerCase().includes('bowling') || 
                            h.textContent.toLowerCase().includes('batting') || 
                            h.textContent.toLowerCase().includes('stats')
                        ).map(h => h.textContent.trim())
                    };
                }
            """)
            logger.info(f"  Debug: Found {debug_info.get('divRoleTables', 0)} div[role='table'], {debug_info.get('allRoleTables', 0)} [role='table'], {debug_info.get('rdtTables', 0)} rdt_Table elements")
            logger.info(f"  Stats headings found: {debug_info.get('statsHeadings', [])}")
            
            div_tables_data = await page.evaluate("""
                () => {
                    const results = [];
                    
                    // Strategy 1: Find all divs with role="table" (react-data-table components)
                    let tableDivs = Array.from(document.querySelectorAll('div[role="table"]'));
                    
                    // Strategy 1.5: Also check for any elements with role="table"
                    const allRoleTables = Array.from(document.querySelectorAll('[role="table"]'));
                    allRoleTables.forEach(table => {
                        if (!tableDivs.includes(table)) {
                            tableDivs.push(table);
                        }
                    });
                    
                    // Strategy 2: Also look for divs with rdt_Table classes (case insensitive)
                    // Don't filter - collect all potential tables
                    const allDivs = Array.from(document.querySelectorAll('div'));
                    const classBasedTables = allDivs.filter(div => {
                        const className = (div.className || '').toString();
                        return className.includes('rdt_Table') || 
                               className.includes('Table') ||
                               className.toLowerCase().includes('table');
                    });
                    
                    // Combine all found tables (avoid duplicates)
                    const allTableDivs = [];
                    const seenTables = new Set();
                    [...tableDivs, ...classBasedTables].forEach(div => {
                        if (!seenTables.has(div)) {
                            seenTables.add(div);
                            allTableDivs.push(div);
                        }
                    });
                    tableDivs = allTableDivs;
                    
                    // Strategy 3: Find tables by looking near stats headings (even if we found some)
                    const headings = Array.from(document.querySelectorAll('h2, h1, h3'));
                    headings.forEach(heading => {
                        const headingText = heading.textContent.toLowerCase();
                        if (headingText.includes('bowling stats') || headingText.includes('batting') || headingText.includes('fielding')) {
                            // Look for table-like divs after the heading
                            let element = heading.nextElementSibling;
                            let attempts = 0;
                            while (element && attempts < 30) {
                                // Check if this element or its children have table structure
                                const potentialTables = element.querySelectorAll ? 
                                    Array.from(element.querySelectorAll('div[role="table"], [role="table"]')) : [];
                                potentialTables.forEach(potentialTable => {
                                    if (potentialTable && !seenTables.has(potentialTable)) {
                                        seenTables.add(potentialTable);
                                        tableDivs.push(potentialTable);
                                    }
                                });
                                
                                // Also check if the element itself is a table
                                if (element.getAttribute && (element.getAttribute('role') === 'table' || element.tagName === 'TABLE')) {
                                    if (!seenTables.has(element)) {
                                        seenTables.add(element);
                                        tableDivs.push(element);
                                    }
                                }
                                
                                element = element.nextElementSibling;
                                attempts++;
                            }
                        }
                    });
                    
                    tableDivs.forEach((tableDiv, idx) => {
                        const tableData = [];
                        
                        // Handle both div-based tables and HTML tables
                        let rows = [];
                        
                        if (tableDiv.tagName === 'TABLE') {
                            // HTML table
                            rows = Array.from(tableDiv.querySelectorAll('tr'));
                        } else {
                            // Div-based table - try multiple strategies
                            // Strategy 1: Find rows with role="row"
                            rows = Array.from(tableDiv.querySelectorAll('div[role="row"]'));
                            
                            // Strategy 2: Find rows by class
                            if (rows.length === 0) {
                                const tableHead = tableDiv.querySelector('[class*="TableHead"], [class*="Head"], [class*="rdt_TableHead"]');
                                const tableBody = tableDiv.querySelector('[class*="TableBody"], [class*="Body"], [class*="rdt_TableBody"]');
                                
                                if (tableHead) {
                                    const headRows = Array.from(tableHead.querySelectorAll('[class*="Row"], [class*="rdt_TableRow"], div'));
                                    rows.push(...headRows);
                                }
                                if (tableBody) {
                                    const bodyRows = Array.from(tableBody.querySelectorAll('[class*="Row"], [class*="rdt_TableRow"], div'));
                                    rows.push(...bodyRows);
                                }
                            }
                            
                            // Strategy 3: Find all rows by class name containing "Row"
                            if (rows.length === 0) {
                                rows = Array.from(tableDiv.querySelectorAll('[class*="Row"], [class*="rdt_TableRow"]'));
                            }
                            
                            // Strategy 4: Look for divs that contain multiple child divs (potential cells)
                            if (rows.length === 0) {
                                const allDivs = Array.from(tableDiv.querySelectorAll('div'));
                                const rowCandidates = allDivs.filter(div => {
                                    const children = Array.from(div.children).filter(c => c.tagName === 'DIV' || c.tagName === 'SPAN');
                                    return children.length >= 3; // At least 3 cells
                                });
                                
                                // Group by parent to avoid duplicates, keeping only top-level rows
                                const uniqueRows = [];
                                rowCandidates.forEach(div => {
                                    const isChild = rowCandidates.some(other => other !== div && other.contains(div));
                                    if (!isChild && !uniqueRows.some(r => r.contains(div) || div.contains(r))) {
                                        uniqueRows.push(div);
                                    }
                                });
                                rows = uniqueRows;
                            }
                        }
                        
                        // Extract data from rows
                        rows.forEach((row, rowIdx) => {
                            // Extract cells
                            let cells = [];
                            
                            if (row.tagName === 'TR') {
                                // HTML table row
                                cells = Array.from(row.querySelectorAll('td, th'));
                            } else {
                                // Div-based row - try multiple strategies
                                // Strategy 1: Find cells by role
                                cells = Array.from(row.querySelectorAll('[role="gridcell"], [role="columnheader"], [role="cell"]'));
                                
                                // Strategy 2: Find cells by class
                                if (cells.length === 0) {
                                    cells = Array.from(row.querySelectorAll('[class*="TableCell"], [class*="Cell"], [class*="rdt_TableCell"]'));
                                }
                                
                                // Strategy 3: Get direct children
                                if (cells.length === 0) {
                                    cells = Array.from(row.children).filter(c => 
                                        c.tagName === 'DIV' || c.tagName === 'SPAN' || c.tagName === 'P'
                                    );
                                }
                                
                                // Strategy 4: Look for any divs within the row
                                if (cells.length === 0) {
                                    const allElements = Array.from(row.querySelectorAll('div, span'));
                                    cells = allElements.filter(c => {
                                        const text = (c.textContent || '').trim();
                                        return text.length > 0 && text.length < 200 && 
                                               !c.querySelector('div, span'); // Leaf nodes only
                                    });
                                }
                            }
                            
                            // Extract text from cells
                            const rowData = cells.map(cell => {
                                let text = (cell.textContent || cell.innerText || '').trim();
                                text = text.replace(/\\s+/g, ' ').replace(/\\n/g, ' ').trim();
                                return text;
                            }).filter(cell => cell.length > 0 && !cell.match(/^\\s*$/));
                            
                            if (rowData.length >= 2) { // At least 2 columns (reduced from 3)
                                tableData.push(rowData);
                            }
                        });
                        
                        if (tableData.length >= 2) {
                            // Check if this looks like a stats table
                            const headerText = tableData[0].join(' ').toLowerCase();
                            const hasYear = headerText.includes('year');
                            const hasTeam = headerText.includes('team');
                            const hasMat = headerText.includes('mat') || headerText.includes('matches');
                            
                            // Check if data rows contain years (check more rows)
                            let hasYearData = false;
                            let yearPattern = /\\b(20\\d{2})\\b/;
                            for (let i = 1; i < Math.min(tableData.length, 10); i++) {
                                const rowText = tableData[i].join(' ');
                                if (yearPattern.test(rowText)) {
                                    hasYearData = true;
                                    break;
                                }
                            }
                            
                            // Also check if header or data contains stats keywords
                            const hasStatsKeywords = headerText.includes('runs') || 
                                                     headerText.includes('wickets') || 
                                                     headerText.includes('wkts') ||
                                                     headerText.includes('balls') ||
                                                     headerText.includes('hs') ||
                                                     headerText.includes('ave') ||
                                                     headerText.includes('econ');
                            
                            // More lenient matching - accept if we have year data OR stats keywords
                            if ((hasYear && hasTeam && hasMat) || hasYearData || (hasStatsKeywords && hasYearData)) {
                                results.push({
                                    index: idx,
                                    data: tableData,
                                    rowCount: tableData.length,
                                    colCount: tableData.length > 0 ? tableData[0].length : 0
                                });
                            }
                        }
                    });
                    
                    return results;
                }
            """)
            
            if div_tables_data:
                logger.info(f"  Found {len(div_tables_data)} div-based tables from extraction")
                all_tables_data.extend(div_tables_data)
            else:
                # If extraction failed but we know tables exist, try a simpler direct extraction
                logger.info("  Div-based extraction found no tables, trying simpler direct extraction")
                if debug_info.get('divRoleTables', 0) > 0:
                    simple_div_data = await page.evaluate("""
                        () => {
                            const results = [];
                            const tableDivs = Array.from(document.querySelectorAll('div[role="table"]'));
                            
                            tableDivs.forEach((tableDiv, idx) => {
                                // Get all text content from the table
                                const allText = tableDiv.textContent || '';
                                const lines = allText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                                
                                // Try to find rows by looking for year patterns
                                const yearPattern = /\\b(20\\d{2})\\b/;
                                const potentialRows = [];
                                
                                lines.forEach(line => {
                                    if (yearPattern.test(line)) {
                                        // This line might be a stats row
                                        const parts = line.split(/\\s{2,}|\\t/).filter(p => p.trim().length > 0);
                                        if (parts.length >= 3) {
                                            potentialRows.push(parts);
                                        }
                                    }
                                });
                                
                                if (potentialRows.length > 0) {
                                    results.push({
                                        index: idx,
                                        data: potentialRows,
                                        rowCount: potentialRows.length,
                                        colCount: potentialRows[0] ? potentialRows[0].length : 0,
                                        type: 'simple_text'
                                    });
                                }
                            });
                            
                            return results;
                        }
                    """)
                    if simple_div_data:
                        logger.info(f"  Found {len(simple_div_data)} tables using simple text extraction")
                        all_tables_data.extend(simple_div_data)
            
            logger.info(f"  Total tables found: {len(all_tables_data)} (HTML: {len(html_tables_data) if html_tables_data else 0}, Div-based: {len(div_tables_data) if div_tables_data else 0})")
            for idx, table_info in enumerate(all_tables_data):
                logger.info(f"    Table {idx}: {table_info['rowCount']} rows, {table_info['colCount']} columns")
                if table_info['data'] and len(table_info['data']) > 0:
                    logger.info(f"      Header: {table_info['data'][0]}")
                    if len(table_info['data']) > 1:
                        logger.info(f"      First row: {table_info['data'][1][:5]}")
            
            # If no div-based tables found, try to find HTML tables or extract from text
            if len(all_tables_data) == 0:
                logger.info("  No div-based tables found, trying HTML tables and alternative extraction methods")
                # Try to find HTML table elements
                html_tables = await page.evaluate("""
                    () => {
                        const tables = Array.from(document.querySelectorAll('table'));
                        const results = [];
                        tables.forEach((table, idx) => {
                            const rows = Array.from(table.querySelectorAll('tr'));
                            const tableData = rows.map(row => {
                                const cells = Array.from(row.querySelectorAll('td, th'));
                                return cells.map(cell => cell.textContent.trim()).filter(cell => cell.length > 0);
                            }).filter(row => row.length >= 3);
                            if (tableData.length >= 2) {
                                results.push({
                                    index: idx,
                                    data: tableData,
                                    rowCount: tableData.length,
                                    colCount: tableData.length > 0 ? tableData[0].length : 0
                                });
                            }
                        });
                        return results;
                    }
                """)
                if html_tables:
                    logger.info(f"  Found {len(html_tables)} HTML tables")
                    all_tables_data.extend(html_tables)
                
                # If still no tables, try more aggressive extraction - look for any structured data
                if len(all_tables_data) == 0:
                    logger.info("  No tables found, trying direct text extraction from stats sections")
                    # Try to extract by finding stats sections and parsing their content directly
                    text_based_data = await page.evaluate("""
                        () => {
                            const results = [];
                            
                            // Find all headings that might contain stats
                            const headings = Array.from(document.querySelectorAll('h2, h3, h1'));
                            const statsHeadings = headings.filter(h => {
                                const text = h.textContent.toLowerCase();
                                return text.includes('bowling') || text.includes('batting') || text.includes('stats');
                            });
                            
                            // For each stats heading, look for data in nearby elements
                            statsHeadings.forEach(heading => {
                                let currentElement = heading.nextElementSibling;
                                let attempts = 0;
                                const maxAttempts = 50;
                                
                                while (currentElement && attempts < maxAttempts) {
                                    // Look for any elements with year-like data
                                    const text = currentElement.textContent || '';
                                    const yearMatch = text.match(/\\b(20\\d{2})\\b/);
                                    
                                    if (yearMatch) {
                                        // Found year data, try to extract stats from this section
                                        const lines = text.split('\\n').filter(line => line.trim().length > 0);
                                        lines.forEach(line => {
                                            if (line.match(/\\b(20\\d{2})\\b/)) {
                                                // This line might contain stats
                                                const parts = line.trim().split(/\\s+/);
                                                if (parts.length >= 3) {
                                                    results.push({
                                                        type: heading.textContent.toLowerCase().includes('bowling') ? 'bowling' : 'batting',
                                                        raw_line: line,
                                                        parts: parts
                                                    });
                                                }
                                            }
                                        });
                                    }
                                    
                                    currentElement = currentElement.nextElementSibling;
                                    attempts++;
                                }
                            });
                            
                            return results;
                        }
                    """)
                    
                    if text_based_data:
                        logger.info(f"  Found {len(text_based_data)} potential stats records from text extraction")
            
            # Now process the extracted table data
            return await self._extract_stats_from_page_structure(page, all_tables_data)
            
        except Exception as e:
            logger.error(f"Error extracting season stats: {e}", exc_info=True)
        
        return season_stats
    
    async def _extract_stats_from_page_structure(self, page: Page, all_tables_data: List[Dict] = None) -> List[Dict]:
        """Extract stats by finding the Bowling Stats and Batting Stats sections and parsing their content."""
        season_stats = []
        
        try:
            # If we have pre-extracted table data, use it
            if all_tables_data:
                # Process the pre-extracted tables
                bowling_stats = []
                batting_stats = []
                
                # Find headings to identify which tables are which
                headings = await page.evaluate("""
                    () => {
                        const headings = Array.from(document.querySelectorAll('h2, h1'));
                        return headings.map(h => ({
                            text: h.textContent.trim(),
                            element: h
                        })).filter(h => h.text.toLowerCase().includes('bowling') || h.text.toLowerCase().includes('batting') || h.text.toLowerCase().includes('fielding'));
                    }
                """)
                
                # For each table, try to match it with a heading
                for table_info in all_tables_data:
                    table_rows = table_info.get('data', [])
                    if not table_rows or len(table_rows) < 2:
                        continue
                    
                    header_row = table_rows[0]
                    header_text = " ".join(header_row).lower()
                    
                    # Check if this looks like a stats table
                    has_year = 'year' in header_text
                    has_team = 'team' in header_text
                    has_mat = 'mat' in header_text
                    
                    if not (has_year and has_team and has_mat):
                        continue
                    
                    # Check if data rows have years
                    has_year_data = False
                    for row in table_rows[1:min(4, len(table_rows))]:
                        row_text = " ".join(row)
                        if any(year in row_text for year in ['2023', '2024', '2025', '2026']):
                            has_year_data = True
                            break
                    
                    if not has_year_data:
                        continue
                    
                    # Determine table type from header
                    table_type = 'unknown'
                    if any(word in header_text for word in ['wkts', 'wickets', 'bbm', 'econ', '5w', 'balls']):
                        table_type = 'bowling'
                    elif any(word in header_text for word in ['hs', 'highest', '100', '50', '4s', '6s', 'bf', 'runs']):
                        table_type = 'batting'
                    
                    # Also check if table_info has stats_data (from alternative extraction)
                    if table_type == 'unknown' and table_info.get('stats_data'):
                        # Use the stats_data directly
                        stats_data = table_info.get('stats_data')
                        if stats_data.get('bowling'):
                            table_type = 'bowling'
                        elif stats_data.get('batting'):
                            table_type = 'batting'
                    
                    if table_type == 'unknown':
                        # Try to infer from data rows - if rows contain wickets/runs patterns
                        if table_rows and len(table_rows) > 1:
                            sample_row = " ".join(table_rows[1])
                            if any(word in sample_row.lower() for word in ['wkts', 'wickets', 'bbm']):
                                table_type = 'bowling'
                            elif any(word in sample_row.lower() for word in ['runs', 'hs', 'highest']):
                                table_type = 'batting'
                    
                    if table_type == 'unknown':
                        logger.debug(f"  Could not determine table type for table {table_info.get('index')}")
                        continue
                    
                    logger.info(f"  Found {table_type} stats table: {len(table_rows)} rows, header: {header_row[:5]}")
                    
                    # Process the table based on type
                    if table_type == 'bowling':
                        for row_idx, row in enumerate(table_rows[1:], start=1):
                            if len(row) < 5:
                                continue
                            
                            try:
                                # Find year in row
                                year_int = None
                                year_col_idx = None
                                for col_idx, cell in enumerate(row):
                                    cell_clean = cell.strip()
                                    if cell_clean.isdigit() and len(cell_clean) == 4 and 2000 <= int(cell_clean) <= 2100:
                                        year_int = int(cell_clean)
                                        year_col_idx = col_idx
                                        break
                                
                                if not year_int:
                                    continue
                                
                                team_str = row[year_col_idx + 1].strip() if year_col_idx + 1 < len(row) else ""
                                offset = year_col_idx
                                
                                bowling_stat = {
                                    "season": year_int,
                                    "team": team_str,
                                    "matches": self._parse_int(row[offset + 2] if len(row) > offset + 2 else "0"),
                                    "balls": self._parse_int(row[offset + 3] if len(row) > offset + 3 else "0"),
                                    "runs": self._parse_int(row[offset + 4] if len(row) > offset + 4 else "0"),
                                    "wickets": self._parse_int(row[offset + 5] if len(row) > offset + 5 else "0"),
                                    "best_figures": row[offset + 6].strip() if len(row) > offset + 6 and row[offset + 6].strip() not in ["—", "-", "", "0", "–"] else None,
                                    "average": self._parse_float(row[offset + 7] if len(row) > offset + 7 else "0"),
                                    "economy": self._parse_float(row[offset + 8] if len(row) > offset + 8 else "0"),
                                    "strike_rate": self._parse_float(row[offset + 9] if len(row) > offset + 9 else "0"),
                                    "five_wickets": self._parse_int(row[offset + 10] if len(row) > offset + 10 else "0"),
                                }
                                bowling_stats.append(bowling_stat)
                                logger.info(f"    ✓ Bowling: {year_int} - {team_str} - {bowling_stat['wickets']} wkts")
                            except Exception as e:
                                logger.debug(f"    Error parsing bowling row: {e}")
                                continue
                    
                    elif table_type == 'batting':
                        for row_idx, row in enumerate(table_rows[1:], start=1):
                            if len(row) < 5:
                                continue
                            
                            try:
                                # Find year in row
                                year_int = None
                                year_col_idx = None
                                for col_idx, cell in enumerate(row):
                                    cell_clean = cell.strip()
                                    if cell_clean.isdigit() and len(cell_clean) == 4 and 2000 <= int(cell_clean) <= 2100:
                                        year_int = int(cell_clean)
                                        year_col_idx = col_idx
                                        break
                                
                                if not year_int:
                                    continue
                                
                                team_str = row[year_col_idx + 1].strip() if year_col_idx + 1 < len(row) else ""
                                offset = year_col_idx
                                
                                batting_stat = {
                                    "season": year_int,
                                    "team": team_str,
                                    "matches": self._parse_int(row[offset + 2] if len(row) > offset + 2 else "0"),
                                    "runs": self._parse_int(row[offset + 4] if len(row) > offset + 4 else (row[offset + 3] if len(row) > offset + 3 else "0")),
                                    "highest_score": self._parse_int(row[offset + 5] if len(row) > offset + 5 else (row[offset + 4] if len(row) > offset + 4 else "0")),
                                    "average": self._parse_float(row[offset + 6] if len(row) > offset + 6 else (row[offset + 5] if len(row) > offset + 5 else "0")),
                                    "balls_faced": self._parse_int(row[offset + 7] if len(row) > offset + 7 else (row[offset + 6] if len(row) > offset + 6 else "0")),
                                    "strike_rate": self._parse_float(row[offset + 8] if len(row) > offset + 8 else (row[offset + 7] if len(row) > offset + 7 else "0")),
                                    "fours": self._parse_int(row[offset + 11] if len(row) > offset + 11 else (row[offset + 10] if len(row) > offset + 10 else (row[offset + 8] if len(row) > offset + 8 else "0"))),
                                    "sixes": self._parse_int(row[offset + 12] if len(row) > offset + 12 else (row[offset + 11] if len(row) > offset + 11 else (row[offset + 9] if len(row) > offset + 9 else "0"))),
                                }
                                batting_stats.append(batting_stat)
                                logger.info(f"    ✓ Batting: {year_int} - {team_str} - {batting_stat['runs']} runs")
                            except Exception as e:
                                logger.debug(f"    Error parsing batting row: {e}")
                                continue
                
                # Merge stats by season and team
                stats_by_season = {}
                for stat in bowling_stats:
                    key = (stat["season"], stat["team"])
                    if key not in stats_by_season:
                        stats_by_season[key] = {"season": stat["season"], "team": stat["team"], "bowling": stat, "batting": None}
                    else:
                        stats_by_season[key]["bowling"] = stat
                
                for stat in batting_stats:
                    key = (stat["season"], stat["team"])
                    if key not in stats_by_season:
                        stats_by_season[key] = {"season": stat["season"], "team": stat["team"], "batting": stat, "bowling": None}
                    else:
                        stats_by_season[key]["batting"] = stat
                
                season_stats = list(stats_by_season.values())
                season_stats.sort(key=lambda x: x["season"], reverse=True)
                logger.info(f"  Extracted {len(bowling_stats)} bowling stats and {len(batting_stats)} batting stats")
                return season_stats
            
            # Fallback to original JavaScript-based extraction
            # Use JavaScript to extract all table data from the page
            # Handle both HTML tables and div-based tables (CSS Grid/Flexbox)
            table_data = await page.evaluate("""
                () => {
                    const results = [];
                    
                    // Find all h2 headings that might indicate stats sections
                    const headings = Array.from(document.querySelectorAll('h2, h1'));
                    const statsSections = [];
                    
                    headings.forEach(heading => {
                        const text = heading.textContent.trim().toLowerCase();
                        if (text.includes('bowling stats') || text.includes('batting') || text.includes('fielding stats')) {
                            statsSections.push({
                                heading: heading.textContent.trim(),
                                element: heading,
                                type: text.includes('bowling') ? 'bowling' : 'batting'
                            });
                        }
                    });
                    
                    // For each stats section, find the associated table data
                    statsSections.forEach((section, sectionIdx) => {
                        // Look for the table within the same container as the heading
                        // The table should be in a parent container or nearby sibling
                        let container = section.element.parentElement;
                        let tableFound = false;
                        
                        // Search in the container and its children for tables
                        while (container && !tableFound) {
                            // Look for all tables in this container
                            const tables = container.querySelectorAll('table');
                            
                            tables.forEach((table) => {
                                // Check if this table is after our heading and looks like a stats table
                                const tableRect = table.getBoundingClientRect();
                                const headingRect = section.element.getBoundingClientRect();
                                
                                // Table should be below the heading
                                if (tableRect.top >= headingRect.top) {
                                    const rows = Array.from(table.querySelectorAll('tr'));
                                    
                                    if (rows.length >= 2) { // At least header + 1 data row
                                        // Extract table data
                                        const tableData = rows.map(row => {
                                            const cells = Array.from(row.querySelectorAll('td, th'));
                                            return cells.map(cell => {
                                                let text = cell.textContent || cell.innerText || '';
                                                text = text.replace(/\\s+/g, ' ').trim();
                                                return text;
                                            }).filter(cell => cell.length > 0);
                                        }).filter(row => row.length > 0);
                                        
                                        // Verify this looks like a stats table
                                        // Check if header row contains stats-related keywords
                                        if (tableData.length > 0) {
                                            const headerRow = tableData[0].join(' ').toLowerCase();
                                            const isStatsTable = 
                                                (section.type === 'bowling' && (headerRow.includes('wkts') || headerRow.includes('wickets') || headerRow.includes('bbm') || headerRow.includes('econ') || headerRow.includes('5w'))) ||
                                                (section.type === 'batting' && (headerRow.includes('hs') || headerRow.includes('highest') || headerRow.includes('100') || headerRow.includes('50') || headerRow.includes('4s') || headerRow.includes('6s') || headerRow.includes('bf'))) ||
                                                headerRow.includes('year') && headerRow.includes('team') && headerRow.includes('mat');
                                            
                                            if (isStatsTable && tableData.length >= 2) {
                                                // Check if data rows contain years (4-digit numbers)
                                                let hasYearData = false;
                                                for (let i = 1; i < Math.min(tableData.length, 4); i++) {
                                                    const rowText = tableData[i].join(' ');
                                                    if (rowText.match(/\\b(20\\d{2})\\b/)) {
                                                        hasYearData = true;
                                                        break;
                                                    }
                                                }
                                                
                                                if (hasYearData) {
                                                    results.push({
                                                        index: sectionIdx,
                                                        type: section.type,
                                                        heading: section.heading,
                                                        data: tableData
                                                    });
                                                    tableFound = true;
                                                }
                                            }
                                        }
                                    }
                                }
                            });
                            
                            // Move up to parent container if table not found
                            if (!tableFound) {
                                container = container.parentElement;
                                // Stop if we've gone too far up or hit body
                                if (!container || container.tagName === 'BODY' || container.tagName === 'HTML') {
                                    break;
                                }
                            } else {
                                break;
                            }
                        }
                    });
                    
                    // Fallback: Find all tables on the page and check if they're stats tables
                    const allTables = Array.from(document.querySelectorAll('table'));
                    const foundTableData = new Set(); // Track which tables we've already processed
                    
                    allTables.forEach((table, idx) => {
                        const rows = Array.from(table.querySelectorAll('tr'));
                        
                        if (rows.length >= 2) { // At least header + 1 data row
                            const tableData = rows.map(row => {
                                const cells = Array.from(row.querySelectorAll('td, th'));
                                return cells.map(cell => {
                                    let text = cell.textContent || cell.innerText || '';
                                    text = text.replace(/\\s+/g, ' ').trim();
                                    return text;
                                }).filter(cell => cell.length > 0);
                            }).filter(row => row.length > 0);
                            
                            if (tableData.length >= 2) {
                                const headerRow = tableData[0].join(' ').toLowerCase();
                                
                                // Check if this looks like a stats table
                                const hasYear = headerRow.includes('year');
                                const hasTeam = headerRow.includes('team');
                                const hasMat = headerRow.includes('mat');
                                
                                // Check if data rows have years
                                let hasYearData = false;
                                for (let i = 1; i < Math.min(tableData.length, 5); i++) {
                                    const rowText = tableData[i].join(' ');
                                    if (rowText.match(/\\b(20\\d{2})\\b/)) {
                                        hasYearData = true;
                                        break;
                                    }
                                }
                                
                                if (hasYear && hasTeam && hasMat && hasYearData) {
                                    // Determine table type
                                    let tableType = 'unknown';
                                    let heading = '';
                                    
                                    // Check for bowling indicators
                                    if (headerRow.includes('wkts') || headerRow.includes('wickets') || headerRow.includes('bbm') || headerRow.includes('econ') || headerRow.includes('5w') || headerRow.includes('balls')) {
                                        tableType = 'bowling';
                                    }
                                    // Check for batting indicators
                                    else if (headerRow.includes('hs') || headerRow.includes('highest') || headerRow.includes('100') || headerRow.includes('50') || headerRow.includes('4s') || headerRow.includes('6s') || headerRow.includes('bf') || headerRow.includes('runs')) {
                                        tableType = 'batting';
                                    }
                                    
                                    // Try to find nearby heading
                                    let searchElement = table;
                                    for (let depth = 0; depth < 5; depth++) {
                                        searchElement = searchElement.previousElementSibling;
                                        if (!searchElement) {
                                            const parent = table.parentElement;
                                            if (parent) {
                                                const siblings = Array.from(parent.children);
                                                const tableIdx = siblings.indexOf(table);
                                                if (tableIdx > 0) {
                                                    searchElement = siblings[tableIdx - 1];
                                                }
                                            }
                                        }
                                        
                                        if (searchElement && (searchElement.tagName === 'H2' || searchElement.tagName === 'H1')) {
                                            heading = searchElement.textContent.trim();
                                            const headingLower = heading.toLowerCase();
                                            if (tableType === 'unknown') {
                                                if (headingLower.includes('bowling')) {
                                                    tableType = 'bowling';
                                                } else if (headingLower.includes('batting') || headingLower.includes('fielding')) {
                                                    tableType = 'batting';
                                                }
                                            }
                                            break;
                                        }
                                        
                                        if (!searchElement) break;
                                    }
                                    
                                    // Create a unique key for this table to avoid duplicates
                                    const tableKey = tableData[0].join('|') + '|' + tableData.slice(1, 3).map(r => r.join('|')).join('||');
                                    
                                    if (tableType !== 'unknown' && !foundTableData.has(tableKey)) {
                                        foundTableData.add(tableKey);
                                        
                                        // Check if we already have this table from the section search
                                        const alreadyAdded = results.some(r => {
                                            if (r.data && r.data.length > 0 && r.data[0].join('|') === tableData[0].join('|')) {
                                                return true;
                                            }
                                            return false;
                                        });
                                        
                                        if (!alreadyAdded) {
                                            results.push({
                                                index: 1000 + idx,
                                                type: tableType,
                                                heading: heading || 'Stats Table',
                                                data: tableData
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    });
                    
                    return results;
                }
            """)
            
            if table_data:
                logger.info(f"  Found {len(table_data)} potential stats tables via JavaScript evaluation")
                # Process the table data
                bowling_stats = []
                batting_stats = []
                
                for table_info in table_data:
                    table_rows = table_info.get('data', [])
                    table_type = table_info.get('type', 'unknown')
                    table_heading = table_info.get('heading', '')
                    
                    logger.info(f"  Table candidate: type={table_type}, heading='{table_heading}', rows={len(table_rows) if table_rows else 0}")
                    
                    if not table_rows or len(table_rows) < 2:
                        logger.debug(f"    Skipping: insufficient rows")
                        continue
                    
                    logger.info(f"Processing table {table_info.get('index')}: type={table_type}, heading={table_heading}, rows={len(table_rows)}")
                    if len(table_rows) > 0:
                        logger.info(f"  Header row: {table_rows[0]}")
                    if len(table_rows) > 1:
                        logger.info(f"  First data row: {table_rows[1]}")
                        if len(table_rows) > 2:
                            logger.info(f"  Second data row: {table_rows[2]}")
                    
                    # Check header row to identify table type (use table_type from JS if available)
                    header_row = table_rows[0] if table_rows else []
                    header_text = " ".join(header_row).lower()
                    
                    # Use the table_type from JavaScript if available, otherwise infer from header
                    is_bowling = table_type == 'bowling'
                    is_batting = table_type == 'batting'
                    
                    # If type is unknown, try to infer from header
                    if table_type == 'unknown':
                        is_bowling = any(word in header_text for word in ['year', 'team', 'mat', 'balls', 'runs', 'wkts', 'wickets', 'bbm', 'ave', 'econ', 'sr', '5w'])
                        is_batting = any(word in header_text for word in ['year', 'team', 'mat', 'runs', 'hs', 'highest', 'avg', 'bf', 'sr', 'strike', '100', '50', '4s', '6s', 'fours', 'sixes', 'no'])
                    
                    logger.info(f"  Identified as: bowling={is_bowling}, batting={is_batting}, header_text='{header_text[:80]}'")
                    
                    # Process bowling stats
                    if is_bowling:
                        logger.info(f"Processing bowling stats table with {len(table_rows)} total rows")
                        # Find the header row index (might be first row, or we need to skip it)
                        data_start_idx = 1  # Assume header is first row
                        
                        # Check if first row looks like a header (contains words like "YEAR", "TEAM", etc.)
                        if table_rows and len(table_rows[0]) > 0:
                            first_row_text = " ".join(table_rows[0]).lower()
                            if any(word in first_row_text for word in ['year', 'team', 'mat', 'balls', 'wkts']):
                                data_start_idx = 1  # Header is first row, data starts at index 1
                            else:
                                data_start_idx = 0  # No header row, data starts at index 0
                        
                        for row_idx in range(data_start_idx, len(table_rows)):
                            row = table_rows[row_idx]
                            if len(row) < 3:  # Need at least year, team
                                logger.info(f"  Skipping row {row_idx}: too few columns ({len(row)}), row={row}")
                                continue
                            
                            try:
                                # Try to find year in the row - it should be a 4-digit number
                                year_int = None
                                year_col_idx = None
                                for col_idx, cell in enumerate(row):
                                    cell_clean = cell.strip()
                                    if cell_clean.isdigit() and len(cell_clean) == 4 and 2000 <= int(cell_clean) <= 2100:
                                        year_int = int(cell_clean)
                                        year_col_idx = col_idx
                                        break
                                
                                if not year_int:
                                    logger.info(f"  Skipping row {row_idx}: no valid year found, row={row[:5]}")
                                    continue
                                
                                # Team should be next column after year, or we can try to find it
                                team_str = ""
                                if year_col_idx + 1 < len(row):
                                    team_str = row[year_col_idx + 1].strip()
                                
                                logger.info(f"  Parsing bowling row {row_idx}: year={year_int}, team={team_str}, columns={len(row)}, row={row}")
                                
                                # Map columns: YEAR, TEAM, MAT, BALLS, RUNS, WKTS, BBM, AVE, ECON, SR, 5W
                                # Based on screenshot: 2025, MI Cape Town, 8, 132, 191, 11, 4/19, 17.36, 8.68, 132, 0
                                # So: col 0=YEAR, col 1=TEAM, col 2=MAT, col 3=BALLS, col 4=RUNS, col 5=WKTS, col 6=BBM, col 7=AVE, col 8=ECON, col 9=SR, col 10=5W
                                offset = year_col_idx
                                bowling_stat = {
                                    "season": year_int,
                                    "team": team_str,
                                    "matches": self._parse_int(row[offset + 2] if len(row) > offset + 2 else "0"),
                                    "balls": self._parse_int(row[offset + 3] if len(row) > offset + 3 else "0"),
                                    "runs": self._parse_int(row[offset + 4] if len(row) > offset + 4 else "0"),
                                    "wickets": self._parse_int(row[offset + 5] if len(row) > offset + 5 else "0"),
                                    "best_figures": row[offset + 6].strip() if len(row) > offset + 6 and row[offset + 6].strip() not in ["—", "-", "", "0", "–"] else None,
                                    "average": self._parse_float(row[offset + 7] if len(row) > offset + 7 else "0"),
                                    "economy": self._parse_float(row[offset + 8] if len(row) > offset + 8 else "0"),
                                    "strike_rate": self._parse_float(row[offset + 9] if len(row) > offset + 9 else "0"),
                                    "five_wickets": self._parse_int(row[offset + 10] if len(row) > offset + 10 else "0"),
                                }
                                bowling_stats.append(bowling_stat)
                                logger.info(f"  ✓ Added bowling stat: {year_int} - {team_str} - {bowling_stat['wickets']} wickets, {bowling_stat['runs']} runs")
                            except (ValueError, IndexError) as e:
                                logger.warning(f"  ✗ Could not parse bowling stats row {row_idx}: {e}, row={row}")
                                continue
                    
                    # Process batting stats
                    elif is_batting:
                        logger.info(f"Processing batting stats table with {len(table_rows)} total rows")
                        # Find the header row index
                        data_start_idx = 1  # Assume header is first row
                        
                        if table_rows and len(table_rows[0]) > 0:
                            first_row_text = " ".join(table_rows[0]).lower()
                            if any(word in first_row_text for word in ['year', 'team', 'mat', 'runs', 'hs']):
                                data_start_idx = 1
                            else:
                                data_start_idx = 0
                        
                        for row_idx in range(data_start_idx, len(table_rows)):
                            row = table_rows[row_idx]
                            if len(row) < 3:
                                logger.info(f"  Skipping row {row_idx}: too few columns ({len(row)}), row={row}")
                                continue
                            
                            try:
                                # Find year in row
                                year_int = None
                                year_col_idx = None
                                for col_idx, cell in enumerate(row):
                                    cell_clean = cell.strip()
                                    if cell_clean.isdigit() and len(cell_clean) == 4 and 2000 <= int(cell_clean) <= 2100:
                                        year_int = int(cell_clean)
                                        year_col_idx = col_idx
                                        break
                                
                                if not year_int:
                                    logger.info(f"  Skipping row {row_idx}: no valid year found, row={row[:5]}")
                                    continue
                                
                                team_str = ""
                                if year_col_idx + 1 < len(row):
                                    team_str = row[year_col_idx + 1].strip()
                                
                                logger.info(f"  Parsing batting row {row_idx}: year={year_int}, team={team_str}, columns={len(row)}, row={row}")
                                
                                # Map columns: YEAR, TEAM, MAT, NO, RUNS, HS, AVG, BF, SR, 100, 50, 4S, 6S
                                # Based on screenshot: 2025, MI Cape Town, 8, 0, 0, 0, 0.00, 2, 0.00, 0, 0, 0, 0
                                offset = year_col_idx
                                batting_stat = {
                                    "season": year_int,
                                    "team": team_str,
                                    "matches": self._parse_int(row[offset + 2] if len(row) > offset + 2 else "0"),
                                    "runs": self._parse_int(row[offset + 4] if len(row) > offset + 4 else (row[offset + 3] if len(row) > offset + 3 else "0")),  # RUNS might skip NO column
                                    "highest_score": self._parse_int(row[offset + 5] if len(row) > offset + 5 else (row[offset + 4] if len(row) > offset + 4 else "0")),
                                    "average": self._parse_float(row[offset + 6] if len(row) > offset + 6 else (row[offset + 5] if len(row) > offset + 5 else "0")),
                                    "balls_faced": self._parse_int(row[offset + 7] if len(row) > offset + 7 else (row[offset + 6] if len(row) > offset + 6 else "0")),
                                    "strike_rate": self._parse_float(row[offset + 8] if len(row) > offset + 8 else (row[offset + 7] if len(row) > offset + 7 else "0")),
                                    "fours": self._parse_int(row[offset + 11] if len(row) > offset + 11 else (row[offset + 10] if len(row) > offset + 10 else (row[offset + 8] if len(row) > offset + 8 else "0"))),
                                    "sixes": self._parse_int(row[offset + 12] if len(row) > offset + 12 else (row[offset + 11] if len(row) > offset + 11 else (row[offset + 9] if len(row) > offset + 9 else "0"))),
                                }
                                batting_stats.append(batting_stat)
                                logger.info(f"  ✓ Added batting stat: {year_int} - {team_str} - {batting_stat['runs']} runs, HS: {batting_stat['highest_score']}")
                            except (ValueError, IndexError) as e:
                                logger.warning(f"  ✗ Could not parse batting stats row {row_idx}: {e}, row={row}")
                                continue
                    else:
                        logger.info(f"  Table type unknown, skipping. Header: {header_text[:50]}")
                
                # Merge stats by season and team
                stats_by_season = {}
                for stat in bowling_stats:
                    key = (stat["season"], stat["team"])
                    if key not in stats_by_season:
                        stats_by_season[key] = {"season": stat["season"], "team": stat["team"], "bowling": stat, "batting": None}
                    else:
                        stats_by_season[key]["bowling"] = stat
                
                for stat in batting_stats:
                    key = (stat["season"], stat["team"])
                    if key not in stats_by_season:
                        stats_by_season[key] = {"season": stat["season"], "team": stat["team"], "batting": stat, "bowling": None}
                    else:
                        stats_by_season[key]["batting"] = stat
                
                season_stats = list(stats_by_season.values())
                season_stats.sort(key=lambda x: x["season"], reverse=True)
                logger.info(f"  Extracted {len(bowling_stats)} bowling stats and {len(batting_stats)} batting stats via JS evaluation")
            
        except Exception as e:
            logger.error(f"Error extracting stats from page structure: {e}", exc_info=True)
        
        return season_stats
    
    def _parse_int(self, value: str) -> int:
        """Parse integer value, handling dashes and empty strings."""
        value = value.strip()
        if not value or value == "—" or value == "-" or value == "0.00" or value == "0":
            return 0
        try:
            # Remove any non-digit characters except minus sign
            import re
            value = re.sub(r'[^\d\-]', '', value)
            return int(float(value)) if value else 0
        except (ValueError, AttributeError):
            return 0
    
    def _parse_float(self, value: str) -> float:
        """Parse float value, handling dashes and empty strings."""
        value = value.strip()
        if not value or value == "—" or value == "-":
            return 0.0
        try:
            # Remove any non-digit characters except decimal point and minus sign
            import re
            value = re.sub(r'[^\d.\-]', '', value)
            return float(value) if value else 0.0
        except (ValueError, AttributeError):
            return 0.0


