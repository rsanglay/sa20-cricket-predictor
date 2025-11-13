"""Service utilities for exposing aggregated cricket analytics."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class AnalyticsService:
    """Loads pre-computed aggregates stored under data/processed."""

    processed_dir: Path = (
        Path(__file__).resolve().parents[2] / "data" / "processed"
        if (Path(__file__).resolve().parents[2] / "data" / "processed").exists()
        else Path("/app/data/processed")
        if Path("/app/data/processed").exists()
        else Path(__file__).resolve().parents[3] / "data" / "processed"
    )

    def __post_init__(self) -> None:
        self._team_stats = self._load_csv("team_season_stats.csv")
        self._player_stats = self._load_csv("player_season_stats.csv")
        self._match_scorecards = self._load_csv("match_scorecards.csv")
        self._match_results = self._load_csv("cricsheet_deliveries.csv")

    def get_team_stats(self, competition: Optional[str] = None, season: Optional[str] = None) -> List[Dict]:
        df = self._team_stats.copy()
        if df.empty:
            return []
        if competition and "competition" in df.columns:
            df = df[df["competition"].str.lower() == competition.lower()]
        if season and "season" in df.columns:
            df = df[df["season"].astype(str) == str(season)]
        if df.empty:
            return []
        sort_cols = [col for col in ["competition", "season", "team_name"] if col in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols)
        return df.to_dict("records")

    def get_player_stats(
        self,
        competition: Optional[str] = None,
        season: Optional[str] = None,
        team_name: Optional[str] = None,
        min_matches: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        df = self._player_stats.copy()
        if df.empty:
            return []
        if competition and "competition" in df.columns:
            df = df[df["competition"].str.lower() == competition.lower()]
        if season and "season" in df.columns:
            df = df[df["season"].astype(str) == str(season)]
        if team_name and "team_name" in df.columns:
            df = df[df["team_name"].str.lower() == team_name.lower()]
        if min_matches is not None and "matches_played" in df.columns:
            df = df[df["matches_played"] >= min_matches]
        if df.empty:
            return []
        sort_cols = [col for col in ["competition", "season", "team_name", "player_name"] if col in df.columns]
        if sort_cols:
            df = df.sort_values(sort_cols)
        if limit:
            df = df.head(limit)
        return df.to_dict("records")

    def get_match_scorecards(
        self,
        competition: Optional[str] = None,
        season: Optional[str] = None,
        team_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        df = self._match_scorecards.copy()
        if df.empty:
            return []
        if competition and "competition" in df.columns:
            df = df[df["competition"].str.lower() == competition.lower()]
        if season and "season" in df.columns:
            df = df[df["season"].astype(str) == str(season)]
        if team_name and "innings_team" in df.columns:
            df = df[df["innings_team"].str.lower() == team_name.lower()]
        if df.empty:
            return []
        if "match_date" in df.columns:
            df = df.sort_values("match_date")
        if limit:
            df = df.tail(limit)
        return df.to_dict("records")

    def get_batting_leaderboard(
        self,
        competition: Optional[str] = None,
        season: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        df = self._player_stats.copy()
        if df.empty:
            return []
        if competition and "competition" in df.columns:
            df = df[df["competition"].str.lower() == competition.lower()]
        if season and "season" in df.columns:
            df = df[df["season"].astype(str) == str(season)]
        if "matches_played" in df.columns:
            df = df[df["matches_played"] >= 3]
        df = df.sort_values(["runs", "strike_rate"], ascending=False)
        df = df.head(limit)
        return df.to_dict("records")

    def get_bowling_leaderboard(
        self,
        competition: Optional[str] = None,
        season: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        df = self._player_stats.copy()
        if df.empty:
            return []
        if competition and "competition" in df.columns:
            df = df[df["competition"].str.lower() == competition.lower()]
        if season and "season" in df.columns:
            df = df[df["season"].astype(str) == str(season)]
        if "matches_bowled" in df.columns:
            df = df[df["matches_bowled"] >= 3]
        df = df.sort_values(["wickets", "economy_rate"], ascending=[False, True])
        df = df.head(limit)
        return df.to_dict("records")

    def get_head_to_head(
        self,
        team_a: str,
        team_b: str,
        competition: Optional[str] = None,
    ) -> Dict:
        scorecards = self._match_scorecards.copy()
        if scorecards.empty:
            return {}
        df = scorecards.copy()
        teams = {team_a.lower(), team_b.lower()}
        if "innings_team" in df.columns:
            df = df[df["innings_team"].str.lower().isin(teams)]
        else:
            df = df.iloc[0:0]
        if competition and "competition" in df.columns:
            df = df[df["competition"].str.lower() == competition.lower()]
        if df.empty:
            return {}
        matches = df.groupby("match_id").agg({
            "competition": "first",
            "season": "first",
            "winning_team": "first"
        }).reset_index()
        total = len(matches)
        wins_a = (matches["winning_team"].str.lower() == team_a.lower()).sum()
        wins_b = (matches["winning_team"].str.lower() == team_b.lower()).sum()
        ties = total - wins_a - wins_b
        recent = matches.sort_values("match_id", ascending=False).head(5).to_dict("records")
        return {
            "team_a": team_a,
            "team_b": team_b,
            "competition": competition,
            "total_matches": int(total),
            "team_a_wins": int(wins_a),
            "team_b_wins": int(wins_b),
            "ties": int(ties),
            "recent_meetings": recent,
        }

    def get_sa20_official_stats(
        self,
        stat_type: str = "batting",
        season: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Get stats from scraped SA20 official website data."""
        raw_dir = self.processed_dir.parent / "raw" / "sa20_stats"
        season_str = str(season) if season else "alltime"
        
        if stat_type == "batting":
            filename = f"sa20_batting_stats_{season_str}.csv"
        elif stat_type == "bowling":
            filename = f"sa20_bowling_stats_{season_str}.csv"
        else:
            return []
        
        path = raw_dir / filename
        if not path.exists():
            return []
        
        df = pd.read_csv(path)
        if df.empty:
            return []
        
        # Sort and limit
        if stat_type == "batting":
            df = df.sort_values("runs", ascending=False, na_last=True)
        else:
            df = df.sort_values("wickets", ascending=False, na_last=True)
        
        return df.head(limit).to_dict("records")

    def _load_csv(self, filename: str) -> pd.DataFrame:
        path = self.processed_dir / filename
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        return df
