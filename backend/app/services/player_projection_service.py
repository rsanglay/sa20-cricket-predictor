"""Player performance projection service using trained regressors."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from joblib import load

from app.core.config import settings


def _normalise_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


@dataclass
class PlayerProjectionService:
    """Loads player regression models and feature snapshot for inference."""

    models_dir: Path = Path(settings.MODEL_PATH)
    processed_dir: Path = Path(__file__).resolve().parents[3] / "data" / "processed"

    def __post_init__(self) -> None:
        # Fix path resolution for Docker container
        # Try multiple paths: Docker container path, relative path, or absolute path from config
        possible_model_paths = [
            Path("/app/data/models"),  # Docker container path
            Path(__file__).resolve().parents[3] / "data" / "models",  # Relative to project root
            Path(settings.MODEL_PATH) if Path(settings.MODEL_PATH).is_absolute() else None,
            Path(__file__).resolve().parents[3] / Path(settings.MODEL_PATH) if not Path(settings.MODEL_PATH).is_absolute() else None,
        ]
        
        model_dir = None
        for path in possible_model_paths:
            if path and path.exists():
                model_dir = path
                break
        
        if model_dir:
            self.models_dir = model_dir
        elif not self.models_dir.is_absolute():
            self.models_dir = Path(__file__).resolve().parents[3] / self.models_dir
        
        # Fix processed_dir path resolution for Docker container
        possible_processed_paths = [
            Path("/app/data/processed"),  # Docker container path
            Path(__file__).resolve().parents[3] / "data" / "processed",  # Relative to project root
        ]
        
        processed_dir = None
        for path in possible_processed_paths:
            if path and path.exists():
                processed_dir = path
                break
        
        if processed_dir:
            self.processed_dir = processed_dir
        
        self._load_models()
        self._load_feature_snapshot()

    def _load_models(self) -> None:
        runs_model_path = self.models_dir / "player_runs_regressor.pkl"
        runs_features_path = self.models_dir / "player_runs_features.json"
        wickets_model_path = self.models_dir / "player_wickets_regressor.pkl"
        wickets_features_path = self.models_dir / "player_wickets_features.json"

        if not runs_model_path.exists() or not runs_features_path.exists():
            raise FileNotFoundError("Player runs model artifacts missing. Run train_player_models.py")
        if not wickets_model_path.exists() or not wickets_features_path.exists():
            raise FileNotFoundError("Player wickets model artifacts missing. Run train_player_models.py")

        self.runs_model = load(runs_model_path)
        self.wickets_model = load(wickets_model_path)

        self.runs_features = self._load_feature_metadata(runs_features_path)
        self.wickets_features = self._load_feature_metadata(wickets_features_path)
        self.runs_feature_set = set(self.runs_features)
        self.wickets_feature_set = set(self.wickets_features)

    def _load_feature_metadata(self, path: Path) -> list[str]:
        with path.open("r", encoding="utf-8") as fh:
            metadata = json.load(fh)
        return metadata.get("feature_names", [])

    def _load_feature_snapshot(self) -> None:
        snapshot_path = self.processed_dir / "player_feature_snapshot.csv"
        if not snapshot_path.exists():
            raise FileNotFoundError(
                "player_feature_snapshot.csv not found. Run train_player_models.py"
            )
        df = pd.read_csv(snapshot_path)
        df["key"] = df["player_name"].fillna("").map(_normalise_name)
        self.snapshot_lookup: Dict[str, Dict] = {
            row["key"]: row for row in df.to_dict("records")
        }

    def predict_player(self, player_name: str) -> Dict[str, float]:
        key = _normalise_name(player_name)
        snapshot = self.snapshot_lookup.get(key)
        if snapshot is None:
            raise ValueError(f"No feature snapshot available for player '{player_name}'")

        runs_vector = self._build_vector(snapshot, self.runs_features)
        wickets_vector = self._build_vector(snapshot, self.wickets_features)

        predicted_runs = float(self.runs_model.predict([runs_vector])[0])
        predicted_wickets = float(self.wickets_model.predict([wickets_vector])[0])

        features = {
            feature: float(snapshot.get(feature, 0.0))
            for feature in set(self.runs_features + self.wickets_features)
        }

        return {
            "player_name": player_name,
            "predicted_runs": max(0.0, predicted_runs),
            "predicted_wickets": max(0.0, predicted_wickets),
            "features": features,
        }

    def has_projection(self, player_name: str) -> bool:
        """Return True if projection data exists for the given player name."""
        key = _normalise_name(player_name)
        return key in self.snapshot_lookup

    def _build_vector(self, snapshot: Dict, feature_names: list[str]) -> list[float]:
        return [float(snapshot.get(feature, 0.0)) for feature in feature_names]

