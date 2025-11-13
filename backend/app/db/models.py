"""Core database models for the SA20 platform."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, relationship

from app.db.base import Base


class PlayerRole(str, enum.Enum):
    BATSMAN = "batsman"
    BOWLER = "bowler"
    ALL_ROUNDER = "all_rounder"
    WICKET_KEEPER = "wicket_keeper"


class BattingStyle(str, enum.Enum):
    RIGHT_HAND = "right_hand"
    LEFT_HAND = "left_hand"


class BowlingStyle(str, enum.Enum):
    RIGHT_ARM_FAST = "right_arm_fast"
    LEFT_ARM_FAST = "left_arm_fast"
    RIGHT_ARM_MEDIUM = "right_arm_medium"
    LEFT_ARM_MEDIUM = "left_arm_medium"
    RIGHT_ARM_SPIN = "right_arm_spin"
    LEFT_ARM_SPIN = "left_arm_spin"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String, unique=True, index=True, nullable=False)
    short_name: Mapped[str] = Column(String(16), nullable=False)
    city: Mapped[str] = Column(String, nullable=True)  # Changed from home_venue
    founded_year: Mapped[int] = Column(Integer, nullable=True)
    owner: Mapped[str] = Column(String, nullable=True)
    squad_value: Mapped[float] = Column(Float, nullable=True)

    players: Mapped[List["Player"]] = relationship("Player", back_populates="team")
    home_matches: Mapped[List["Match"]] = relationship(
        "Match",
        foreign_keys="Match.home_team_id",
        back_populates="home_team",
    )
    away_matches: Mapped[List["Match"]] = relationship(
        "Match",
        foreign_keys="Match.away_team_id",
        back_populates="away_team",
    )


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("name", "team_id", name="uq_player_team"),)

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String, index=True, nullable=False)  # Keep name for backward compat
    full_name: Mapped[str | None] = Column(String, nullable=True)
    role: Mapped[PlayerRole] = Column(Enum(PlayerRole), nullable=False)
    batting_style: Mapped[BattingStyle] = Column(Enum(BattingStyle), nullable=False)
    bowling_style: Mapped[BowlingStyle | None] = Column(Enum(BowlingStyle), nullable=True)
    team_id: Mapped[int | None] = Column(Integer, ForeignKey("teams.id"), nullable=True)
    country: Mapped[str] = Column(String, nullable=False)
    age: Mapped[int | None] = Column(Integer, nullable=True)  # Make nullable
    birth_date: Mapped[datetime | None] = Column(DateTime, nullable=True)
    international_caps: Mapped[int] = Column(Integer, default=0)
    auction_price: Mapped[float | None] = Column(Float, nullable=True)
    image_url: Mapped[str | None] = Column(String, nullable=True)
    scraped_season_stats: Mapped[dict | None] = Column(JSONB, nullable=True)  # Store scraped season stats from SA20 website

    team: Mapped[Team | None] = relationship("Team", back_populates="players")
    performances: Mapped[List["PlayerPerformance"]] = relationship(
        "PlayerPerformance", back_populates="player"
    )


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    name: Mapped[str] = Column(String, unique=True, nullable=False)
    city: Mapped[str] = Column(String, nullable=False)
    country: Mapped[str] = Column(String, nullable=False)
    altitude_m: Mapped[float | None] = Column(Float, nullable=True)
    capacity: Mapped[int] = Column(Integer, nullable=True)
    avg_first_innings_score: Mapped[float | None] = Column(Float, nullable=True)
    avg_second_innings_score: Mapped[float | None] = Column(Float, nullable=True)
    pitch_type: Mapped[str | None] = Column(String, nullable=True)

    matches: Mapped[List["Match"]] = relationship("Match", back_populates="venue")


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        Index("idx_matches_date_utc", "date_utc"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    home_team_id: Mapped[int] = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = Column(Integer, ForeignKey("teams.id"), nullable=False)
    venue_id: Mapped[int] = Column(Integer, ForeignKey("venues.id"), nullable=False)
    match_date: Mapped[datetime] = Column(DateTime, nullable=False)  # Keep for backward compat
    date_utc: Mapped[datetime | None] = Column(TIMESTAMP(timezone=True), nullable=True)
    season: Mapped[int] = Column(Integer, nullable=False)
    match_number: Mapped[int | None] = Column(Integer, nullable=True)
    match_no: Mapped[int | None] = Column(Integer, nullable=True)
    winner_id: Mapped[int | None] = Column(Integer, ForeignKey("teams.id"), nullable=True)
    winner_team_id: Mapped[int | None] = Column(Integer, ForeignKey("teams.id"), nullable=True)
    margin: Mapped[str | None] = Column(String, nullable=True)
    margin_text: Mapped[str | None] = Column(String, nullable=True)
    result: Mapped[str | None] = Column(String, nullable=True)
    status: Mapped[str | None] = Column(String, nullable=True)
    toss_winner_id: Mapped[int | None] = Column(Integer, ForeignKey("teams.id"), nullable=True)
    toss_decision: Mapped[str | None] = Column(String, nullable=True)
    match_stage: Mapped[str | None] = Column(String, nullable=True)  # 'group', 'qualifier', 'eliminator', 'final', etc.

    home_team: Mapped[Team] = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team: Mapped[Team] = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    venue: Mapped[Venue] = relationship("Venue", back_populates="matches")
    performances: Mapped[List["PlayerPerformance"]] = relationship(
        "PlayerPerformance", back_populates="match"
    )
    predictions: Mapped[List["Prediction"]] = relationship("Prediction", back_populates="match")


class PlayerPerformance(Base):
    __tablename__ = "player_performances"
    __table_args__ = (
        Index("idx_player_performances_player_id", "player_id"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    player_id: Mapped[int] = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    match_id: Mapped[int] = Column(Integer, ForeignKey("matches.id"), nullable=False)
    team_id: Mapped[int | None] = Column(Integer, ForeignKey("teams.id"), nullable=True)
    runs_scored: Mapped[int] = Column(Integer, default=0)
    runs: Mapped[int | None] = Column(Integer, nullable=True)
    balls_faced: Mapped[int] = Column(Integer, default=0)
    balls: Mapped[int | None] = Column(Integer, nullable=True)
    fours: Mapped[int] = Column(Integer, default=0)
    sixes: Mapped[int] = Column(Integer, default=0)
    wickets_taken: Mapped[int] = Column(Integer, default=0)
    wickets: Mapped[int | None] = Column(Integer, nullable=True)
    overs_bowled: Mapped[float] = Column(Float, default=0.0)
    overs: Mapped[float | None] = Column(Float, nullable=True)
    runs_conceded: Mapped[int] = Column(Integer, default=0)
    catches: Mapped[int] = Column(Integer, default=0)
    stumpings: Mapped[int] = Column(Integer, default=0)
    strike_rate: Mapped[float | None] = Column(Float, nullable=True)
    sr: Mapped[float | None] = Column(Float, nullable=True)
    economy_rate: Mapped[float | None] = Column(Float, nullable=True)
    econ: Mapped[float | None] = Column(Float, nullable=True)

    player: Mapped[Player] = relationship("Player", back_populates="performances")
    match: Mapped[Match] = relationship("Match", back_populates="performances")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    match_id: Mapped[int] = Column(Integer, ForeignKey("matches.id"), nullable=False)
    predicted_winner_id: Mapped[int | None] = Column(Integer, ForeignKey("teams.id"), nullable=True)
    win_probability: Mapped[float] = Column(Float, nullable=False)
    model_version: Mapped[str] = Column(String, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)

    match: Mapped[Match] = relationship("Match", back_populates="predictions")


# Derived/Analytics tables
class AggPlayerSeason(Base):
    __tablename__ = "agg_player_season"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_agg_player_season"),
    )

    player_id: Mapped[int] = Column(Integer, ForeignKey("players.id"), primary_key=True)
    season: Mapped[int] = Column(Integer, primary_key=True)
    runs: Mapped[int] = Column(Integer, default=0)
    sr: Mapped[float] = Column(Float, default=0.0)
    avg: Mapped[float] = Column(Float, default=0.0)
    wickets: Mapped[int] = Column(Integer, default=0)
    econ: Mapped[float] = Column(Float, default=0.0)
    matches: Mapped[int] = Column(Integer, default=0)


class AggTeamSeason(Base):
    __tablename__ = "agg_team_season"
    __table_args__ = (
        UniqueConstraint("team_id", "season", name="uq_agg_team_season"),
    )

    team_id: Mapped[int] = Column(Integer, ForeignKey("teams.id"), primary_key=True)
    season: Mapped[int] = Column(Integer, primary_key=True)
    wins: Mapped[int] = Column(Integer, default=0)
    losses: Mapped[int] = Column(Integer, default=0)
    nrr: Mapped[float] = Column(Float, default=0.0)
    points: Mapped[int] = Column(Integer, default=0)


# Simulation tables
class SimRun(Base):
    __tablename__ = "sim_runs"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
    seasons: Mapped[int] = Column(Integer, nullable=False)
    engine: Mapped[str] = Column(String, nullable=False)  # 'fast' or 'ball'
    seed: Mapped[int | None] = Column(Integer, nullable=True)
    config: Mapped[dict] = Column(JSONB, nullable=True)

    team_summaries: Mapped[List["SimTeamSummary"]] = relationship("SimTeamSummary", back_populates="run")
    player_summaries: Mapped[List["SimPlayerSummary"]] = relationship("SimPlayerSummary", back_populates="run")


class SimTeamSummary(Base):
    __tablename__ = "sim_team_summary"
    __table_args__ = (
        Index("idx_sim_team_summary_run_id", "run_id"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = Column(Integer, ForeignKey("sim_runs.id"), nullable=False, index=True)
    team_id: Mapped[int] = Column(Integer, ForeignKey("teams.id"), nullable=False)
    title_p: Mapped[float] = Column(Float, nullable=False)  # Title probability
    finals_p: Mapped[float] = Column(Float, nullable=False)  # Finals probability
    playoffs_p: Mapped[float] = Column(Float, nullable=False)  # Playoffs probability
    exp_wins: Mapped[float] = Column(Float, nullable=False)  # Expected wins
    nrr_p10: Mapped[float] = Column(Float, nullable=True)  # NRR 10th percentile
    nrr_p50: Mapped[float] = Column(Float, nullable=True)  # NRR 50th percentile (median)
    nrr_p90: Mapped[float] = Column(Float, nullable=True)  # NRR 90th percentile

    run: Mapped[SimRun] = relationship("SimRun", back_populates="team_summaries")


class SimPlayerSummary(Base):
    __tablename__ = "sim_player_summary"
    __table_args__ = (
        Index("idx_sim_player_summary_run_id", "run_id"),
        CheckConstraint("award_type IN ('orange', 'purple')", name="chk_award_type"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = Column(Integer, ForeignKey("sim_runs.id"), nullable=False, index=True)
    player_id: Mapped[int] = Column(Integer, ForeignKey("players.id"), nullable=False)
    award_type: Mapped[str] = Column(String, nullable=False)  # 'orange' or 'purple'
    p_win: Mapped[float] = Column(Float, nullable=False)  # Probability of winning award
    exp_value: Mapped[float] = Column(Float, nullable=False)  # Expected value
    p10: Mapped[float] = Column(Float, nullable=True)  # 10th percentile
    p50: Mapped[float] = Column(Float, nullable=True)  # 50th percentile (median)
    p90: Mapped[float] = Column(Float, nullable=True)  # 90th percentile

    run: Mapped[SimRun] = relationship("SimRun", back_populates="player_summaries")


# Strategy tables
class StrategyContext(Base):
    __tablename__ = "strategy_context"
    __table_args__ = (
        Index("idx_strategy_context_match", "match_id", "innings", "over_no"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    match_id: Mapped[int] = Column(Integer, ForeignKey("matches.id"), nullable=False)
    innings: Mapped[int] = Column(Integer, nullable=False)
    over_no: Mapped[int] = Column(Integer, nullable=False)
    wickets_down: Mapped[int] = Column(Integer, nullable=False)
    striker_id: Mapped[int | None] = Column(Integer, ForeignKey("players.id"), nullable=True)
    non_striker_id: Mapped[int | None] = Column(Integer, ForeignKey("players.id"), nullable=True)
    current_bowler_id: Mapped[int | None] = Column(Integer, ForeignKey("players.id"), nullable=True)
    phase: Mapped[str | None] = Column(String, nullable=True)  # 'powerplay', 'middle', 'death'
    state_json: Mapped[dict] = Column(JSONB, nullable=True)

    recommendations: Mapped[List["StrategyRecommendation"]] = relationship("StrategyRecommendation", back_populates="context")


class StrategyRecommendation(Base):
    __tablename__ = "strategy_recommendation"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    context_id: Mapped[int] = Column(Integer, ForeignKey("strategy_context.id"), nullable=False)
    type: Mapped[str] = Column(String, nullable=False)  # 'batting_order', 'bowling_change', 'drs', 'powerplay'
    payload: Mapped[dict] = Column(JSONB, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    context: Mapped[StrategyContext] = relationship("StrategyContext", back_populates="recommendations")


# Fantasy tables
class FantasyProjection(Base):
    __tablename__ = "fantasy_projection"
    __table_args__ = (
        Index("idx_fantasy_projection_matchday", "matchday"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    matchday: Mapped[str] = Column(String, nullable=False, index=True)
    player_id: Mapped[int] = Column(Integer, ForeignKey("players.id"), nullable=False)
    expected_points: Mapped[float] = Column(Float, nullable=False)
    p10: Mapped[float] = Column(Float, nullable=True)
    p50: Mapped[float] = Column(Float, nullable=True)
    p90: Mapped[float] = Column(Float, nullable=True)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)


class FantasySolution(Base):
    __tablename__ = "fantasy_solution"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    matchday: Mapped[str] = Column(String, nullable=False)
    config: Mapped[dict] = Column(JSONB, nullable=True)  # Budget, constraints, etc.
    total_points: Mapped[float] = Column(Float, nullable=False)
    team_json: Mapped[dict] = Column(JSONB, nullable=True)  # Selected team
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)
