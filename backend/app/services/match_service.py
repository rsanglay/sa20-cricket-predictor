"""Match service layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from sqlalchemy.orm import Session

from app.db import models


@dataclass
class MatchService:
    db: Session

    def get_matches(self, season: int | None = None, team_id: int | None = None, venue_id: int | None = None) -> List[Dict]:
        query = self.db.query(models.Match)
        if season:
            query = query.filter(models.Match.season == season)
        if team_id:
            query = query.filter(
                (models.Match.home_team_id == team_id) | (models.Match.away_team_id == team_id)
            )
        if venue_id:
            query = query.filter(models.Match.venue_id == venue_id)
        return [self._to_dict(match) for match in query.all()]
    
    def get_upcoming_matches(self, season: int = 2026, limit: int = 10) -> List[Dict]:
        """Get upcoming matches for the season, ordered by date."""
        from datetime import datetime
        query = self.db.query(models.Match).filter(
            models.Match.season == season
        )
        # Filter by winner_team_id (or winner_id as fallback) - for new matches, this will be None
        # Check if winner_team_id exists first, then fall back to winner_id
        if hasattr(models.Match, 'winner_team_id'):
            query = query.filter(models.Match.winner_team_id.is_(None))
        else:
            query = query.filter(models.Match.winner_id.is_(None))
        # Order by date_utc if available, otherwise match_date
        if hasattr(models.Match, 'date_utc'):
            query = query.order_by(models.Match.date_utc.asc().nulls_last())
        else:
            query = query.order_by(models.Match.match_date.asc().nulls_last())
        if limit:
            query = query.limit(limit)
        matches = query.all()
        result = []
        for match in matches:
            match_dict = self._to_dict(match)
            # Add team names and venue name
            if match.home_team:
                match_dict["home_team_name"] = match.home_team.name
            if match.away_team:
                match_dict["away_team_name"] = match.away_team.name
            if match.venue:
                match_dict["venue_name"] = match.venue.name
            result.append(match_dict)
        return result

    def get_match_detail(self, match_id: int) -> Dict:
        match = self.db.get(models.Match, match_id)
        return self._to_dict(match) if match else {}

    def get_head_to_head(self, team1_id: int, team2_id: int) -> Dict:
        matches = self.db.query(models.Match).filter(
            ((models.Match.home_team_id == team1_id) & (models.Match.away_team_id == team2_id))
            | ((models.Match.home_team_id == team2_id) & (models.Match.away_team_id == team1_id))
        )
        total = matches.count()
        # Use winner_team_id if available, otherwise fall back to winner_id
        winner_field = models.Match.winner_team_id if hasattr(models.Match, 'winner_team_id') else models.Match.winner_id
        team1_wins = matches.filter(winner_field == team1_id).count()
        team2_wins = matches.filter(winner_field == team2_id).count()
        return {
            "team1_id": team1_id,
            "team2_id": team2_id,
            "total_matches": total,
            "team1_wins": team1_wins,
            "team2_wins": team2_wins,
            "ties": total - team1_wins - team2_wins,
        }

    def _to_dict(self, match: models.Match | None) -> Dict:
        if not match:
            return {}
        # Use date_utc if available, otherwise match_date
        match_date = match.date_utc if hasattr(match, 'date_utc') and match.date_utc else match.match_date
        # Use winner_team_id if available, otherwise winner_id
        winner_id = match.winner_team_id if hasattr(match, 'winner_team_id') and match.winner_team_id else (match.winner_id if hasattr(match, 'winner_id') else None)
        result = {
            "id": match.id,
            "home_team_id": match.home_team_id,
            "away_team_id": match.away_team_id,
            "venue_id": match.venue_id,
            "match_date": match_date.isoformat() if match_date else "",
            "season": match.season,
            "winner_id": winner_id,
            "margin": match.margin if hasattr(match, 'margin') else None,
            "match_number": match.match_no if hasattr(match, 'match_no') else (match.match_number if hasattr(match, 'match_number') else None),
        }
        # Add team and venue names if available
        if match.home_team:
            result["home_team_name"] = match.home_team.name
        if match.away_team:
            result["away_team_name"] = match.away_team.name
        if match.venue:
            result["venue_name"] = match.venue.name
        return result
