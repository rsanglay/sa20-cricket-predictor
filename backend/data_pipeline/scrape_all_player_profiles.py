"""
Scrape player profiles and performance statistics for all players in the SA20 league
from the official website https://www.sa20.co.za/player/<slug>.

Each page contains:
- Player details (bio, nationality, role, birth info)
- Batting & fielding stats table
- Bowling stats table
- Optional related news

Output: players.json with structured data for all players
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# List of all SA20 players
PLAYERS = [
    "Adam Milne", "Aiden Markram", "Akeal Hosein", "Am Ghazanfar", "Andile Simelane",
    "Andre Russell", "Anrich Nortje", "Asa Tribe", "Bayanda Majola", "Beyers Swanepoel",
    "Bjorn Fortuin", "Brandon King", "Bryce Parsons", "Chris Wood", "Cj King", "Codi Yusuf",
    "Connor Esterhuizen", "Corbin Bosch", "Craig Overton", "Dan Lategan", "Dan Lawrence",
    "Dane Piedt", "Daniel Worrall", "Daryn Dupavillon", "David Bedingham", "David Miller",
    "David Wiese", "Dayyaan Galiem", "Delano Potgieter", "Devon Conway", "Dewald Brevis",
    "Dian Forrester", "Donovan Ferreira", "Dwaine Pretorius", "Eathan Bosch", "Eshan Malinga",
    "Evan Jones", "Faf Du Plessis", "George Linde", "Gerald Coetzee", "Gideon Peters",
    "Gudakesh Motie", "Gysbert Wege", "Hardus Viljoen", "Heinrich Klaasen", "Imran Tahir",
    "Jacques Snyman", "James Coles", "James Vince", "Janco Smit", "Jason Smith", "Jj Basson",
    "Jonny Bairstow", "Jordan Hermann", "Jos Buttler", "Jp King", "Junaid Dawood", "Kagiso Rabada",
    "Karim Janat", "Keagan Lion Cachet", "Keshav Maharaj", "Kwena Maphaka", "Kyle Verreynne",
    "Lewis Gregory", "Lhuan Dre Pretorius", "Lizaad Williams", "Lungi Ngidi", "Lutho Sipamla",
    "Marco Jansen", "Marques Ackerman", "Matthew Breetzke", "Meeka Eel Prince", "Mitchell Van Buuren",
    "Mujeeb Ur Rahman", "Nandre Burger", "Neil Timmers", "Nicholas Pooran", "Noor Ahmad", "Nqaba Peter",
    "Nqobani Mokoena", "Ottniel Baartman", "Patrick Kruger", "Prenelan Subrayen", "Quinton De Kock",
    "Rashid Khan", "Rassie Van Der Dussen", "Reece Topley", "Reeza Hendricks", "Richard Gleeson",
    "Rilee Rossouw", "Rivaldo Moonsamy", "Rubin Hermann", "Ryan Rickelton", "Saqib Mahmood",
    "Senuran Muthusamy", "Shai Hope", "Sherfane Rutherford", "Shubham Ranjane", "Sibonelo Makhanya",
    "Sikandar Raza", "Steve Stolk", "Sunil Narine", "Tabraiz Shamsi", "Tiaan Van Vuuren", "Tom Moores",
    "Tony De Zorzi", "Trent Boult", "Tristan Luus", "Tristan Stubbs", "Vishen Halambage", "Wiaan Mulder",
    "Wihan Lubbe", "Will Smeed"
]

BASE_URL = "https://www.sa20.co.za/player/"


def player_name_to_slug(name: str) -> str:
    """Convert player name to URL slug format (e.g., 'Faf Du Plessis' -> 'faf-du-plessis')."""
    slug = name.lower().strip()
    # Replace spaces with hyphens
    slug = slug.replace(" ", "-")
    # Remove special characters except hyphens
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def generate_player_urls() -> List[tuple[str, str]]:
    """Generate (player_name, url) tuples for all players."""
    urls = []
    for player_name in PLAYERS:
        slug = player_name_to_slug(player_name)
        url = BASE_URL + slug
        urls.append((player_name, url))
    return urls


def parse_int(value: str) -> int:
    """Parse integer value, handling dashes and empty strings."""
    value = str(value).strip()
    if not value or value == "—" or value == "-" or value == "0.00" or value == "":
        return 0
    # Remove commas and other formatting
    value = re.sub(r'[^\d]', '', value)
    try:
        return int(value) if value else 0
    except ValueError:
        return 0


def parse_float(value: str) -> float:
    """Parse float value, handling dashes and empty strings."""
    value = str(value).strip()
    if not value or value == "—" or value == "-" or value == "":
        return 0.0
    # Remove commas
    value = value.replace(',', '')
    try:
        return float(value) if value else 0.0
    except ValueError:
        return 0.0


async def extract_player_info(page: Page, player_name: str) -> Dict:
    """Extract player information from the page."""
    data = {
        "player_name": player_name,
        "team_name": None,
        "is_captain": False,
        "player_role": None,
        "personal_details": {
            "nationality": None,
            "date_of_birth": None,
            "birth_place": None,
            "batting_style": None,
            "bowling_style": None
        },
        "batting_fielding_stats": [],
        "bowling_stats": []
    }
    
    try:
        # Wait for page to fully load
        await page.wait_for_timeout(3000)
        
        # Wait for network to be idle
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        # Scroll to trigger lazy loading - more aggressive scrolling
        scroll_height = await page.evaluate("document.body.scrollHeight")
        scroll_steps = 5
        step_size = scroll_height // scroll_steps
        
        for i in range(scroll_steps + 1):
            scroll_pos = i * step_size
            await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
            await page.wait_for_timeout(1500)
        
        # Scroll back to top slowly
        for i in range(scroll_steps, -1, -1):
            scroll_pos = i * step_size
            await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
            await page.wait_for_timeout(1000)
        
        # Final wait for any remaining content to load
        await page.wait_for_timeout(3000)
        
        # Try to wait for table elements
        try:
            await page.wait_for_selector("div[role='table'], [class*='Table'], [class*='rdt_Table'], table", timeout=5000)
        except:
            pass
        
        # Extract player name, team, and role from header
        header_info = await page.evaluate("""
            () => {
                const h1 = document.querySelector('h1');
                const playerName = h1 ? h1.textContent.trim() : null;
                
                // Look for team name and captain indicator
                const teamElements = Array.from(document.querySelectorAll('*')).filter(el => {
                    const text = el.textContent || '';
                    return text.includes('Super Kings') || text.includes('Super Giants') || 
                           text.includes('Royals') || text.includes('Capitals') ||
                           text.includes('Eastern Cape') || text.includes('Cape Town');
                });
                
                let teamName = null;
                let isCaptain = false;
                
                // Check for captain badge or text
                const captainIndicators = Array.from(document.querySelectorAll('*')).filter(el => {
                    const text = (el.textContent || '').toLowerCase();
                    return text.includes('captain') || text.includes('(c)');
                });
                isCaptain = captainIndicators.length > 0;
                
                // Try to find role
                let role = null;
                const roleElements = Array.from(document.querySelectorAll('*')).filter(el => {
                    const text = (el.textContent || '').toLowerCase();
                    return text.includes('batter') || text.includes('bowler') || 
                           text.includes('all-rounder') || text.includes('wicket-keeper');
                });
                if (roleElements.length > 0) {
                    role = roleElements[0].textContent.trim();
                }
                
                return { playerName, teamName, isCaptain, role };
            }
        """)
        
        if header_info.get('playerName'):
            data["player_name"] = header_info['playerName']
        if header_info.get('teamName'):
            data["team_name"] = header_info['teamName']
        if header_info.get('isCaptain'):
            data["is_captain"] = header_info['isCaptain']
        if header_info.get('role'):
            data["player_role"] = header_info['role']
        
        # Extract personal details with better regex patterns
        personal_details = await page.evaluate("""
            () => {
                const bodyText = document.body.textContent || '';
                const details = {};
                
                // Extract nationality - more specific pattern
                const nationalityMatch = bodyText.match(/Nationality[^\\n]*?([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*?)(?:Date|Batting|Bowling|$)/i);
                if (nationalityMatch) {
                    details.nationality = nationalityMatch[1].trim();
                }
                
                // Extract date of birth - more specific pattern
                const dobMatch = bodyText.match(/Date of Birth[^\\n]*?(\\d{1,2}\\/\\d{1,2}\\/\\d{4})/i);
                if (dobMatch) {
                    details.date_of_birth = dobMatch[1].trim();
                }
                
                // Extract birth place - more specific pattern
                const birthPlaceMatch = bodyText.match(/Date of Birth[^\\n]*?in\\s+([^\\n<,]+?)(?:Batting|Bowling|Nationality|$)/i);
                if (birthPlaceMatch) {
                    details.birth_place = birthPlaceMatch[1].trim().replace(/\\s+/g, ' ');
                }
                
                // Extract batting style - more specific pattern
                const battingMatch = bodyText.match(/Batting Style[^\\n]*?([^\\n<]+?)(?:Bowling|Nationality|Date|$)/i);
                if (battingMatch) {
                    details.batting_style = battingMatch[1].trim().replace(/\\s+/g, ' ');
                }
                
                // Extract bowling style - more specific pattern
                const bowlingMatch = bodyText.match(/Bowling Style[^\\n]*?([^\\n<]+?)(?:Batting|Nationality|Date|$)/i);
                if (bowlingMatch) {
                    details.bowling_style = bowlingMatch[1].trim().replace(/\\s+/g, ' ');
                }
                
                return details;
            }
        """)
        
        if personal_details:
            # Clean up extracted values
            for key, value in personal_details.items():
                if value:
                    # Remove extra whitespace and limit length
                    cleaned = ' '.join(value.split())[:200]
                    if cleaned and not cleaned.startswith('Bowling') and not cleaned.startswith('Batting'):
                        data["personal_details"][key] = cleaned
        
        # Extract stats tables using more robust method
        # First extract all table data
        all_tables_data = await page.evaluate("""
            () => {
                const results = [];
                
                // Get HTML tables
                const htmlTables = Array.from(document.querySelectorAll('table'));
                htmlTables.forEach((table, idx) => {
                    const rows = Array.from(table.querySelectorAll('tr'));
                    const tableData = rows.map(row => {
                        const cells = Array.from(row.querySelectorAll('td, th'));
                        return cells.map(cell => cell.textContent.trim()).filter(cell => cell.length > 0);
                    }).filter(row => row.length >= 2);
                    if (tableData.length >= 2) {
                        results.push({
                            index: idx,
                            data: tableData,
                            type: 'html'
                        });
                    }
                });
                
                // Get div-based tables (React data tables)
                const divTables = Array.from(document.querySelectorAll('div[role="table"]'));
                divTables.forEach((table, idx) => {
                    const rows = Array.from(table.querySelectorAll('div[role="row"]'));
                    const tableData = rows.map(row => {
                        const cells = Array.from(row.querySelectorAll('div[role="cell"]'));
                        return cells.map(cell => cell.textContent.trim()).filter(cell => cell.length > 0);
                    }).filter(row => row.length >= 2);
                    if (tableData.length >= 2) {
                        results.push({
                            index: idx + htmlTables.length,
                            data: tableData,
                            type: 'div'
                        });
                    }
                });
                
                return results;
            }
        """)
        
        # Process tables to extract stats
        batting_stats = []
        bowling_stats = []
        
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
            
            # Determine table type
            table_type = 'unknown'
            if any(word in header_text for word in ['wkts', 'wickets', 'bbm', 'econ', '5w', 'balls']):
                table_type = 'bowling'
            elif any(word in header_text for word in ['hs', 'highest', '100', '50', '4s', '6s', 'bf', 'runs']):
                table_type = 'batting'
            
            if table_type == 'unknown':
                continue
            
            # Process rows
            for row in table_rows[1:]:
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
                    
                    if table_type == 'batting':
                        batting_stat = {
                            "year": str(year_int),
                            "team": team_str,
                            "mat": row[offset + 2] if offset + 2 < len(row) else "0",
                            "no": row[offset + 3] if offset + 3 < len(row) else "0",
                            "runs": row[offset + 4] if offset + 4 < len(row) else (row[offset + 3] if offset + 3 < len(row) else "0"),
                            "hs": row[offset + 5] if offset + 5 < len(row) else (row[offset + 4] if offset + 4 < len(row) else "0"),
                            "avg": row[offset + 6] if offset + 6 < len(row) else (row[offset + 5] if offset + 5 < len(row) else "0"),
                            "bf": row[offset + 7] if offset + 7 < len(row) else (row[offset + 6] if offset + 6 < len(row) else "0"),
                            "sr": row[offset + 8] if offset + 8 < len(row) else (row[offset + 7] if offset + 7 < len(row) else "0"),
                            "100": row[offset + 9] if offset + 9 < len(row) else (row[offset + 8] if offset + 8 < len(row) else "0"),
                            "50": row[offset + 10] if offset + 10 < len(row) else (row[offset + 9] if offset + 9 < len(row) else "0"),
                            "4s": row[offset + 11] if offset + 11 < len(row) else (row[offset + 10] if offset + 10 < len(row) else "0"),
                            "6s": row[offset + 12] if offset + 12 < len(row) else (row[offset + 11] if offset + 11 < len(row) else "0"),
                        }
                        batting_stats.append(batting_stat)
                    elif table_type == 'bowling':
                        bowling_stat = {
                            "year": str(year_int),
                            "team": team_str,
                            "mat": row[offset + 2] if offset + 2 < len(row) else "0",
                            "balls": row[offset + 3] if offset + 3 < len(row) else "0",
                            "runs": row[offset + 4] if offset + 4 < len(row) else "0",
                            "wkts": row[offset + 5] if offset + 5 < len(row) else "0",
                            "bbm": row[offset + 6].strip() if offset + 6 < len(row) and row[offset + 6].strip() not in ["—", "-", "", "0", "–"] else "-",
                            "ave": row[offset + 7] if offset + 7 < len(row) else "0",
                            "econ": row[offset + 8] if offset + 8 < len(row) else "0",
                            "sr": row[offset + 9] if offset + 9 < len(row) else "0",
                            "5w": row[offset + 10] if offset + 10 < len(row) else "0",
                        }
                        bowling_stats.append(bowling_stat)
                except Exception as e:
                    logger.debug(f"Error parsing {table_type} row: {e}")
                    continue
        
        data["batting_fielding_stats"] = batting_stats
        data["bowling_stats"] = bowling_stats
        
        
    except Exception as e:
        logger.error(f"Error extracting player info for {player_name}: {e}")
    
    return data


async def scrape_player_profile(player_name: str, url: str) -> Optional[Dict]:
    """Scrape a single player profile page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            logger.info(f"Scraping: {player_name} ({url})")
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Check if page loaded successfully
            if response and response.status == 404:
                logger.warning(f"  ✗ Page not found (404): {url}")
                await browser.close()
                return None
            
            # Wait for content to load
            await page.wait_for_timeout(3000)
            
            # Scroll to trigger lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(2000)
            
            # Extract player data
            player_data = await extract_player_info(page, player_name)
            
            await browser.close()
            logger.info(f"  ✓ Successfully scraped {player_name}")
            return player_data
            
        except PlaywrightTimeout:
            logger.error(f"  ✗ Timeout loading {player_name} ({url})")
            await browser.close()
            return None
        except Exception as e:
            logger.error(f"  ✗ Error scraping {player_name} ({url}): {e}")
            await browser.close()
            return None


async def scrape_all_players(limit: Optional[int] = None, output_file: str = "players.json") -> List[Dict]:
    """Scrape all player profiles."""
    urls = generate_player_urls()
    
    if limit:
        urls = urls[:limit]
        logger.info(f"Limiting to first {limit} players")
    
    logger.info(f"Starting to scrape {len(urls)} players...")
    
    all_players = []
    successful = 0
    failed = 0
    
    # Scrape sequentially to avoid overwhelming the server
    for i, (player_name, url) in enumerate(urls, 1):
        logger.info(f"[{i}/{len(urls)}] Processing {player_name}...")
        
        player_data = await scrape_player_profile(player_name, url)
        
        if player_data:
            all_players.append(player_data)
            successful += 1
        else:
            failed += 1
        
        # Be respectful - add delay between requests
        if i < len(urls):
            await asyncio.sleep(2)
    
    # Save to JSON file
    output_path = Path(__file__).parent.parent.parent / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_players, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n=== Scraping Summary ===")
    logger.info(f"Total players: {len(urls)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Output saved to: {output_path}")
    
    return all_players


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape all SA20 player profiles")
    parser.add_argument("--limit", type=int, help="Limit number of players to scrape")
    parser.add_argument("--output", type=str, default="players.json", help="Output JSON file name")
    
    args = parser.parse_args()
    
    await scrape_all_players(limit=args.limit, output_file=args.output)


if __name__ == "__main__":
    asyncio.run(main())

