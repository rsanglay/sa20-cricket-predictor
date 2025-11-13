"""Loading utilities for persisting data into the database."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from app.db import models


@dataclass
class DataLoader:
    db: Session

    def load_teams(self, teams: pd.DataFrame) -> None:
        for _, row in teams.iterrows():
            team = models.Team(
                name=row["name"],
                short_name=row.get("short_name", row["name"][:3].upper()),
                home_venue=row.get("home_venue", ""),
                founded_year=row.get("founded_year"),
            )
            self.db.add(team)
        self.db.commit()

    def load_players(self, players: pd.DataFrame) -> None:
        # Map role strings to enum
        role_map = {
            "batsman": models.PlayerRole.BATSMAN,
            "batter": models.PlayerRole.BATSMAN,
            "bowler": models.PlayerRole.BOWLER,
            "all-rounder": models.PlayerRole.ALL_ROUNDER,
            "all_rounder": models.PlayerRole.ALL_ROUNDER,
            "wicket-keeper": models.PlayerRole.WICKET_KEEPER,
            "wicket_keeper": models.PlayerRole.WICKET_KEEPER,
            "keeper": models.PlayerRole.WICKET_KEEPER,
            "wk": models.PlayerRole.WICKET_KEEPER,
        }
        
        for _, row in players.iterrows():
            # Get and normalize role
            role_str = row.get("role")
            if role_str:
                role_str = str(role_str).lower().strip()
                role = role_map.get(role_str, models.PlayerRole.BATSMAN)
            else:
                role = models.PlayerRole.BATSMAN  # Default fallback
            
            # Get and normalize batting style
            batting_style_str = row.get("batting_style")
            batting_style = models.BattingStyle.RIGHT_HAND  # Default
            if batting_style_str:
                batting_style_str = str(batting_style_str).lower().strip()
                if "left" in batting_style_str:
                    batting_style = models.BattingStyle.LEFT_HAND
            
            # Get and normalize bowling style
            bowling_style = None
            bowling_style_str = row.get("bowling_style")
            if bowling_style_str:
                bowling_style_str = str(bowling_style_str).lower().strip()
                if "fast" in bowling_style_str:
                    bowling_style = models.BowlingStyle.RIGHT_ARM_FAST if "right" in bowling_style_str else models.BowlingStyle.LEFT_ARM_FAST
                elif "medium" in bowling_style_str:
                    bowling_style = models.BowlingStyle.RIGHT_ARM_MEDIUM if "right" in bowling_style_str else models.BowlingStyle.LEFT_ARM_MEDIUM
                elif "spin" in bowling_style_str:
                    bowling_style = models.BowlingStyle.RIGHT_ARM_SPIN if "right" in bowling_style_str else models.BowlingStyle.LEFT_ARM_SPIN
            
            player = models.Player(
                name=row["name"],
                role=role,
                batting_style=batting_style,
                bowling_style=bowling_style,
                team_id=row.get("team_id"),
                country=row.get("country", "South Africa"),
                age=row.get("age", 0),
                auction_price=row.get("auction_price"),
            )
            self.db.add(player)
        self.db.commit()

    def load_matches(self, matches: pd.DataFrame) -> None:
        for _, row in matches.iterrows():
            match = models.Match(
                home_team_id=row["home_team_id"],
                away_team_id=row["away_team_id"],
                venue_id=row["venue_id"],
                match_date=row["match_date"],
                season=row.get("season", 2025),
                winner_id=row.get("winner_id"),
            )
            self.db.add(match)
        self.db.commit()
