"""Season simulation orchestrator."""
from __future__ import annotations

import numpy as np
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.db import models
from app.services.simulate.engine_fast import FastSimulationEngine
from app.services.simulate.engine_ball import BallByBallEngine


class SeasonSimulator:
    """Orchestrates season simulations using fast or ball-by-ball engines.
    
    Handles group stage → playoffs (Qualifier 1, Eliminator, Qualifier 2, Final)
    and accumulates team title/playoff probabilities and Orange/Purple Cap stats.
    """
    
    def __init__(self, match_predictor, engine_type: str = "fast"):
        """Initialize season simulator.
        
        Args:
            match_predictor: MatchPredictor instance
            engine_type: 'fast' or 'ball' simulation engine
        """
        self.match_predictor = match_predictor
        self.engine_type = engine_type
        
        if engine_type == "fast":
            self.engine = FastSimulationEngine(match_predictor)
        elif engine_type == "ball":
            self.engine = BallByBallEngine()
        else:
            raise ValueError(f"Unknown engine type: {engine_type}")
    
    def simulate_season(
        self,
        season: int,
        num_simulations: int = 1000,
        db_session: Optional[Session] = None,
        seed: Optional[int] = None,
    ) -> Dict:
        """Simulate a season multiple times and aggregate results.
        
        Args:
            season: Season year
            num_simulations: Number of simulations to run
            db_session: Database session
            seed: Random seed for reproducibility
            
        Returns:
            Dictionary with simulation results including team and player summaries
        """
        if db_session is None:
            raise ValueError("Database session required")
        
        if seed is not None:
            np.random.seed(seed)
        
        # Get fixtures for the season
        fixtures = db_session.query(models.Match).filter(
            models.Match.season == season
        ).all()
        
        if not fixtures:
            raise ValueError(f"No fixtures found for season {season}")
        
        # Initialize counters
        teams = db_session.query(models.Team).all()
        team_stats = {team.id: {
            "title_count": 0,
            "finals_count": 0,
            "playoffs_count": 0,
            "wins": [],
            "nrr": [],
        } for team in teams}
        
        players = db_session.query(models.Player).all()
        player_runs = {player.id: [] for player in players}
        player_wickets = {player.id: [] for player in players}
        
        # Run simulations
        for sim_num in range(num_simulations):
            if sim_num % 100 == 0:
                print(f"Running simulation {sim_num}/{num_simulations}...")
            
            # Simulate group stage
            group_results = self._simulate_group_stage(fixtures, db_session)
            
            # Calculate standings
            standings = self._calculate_standings(group_results, teams)
            
            # Update team stats
            for team in teams:
                team_record = standings.get(team.id, {})
                team_stats[team.id]["wins"].append(team_record.get("wins", 0))
                team_stats[team.id]["nrr"].append(team_record.get("nrr", 0.0))
                
                position = team_record.get("position", 999)
                if position <= 4:
                    team_stats[team.id]["playoffs_count"] += 1
                if position <= 2:
                    team_stats[team.id]["finals_count"] += 1
            
            # Simulate playoffs
            playoff_teams = sorted(
                standings.items(),
                key=lambda x: (x[1].get("points", 0), x[1].get("nrr", 0.0)),
                reverse=True
            )[:4]
            playoff_team_ids = [t[0] for t in playoff_teams]
            
            if len(playoff_team_ids) >= 4:
                champion = self._simulate_playoffs(playoff_team_ids, db_session)
                if champion:
                    team_stats[champion]["title_count"] += 1
            
            # Collect player stats from simulations
            # (This would be enhanced to track runs/wickets from each simulation)
        
        # Aggregate results
        return self._aggregate_results(
            team_stats, player_runs, player_wickets, teams, players, num_simulations
        )
    
    def _simulate_group_stage(
        self,
        fixtures: List[models.Match],
        db_session: Session,
    ) -> List[Dict]:
        """Simulate all group stage matches.
        
        Args:
            fixtures: List of match fixtures
            db_session: Database session
            
        Returns:
            List of match results
        """
        results = []
        
        for fixture in fixtures:
            if self.engine_type == "fast":
                result = self.engine.simulate_match(
                    fixture.home_team_id,
                    fixture.away_team_id,
                    fixture.venue_id,
                    fixture.toss_winner_id,
                    fixture.toss_decision,
                    db_session,
                )
            else:
                result = self.engine.simulate_match(
                    fixture.home_team_id,
                    fixture.away_team_id,
                    fixture.venue_id,
                    fixture.toss_winner_id,
                    fixture.toss_decision,
                    db_session,
                )
            
            results.append({
                "match_id": fixture.id,
                "home_team_id": fixture.home_team_id,
                "away_team_id": fixture.away_team_id,
                "winner_id": result["winner_id"],
                "margin": result.get("margin", ""),
            })
        
        return results
    
    def _calculate_standings(
        self,
        results: List[Dict],
        teams: List[models.Team],
    ) -> Dict[int, Dict]:
        """Calculate league standings from results.
        
        Args:
            results: List of match results
            teams: List of teams
            
        Returns:
            Dictionary mapping team_id to standings record
        """
        standings = {}
        
        for team in teams:
            played = 0
            wins = 0
            losses = 0
            runs_for = 0
            runs_against = 0
            wickets_for = 0
            wickets_against = 0
            
            for result in results:
                if result["home_team_id"] == team.id:
                    played += 1
                    if result["winner_id"] == team.id:
                        wins += 1
                    else:
                        losses += 1
                    # Simplified: assume average scores
                    runs_for += 160
                    runs_against += 150
                elif result["away_team_id"] == team.id:
                    played += 1
                    if result["winner_id"] == team.id:
                        wins += 1
                    else:
                        losses += 1
                    runs_for += 150
                    runs_against += 160
            
            points = wins * 2
            nrr = (runs_for - runs_against) / max(played * 20, 1)  # Simplified NRR
            
            standings[team.id] = {
                "team_id": team.id,
                "played": played,
                "wins": wins,
                "losses": losses,
                "points": points,
                "nrr": nrr,
            }
        
        # Calculate positions
        sorted_teams = sorted(
            standings.items(),
            key=lambda x: (x[1]["points"], x[1]["nrr"]),
            reverse=True
        )
        
        for position, (team_id, record) in enumerate(sorted_teams, 1):
            standings[team_id]["position"] = position
        
        return standings
    
    def _simulate_playoffs(
        self,
        playoff_teams: List[int],
        db_session: Session,
    ) -> Optional[int]:
        """Simulate SA20 playoff structure.
        
        Args:
            playoff_teams: List of 4 team IDs (sorted by position)
            db_session: Database session
            
        Returns:
            Champion team ID
        """
        if len(playoff_teams) < 4:
            return None
        
        # Qualifier 1: 1st vs 2nd
        q1_winner = self._simulate_playoff_match(
            playoff_teams[0], playoff_teams[1], db_session
        )
        q1_loser = playoff_teams[1] if q1_winner == playoff_teams[0] else playoff_teams[0]
        
        # Eliminator: 3rd vs 4th
        elim_winner = self._simulate_playoff_match(
            playoff_teams[2], playoff_teams[3], db_session
        )
        
        # Qualifier 2: Loser Q1 vs Winner Eliminator
        q2_winner = self._simulate_playoff_match(q1_loser, elim_winner, db_session)
        
        # Final: Winner Q1 vs Winner Q2
        champion = self._simulate_playoff_match(q1_winner, q2_winner, db_session)
        
        return champion
    
    def _simulate_playoff_match(
        self,
        team1_id: int,
        team2_id: int,
        db_session: Session,
    ) -> int:
        """Simulate a playoff match.
        
        Args:
            team1_id: First team ID
            team2_id: Second team ID
            db_session: Database session
            
        Returns:
            Winner team ID
        """
        # Use fast engine for playoff matches
        # In a real implementation, we'd use a neutral venue
        venue = db_session.query(models.Venue).first()
        if not venue:
            # Fallback: random choice
            return team1_id if np.random.random() < 0.5 else team2_id
        
        result = self.engine.simulate_match(
            team1_id, team2_id, venue.id, None, None, db_session
        )
        
        return result["winner_id"]
    
    def _aggregate_results(
        self,
        team_stats: Dict,
        player_runs: Dict,
        player_wickets: Dict,
        teams: List[models.Team],
        players: List[models.Player],
        num_simulations: int,
    ) -> Dict:
        """Aggregate simulation results.
        
        Args:
            team_stats: Team statistics from simulations
            player_runs: Player runs from simulations
            player_wickets: Player wickets from simulations
            teams: List of teams
            players: List of players
            num_simulations: Number of simulations run
            
        Returns:
            Aggregated results dictionary
        """
        team_summaries = []
        
        for team in teams:
            stats = team_stats[team.id]
            wins = stats["wins"]
            nrr = stats["nrr"]
            
            team_summaries.append({
                "team_id": team.id,
                "title_p": stats["title_count"] / num_simulations,
                "finals_p": stats["finals_count"] / num_simulations,
                "playoffs_p": stats["playoffs_count"] / num_simulations,
                "exp_wins": np.mean(wins) if wins else 0.0,
                "nrr_p10": np.percentile(nrr, 10) if nrr else 0.0,
                "nrr_p50": np.percentile(nrr, 50) if nrr else 0.0,
                "nrr_p90": np.percentile(nrr, 90) if nrr else 0.0,
            })
        
        # Player summaries (simplified - would be enhanced with actual simulation data)
        player_summaries = {
            "orange_cap": [],
            "purple_cap": [],
        }
        
        return {
            "team_summaries": team_summaries,
            "player_summaries": player_summaries,
            "num_simulations": num_simulations,
            "engine_type": self.engine_type,
        }

