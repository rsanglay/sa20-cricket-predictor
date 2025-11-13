"""Player service layer."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.db import models
from app.services.player_projection_service import PlayerProjectionService
from app.core.cache import cache_result

logger = logging.getLogger(__name__)


@dataclass
class PlayerService:
    db: Session
    projection_service: Optional[PlayerProjectionService] = None

    def __post_init__(self) -> None:
        if self.projection_service is None:
            try:
                self.projection_service = PlayerProjectionService()
            except FileNotFoundError:
                self.projection_service = None

    def get_players(
        self,
        role: Optional[str] = None,
        team_id: Optional[int] = None,
        country: Optional[str] = None,
        only_with_images: bool = False,
        only_with_projection: bool = False,
        skip_image_filter: bool = False,
    ) -> List[Dict]:
        # Optimized query - only load what's needed
        query = self.db.query(models.Player)
        if role:
            query = query.filter(models.Player.role == role)
        if team_id:
            query = query.filter(models.Player.team_id == team_id)
        if country:
            query = query.filter(models.Player.country == country)
        
        # Filter players with images if requested (for team views, only show current squad with photos)
        if not skip_image_filter and (only_with_images or team_id):
            # Only return players with valid image URLs
            query = query.filter(
                models.Player.image_url.isnot(None),
                models.Player.image_url != '',
                ~models.Player.image_url.like('%placeholder%'),
                ~models.Player.image_url.like('%default%'),
            )
        
        # Order by name for consistent results
        query = query.order_by(models.Player.name)
        players = query.all()
        
        # Additional filtering for image URLs (filter out UI elements and invalid URLs)
        filtered_players = []
        ui_patterns = ['instagram', 'logo', 'search', 'hamburger', 'chevron', 'icon', 'button', 'menu', 'arrow', 'svg', 'facebook', 'twitter', 'youtube']
        image_keywords = ['player', 'squad', 'team', 'photo', 'image', 'picture', 'portrait', 'headshot']
        image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        
        for player in players:
            if player.image_url:
                url_lower = player.image_url.lower().strip()
                
                # Skip if URL contains UI element patterns
                if any(pattern in url_lower for pattern in ui_patterns):
                    continue
                
                # Skip if URL is too short (likely invalid)
                if len(url_lower) < 10:
                    continue
                
                # Check if it's a valid image URL
                is_valid = False
                
                # Check for image extensions
                if any(ext in url_lower for ext in image_extensions):
                    is_valid = True
                # Check for image-related keywords
                elif any(keyword in url_lower for keyword in image_keywords):
                    is_valid = True
                # Check if it starts with http/https (valid URL)
                elif url_lower.startswith('http://') or url_lower.startswith('https://'):
                    # Additional check: should not be a social media or UI URL
                    if not any(bad_pattern in url_lower for bad_pattern in ['facebook', 'twitter', 'instagram', 'linkedin', 'youtube', 'google', 'cdn']):
                        is_valid = True
                
                if is_valid:
                    filtered_players.append(player)
            elif not only_with_images and (not team_id or skip_image_filter):
                # Allow players without images if we're not restricting to images or when explicitly skipping the filter
                filtered_players.append(player)

        # Optionally filter to players with projection data available
        if only_with_projection and self.projection_service:
            filtered_players = [
                player for player in filtered_players
                if self.projection_service.has_projection(player.name)
            ]
        
        return [self._to_dict(player) for player in filtered_players]

    @cache_result(expire=1800, key_prefix="player_detail")  # Cache for 30 minutes
    def get_player_detail(self, player_id: int) -> Optional[Dict]:
        # Optimized query with eager loading and aggregation
        player = self.db.query(models.Player).filter(models.Player.id == player_id).first()
        if not player:
            return None
        
        # Ensure JSONB field is loaded (refresh if needed)
        self.db.refresh(player, ['scraped_season_stats'])
        
        # Calculate age from birth_date if available
        age = player.age
        if player.birth_date:
            today = datetime.now().date()
            birth_date = player.birth_date.date() if isinstance(player.birth_date, datetime) else player.birth_date
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        # ALWAYS prioritize scraped season stats from sa20.co.za for overall career stats
        # This is the authoritative source with all historical data from https://www.sa20.co.za/player/
        # Only use PlayerPerformance records if scraped stats are completely unavailable
        stats = None
        
        # Check if we have scraped stats from sa20.co.za
        has_scraped_stats = (
            player.scraped_season_stats 
            and isinstance(player.scraped_season_stats, dict)
            and player.scraped_season_stats.get('season_stats')
            and isinstance(player.scraped_season_stats.get('season_stats'), list)
            and len(player.scraped_season_stats.get('season_stats', [])) > 0
        )
        
        if has_scraped_stats:
            # Use scraped stats from sa20.co.za (authoritative source)
            stats = self._calculate_stats_from_scraped_data(player)
        else:
            # Fallback to PlayerPerformance records ONLY if no scraped stats available
            # Count distinct matches, not performance records (a player can have multiple records per match)
            stats = self.db.query(
                func.count(func.distinct(models.PlayerPerformance.match_id)).label('matches_played'),
                func.coalesce(func.sum(models.PlayerPerformance.runs_scored), 0).label('runs_scored'),
                func.coalesce(func.sum(models.PlayerPerformance.balls_faced), 0).label('balls_faced'),
                func.coalesce(func.sum(models.PlayerPerformance.wickets_taken), 0).label('wickets_taken'),
                func.coalesce(func.sum(models.PlayerPerformance.runs_conceded), 0).label('runs_conceded'),
                func.coalesce(func.sum(models.PlayerPerformance.overs_bowled), 0).label('overs_bowled'),
                func.coalesce(func.sum(models.PlayerPerformance.fours), 0).label('fours'),
                func.coalesce(func.sum(models.PlayerPerformance.sixes), 0).label('sixes'),
                func.max(models.PlayerPerformance.runs_scored).label('highest_score'),
            ).filter(models.PlayerPerformance.player_id == player_id).first()
            
            # Last resort: try to get from scraped stats even if structure seems wrong
            if not stats or (stats.matches_played or 0) == 0:
                stats = self._calculate_stats_from_scraped_data(player)
        
        # Get best bowling figures - ALWAYS prioritize scraped stats from sa20.co.za
        best_bowling_figures = None
        if has_scraped_stats:
            # Calculate from scraped stats (authoritative source from sa20.co.za)
            best_bowling_figures = self._get_best_bowling_from_scraped(player.scraped_season_stats)
        
        # Fallback to PlayerPerformance ONLY if not in scraped stats
        if not best_bowling_figures:
            best_bowling = self.db.query(
                models.PlayerPerformance.wickets_taken,
                models.PlayerPerformance.runs_conceded
            ).filter(
                models.PlayerPerformance.player_id == player_id,
                models.PlayerPerformance.wickets_taken > 0
            ).order_by(
                models.PlayerPerformance.wickets_taken.desc(),
                models.PlayerPerformance.runs_conceded.asc()
            ).first()
            
            if best_bowling:
                best_bowling_figures = f"{best_bowling.wickets_taken}/{best_bowling.runs_conceded}"
        
        # Get season-by-season stats - ALWAYS prioritize scraped stats from sa20.co.za
        if has_scraped_stats:
            # Use scraped stats (authoritative source from https://www.sa20.co.za/player/)
            season_stats = self._convert_scraped_season_stats(player.scraped_season_stats)
        else:
            # Fallback to PlayerPerformance records ONLY if no scraped stats
            season_stats = self._get_season_stats(player_id)
        
        # Get recent performances with optimized query using join and selectinload
        recent_perfs = self.db.query(models.PlayerPerformance).filter(
            models.PlayerPerformance.player_id == player_id
        ).join(models.Match).options(
            selectinload(models.PlayerPerformance.match).selectinload(models.Match.home_team),
            selectinload(models.PlayerPerformance.match).selectinload(models.Match.away_team)
        ).order_by(models.Match.match_date.desc()).limit(5).all()
        
        # Build recent form
        recent_form = []
        for perf in recent_perfs:
            match = perf.match
            if match:
                # Determine opponent - need to check which team the player was playing for
                # For simplicity, show away team if player's team was home, else home team
                if match.home_team_id == player.team_id:
                    opponent = match.away_team.name if match.away_team else "TBD"
                else:
                    opponent = match.home_team.name if match.home_team else "TBD"
                recent_form.append({
                    "match_id": perf.match_id,
                    "date": match.match_date.isoformat() if match.match_date else "",
                    "opponent": opponent,
                    "runs": perf.runs_scored,
                    "balls_faced": perf.balls_faced,
                    "wickets": perf.wickets_taken,
                })
        
        # Count fifties, hundreds, and 5-wicket hauls - ALWAYS prioritize scraped stats from sa20.co.za
        fifties = 0
        hundreds = 0
        five_wickets = 0
        
        if has_scraped_stats:
            # Calculate from scraped stats (authoritative source from sa20.co.za)
            scraped_fifties, scraped_hundreds, scraped_five_wickets = self._calculate_milestones_from_scraped(player.scraped_season_stats)
            fifties = scraped_fifties
            hundreds = scraped_hundreds
            five_wickets = scraped_five_wickets
        
        # Fallback to PlayerPerformance ONLY if scraped stats not available or incomplete
        if fifties == 0 and hundreds == 0 and five_wickets == 0:
            fifties = self.db.query(func.count(models.PlayerPerformance.id)).filter(
                models.PlayerPerformance.player_id == player_id,
                models.PlayerPerformance.runs_scored >= 50,
                models.PlayerPerformance.runs_scored < 100
            ).scalar() or 0
            
            hundreds = self.db.query(func.count(models.PlayerPerformance.id)).filter(
                models.PlayerPerformance.player_id == player_id,
                models.PlayerPerformance.runs_scored >= 100
            ).scalar() or 0
            
            five_wickets = self.db.query(func.count(models.PlayerPerformance.id)).filter(
                models.PlayerPerformance.player_id == player_id,
                models.PlayerPerformance.wickets_taken >= 5
            ).scalar() or 0
        
        player_dict = self._to_dict(player)
        player_dict['age'] = age
        player_dict['birth_date'] = player.birth_date.isoformat() if player.birth_date else None
        
        return {
            **player_dict,
            "international_caps": player.international_caps,
            "career_stats": {
                "matches_played": stats.matches_played or 0 if stats else 0,
                "runs_scored": int(stats.runs_scored or 0),
                "batting_average": self._safe_div(stats.runs_scored or 0, stats.matches_played or 1),
                "strike_rate": self._safe_div((stats.runs_scored or 0) * 100, stats.balls_faced or 1),
                "highest_score": int(stats.highest_score or 0),
                "fours": int(stats.fours or 0),
                "sixes": int(stats.sixes or 0),
                "fifties": fifties,
                "hundreds": hundreds,
                "wickets_taken": int(stats.wickets_taken or 0),
                "economy_rate": self._safe_div(stats.runs_conceded or 0, stats.overs_bowled or 1),
                "bowling_average": self._safe_div(stats.runs_conceded or 0, stats.wickets_taken or 1),
                "best_bowling_figures": best_bowling_figures,
                "five_wickets": five_wickets,
            },
            "season_stats": season_stats,
            "recent_form": {
                "last_5_matches": recent_form,
                "trend": "stable",
            },
        }
    
    def _get_season_stats(self, player_id: int) -> List[Dict]:
        """Get season-by-season stats for a player."""
        # Get all performances with match info
        performances = self.db.query(
            models.PlayerPerformance,
            models.Match.season,
            models.Team.name.label('team_name')
        ).join(
            models.Match, models.PlayerPerformance.match_id == models.Match.id
        ).join(
            models.Team, models.Team.id == models.PlayerPerformance.team_id
        ).filter(
            models.PlayerPerformance.player_id == player_id
        ).all()
        
        # Group by season and team
        season_data = {}
        for perf, season, team_name in performances:
            key = (season, team_name)
            if key not in season_data:
                season_data[key] = {
                    'season': season,
                    'team': team_name,
                    'matches': set(),
                    'batting_matches': set(),
                    'bowling_matches': set(),
                    'runs': 0,
                    'balls_faced': 0,
                    'fours': 0,
                    'sixes': 0,
                    'highest_score': 0,
                    'overs_bowled': 0.0,
                    'runs_conceded': 0,
                    'wickets': 0,
                    'best_bowling': None,
                    'five_wickets_count': 0,
                }
            
            data = season_data[key]
            data['matches'].add(perf.match_id)
            
            # Batting stats
            if perf.runs_scored > 0 or perf.balls_faced > 0:
                data['batting_matches'].add(perf.match_id)
                data['runs'] += perf.runs_scored
                data['balls_faced'] += perf.balls_faced
                data['highest_score'] = max(data['highest_score'], perf.runs_scored)
                data['fours'] += perf.fours
                data['sixes'] += perf.sixes
            
            # Bowling stats
            if perf.overs_bowled > 0:
                data['bowling_matches'].add(perf.match_id)
                data['overs_bowled'] += perf.overs_bowled
                data['runs_conceded'] += perf.runs_conceded
                data['wickets'] += perf.wickets_taken
                if perf.wickets_taken >= 5:
                    data['five_wickets_count'] += 1
                # Track best bowling
                if perf.wickets_taken > 0:
                    if data['best_bowling'] is None:
                        data['best_bowling'] = (perf.wickets_taken, perf.runs_conceded)
                    else:
                        current_wkts, current_runs = data['best_bowling']
                        if perf.wickets_taken > current_wkts or (perf.wickets_taken == current_wkts and perf.runs_conceded < current_runs):
                            data['best_bowling'] = (perf.wickets_taken, perf.runs_conceded)
        
        # Convert to list and format
        result = []
        for (season, team_name), data in sorted(season_data.items(), key=lambda x: x[0][0], reverse=True):
            matches = len(data['matches'])
            batting_matches = len(data['batting_matches'])
            bowling_matches = len(data['bowling_matches'])
            balls_bowled = int(data['overs_bowled'] * 6)
            
            # Calculate batting stats
            batting_avg = self._safe_div(data['runs'], batting_matches) if batting_matches > 0 else 0.0
            strike_rate = self._safe_div(data['runs'] * 100, data['balls_faced']) if data['balls_faced'] > 0 else 0.0
            
            # Calculate bowling stats
            bowling_avg = self._safe_div(data['runs_conceded'], data['wickets']) if data['wickets'] > 0 else 0.0
            economy = self._safe_div(data['runs_conceded'], data['overs_bowled']) if data['overs_bowled'] > 0 else 0.0
            bowling_sr = self._safe_div(balls_bowled, data['wickets']) if data['wickets'] > 0 else 0.0
            
            best_figures_str = None
            if data['best_bowling']:
                wkts, runs = data['best_bowling']
                best_figures_str = f"{wkts}/{runs}"
            
            result.append({
                "season": season,
                "team": team_name,
                "batting": {
                    "matches": batting_matches if batting_matches > 0 else matches,
                    "runs": data['runs'],
                    "highest_score": data['highest_score'],
                    "average": batting_avg,
                    "strike_rate": strike_rate,
                    "balls_faced": data['balls_faced'],
                    "fours": data['fours'],
                    "sixes": data['sixes'],
                },
                "bowling": {
                    "matches": bowling_matches if bowling_matches > 0 else 0,
                    "balls": balls_bowled,
                    "runs": data['runs_conceded'],
                    "wickets": data['wickets'],
                    "average": bowling_avg,
                    "economy": economy,
                    "strike_rate": bowling_sr,
                    "best_figures": best_figures_str,
                    "five_wickets": data['five_wickets_count'],
                }
            })
        
        return result

    def get_player_stats(self, player_id: int, season: Optional[int] = None) -> Optional[Dict]:
        player = self.db.get(models.Player, player_id)
        if not player:
            return None
        performances = player.performances
        if season:
            performances = [p for p in performances if p.match and p.match.season == season]
        return {
            "player_id": player_id,
            "season": season,
            "batting": {
                "innings": len(performances),
                "runs": sum(p.runs_scored for p in performances),
                "average": self._safe_div(sum(p.runs_scored for p in performances), len(performances) or 1),
                "strike_rate": self._safe_div(
                    sum(p.runs_scored for p in performances) * 100,
                    sum(p.balls_faced for p in performances) or 1,
                ),
                "fifties": 0,
                "hundreds": 0,
            },
            "bowling": {
                "innings": len([p for p in performances if p.overs_bowled > 0]),
                "overs": sum(p.overs_bowled for p in performances),
                "wickets": sum(p.wickets_taken for p in performances),
                "average": self._safe_div(
                    sum(p.runs_conceded for p in performances),
                    sum(p.wickets_taken for p in performances) or 1,
                ),
                "economy": self._safe_div(
                    sum(p.runs_conceded for p in performances),
                    sum(p.overs_bowled for p in performances) or 1,
                ),
                "best_figures": "",
            },
        }

    def _to_dict(self, player: models.Player) -> Dict:
        # Calculate age from birth_date if available
        age = player.age
        if player.birth_date:
            today = datetime.now().date()
            birth_date = player.birth_date.date() if isinstance(player.birth_date, datetime) else player.birth_date
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        return {
            "id": player.id,
            "team_id": player.team_id,
            "name": player.name,
            "role": player.role.value if hasattr(player.role, "value") else player.role,
            "batting_style": player.batting_style.value if hasattr(player.batting_style, "value") else player.batting_style,
            "bowling_style": player.bowling_style.value if hasattr(player.bowling_style, "value") else player.bowling_style,
            "country": player.country,
            "age": age,
            "birth_date": player.birth_date.isoformat() if player.birth_date else None,
            "auction_price": player.auction_price,
            "image_url": player.image_url,
            "has_projection": bool(self.projection_service and self.projection_service.has_projection(player.name)),
        }

    def _safe_div(self, numerator: float, denominator: float) -> float:
        return float(numerator / denominator) if denominator else 0.0
    
    def _calculate_stats_from_scraped_data(self, player: models.Player) -> type('Stats', (), {}):
        """Calculate career stats from scraped season stats."""
        # Create a simple object to hold stats (similar to SQLAlchemy result)
        class Stats:
            def __init__(self):
                self.matches_played = 0
                self.runs_scored = 0
                self.balls_faced = 0
                self.wickets_taken = 0
                self.runs_conceded = 0
                self.overs_bowled = 0.0
                self.fours = 0
                self.sixes = 0
                self.highest_score = 0
        
        stats = Stats()
        
        if not player.scraped_season_stats or 'season_stats' not in player.scraped_season_stats:
            return stats
        
        season_stats_list = player.scraped_season_stats.get('season_stats', [])
        # Track matches per season+team to avoid double counting
        # Use max of batting and bowling matches since a player can both bat and bowl in same match
        season_team_matches = {}  # (season, team) -> matches
        
        for season_stat in season_stats_list:
            season = season_stat.get('season', '')
            team = season_stat.get('team', '')
            key = (season, team)
            
            # Aggregate batting stats
            if 'batting' in season_stat:
                batting = season_stat['batting']
                stats.runs_scored += batting.get('runs', 0) or 0
                # Scraped data uses 'balls_faced' for batting, 'balls' for bowling
                stats.balls_faced += batting.get('balls_faced', batting.get('balls', 0)) or 0
                stats.fours += batting.get('fours', 0) or 0
                stats.sixes += batting.get('sixes', 0) or 0
                highest = batting.get('highest_score', 0) or 0
                if highest > stats.highest_score:
                    stats.highest_score = highest
                # Track batting matches for this season+team
                batting_matches = batting.get('matches', 0) or 0
                if key not in season_team_matches:
                    season_team_matches[key] = 0
                season_team_matches[key] = max(season_team_matches[key], batting_matches)
            
            # Aggregate bowling stats
            if 'bowling' in season_stat:
                bowling = season_stat['bowling']
                stats.wickets_taken += bowling.get('wickets', 0) or 0
                stats.runs_conceded += bowling.get('runs', 0) or 0
                # Convert balls to overs (6 balls = 1 over)
                balls = bowling.get('balls', 0) or 0
                stats.overs_bowled += balls / 6.0
                # Track bowling matches for this season+team (use max to avoid double counting)
                bowling_matches = bowling.get('matches', 0) or 0
                if key not in season_team_matches:
                    season_team_matches[key] = 0
                season_team_matches[key] = max(season_team_matches[key], bowling_matches)
        
        # Sum up all unique season+team match counts
        stats.matches_played = sum(season_team_matches.values())
        
        return stats
    
    def _get_best_bowling_from_scraped(self, scraped_stats: dict) -> Optional[str]:
        """Get best bowling figures from scraped stats."""
        if not scraped_stats or 'season_stats' not in scraped_stats:
            return None
        
        best_wickets = 0
        best_runs = float('inf')
        
        for season_stat in scraped_stats.get('season_stats', []):
            if 'bowling' in season_stat:
                bowling = season_stat['bowling']
                best_figures = bowling.get('best_figures')
                if best_figures:
                    # Parse "X/Y" format
                    if '/' in str(best_figures):
                        try:
                            parts = str(best_figures).split('/')
                            wickets = int(parts[0])
                            runs = int(parts[1])
                            if wickets > best_wickets or (wickets == best_wickets and runs < best_runs):
                                best_wickets = wickets
                                best_runs = runs
                        except:
                            pass
        
        if best_wickets > 0:
            return f"{best_wickets}/{int(best_runs)}"
        return None
    
    def _calculate_milestones_from_scraped(self, scraped_stats: dict) -> tuple[int, int, int]:
        """Calculate fifties, hundreds, and 5-wicket hauls from scraped stats."""
        fifties = 0
        hundreds = 0
        five_wickets = 0
        
        if not scraped_stats or 'season_stats' not in scraped_stats:
            return (fifties, hundreds, five_wickets)
        
        for season_stat in scraped_stats.get('season_stats', []):
            # Count fifties and hundreds from batting stats
            if 'batting' in season_stat:
                batting = season_stat['batting']
                fifties += batting.get('fifties', 0) or 0
                hundreds += batting.get('hundreds', 0) or 0
            
            # Count 5-wicket hauls from bowling stats
            if 'bowling' in season_stat:
                bowling = season_stat['bowling']
                five_wickets += bowling.get('five_wickets', 0) or 0
        
        return (fifties, hundreds, five_wickets)
    
    def _convert_scraped_season_stats(self, scraped_stats: dict) -> List[Dict]:
        """Convert scraped season stats to the format expected by the API."""
        if not scraped_stats or 'season_stats' not in scraped_stats:
            return []
        
        result = []
        for season_stat in scraped_stats.get('season_stats', []):
            batting = season_stat.get('batting', {})
            bowling = season_stat.get('bowling', {})
            
            # Calculate averages and rates
            # Scraped data uses 'balls_faced' for batting, 'balls' for bowling
            batting_balls = batting.get('balls_faced', batting.get('balls', 0)) or 0
            batting_avg = self._safe_div(batting.get('runs', 0) or 0, batting.get('matches', 1) or 1)
            strike_rate = self._safe_div((batting.get('runs', 0) or 0) * 100, batting_balls or 1)
            
            bowling_avg = self._safe_div(bowling.get('runs', 0) or 0, bowling.get('wickets', 1) or 1)
            economy = self._safe_div(bowling.get('runs', 0) or 0, (bowling.get('balls', 0) or 0) / 6.0)
            bowling_sr = self._safe_div(bowling.get('balls', 0) or 0, bowling.get('wickets', 1) or 1)
            
            result.append({
                "season": season_stat.get('season', ''),
                "team": season_stat.get('team', ''),
                "batting": {
                    "matches": batting.get('matches', 0) or 0,
                    "runs": batting.get('runs', 0) or 0,
                    "highest_score": batting.get('highest_score', 0) or 0,
                    "average": batting_avg,
                    "strike_rate": strike_rate,
                    "balls_faced": batting_balls,
                    "fours": batting.get('fours', 0) or 0,
                    "sixes": batting.get('sixes', 0) or 0,
                },
                "bowling": {
                    "matches": bowling.get('matches', 0) or 0,
                    "balls": bowling.get('balls', 0) or 0,
                    "runs": bowling.get('runs', 0) or 0,
                    "wickets": bowling.get('wickets', 0) or 0,
                    "average": bowling_avg,
                    "economy": economy,
                    "strike_rate": bowling_sr,
                    "best_figures": bowling.get('best_figures'),
                    "five_wickets": bowling.get('five_wickets', 0) or 0,
                }
            })
        
        return result

    def predict_performance(self, player_id: int) -> Optional[Dict]:
        if not self.projection_service:
            return None
        player = self.db.get(models.Player, player_id)
        if not player:
            return None
        try:
            projection = self.projection_service.predict_player(player.name)
        except ValueError:
            return None
        projection.update(
            {
                "player_id": player.id,
                "team_id": player.team_id,
            }
        )
        return projection
