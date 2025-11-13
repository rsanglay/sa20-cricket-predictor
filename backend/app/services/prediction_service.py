"""Business logic for predictions."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import random

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.ml.models.match_predictor import MatchPredictor
from app.ml.models.season_simulator import SeasonSimulator


def _normalise_team_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


@dataclass
class PredictionService:
    db: Session
    match_predictor: MatchPredictor = field(init=False)

    def __post_init__(self) -> None:
        import logging
        logger = logging.getLogger(__name__)
        
        self.match_predictor = MatchPredictor()
        try:
            self._load_models()
            logger.info("Match prediction model loaded successfully")
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Could not load match prediction model: {e}")
            # Models not loaded - will fail gracefully when trying to predict
        except Exception as e:
            logger.error(f"Unexpected error loading models: {e}", exc_info=True)
        
        if self.match_predictor.model:
            self.season_simulator = SeasonSimulator(self.match_predictor)
        else:
            self.season_simulator = None
            logger.warning("Season simulator not initialized - model not loaded")
        
        self.team_feature_lookup = self._load_team_features()

    def predict_match(
        self,
        home_team_id: int,
        away_team_id: int,
        venue_id: int,
        overwrite_venue_avg_score: Optional[float] = None,
        home_lineup: Optional[List[int]] = None,
        away_lineup: Optional[List[int]] = None,
    ) -> Dict:
        if not self.match_predictor.model or not self.match_predictor.feature_names:
            raise ValueError("Match prediction model not loaded. Please train the model first.")
        
        home_team = self.db.get(models.Team, home_team_id)
        away_team = self.db.get(models.Team, away_team_id)
        venue = self.db.get(models.Venue, venue_id)
        if not home_team or not away_team or not venue:
            raise ValueError("Invalid team or venue id")

        competition = "sa20"
        home_row = self._select_team_row(home_team, competition)
        away_row = self._select_team_row(away_team, competition)
        venue_avg = overwrite_venue_avg_score or venue.avg_first_innings_score or 160
        
        feature_vector = self._build_feature_vector(
            home_row, away_row, home_lineup, away_lineup, venue_avg,
            home_team_id=home_team_id, away_team_id=away_team_id
        )
        # Ensure all required features are present
        required_features = self.match_predictor.feature_names
        for feature in required_features:
            if feature not in feature_vector:
                feature_vector[feature] = 0.0
        prediction = self.match_predictor.predict_from_vector(feature_vector)
        # Convert top_factors (list of tuples) to key_factors (list of lists) for schema
        top_factors = prediction.get("top_factors", [])
        key_factors = [[str(factor[0]), float(factor[1])] for factor in top_factors]
        
        # Get player predictions for both teams
        from app.services.player_service import PlayerService
        
        player_service = PlayerService(self.db)
        
        home_players = player_service.get_players(team_id=home_team_id, skip_image_filter=True)
        if not home_players:
            home_players = player_service.get_players(team_id=home_team_id)
        away_players = player_service.get_players(team_id=away_team_id, skip_image_filter=True)
        if not away_players:
            away_players = player_service.get_players(team_id=away_team_id)
        
        def build_player_predictions(players: List[Dict], team_name: str, side: str) -> List[Dict]:
            predictions: List[Dict] = []
            for player in players:
                projection_data = None
                if player_service.projection_service:
                    try:
                        projection_data = player_service.predict_performance(player["id"])
                    except Exception:
                        projection_data = None
                if projection_data:
                    predicted_runs = float(projection_data.get("predicted_runs", 0.0))
                    predicted_wickets = float(projection_data.get("predicted_wickets", 0.0))
                else:
                    predicted_runs, predicted_wickets = self._fallback_player_projection(player_service, player)
                
                # Get player stats for intelligent selection
                player_detail = None
                try:
                    player_detail = player_service.get_player_detail(player["id"])
                except Exception:
                    pass
                
                # Extract stats from player detail
                batting_avg = 0.0
                strike_rate = 0.0
                bowling_avg = 0.0
                economy = 0.0
                matches_played = 0
                
                if player_detail:
                    # Get batting stats
                    if player_detail.get("stats"):
                        stats = player_detail["stats"]
                        batting_avg = float(stats.get("batting_average", 0.0) or 0.0)
                        strike_rate = float(stats.get("strike_rate", 0.0) or 0.0)
                        bowling_avg = float(stats.get("bowling_average", 0.0) or 0.0)
                        economy = float(stats.get("economy_rate", 0.0) or 0.0)
                        matches_played = int(stats.get("matches_played", 0) or 0)
                
                predictions.append({
                    "player_id": player["id"],
                    "player_name": player["name"],
                    "team_id": player.get("team_id"),
                    "team_name": team_name,
                    "role": player.get("role"),
                    "team_side": side,
                    "predicted_runs": predicted_runs,
                    "predicted_wickets": predicted_wickets,
                    "batting_avg": batting_avg,
                    "strike_rate": strike_rate,
                    "bowling_avg": bowling_avg,
                    "economy": economy,
                    "matches_played": matches_played,
                })
            return predictions
        
        home_player_predictions = build_player_predictions(home_players, home_team.name, "home")
        away_player_predictions = build_player_predictions(away_players, away_team.name, "away")
        
        def select_balanced_xi(predictions: List[Dict]) -> List[Dict]:
            """
            Select a balanced T20 XI like a cricket coach would:
            - Maximum 5-6 specialist batsmen (including wicket-keeper)
            - 1-2 all-rounders (provide balance)
            - Rest specialist bowlers (3-4 bowlers)
            - Proper batting order: batsmen at top, all-rounders in middle, bowlers at bottom
            """
            if not predictions:
                return []
            
            # Categorize players by role (normalize role strings)
            def normalize_role(role_str: str) -> str:
                if not role_str:
                    return ""
                role_lower = str(role_str).lower().replace("_", "").replace("-", "")
                if role_lower in ["batsman", "batter"]:
                    return "batsman"
                elif role_lower in ["wicketkeeper", "wk", "wicket_keeper"]:
                    return "wicket_keeper"
                elif role_lower in ["allrounder", "all_rounder"]:
                    return "all_rounder"
                elif role_lower in ["bowler", "fastbowler", "pacebowler", "seamer", "spinner", "legspinner", "offspinner"]:
                    return "bowler"
                return role_lower
            
            batsmen = [p for p in predictions if normalize_role(p.get("role", "")) == "batsman"]
            wicket_keepers = [p for p in predictions if normalize_role(p.get("role", "")) == "wicket_keeper"]
            all_rounders = [p for p in predictions if normalize_role(p.get("role", "")) == "all_rounder"]
            bowlers = [p for p in predictions if normalize_role(p.get("role", "")) == "bowler"]
            
            selected = []
            
            # 1. Select 1 wicket-keeper (prefer dedicated WK, otherwise use best batsman)
            wk_selected = None
            if wicket_keepers:
                wk_selected = max(wicket_keepers, key=lambda p: (
                    p.get("batting_avg", 0) * 1.5 +
                    p.get("strike_rate", 0) * 0.01 +
                    p.get("predicted_runs", 0) * 0.8 +
                    p.get("matches_played", 0) * 0.1
                ))
            elif batsmen:
                # If no dedicated WK, use best batsman as WK
                wk_selected = max(batsmen, key=lambda p: (
                    p.get("batting_avg", 0) * 1.5 +
                    p.get("strike_rate", 0) * 0.01 +
                    p.get("predicted_runs", 0) * 0.8 +
                    p.get("matches_played", 0) * 0.1
                ))
            
            if wk_selected:
                selected.append(wk_selected)
                # Remove from batsmen if it was there
                if wk_selected in batsmen:
                    batsmen.remove(wk_selected)
            
            # 2. Select 1-2 all-rounders (prefer 2 if available)
            all_rounders_sorted = sorted(all_rounders, key=lambda p: (
                p.get("predicted_runs", 0) * 0.6 +
                p.get("predicted_wickets", 0) * 20 +
                p.get("batting_avg", 0) * 0.5 +
                (p.get("bowling_avg", 0) * -0.3 if p.get("bowling_avg", 0) > 0 else 0)
            ), reverse=True)
            num_all_rounders = min(2, len(all_rounders_sorted))
            selected.extend(all_rounders_sorted[:num_all_rounders])
            
            # 3. Select 4-5 more batsmen (total batsmen including WK should be 5-6)
            # We already have 1 WK, so select 4-5 more batsmen
            batsmen_sorted = sorted(batsmen, key=lambda p: (
                p.get("batting_avg", 0) * 1.2 +
                p.get("strike_rate", 0) * 0.015 +
                p.get("predicted_runs", 0) * 0.7 +
                p.get("matches_played", 0) * 0.05
            ), reverse=True)
            num_batsmen_needed = 5 if len(batsmen_sorted) >= 5 else len(batsmen_sorted)  # Prefer 5, but take what's available
            selected.extend(batsmen_sorted[:num_batsmen_needed])
            
            # 4. Fill remaining slots with bowlers (should be 3-4 bowlers)
            bowlers_sorted = sorted(bowlers, key=lambda p: (
                p.get("predicted_wickets", 0) * 25 +
                ((10.0 - p.get("economy", 10.0)) * 2 if p.get("economy", 10.0) > 0 else 0) +
                (p.get("bowling_avg", 0) * -0.5 if p.get("bowling_avg", 0) > 0 else 0) +
                p.get("matches_played", 0) * 0.1
            ), reverse=True)
            remaining_slots = 11 - len(selected)
            selected.extend(bowlers_sorted[:min(remaining_slots, len(bowlers_sorted))])
            
            # 5. If we still don't have 11, fill with best remaining players (any role)
            if len(selected) < 11:
                all_remaining = [p for p in predictions if p not in selected]
                all_remaining_sorted = sorted(all_remaining, key=lambda p: (
                    p.get("predicted_runs", 0) * 0.5 +
                    p.get("predicted_wickets", 0) * 15 +
                    p.get("batting_avg", 0) * 0.8 +
                    p.get("matches_played", 0) * 0.1
                ), reverse=True)
                selected.extend(all_remaining_sorted[:11 - len(selected)])
            
            # 6. Order players in proper batting order:
            # - Batsmen (including WK) at top (positions 1-6)
            # - All-rounders in middle (positions 6-8)
            # - Bowlers at bottom (positions 8-11)
            
            def batting_order_score(player: Dict) -> float:
                """Score for batting order - higher = bat higher"""
                role = normalize_role(player.get("role", ""))
                
                # Specialist batsmen and wicket-keepers bat at top (positions 1-6)
                if role in ["batsman", "wicket_keeper"]:
                    return (
                        player.get("batting_avg", 0) * 1.8 +
                        player.get("strike_rate", 0) * 0.025 +
                        player.get("predicted_runs", 0) * 1.0 +
                        100  # Highest base score for top order
                    )
                # All-rounders bat in middle (positions 6-8)
                elif role == "all_rounder":
                    return (
                        player.get("batting_avg", 0) * 1.0 +
                        player.get("strike_rate", 0) * 0.015 +
                        player.get("predicted_runs", 0) * 0.6 +
                        30  # Base score for middle order
                    )
                # Bowlers bat last (positions 8-11)
                else:  # bowler
                    return (
                        player.get("batting_avg", 0) * 0.5 +
                        player.get("predicted_runs", 0) * 0.3 +
                        0  # Lowest base score
                    )
            
            # Sort by batting order score (highest first = openers)
            selected = sorted(selected, key=batting_order_score, reverse=True)
            
            return selected[:11]
        
        home_starting_xi = select_balanced_xi(home_player_predictions)
        away_starting_xi = select_balanced_xi(away_player_predictions)
        
        home_avg_runs = home_row.get("avg_runs_for", 0.0) if home_row else 0.0
        away_avg_runs = away_row.get("avg_runs_for", 0.0) if away_row else 0.0
        
        def compute_team_score_and_wickets(starting_xi: List[Dict], venue_average: float, team_avg_runs: float) -> tuple[int, int]:
            """Compute team score and wickets lost. Returns (runs, wickets)."""
            base_venue = venue_average or 160
            base_team = team_avg_runs or base_venue
            if not starting_xi:
                noise = random.gauss(0, 7)
                blended = 0.6 * base_venue + 0.4 * base_team
                runs = int(np.clip(blended + noise, 125, 215))
                wickets = random.choices([10, 9, 8, 7, 6], weights=[0.1, 0.15, 0.2, 0.25, 0.3])[0]
                return (runs, wickets)
            
            top_order = starting_xi[:6]
            lower_order = starting_xi[6:]
            top_runs = sum(p["predicted_runs"] for p in top_order)
            lower_runs = sum(p["predicted_runs"] * 0.35 for p in lower_order)
            expected_runs = top_runs + lower_runs
            blended = 0.55 * expected_runs + 0.3 * base_venue + 0.15 * base_team
            noise = random.gauss(0, max(5.0, blended * 0.05))
            runs = int(np.clip(blended + noise, 130, 230))
            
            # Calculate wickets: higher scores = more wickets lost (but not always all out)
            # Probability of being all out increases with score (more aggressive batting)
            if runs > 180:
                # High scoring, more likely to be all out
                wickets = random.choices([10, 9, 8, 7], weights=[0.3, 0.25, 0.25, 0.2])[0]
            elif runs > 150:
                # Medium-high scoring
                wickets = random.choices([10, 9, 8, 7, 6], weights=[0.15, 0.2, 0.25, 0.25, 0.15])[0]
            else:
                # Lower scoring, less likely to be all out
                wickets = random.choices([10, 9, 8, 7, 6, 5, 4], weights=[0.05, 0.1, 0.15, 0.2, 0.25, 0.15, 0.1])[0]
            
            return (runs, wickets)
        
        # First, generate base scores for both teams
        home_score, home_wickets = compute_team_score_and_wickets(home_starting_xi, venue_avg, home_avg_runs)
        away_score, away_wickets = compute_team_score_and_wickets(away_starting_xi, venue_avg, away_avg_runs)
        
        # Use the full match prediction logic (toss, bat first, scores, result)
        match_result = self._predict_match_result(
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            venue_id=venue_id,
            home_score=home_score,
            home_wickets=home_wickets,
            away_score=away_score,
            away_wickets=away_wickets,
            home_team_name=home_team.name,
            away_team_name=away_team.name,
            prediction=prediction
        )
        
        # Extract results
        toss_winner = match_result["toss_winner"]
        bat_first = match_result["bat_first"]
        home_score = match_result["home_score"]
        home_wickets = match_result["home_wickets"]
        away_score = match_result["away_score"]
        away_wickets = match_result["away_wickets"]
        first_innings_score = match_result["first_innings_score"]
        first_innings_wickets = match_result["first_innings_wickets"]
        second_innings_score = match_result["second_innings_score"]
        second_innings_wickets = match_result["second_innings_wickets"]
        first_team_name = match_result["first_team_name"]
        second_team_name = match_result["second_team_name"]
        winner = match_result["winner"]
        result_type = match_result["result_type"]
        result_text = match_result["result_text"]
        margin = match_result["margin"]
        
        # Round all predictions to whole numbers
        for player in home_player_predictions:
            player["predicted_runs"] = int(round(player["predicted_runs"]))
            player["predicted_wickets"] = int(round(player["predicted_wickets"]))
        for player in away_player_predictions:
            player["predicted_runs"] = int(round(player["predicted_runs"]))
            player["predicted_wickets"] = int(round(player["predicted_wickets"]))
        
        home_top_run_scorers = sorted(home_player_predictions, key=lambda x: x["predicted_runs"], reverse=True)[:3]
        away_top_run_scorers = sorted(away_player_predictions, key=lambda x: x["predicted_runs"], reverse=True)[:3]
        
        home_top_wicket_takers = sorted(home_player_predictions, key=lambda x: x["predicted_wickets"], reverse=True)[:3]
        away_top_wicket_takers = sorted(away_player_predictions, key=lambda x: x["predicted_wickets"], reverse=True)[:3]
        
        home_top_run_scorer = home_top_run_scorers[0] if home_top_run_scorers else None
        away_top_run_scorer = away_top_run_scorers[0] if away_top_run_scorers else None
        home_top_wicket_taker = home_top_wicket_takers[0] if home_top_wicket_takers else None
        away_top_wicket_taker = away_top_wicket_takers[0] if away_top_wicket_takers else None
        
        man_of_the_match = None
        all_players = home_player_predictions + away_player_predictions
        if all_players:
            for player in all_players:
                player["performance_score"] = player["predicted_runs"] + player["predicted_wickets"] * 20
            best_player = max(all_players, key=lambda x: x["performance_score"])
            man_of_the_match = {
                "player_id": best_player["player_id"],
                "player_name": best_player["player_name"],
                "team": best_player.get("team_side", ""),
                "team_name": best_player.get("team_name", ""),
                "predicted_runs": int(round(best_player["predicted_runs"])),
                "predicted_wickets": int(round(best_player["predicted_wickets"])),
            }
        
        result = {
            "home_team": home_team.name,
            "away_team": away_team.name,
            "venue": venue.name,
            "home_win_probability": prediction.get("home_win_probability", 0.5),
            "away_win_probability": prediction.get("away_win_probability", 0.5),
            "predicted_winner": winner,
            "confidence": prediction.get("confidence", 0.5),
            "key_factors": key_factors,
            "toss_winner": toss_winner,
            "bat_first": bat_first,
            "predicted_scores": {
                "home_score": home_score,
                "home_wickets": home_wickets,
                "away_score": away_score,
                "away_wickets": away_wickets,
                "first_innings_score": first_innings_score,
                "first_innings_wickets": first_innings_wickets,
                "second_innings_score": second_innings_score,
                "second_innings_wickets": second_innings_wickets,
                "first_team": first_team_name,
                "second_team": second_team_name,
            },
            "match_result": {
                "winner": winner,
                "result_type": result_type,
                "result_text": result_text,
                "margin": margin,
            },
            "top_run_scorers": {
                "home": {
                    "player_id": home_top_run_scorer["player_id"],
                    "player_name": home_top_run_scorer["player_name"],
                    "predicted_runs": int(round(home_top_run_scorer["predicted_runs"])),
                } if home_top_run_scorer else None,
                "away": {
                    "player_id": away_top_run_scorer["player_id"],
                    "player_name": away_top_run_scorer["player_name"],
                    "predicted_runs": int(round(away_top_run_scorer["predicted_runs"])),
                } if away_top_run_scorer else None,
            },
            "top_3_run_scorers": {
                "home": [
                    {
                        "player_id": p["player_id"],
                        "player_name": p["player_name"],
                        "predicted_runs": int(round(p["predicted_runs"])),
                    }
                    for p in home_top_run_scorers
                ],
                "away": [
                    {
                        "player_id": p["player_id"],
                        "player_name": p["player_name"],
                        "predicted_runs": int(round(p["predicted_runs"])),
                    }
                    for p in away_top_run_scorers
                ],
            },
            "top_wicket_takers": {
                "home": {
                    "player_id": home_top_wicket_taker["player_id"],
                    "player_name": home_top_wicket_taker["player_name"],
                    "predicted_wickets": int(round(home_top_wicket_taker["predicted_wickets"])),
                } if home_top_wicket_taker else None,
                "away": {
                    "player_id": away_top_wicket_taker["player_id"],
                    "player_name": away_top_wicket_taker["player_name"],
                    "predicted_wickets": int(round(away_top_wicket_taker["predicted_wickets"])),
                } if away_top_wicket_taker else None,
            },
            "top_3_wicket_takers": {
                "home": [
                    {
                        "player_id": p["player_id"],
                        "player_name": p["player_name"],
                        "predicted_wickets": int(round(p["predicted_wickets"])),
                    }
                    for p in home_top_wicket_takers
                ],
                "away": [
                    {
                        "player_id": p["player_id"],
                        "player_name": p["player_name"],
                        "predicted_wickets": int(round(p["predicted_wickets"])),
                    }
                    for p in away_top_wicket_takers
                ],
            },
            "man_of_the_match": {
                "player_id": man_of_the_match["player_id"],
                "player_name": man_of_the_match["player_name"],
                "team": man_of_the_match["team"],
                "team_name": man_of_the_match["team_name"],
                "predicted_runs": int(round(man_of_the_match["predicted_runs"])),
                "predicted_wickets": int(round(man_of_the_match["predicted_wickets"])),
            } if man_of_the_match else None,
            "predicted_starting_xi": {
                "home": [
                    {
                        "player_id": player["player_id"],
                        "player_name": player["player_name"],
                        "role": player.get("role", "batsman"),
                        "team_name": player.get("team_name"),
                        "predicted_runs": int(round(player["predicted_runs"])),
                        "predicted_wickets": int(round(player["predicted_wickets"])),
                    }
                    for player in home_starting_xi
                ],
                "away": [
                    {
                        "player_id": player["player_id"],
                        "player_name": player["player_name"],
                        "role": player.get("role", "batsman"),
                        "team_name": player.get("team_name"),
                        "predicted_runs": int(round(player["predicted_runs"])),
                        "predicted_wickets": int(round(player["predicted_wickets"])),
                    }
                    for player in away_starting_xi
                ],
            },
        }
        
        return result

    def simulate_season(
        self, 
        num_simulations: int = 1000,
        custom_xis: Optional[Dict[int, List[int]]] = None
    ) -> Dict:
        """Simulate season with optional custom XIs for each team.
        
        Args:
            num_simulations: Number of Monte Carlo simulations to run
            custom_xis: Dict mapping team_id to list of player_ids (XI)
        """
        if not self.match_predictor.model:
            raise ValueError("Match prediction model not loaded. Please train the model first.")
        
        # Get all matches for the season
        matches = self.db.query(models.Match).all()
        if not matches:
            return {
                "predicted_standings": [],
                "playoff_probabilities": {},
                "championship_probabilities": {},
                "num_simulations": num_simulations,
                "orange_cap": None,
                "purple_cap": None,
                "champion": None,
            }
        
        fixtures = pd.DataFrame(
            [
                {
                    "match_id": match.id,
                    "home_team_id": match.home_team_id,
                    "away_team_id": match.away_team_id,
                    "venue_id": match.venue_id,
                }
                for match in matches
            ]
        )
        
        # Use enhanced simulation with team features and player tracking
        return self._simulate_season_with_features(fixtures, num_simulations, custom_xis)

    def get_predicted_standings(self) -> Dict:
        return self.simulate_season(500)["predicted_standings"]

    def _load_models(self) -> None:
        # Try multiple paths: Docker container path, relative path, or absolute path from config
        possible_paths = [
            Path("/app/data/models"),  # Docker container path
            Path(__file__).resolve().parents[3] / "data" / "models",  # Relative to project root
            Path(settings.MODEL_PATH) if Path(settings.MODEL_PATH).is_absolute() else None,
            Path(__file__).resolve().parents[3] / Path(settings.MODEL_PATH) if not Path(settings.MODEL_PATH).is_absolute() else None,
        ]
        
        model_dir = None
        for path in possible_paths:
            if path and path.exists():
                model_dir = path
                break
        
        if not model_dir:
            raise FileNotFoundError(f"Model directory not found. Tried: {[str(p) for p in possible_paths if p]}")
        
        model_path = model_dir / "match_predictor.pkl"
        feature_path = model_dir / "match_predictor_features.json"
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if not feature_path.exists():
            raise FileNotFoundError(f"Feature metadata not found: {feature_path}")
        self.match_predictor.load_artifacts(model_path, feature_path)

    def _load_team_features(self) -> Dict[tuple[str, str], Dict]:
        # Try multiple paths for processed data
        possible_paths = [
            Path("/app/data/processed"),  # Docker container path
            Path(__file__).resolve().parents[3] / "data" / "processed",  # Relative to project root
        ]
        
        processed_dir = None
        for path in possible_paths:
            if path and path.exists():
                processed_dir = path
                break
        
        if not processed_dir:
            return {}
        
        snapshot_path = processed_dir / "team_feature_snapshot.csv"
        if not snapshot_path.exists():
            # Fallback to team_season_stats.csv if snapshot doesn't exist
            snapshot_path = processed_dir / "team_season_stats.csv"
            if not snapshot_path.exists():
                return {}
        df = pd.read_csv(snapshot_path)
        df["competition"] = df["competition"].fillna("sa20")
        df["team_key"] = df["team_name"].fillna("").map(_normalise_team_name)
        lookup: Dict[tuple[str, str], Dict] = {}
        for row in df.to_dict("records"):
            key = (row["competition"], row["team_key"])
            lookup[key] = row
        return lookup

    def _select_team_row(self, team: models.Team, competition: str) -> Optional[Dict]:
        candidates = [team.name]
        if team.short_name:
            candidates.append(team.short_name)
        for candidate in candidates:
            key = (competition, _normalise_team_name(candidate))
            if key in self.team_feature_lookup:
                return self.team_feature_lookup[key]
        return None

    def _get_head_to_head_stats(
        self,
        team1_id: int,
        team2_id: int,
    ) -> Dict[str, float]:
        """Calculate head-to-head statistics between two teams."""
        # Get all matches between these two teams
        matches = self.db.query(models.Match).filter(
            (
                ((models.Match.home_team_id == team1_id) & (models.Match.away_team_id == team2_id)) |
                ((models.Match.home_team_id == team2_id) & (models.Match.away_team_id == team1_id))
            ),
            models.Match.winner_id.isnot(None)  # Only completed matches
        ).all()
        
        if not matches:
            return {
                "h2h_total_matches": 0.0,
                "h2h_team1_wins": 0.0,
                "h2h_team2_wins": 0.0,
                "h2h_team1_win_pct": 0.5,  # Default to 50% if no history
                "h2h_team1_avg_runs": 0.0,
                "h2h_team2_avg_runs": 0.0,
            }
        
        total_matches = len(matches)
        team1_wins = sum(1 for m in matches if m.winner_id == team1_id)
        team2_wins = total_matches - team1_wins
        
        # Calculate average scores (would need PlayerPerformance data for this)
        # For now, return win statistics
        return {
            "h2h_total_matches": float(total_matches),
            "h2h_team1_wins": float(team1_wins),
            "h2h_team2_wins": float(team2_wins),
            "h2h_team1_win_pct": float(team1_wins) / total_matches if total_matches > 0 else 0.5,
            "h2h_team1_avg_runs": 0.0,  # Would need to calculate from PlayerPerformance
            "h2h_team2_avg_runs": 0.0,  # Would need to calculate from PlayerPerformance
        }

    def _build_feature_vector(
        self,
        home: Optional[Dict],
        away: Optional[Dict],
        home_lineup: Optional[List[int]],
        away_lineup: Optional[List[int]],
        venue_avg_score: float,
        home_team_id: Optional[int] = None,
        away_team_id: Optional[int] = None,
    ) -> Dict[str, float]:
        def val(row: Optional[Dict], key: str) -> float:
            if not row:
                return 0.0
            return float(row.get(key, 0.0))

        # Map CSV field names to expected feature names (with fallbacks)
        team_win_pct = val(home, "win_pct") or val(home, "win_percentage") or 0.0
        opp_win_pct = val(away, "win_pct") or val(away, "win_percentage") or 0.0
        team_run_rate = val(home, "run_rate") or 0.0
        opp_run_rate = val(away, "run_rate") or 0.0
        team_net_rr = val(home, "net_run_rate") or val(home, "net_rr") or 0.0
        opp_net_rr = val(away, "net_run_rate") or val(away, "net_rr") or 0.0
        team_avg_for = val(home, "avg_runs_for") or (val(home, "total_runs") / val(home, "matches_played") if val(home, "matches_played") > 0 else 0.0)
        opp_avg_for = val(away, "avg_runs_for") or (val(away, "total_runs") / val(away, "matches_played") if val(away, "matches_played") > 0 else 0.0)
        team_avg_against = val(home, "avg_runs_against") or 0.0  # Not available in team_season_stats, will use 0
        opp_avg_against = val(away, "avg_runs_against") or 0.0  # Not available in team_season_stats, will use 0
        team_matches = val(home, "matches_played") or 0.0
        opp_matches = val(away, "matches_played") or 0.0

        vector = {
            "team_win_pct": team_win_pct,
            "opp_win_pct": opp_win_pct,
            "delta_win_pct": team_win_pct - opp_win_pct,
            "team_run_rate": team_run_rate,
            "opp_run_rate": opp_run_rate,
            "delta_run_rate": team_run_rate - opp_run_rate,
            "team_net_run_rate": team_net_rr,
            "opp_net_run_rate": opp_net_rr,
            "delta_net_run_rate": team_net_rr - opp_net_rr,
            "team_avg_runs_for": team_avg_for,
            "opp_avg_runs_for": opp_avg_for,
            "delta_avg_runs_for": team_avg_for - opp_avg_for,
            "team_avg_runs_against": team_avg_against,
            "opp_avg_runs_against": opp_avg_against,
            "delta_avg_runs_against": team_avg_against - opp_avg_against,
            "team_matches": team_matches,
            "opp_matches": opp_matches,
            "delta_matches": team_matches - opp_matches,
        }

        vector["venue_avg_score"] = float(venue_avg_score)
        vector["home_lineup_override"] = float(len(home_lineup)) if home_lineup else 0.0
        vector["away_lineup_override"] = float(len(away_lineup)) if away_lineup else 0.0
        
        # Add head-to-head features if team IDs provided
        if home_team_id and away_team_id:
            h2h_stats = self._get_head_to_head_stats(home_team_id, away_team_id)
            vector["h2h_total_matches"] = h2h_stats["h2h_total_matches"]
            vector["h2h_home_wins"] = h2h_stats["h2h_team1_wins"]
            vector["h2h_away_wins"] = h2h_stats["h2h_team2_wins"]
            vector["h2h_home_win_pct"] = h2h_stats["h2h_team1_win_pct"]
            vector["h2h_delta_win_pct"] = h2h_stats["h2h_team1_win_pct"] - (1.0 - h2h_stats["h2h_team1_win_pct"])
        else:
            # Default values if no h2h data
            vector["h2h_total_matches"] = 0.0
            vector["h2h_home_wins"] = 0.0
            vector["h2h_away_wins"] = 0.0
            vector["h2h_home_win_pct"] = 0.5
            vector["h2h_delta_win_pct"] = 0.0

        return vector
    
    def _predict_match_result(
        self,
        home_team_id: int,
        away_team_id: int,
        venue_id: int,
        home_score: int,
        home_wickets: int,
        away_score: int,
        away_wickets: int,
        home_team_name: str,
        away_team_name: str,
        prediction: Dict,
    ) -> Dict:
        """Predict match result including toss, bat first decision, scores, and winner.
        
        This method encapsulates the full match prediction logic that can be reused
        in both single match prediction and season simulation.
        
        Returns:
            Dictionary with toss_winner, bat_first, scores, winner, result_type, etc.
        """
        # Predict toss winner (50/50 chance - fair coin toss)
        toss_winner = "home" if random.random() < 0.5 else "away"
        
        # Get venue for pitch type
        venue = self.db.get(models.Venue, venue_id)
        
        # Determine bat/bowl first decision based on venue conditions and historical data
        # Get venue toss bias statistics
        import sys
        # Add backend directory to path for imports
        backend_dir = Path(__file__).resolve().parents[2]
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from data_pipeline.calculate_venue_stats import calculate_toss_bias
        venue_toss_bias = calculate_toss_bias(self.db, venue_id)
        
        # Use historical win % to determine optimal decision
        bat_first_win_pct = venue_toss_bias.get("bat_first_win_pct", 50.0)
        chase_win_pct = venue_toss_bias.get("chase_win_pct", 50.0)
        
        # If we have enough historical data, use it to make a decision
        bat_first_total = venue_toss_bias.get("bat_first_total", 0)
        chase_total = venue_toss_bias.get("chase_total", 0)
        
        if bat_first_total + chase_total >= 5:  # Minimum matches for statistical significance
            # Choose the option with better historical win rate
            if bat_first_win_pct > chase_win_pct:
                # Batting first is better at this venue
                bat_first = toss_winner
            elif chase_win_pct > bat_first_win_pct:
                # Chasing is better at this venue
                bat_first = "away" if toss_winner == "home" else "home"
            else:
                # Equal or not enough data - use slight bias toward batting first in T20 (60%)
                bat_first = toss_winner if random.random() < 0.6 else ("away" if toss_winner == "home" else "home")
        else:
            # Not enough historical data - use general T20 trend (slight preference to bat first)
            # Also consider pitch type if available
            pitch_type = venue.pitch_type.lower() if venue and venue.pitch_type else ""
            
            # On batting-friendly pitches, teams prefer to bat first
            # On bowling-friendly pitches, teams may prefer to chase
            if "flat" in pitch_type or "hard" in pitch_type or "batting" in pitch_type:
                bat_first = toss_winner if random.random() < 0.65 else ("away" if toss_winner == "home" else "home")
            elif "green" in pitch_type or "moist" in pitch_type or "bowling" in pitch_type:
                bat_first = toss_winner if random.random() < 0.55 else ("away" if toss_winner == "home" else "home")
            else:
                # Default: slight preference to bat first (60%)
                bat_first = toss_winner if random.random() < 0.6 else ("away" if toss_winner == "home" else "home")
        
        # Determine actual scores based on who batted first
        if bat_first == "home":
            first_innings_score = home_score
            first_innings_wickets = home_wickets
            first_team_name = home_team_name
            second_team_name = away_team_name
            # Second team (away) is chasing - will adjust score based on result
            second_innings_score = away_score
            second_innings_wickets = away_wickets
        else:
            first_innings_score = away_score
            first_innings_wickets = away_wickets
            first_team_name = away_team_name
            second_team_name = home_team_name
            # Second team (home) is chasing - will adjust score based on result
            second_innings_score = home_score
            second_innings_wickets = home_wickets
        
        # Use ML prediction to determine winner
        # Prediction gives us probabilities, use random sampling based on probabilities
        home_win_prob = prediction.get("home_win_probability", 0.5)
        home_wins = random.random() < home_win_prob
        
        # IMPORTANT: If second team is all out (10 wickets), they CANNOT win
        # Check this BEFORE determining winner based on prediction
        second_team_all_out = (second_innings_wickets >= 10)
        
        # Determine who won based on ML prediction and who batted first
        # But if second team is all out, they automatically lose
        # If home batted first and home wins, then first team won
        # If away batted first and away wins, then first team won
        if second_team_all_out:
            # Second team is all out - they cannot win, first team wins automatically
            first_team_wins = True
        else:
            first_team_wins = (bat_first == "home" and home_wins) or (bat_first == "away" and not home_wins)
        
        target = first_innings_score + 1  # Target for chasing team
        
        if first_team_wins:
            # First team won (defending) - won by runs
            # Adjust second innings score to be less than first
            if second_innings_score >= first_innings_score:
                # Second team scored too high, reduce to lose by reasonable margin
                margin_to_lose = random.randint(1, 50)  # Lose by 1-50 runs
                second_innings_score = max(100, first_innings_score - margin_to_lose)
            # Adjust wickets - if losing, likely to lose some wickets
            second_innings_wickets = min(10, random.choices([10, 9, 8, 7, 6, 5, 4], weights=[0.1, 0.2, 0.25, 0.2, 0.15, 0.05, 0.05])[0])
            
            winner = "home" if bat_first == "home" else "away"
            margin = first_innings_score - second_innings_score
            result_type = "runs"
            result_text = f"{first_team_name} won by {margin} runs"
        else:
            # Second team won (chasing) - MUST win by wickets (cannot be all out when winning)
            # If batting second and winning, you MUST have wickets remaining
            # Score should be just over target (1-6 runs over, as you correctly pointed out)
            winning_runs_over = random.randint(1, 6)  # 1-6 runs over target
            second_innings_score = target + winning_runs_over
            # Wickets should be reasonable for a winning chase (typically 3-7 wickets lost)
            # NEVER 10 wickets when winning (all out means you lost)
            second_innings_wickets = random.choices([3, 4, 5, 6, 7], weights=[0.15, 0.25, 0.3, 0.2, 0.1])[0]
            
            winner = "away" if bat_first == "home" else "home"
            wickets_remaining = 10 - second_innings_wickets
            margin = wickets_remaining
            result_type = "wickets"
            result_text = f"{second_team_name} won by {wickets_remaining} wickets"
        
        # Update home_score and away_score to reflect adjusted scores
        if bat_first == "home":
            final_home_score = first_innings_score
            final_home_wickets = first_innings_wickets
            final_away_score = second_innings_score
            final_away_wickets = second_innings_wickets
        else:
            final_away_score = first_innings_score
            final_away_wickets = first_innings_wickets
            final_home_score = second_innings_score
            final_home_wickets = second_innings_wickets
        
        return {
            "toss_winner": toss_winner,
            "bat_first": bat_first,
            "home_score": final_home_score,
            "home_wickets": final_home_wickets,
            "away_score": final_away_score,
            "away_wickets": final_away_wickets,
            "first_innings_score": first_innings_score,
            "first_innings_wickets": first_innings_wickets,
            "second_innings_score": second_innings_score,
            "second_innings_wickets": second_innings_wickets,
            "first_team_name": first_team_name,
            "second_team_name": second_team_name,
            "winner": winner,
            "result_type": result_type,
            "result_text": result_text,
            "margin": margin,
        }
    
    def _fallback_player_projection(
        self,
        player_service: "PlayerService",
        player: Dict,
    ) -> tuple[float, float]:
        """Generate heuristic player projections when ML models are unavailable."""
        role_defaults: Dict[str, tuple[float, float]] = {
            "batsman": (32.0, 0.25),
            "batter": (32.0, 0.25),
            "wicket_keeper": (28.0, 0.2),
            "wk": (28.0, 0.2),
            "all_rounder": (24.0, 0.9),
            "bowler": (16.0, 1.4),
            "fast_bowler": (15.0, 1.6),
            "pace_bowler": (15.0, 1.6),
            "seamer": (15.0, 1.5),
            "spinner": (18.0, 1.5),
            "legspinner": (18.0, 1.5),
            "offspinner": (18.0, 1.4),
            "default": (22.0, 0.6),
        }
        role = str(player.get("role") or "").lower()
        base_runs, base_wickets = role_defaults.get(role, role_defaults["default"])
        
        player_detail = None
        try:
            player_detail = player_service.get_player_detail(player["id"])
        except Exception:
            player_detail = None
        
        if player_detail and player_detail.get("career_stats"):
            stats = player_detail["career_stats"]
            matches = max(stats.get("matches_played") or 0, 1)
            avg_runs = (stats.get("runs_scored") or 0) / matches if matches else 0.0
            avg_wickets = (stats.get("wickets_taken") or 0) / matches if matches else 0.0
            if avg_runs > 0:
                base_runs = 0.55 * base_runs + 0.45 * avg_runs
            if avg_wickets > 0:
                base_wickets = 0.5 * base_wickets + 0.5 * avg_wickets
        
        predicted_runs = max(6.0, random.gauss(base_runs, max(4.0, base_runs * 0.25)))
        predicted_wickets = max(0.0, random.gauss(base_wickets, max(0.2, base_wickets * 0.3)))
        return (round(predicted_runs, 2), round(predicted_wickets, 2))

    def predict_top_run_scorers(self, limit: int = 10) -> Dict:
        """Predict top run scorers for the upcoming season using player projections."""
        from app.services.player_projection_service import PlayerProjectionService
        from app.services.player_service import PlayerService
        
        try:
            projection_service = PlayerProjectionService()
        except FileNotFoundError:
            return {
                "error": "Player projection models not available. Please train the models first.",
                "predictions": []
            }
        
        player_service = PlayerService(self.db)
        all_players = player_service.get_players()
        
        predictions = []
        for player_dict in all_players:
            player_id = player_dict["id"]
            try:
                projection = player_service.predict_performance(player_id)
                if projection:
                    predictions.append({
                        "player_id": player_id,
                        "player_name": player_dict["name"],
                        "team_id": player_dict.get("team_id"),
                        "team_name": None,  # Could be added if needed
                        "predicted_runs": projection.get("predicted_runs", 0.0),
                        "role": player_dict.get("role"),
                        "country": player_dict.get("country"),
                    })
            except Exception:
                continue
        
        # Sort by predicted runs and return top N
        predictions.sort(key=lambda x: x["predicted_runs"], reverse=True)
        
        # Add team names
        for pred in predictions:
            if pred["team_id"]:
                team = self.db.get(models.Team, pred["team_id"])
                if team:
                    pred["team_name"] = team.name
        
        return {
            "predictions": predictions[:limit],
            "season": 2026,
        }

    def predict_top_wicket_takers(self, limit: int = 10) -> Dict:
        """Predict top wicket takers for the upcoming season using player projections."""
        from app.services.player_projection_service import PlayerProjectionService
        from app.services.player_service import PlayerService
        
        try:
            projection_service = PlayerProjectionService()
        except FileNotFoundError:
            return {
                "error": "Player projection models not available. Please train the models first.",
                "predictions": []
            }
        
        player_service = PlayerService(self.db)
        all_players = player_service.get_players()
        
        predictions = []
        for player_dict in all_players:
            player_id = player_dict["id"]
            try:
                projection = player_service.predict_performance(player_id)
                if projection:
                    predictions.append({
                        "player_id": player_id,
                        "player_name": player_dict["name"],
                        "team_id": player_dict.get("team_id"),
                        "team_name": None,
                        "predicted_wickets": projection.get("predicted_wickets", 0.0),
                        "role": player_dict.get("role"),
                        "country": player_dict.get("country"),
                    })
            except Exception:
                continue
        
        # Sort by predicted wickets and return top N
        predictions.sort(key=lambda x: x["predicted_wickets"], reverse=True)
        
        # Add team names
        for pred in predictions:
            if pred["team_id"]:
                team = self.db.get(models.Team, pred["team_id"])
                if team:
                    pred["team_name"] = team.name
        
        return {
            "predictions": predictions[:limit],
            "season": 2026,
        }

    def _simulate_season_with_features(
        self, 
        fixtures: pd.DataFrame, 
        num_simulations: int,
        custom_xis: Optional[Dict[int, List[int]]] = None
    ) -> Dict:
        """Simulate season using match predictor with team features and player-level tracking.
        
        Optimized version that pre-loads all data to avoid database queries during simulation.
        """
        competition = "sa20"
        # Convert numpy types to Python int
        teams = sorted([int(tid) for tid in set(fixtures["home_team_id"].unique()).union(fixtures["away_team_id"].unique())])
        playoff_counts = {team: 0 for team in teams}
        champion_counts = {team: 0 for team in teams}
        standings: List[pd.DataFrame] = []
        
        # Player-level tracking across all simulations
        player_runs_totals: Dict[int, List[float]] = {}  # player_id -> list of total runs per sim
        player_wickets_totals: Dict[int, List[float]] = {}  # player_id -> list of total wickets per sim
        player_team_map: Dict[int, int] = {}  # player_id -> team_id
        
        # OPTIMIZATION: Pre-load all data to avoid database queries during simulation
        # Load all teams (we'll reload with players later)
        team_map = {team.id: team for team in self.db.query(models.Team).filter(models.Team.id.in_(teams)).all()}
        
        # Load all venues
        venue_ids = fixtures["venue_id"].dropna().unique().tolist()
        venue_map = {venue.id: venue for venue in self.db.query(models.Venue).filter(models.Venue.id.in_(venue_ids)).all()}
        
        # Load venue mapping for matches
        match_venue_map = {}
        for match in self.db.query(models.Match).all():
            match_venue_map[match.id] = match.venue_id if hasattr(match, 'venue_id') else None
        
        # OPTIMIZATION: Pre-load team players map using eager loading FIRST
        # Load all teams with players relationship in one query
        from sqlalchemy.orm import selectinload
        teams_with_players = self.db.query(models.Team).options(selectinload(models.Team.players)).filter(models.Team.id.in_(teams)).all()
        team_players_map = {}
        # Update team_map with eagerly loaded teams
        for team in teams_with_players:
            team_map[team.id] = team
            if team.players:
                team_players_map[team.id] = [p.id for p in team.players[:11]]  # Top 11 players
            else:
                team_players_map[team.id] = []
        
        # OPTIMIZATION: Collect all player IDs we need
        all_player_ids = set()
        if custom_xis:
            # Use custom XIs if provided
            for player_list in custom_xis.values():
                all_player_ids.update(player_list)
        else:
            # Collect all player IDs from eagerly loaded teams
            for team in teams_with_players:
                if team.players:
                    all_player_ids.update([p.id for p in team.players])
        
        # OPTIMIZATION: Load all players in one query
        player_map = {}
        if all_player_ids:
            # Load players from database if we have IDs
            players_list = self.db.query(models.Player).filter(models.Player.id.in_(list(all_player_ids))).all()
            player_map = {p.id: p for p in players_list}
        else:
            # Fallback: use players from eagerly loaded teams
            for team in teams_with_players:
                if team.players:
                    for player in team.players:
                        player_map[player.id] = player
        
        # OPTIMIZATION: Pre-build team feature rows
        team_feature_rows = {}
        for team_id, team in team_map.items():
            team_feature_rows[team_id] = self._select_team_row(team, competition)
        
        # OPTIMIZATION: Pre-build venue averages
        venue_averages = {}
        for venue_id, venue in venue_map.items():
            venue_averages[venue_id] = venue.avg_first_innings_score if hasattr(venue, 'avg_first_innings_score') and venue.avg_first_innings_score else 160
        
        # OPTIMIZATION: Pre-compute all player projections
        from app.services.player_service import PlayerService
        player_service = PlayerService(self.db)
        player_projections: Dict[int, Dict] = {}
        for player_id, player in player_map.items():
            try:
                proj = player_service.predict_performance(player_id)
                if proj:
                    player_projections[player_id] = {
                        "predicted_runs": proj.get("predicted_runs", 0.0),
                        "predicted_wickets": proj.get("predicted_wickets", 0.0),
                    }
                    player_team_map[player_id] = player.team_id if player.team_id else None
            except Exception:
                # If projection fails, use defaults
                player_projections[player_id] = {
                    "predicted_runs": 0.0,
                    "predicted_wickets": 0.0,
                }
        
        # OPTIMIZATION: Extract all needed data into plain dictionaries to avoid any lazy loading
        # This ensures we don't trigger any database queries during simulation
        # Convert SQLAlchemy objects to plain dicts for team/player names
        team_names = {team_id: team.name for team_id, team in team_map.items()}
        player_names = {player_id: player.name for player_id, player in player_map.items()}
        player_roles = {player_id: (player.role.value if hasattr(player.role, 'value') else str(player.role)) 
                       for player_id, player in player_map.items()}
        
        # All data is now in memory as plain Python objects
        # No database queries will be triggered during simulation
        
        for sim_idx in range(num_simulations):
            outcomes = []
            # Track player stats for this simulation
            sim_player_runs: Dict[int, float] = {}
            sim_player_wickets: Dict[int, float] = {}
            
            for _, match_row in fixtures.iterrows():
                # Convert numpy types to Python int
                match_id = int(match_row["match_id"]) if hasattr(match_row["match_id"], '__int__') else match_row["match_id"]
                home_team_id = int(match_row["home_team_id"]) if hasattr(match_row["home_team_id"], '__int__') else match_row["home_team_id"]
                away_team_id = int(match_row["away_team_id"]) if hasattr(match_row["away_team_id"], '__int__') else match_row["away_team_id"]
                venue_id = match_row.get("venue_id")
                if pd.isna(venue_id) or venue_id is None:
                    venue_id = match_venue_map.get(match_id)
                venue_id = int(venue_id) if venue_id and hasattr(venue_id, '__int__') else venue_id
                
                # OPTIMIZATION: Use pre-loaded data instead of database queries
                home_team = team_map.get(home_team_id)
                away_team = team_map.get(away_team_id)
                
                # Get custom XIs or default to all players
                home_lineup = custom_xis.get(home_team_id, None) if custom_xis else None
                away_lineup = custom_xis.get(away_team_id, None) if custom_xis else None
                
                # OPTIMIZATION: Use pre-built feature rows
                home_row = team_feature_rows.get(home_team_id)
                away_row = team_feature_rows.get(away_team_id)
                venue_avg = venue_averages.get(venue_id, 160) if venue_id else 160
                
                feature_vector = self._build_feature_vector(
                    home_row, away_row, home_lineup, away_lineup, venue_avg,
                    home_team_id=home_team_id, away_team_id=away_team_id
                )
                # Ensure all required features are present
                required_features = self.match_predictor.feature_names
                for feature in required_features:
                    if feature not in feature_vector:
                        feature_vector[feature] = 0.0
                
                prediction = self.match_predictor.predict_from_vector(feature_vector)
                
                # OPTIMIZATION: Use pre-loaded player data
                # Get player IDs for each team (use custom XI if provided)
                if home_lineup:
                    home_player_ids = [pid for pid in home_lineup if pid in player_map]
                else:
                    home_player_ids = team_players_map.get(home_team_id, [])
                
                if away_lineup:
                    away_player_ids = [pid for pid in away_lineup if pid in player_map]
                else:
                    away_player_ids = team_players_map.get(away_team_id, [])
                
                # OPTIMIZATION: Use pre-computed player projections
                # Simulate player runs and wickets using cached projections with variance
                home_team_runs = 0
                away_team_runs = 0
                
                for player_id in home_player_ids[:11]:  # Top 11 players
                    proj = player_projections.get(player_id)
                    if proj:
                        # Add variance using Gaussian distribution
                        runs = max(0, np.random.normal(proj["predicted_runs"], proj["predicted_runs"] * 0.3))
                        wickets = max(0, np.random.normal(proj["predicted_wickets"], max(0.5, proj["predicted_wickets"] * 0.4)))
                        home_team_runs += runs
                        sim_player_runs[player_id] = sim_player_runs.get(player_id, 0) + runs
                        sim_player_wickets[player_id] = sim_player_wickets.get(player_id, 0) + wickets
                
                for player_id in away_player_ids[:11]:
                    proj = player_projections.get(player_id)
                    if proj:
                        runs = max(0, np.random.normal(proj["predicted_runs"], proj["predicted_runs"] * 0.3))
                        wickets = max(0, np.random.normal(proj["predicted_wickets"], max(0.5, proj["predicted_wickets"] * 0.4)))
                        away_team_runs += runs
                        sim_player_runs[player_id] = sim_player_runs.get(player_id, 0) + runs
                        sim_player_wickets[player_id] = sim_player_wickets.get(player_id, 0) + wickets
                
                # Calculate approximate team scores (simplified for season simulation)
                home_score_approx = int(np.clip(home_team_runs * 0.7 + venue_avg * 0.3, 130, 220))
                away_score_approx = int(np.clip(away_team_runs * 0.7 + venue_avg * 0.3, 130, 220))
                
                # Estimate wickets (simplified for season simulation)
                home_wickets_approx = random.choices([3, 4, 5, 6, 7, 8, 9, 10], weights=[0.1, 0.15, 0.2, 0.2, 0.15, 0.1, 0.05, 0.05])[0]
                away_wickets_approx = random.choices([3, 4, 5, 6, 7, 8, 9, 10], weights=[0.1, 0.15, 0.2, 0.2, 0.15, 0.1, 0.05, 0.05])[0]
                
                # Use full match prediction logic (toss, bat first, scores, result)
                # This ensures season simulation uses the same logic as single match prediction
                match_result = self._predict_match_result(
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    venue_id=venue_id if venue_id else 1,  # Fallback venue_id if None
                    home_score=home_score_approx,
                    home_wickets=home_wickets_approx,
                    away_score=away_score_approx,
                    away_wickets=away_wickets_approx,
                    home_team_name=team_names.get(home_team_id, "Home Team"),
                    away_team_name=team_names.get(away_team_id, "Away Team"),
                    prediction=prediction
                )
                
                # Extract winner from match result
                winner_str = match_result["winner"]
                winner_id = int(home_team_id) if winner_str == "home" else int(away_team_id)
                
                # Convert to Python int for database compatibility
                match_id_int = int(match_id) if hasattr(match_id, '__int__') else match_id
                outcomes.append({
                    "match_id": match_id_int,
                    "home_team_id": int(home_team_id),
                    "away_team_id": int(away_team_id),
                    "winner_id": winner_id,
                })
            
            # Store player totals for this simulation
            for player_id, runs in sim_player_runs.items():
                if player_id not in player_runs_totals:
                    player_runs_totals[player_id] = []
                player_runs_totals[player_id].append(runs)
            
            for player_id, wickets in sim_player_wickets.items():
                if player_id not in player_wickets_totals:
                    player_wickets_totals[player_id] = []
                player_wickets_totals[player_id].append(wickets)
            
            results_df = pd.DataFrame(outcomes)
            table = self._calculate_standings(results_df, teams)
            standings.append(table)
            playoff = [int(tid) for tid in table.head(4)["team_id"].tolist()]  # Convert to Python int
            for team in playoff:
                playoff_counts[team] += 1
            champion = self._simulate_playoffs(playoff)
            champion_counts[champion] += 1
        
        # Aggregate results with player stats
        result = self._aggregate_results(standings, playoff_counts, champion_counts, teams, num_simulations)
        
        # OPTIMIZATION: Use pre-loaded data dictionaries instead of SQLAlchemy objects
        # Calculate Orange Cap (top run scorer) and Purple Cap (top wicket taker)
        orange_cap = None
        purple_cap = None
        if player_runs_totals:
            avg_runs = {pid: np.mean(runs_list) for pid, runs_list in player_runs_totals.items()}
            top_scorer_id = max(avg_runs.items(), key=lambda x: x[1])[0]
            if top_scorer_id in player_names:
                team_id = player_team_map.get(top_scorer_id)
                orange_cap = {
                    "player_id": top_scorer_id,
                    "player_name": player_names.get(top_scorer_id, "Unknown"),
                    "team_id": team_id,
                    "team_name": team_names.get(team_id) if team_id else None,
                    "avg_runs": float(avg_runs[top_scorer_id]),
                    "total_runs_range": [float(min(player_runs_totals[top_scorer_id])), float(max(player_runs_totals[top_scorer_id]))],
                }
        
        if player_wickets_totals:
            avg_wickets = {pid: np.mean(wkts_list) for pid, wkts_list in player_wickets_totals.items()}
            top_wicket_taker_id = max(avg_wickets.items(), key=lambda x: x[1])[0]
            if top_wicket_taker_id in player_names:
                team_id = player_team_map.get(top_wicket_taker_id)
                purple_cap = {
                    "player_id": top_wicket_taker_id,
                    "player_name": player_names.get(top_wicket_taker_id, "Unknown"),
                    "team_id": team_id,
                    "team_name": team_names.get(team_id) if team_id else None,
                    "avg_wickets": float(avg_wickets[top_wicket_taker_id]),
                    "total_wickets_range": [float(min(player_wickets_totals[top_wicket_taker_id])), float(max(player_wickets_totals[top_wicket_taker_id]))],
                }
        
        # Find predicted champion (team with highest championship probability)
        champion_team_id = max(champion_counts.items(), key=lambda x: x[1])[0] if champion_counts else None
        
        # Calculate MVP (Most Valuable Player) - best overall performance (runs + wickets weighted)
        mvp = None
        if player_runs_totals and player_wickets_totals:
            mvp_scores = {}
            for player_id in set(player_runs_totals.keys()) | set(player_wickets_totals.keys()):
                avg_runs = np.mean(player_runs_totals.get(player_id, [0]))
                avg_wickets = np.mean(player_wickets_totals.get(player_id, [0]))
                # Weighted score: runs + wickets * 20 (since wickets are rarer)
                mvp_score = avg_runs + avg_wickets * 20
                mvp_scores[player_id] = mvp_score
            
            if mvp_scores:
                mvp_id = max(mvp_scores.items(), key=lambda x: x[1])[0]
                if mvp_id in player_names:
                    team_id = player_team_map.get(mvp_id)
                    mvp = {
                        "player_id": mvp_id,
                        "player_name": player_names.get(mvp_id, "Unknown"),
                        "team_id": team_id,
                        "team_name": team_names.get(team_id) if team_id else None,
                        "avg_runs": float(np.mean(player_runs_totals.get(mvp_id, [0]))),
                        "avg_wickets": float(np.mean(player_wickets_totals.get(mvp_id, [0]))),
                        "mvp_score": float(mvp_scores[mvp_id]),
                    }
        
        # Calculate Team of the Tournament (best XI across all teams)
        team_of_tournament = []
        if player_runs_totals and player_wickets_totals:
            # OPTIMIZATION: Use pre-loaded data dictionaries
            # Get top performers by role
            all_players_data = []
            for player_id in set(player_runs_totals.keys()) | set(player_wickets_totals.keys()):
                if player_id not in player_names:
                    continue
                avg_runs = np.mean(player_runs_totals.get(player_id, [0]))
                avg_wickets = np.mean(player_wickets_totals.get(player_id, [0]))
                team_id = player_team_map.get(player_id)
                all_players_data.append({
                    "player_id": player_id,
                    "player_name": player_names.get(player_id, "Unknown"),
                    "team_id": team_id,
                    "team_name": team_names.get(team_id) if team_id else None,
                    "role": player_roles.get(player_id, "unknown"),
                    "avg_runs": avg_runs,
                    "avg_wickets": avg_wickets,
                    "performance_score": avg_runs + avg_wickets * 20,
                })
            
            # Select best XI: 1 WK, 3-4 batsmen, 1-2 all-rounders, 3-4 bowlers
            wicket_keepers = [p for p in all_players_data if p["role"] == "wicket_keeper"]
            batsmen = [p for p in all_players_data if p["role"] == "batsman"]
            all_rounders = [p for p in all_players_data if p["role"] == "all_rounder"]
            bowlers = [p for p in all_players_data if p["role"] == "bowler"]
            
            # Select top performers
            if wicket_keepers:
                team_of_tournament.append(max(wicket_keepers, key=lambda x: x["performance_score"]))
            
            # Top 4 batsmen
            team_of_tournament.extend(sorted(batsmen, key=lambda x: x["performance_score"], reverse=True)[:4])
            
            # Top 2 all-rounders
            team_of_tournament.extend(sorted(all_rounders, key=lambda x: x["performance_score"], reverse=True)[:2])
            
            # Top 4 bowlers
            team_of_tournament.extend(sorted(bowlers, key=lambda x: x["performance_score"], reverse=True)[:4])
            
            # If we have less than 11, fill with best remaining players
            if len(team_of_tournament) < 11:
                remaining = [p for p in all_players_data if p not in team_of_tournament]
                remaining.sort(key=lambda x: x["performance_score"], reverse=True)
                team_of_tournament.extend(remaining[:11 - len(team_of_tournament)])
            
            # Sort by performance score
            team_of_tournament = sorted(team_of_tournament[:11], key=lambda x: x["performance_score"], reverse=True)
        
        # Calculate Upset Tracker (teams that exceeded expectations)
        upset_tracker = []
        if standings and teams:
            # Calculate expected positions based on initial team strength (using avg_points as proxy)
            expected_positions = {}
            for team in teams:
                positions = [table.loc[table["team_id"] == team, "position"].iloc[0] 
                           for table in standings if len(table.loc[table["team_id"] == team]) > 0]
                if positions:
                    expected_positions[team] = np.mean(positions)
            
            # OPTIMIZATION: Use pre-loaded data dictionaries
            # Find teams that performed better than expected (lower position = better)
            sorted_by_expected = sorted(expected_positions.items(), key=lambda x: x[1])
            for i, (team_id, expected_pos) in enumerate(sorted_by_expected):
                # Teams that finished significantly better than their expected position
                if expected_pos > i + 2:  # Finished at least 2 positions better
                    if team_id in team_names:
                        actual_avg_pos = expected_pos  # This is the average position
                        upset_tracker.append({
                            "team_id": team_id,
                            "team_name": team_names.get(team_id, "Unknown"),
                            "expected_position": float(expected_pos),
                            "actual_avg_position": float(actual_avg_pos),
                            "improvement": float(expected_pos - actual_avg_pos),
                        })
        
        result["orange_cap"] = orange_cap
        result["purple_cap"] = purple_cap
        result["champion"] = {
            "team_id": champion_team_id,
            "team_name": team_names.get(champion_team_id) if champion_team_id else None,
            "win_probability": float(champion_counts[champion_team_id] / num_simulations * 100) if champion_team_id else 0.0,
        } if champion_team_id else None
        result["mvp"] = mvp
        result["team_of_tournament"] = team_of_tournament
        result["upset_tracker"] = upset_tracker
        
        return result
    
    def _calculate_standings(self, results: pd.DataFrame, teams: List[int]) -> pd.DataFrame:
        """Calculate standings from match results."""
        rows = []
        for team in teams:
            played = ((results["home_team_id"] == team) | (results["away_team_id"] == team)).sum()
            wins = (results["winner_id"] == team).sum()
            losses = played - wins
            rows.append({
                "team_id": team,
                "matches_played": played,
                "wins": wins,
                "losses": losses,
                "points": wins * 2,
                "win_rate": wins / played if played else 0,
            })
        table = pd.DataFrame(rows).sort_values(["points", "win_rate"], ascending=False)
        table["position"] = range(1, len(table) + 1)
        return table
    
    def _simulate_playoffs(self, teams: List[int]) -> int:
        """Simulate SA20 playoff structure: Qualifier 1, Eliminator, Qualifier 2, Final."""
        if len(teams) < 4:
            return teams[0] if teams else -1
        
        # Qualifier 1: 1st vs 2nd
        q1_winner = teams[0] if np.random.random() < 0.5 else teams[1]
        q1_loser = teams[1] if q1_winner == teams[0] else teams[0]
        
        # Eliminator: 3rd vs 4th
        elim_winner = teams[2] if np.random.random() < 0.5 else teams[3]
        
        # Qualifier 2: Loser Q1 vs Winner Eliminator
        q2_winner = q1_loser if np.random.random() < 0.5 else elim_winner
        
        # Final: Winner Q1 vs Winner Q2
        champion = q1_winner if np.random.random() < 0.5 else q2_winner
        
        return champion
    
    def _aggregate_results(
        self,
        standings: List[pd.DataFrame],
        playoff_counts: Dict[int, int],
        champion_counts: Dict[int, int],
        teams: List[int],
        num_simulations: int,
    ) -> Dict:
        """Aggregate simulation results into final predictions."""
        aggregated = []
        for team in teams:
            positions = [table.loc[table["team_id"] == team, "position"].iloc[0] for table in standings if len(table.loc[table["team_id"] == team]) > 0]
            points = [table.loc[table["team_id"] == team, "points"].iloc[0] for table in standings if len(table.loc[table["team_id"] == team]) > 0]
            if not positions:
                continue
            aggregated.append({
                "team_id": team,
                "avg_position": float(np.mean(positions)),
                "avg_points": float(np.mean(points)),
                "position_std": float(np.std(positions)),
                "playoff_probability": playoff_counts[team] / num_simulations * 100,
                "championship_probability": champion_counts[team] / num_simulations * 100,
            })
        aggregated_df = pd.DataFrame(aggregated).sort_values("avg_points", ascending=False)
        # Convert team IDs to int for JSON serialization
        playoff_probs = {int(team): float(playoff_counts[team] / num_simulations * 100) for team in teams}
        champ_probs = {int(team): float(champion_counts[team] / num_simulations * 100) for team in teams}
        return {
            "predicted_standings": aggregated_df.to_dict("records"),
            "playoff_probabilities": playoff_probs,
            "championship_probabilities": champ_probs,
            "num_simulations": num_simulations,
        }
