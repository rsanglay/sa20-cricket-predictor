"""Match outcome predictor backed by a scikit-learn classifier."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from joblib import load
from sklearn.ensemble import GradientBoostingClassifier


@dataclass
class MatchPredictor:
    """Wrapper for loading and scoring the trained match outcome model."""

    model: GradientBoostingClassifier | None = None
    feature_names: List[str] = field(default_factory=list)

    def load_artifacts(self, model_path: Path, feature_path: Path) -> None:
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")
        if not feature_path.exists():
            raise FileNotFoundError(f"Feature metadata not found: {feature_path}")

        self.model = load(model_path)
        with feature_path.open("r", encoding="utf-8") as fh:
            metadata = json.load(fh)
        self.feature_names = metadata.get("feature_names", [])
        if not self.feature_names:
            raise ValueError("Feature names missing from metadata")

    def predict_from_vector(self, feature_vector: Dict[str, float]) -> Dict[str, float | List]:
        if self.model is None or not self.feature_names:
            raise ValueError("Model artifacts not loaded")

        # Ensure all required features are present, fill missing ones with 0
        complete_vector = {feature: feature_vector.get(feature, 0.0) for feature in self.feature_names}
        dataframe = pd.DataFrame([complete_vector], columns=self.feature_names)
        probabilities = self.model.predict_proba(dataframe)[0]
        prediction = int(self.model.predict(dataframe)[0])
        importances = getattr(self.model, "feature_importances_", None)
        top_factors: List[tuple[str, float]] = []
        if importances is not None:
            importance_map = dict(zip(self.feature_names, importances))
            top_factors = sorted(importance_map.items(), key=lambda item: item[1], reverse=True)[:5]

        return {
            "home_win_probability": float(probabilities[1]),
            "away_win_probability": float(probabilities[0]),
            "predicted_winner": "home" if prediction == 1 else "away",
            "confidence": float(np.max(probabilities)),
            "top_factors": top_factors,
        }
