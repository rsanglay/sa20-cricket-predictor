import asyncio
import re
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Response
import logging

logger = logging.getLogger(__name__)


class RobustSA20Scraper:
    base_url = "https://www.sa20.co.za"
    
    def __init__(self):
        self.api_responses = []
        self.player_ids_found = set()
    
    async def scrape_teams(self) -> List[Dict]:
        """Scrape all teams - simple implementation."""
        # Return known teams with slugs
        teams = [
            {"name": "Durban's Super Giants", "slug": "durbans-super-giants"},
            {"name": "Joburg Super Kings", "slug": "joburg-super-kings"},
            {"name": "MI Cape Town", "slug": "mi-cape-town"},
            {"name": "Paarl Royals", "slug": "paarl-royals"},
            {"name": "Pretoria Capitals", "slug": "pretoria-capitals"},
            {"name": "Sunrisers Eastern Cape", "slug": "sunrisers-eastern-cape"},
        ]
        logger.info(f"Using known teams: {len(teams)} teams")
        return teams
        
    async def _response_handler(self, response: Response):
        """Capture ALL network responses for debugging"""
        url = response.url
        
        # Log all responses to debug
        if 'incrowdsports' in url or 'article' in url or 'player' in url:
            logger.debug(f"Network call detected: {url[:100]}...")
        
        # Capture article-cms-api responses
        if 'article-cms-api.incrowdsports.com' in url:
            try:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Captured article-cms-api response with {len(data.get('data', {}).get('articles', []))} articles")
                    self.api_responses.append(data)
            except Exception as e:
                logger.debug(f"Error parsing API response: {e}")
    
    async def _extract_player_ids_from_scripts(self, page: Page) -> List[str]:
        """Extract player IDs from inline scripts and data attributes"""
        try:
            # Method 1: Check window.__NEXT_DATA__ or similar
            next_data = await page.evaluate("""
                () => {
                    if (window.__NEXT_DATA__) return JSON.stringify(window.__NEXT_DATA__);
                    if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
                    return null;
                }
            """)
            
            if next_data:
                logger.info(f"Found Next.js data: {next_data[:200]}...")
                # Extract player IDs from the data
                player_id_matches = re.findall(r'"sourceSystemId"\s*:\s*"?(\d+)"?', next_data)
                if player_id_matches:
                    logger.info(f"Extracted {len(player_id_matches)} player IDs from Next.js data")
                    return player_id_matches
            
            # Method 2: Check all script tags
            scripts = await page.query_selector_all('script')
            for script in scripts:
                content = await script.inner_text()
                if 'sourceSystemId' in content or 'CRICVIZ_CRICKET_PLAYER' in content:
                    # Look for the full API URL pattern
                    url_pattern = r'https://article-cms-api[^\s\"\']+sourceSystemId=([\d,]+)'
                    url_matches = re.findall(url_pattern, content)
                    if url_matches:
                        player_ids_str = url_matches[0]
                        player_ids = player_ids_str.split(',')
                        logger.info(f"Found player IDs in script tag: {len(player_ids)} IDs")
                        self.player_ids_found.update(player_ids)
                    else:
                        # Try other patterns
                        player_id_matches = re.findall(r'(?:sourceSystemId|playerId)[":\s]+(\d+)', content)
                        if player_id_matches:
                            logger.info(f"Found player IDs in script tag: {player_id_matches[:5]}")
                            self.player_ids_found.update(player_id_matches)
            
            # Method 3: Check data attributes
            elements_with_data = await page.query_selector_all('[data-player-id], [data-source-system-id]')
            for elem in elements_with_data:
                player_id = await elem.get_attribute('data-player-id') or await elem.get_attribute('data-source-system-id')
                if player_id:
                    self.player_ids_found.add(player_id)
            
            return list(self.player_ids_found)
            
        except Exception as e:
            logger.error(f"Error extracting player IDs from scripts: {e}")
            return []
    
    async def _trigger_api_calls(self, page: Page):
        """Aggressively trigger lazy loading and API calls"""
        try:
            # Scroll multiple times
            for i in range(5):
                await page.evaluate(f'window.scrollTo(0, {(i + 1) * 500})')
                await asyncio.sleep(0.5)
            
            # Scroll to bottom
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1)
            
            # Click any "load more" or "show all" buttons
            load_buttons = await page.query_selector_all('button:has-text("Load"), button:has-text("Show"), button:has-text("More")')
            for button in load_buttons:
                try:
                    await button.click()
                    await asyncio.sleep(1)
                except:
                    pass
            
            # Hover over player elements to trigger lazy loading
            player_cards = await page.query_selector_all('[class*="player"], [class*="card"], [class*="member"]')
            for card in player_cards[:10]:  # Hover first 10
                try:
                    await card.hover()
                    await asyncio.sleep(0.2)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error triggering API calls: {e}")
    
    async def _call_api_directly(self, player_ids: List[str]) -> Optional[Dict]:
        """Call the article-cms-api directly with player IDs"""
        if not player_ids:
            return None
            
        try:
            import aiohttp
            
            # Join player IDs
            ids_param = ','.join(player_ids)
            url = f"https://article-cms-api.incrowdsports.com/v2/articles?clientId=SA20&singlePage=true&linkedId.sourceSystem=CRICVIZ_CRICKET_PLAYER&linkedId.sourceSystemId={ids_param}&categorySlug=player"
            
            logger.info(f"Calling API directly with {len(player_ids)} player IDs...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ Direct API call successful: {len(data.get('data', {}).get('articles', []))} articles")
                        return data
                    else:
                        logger.error(f"API call failed with status {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error calling API directly: {e}")
            return None
    
    async def scrape_team_players(self, team_slug: str) -> List[Dict]:
        """
        Main scraping method with multiple fallback strategies
        """
        self.api_responses = []
        self.player_ids_found = set()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            
            # Set up response handler FIRST
            page.on('response', self._response_handler)
            
            try:
                url = f'https://www.sa20.co.za/team/{team_slug}'
                logger.info(f"Navigating to {url}")
                
                # Navigate and wait for network to be idle
                await page.goto(url, wait_until='networkidle', timeout=30000)
                logger.info("Page loaded, waiting for content...")
                
                # Wait a bit for initial render
                await asyncio.sleep(2)
                
                # STRATEGY 1: Trigger API calls aggressively
                logger.info("Strategy 1: Triggering lazy loading...")
                await self._trigger_api_calls(page)
                await asyncio.sleep(3)
                
                # Check if we captured API responses
                if self.api_responses:
                    logger.info(f"✅ Strategy 1 successful: {len(self.api_responses)} API responses captured")
                    players = self._extract_players_from_api(self.api_responses)
                    await browser.close()
                    return players
                
                # STRATEGY 2: Extract player IDs and call API directly
                logger.info("Strategy 2: Extracting player IDs from page...")
                player_ids = await self._extract_player_ids_from_scripts(page)
                
                if player_ids:
                    logger.info(f"Found {len(player_ids)} player IDs: {player_ids[:5]}...")
                    api_data = await self._call_api_directly(player_ids)
                    if api_data:
                        logger.info("✅ Strategy 2 successful: Got data from direct API call")
                        players = self._extract_players_from_api([api_data])
                        await browser.close()
                        return players
                
                # STRATEGY 3: Wait longer and try again
                logger.info("Strategy 3: Waiting longer for API calls...")
                await asyncio.sleep(5)
                await self._trigger_api_calls(page)
                await asyncio.sleep(3)
                
                if self.api_responses:
                    logger.info(f"✅ Strategy 3 successful: {len(self.api_responses)} API responses captured")
                    players = self._extract_players_from_api(self.api_responses)
                    await browser.close()
                    return players
                
                # STRATEGY 4: Get HTML and look for any player data
                logger.info("Strategy 4: Parsing HTML for player data...")
                html_content = await page.content()
                players = await self._extract_from_html(page)
                
                if players:
                    logger.info(f"✅ Strategy 4 successful: {len(players)} players from HTML")
                    await browser.close()
                    return players
                
                logger.error("❌ All strategies failed")
                await browser.close()
                return []
                
            except Exception as e:
                logger.error(f"Error scraping team {team_slug}: {e}")
                await browser.close()
                return []
    
    def _extract_players_from_api(self, api_responses: List[Dict]) -> List[Dict]:
        """Extract player data from API responses"""
        players = []
        
        for response_data in api_responses:
            # Handle nested data structure
            data = response_data.get('data', {})
            if isinstance(data, dict):
                articles = data.get('articles', [])
            else:
                articles = response_data.get('articles', [])
            
            for article in articles:
                try:
                    # Extract name from title or slug
                    player_name = article.get('title', '').strip()
                    if not player_name:
                        # Try slug
                        slug = article.get('slug', '')
                        if slug:
                            # Convert slug to name (e.g., "firstname-lastname" -> "Firstname Lastname")
                            player_name = ' '.join(word.capitalize() for word in slug.split('-'))
                    
                    if not player_name:
                        continue
                    
                    # Filter out UI elements - check if name looks like a real player name
                    name_lower = player_name.lower()
                    ui_keywords = ['instagram', 'logo', 'search', 'hamburger', 'news', 'ticket', 'login', 'register', 
                                  'button', 'arrow', 'close', 'buy', 'click', 'partner', 'title', 'official', 
                                  'dp world', 'switch', 'energy', 'drink', 'rain', 'absa', 'betway', 'expand', 
                                  'chevron', 'menu', 'icon']
                    
                    # Skip if it's a UI element
                    if any(keyword in name_lower for keyword in ui_keywords):
                        logger.debug(f"Skipping UI element: {player_name}")
                        continue
                    
                    # Must have at least 2 words and look like a person's name
                    words = player_name.split()
                    if len(words) < 2:
                        logger.debug(f"Skipping single word: {player_name}")
                        continue
                    
                    # First word should be capitalized
                    if not words[0] or not words[0][0].isupper():
                        logger.debug(f"Skipping non-capitalized: {player_name}")
                        continue
                    
                    # Extract role from summary
                    summary = article.get('summary', '').lower()
                    role = 'batsman'  # default
                    if 'batsman' in summary or 'batter' in summary:
                        role = 'batsman'
                    elif 'bowler' in summary:
                        role = 'bowler'
                    elif 'all-rounder' in summary or 'allrounder' in summary:
                        role = 'all_rounder'
                    elif 'keeper' in summary or 'wicket-keeper' in summary or 'wicketkeeper' in summary:
                        role = 'wicket_keeper'
                    
                    # Also check categories
                    categories = article.get('categories', [])
                    for cat in categories:
                        if isinstance(cat, dict):
                            cat_text = cat.get('text', '').lower()
                        else:
                            cat_text = str(cat).lower()
                        
                        if 'batsman' in cat_text or 'batter' in cat_text:
                            role = 'batsman'
                        elif 'bowler' in cat_text:
                            role = 'bowler'
                        elif 'all-rounder' in cat_text:
                            role = 'all_rounder'
                        elif 'keeper' in cat_text:
                            role = 'wicket_keeper'
                    
                    # Extract image
                    image_url = None
                    hero_media = article.get('heroMedia', {})
                    if hero_media:
                        # Try different image paths
                        if isinstance(hero_media, dict):
                            content = hero_media.get('content', {})
                            if isinstance(content, dict):
                                image_url = content.get('image') or content.get('url')
                            images = hero_media.get('images', [])
                            if not image_url and images and len(images) > 0:
                                if isinstance(images[0], dict):
                                    image_url = images[0].get('url') or images[0].get('src')
                                else:
                                    image_url = images[0]
                    
                    # Extract player ID
                    player_id = None
                    linked_ids = article.get('linkedIds', [])
                    for linked in linked_ids:
                        if isinstance(linked, dict) and linked.get('sourceSystem') == 'CRICVIZ_CRICKET_PLAYER':
                            player_id = linked.get('sourceSystemId')
                            break
                    
                    players.append({
                        'name': player_name,
                        'role': role,
                        'image_url': image_url,
                        'player_id': player_id,
                        'source': 'api'
                    })
                    
                except Exception as e:
                    logger.debug(f"Error extracting player from article: {e}")
                    continue
        
        logger.info(f"Extracted {len(players)} players from API responses")
        return players
    
    async def _extract_from_html(self, page: Page) -> List[Dict]:
        """Fallback: Extract player data from rendered HTML"""
        players = []
        
        try:
            # Look for player cards with various selectors
            player_selectors = [
                '[class*="PlayerCard"]',
                '[class*="player-card"]',
                '[class*="squad-member"]',
                '[data-testid*="player"]',
                'article[class*="player"]',
            ]
            
            for selector in player_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    logger.info(f"Found {len(elements)} elements with selector: {selector}")
                    
                    for elem in elements:
                        try:
                            # Try to get player name
                            name_elem = await elem.query_selector('h2, h3, h4, [class*="name"]')
                            if name_elem:
                                name = await name_elem.inner_text()
                                name = name.strip()
                                
                                # Filter out non-player elements
                                if len(name) < 3 or name.lower() in ['instagram', 'facebook', 'twitter', 'search', 'logo']:
                                    continue
                                
                                # Try to get role
                                role_elem = await elem.query_selector('[class*="role"], [class*="position"]')
                                role = 'batsman'
                                if role_elem:
                                    role_text = await role_elem.inner_text()
                                    role = role_text.strip().lower()
                                
                                # Try to get image
                                img_elem = await elem.query_selector('img')
                                image_url = None
                                if img_elem:
                                    image_url = await img_elem.get_attribute('src')
                                
                                players.append({
                                    'name': name,
                                    'role': role,
                                    'image_url': image_url,
                                    'player_id': None,
                                    'source': 'html'
                                })
                                
                        except Exception as e:
                            logger.debug(f"Error extracting player from element: {e}")
                            continue
                    
                    if players:
                        break  # Found players, no need to try other selectors
            
        except Exception as e:
            logger.error(f"Error in HTML extraction: {e}")
        
        return players

