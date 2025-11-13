"""ML model inference service."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.ml.models.match_predictor import MatchPredictor
from app.services.ml.features import FeatureService
from app.services.ml.registry import ModelRegistry


class InferenceService:
    """Service for running ML model inference."""
    
    def __init__(self, feature_service: FeatureService, model_registry: ModelRegistry):
        """Initialize inference service.
        
        Args:
            feature_service: Feature service instance
            model_registry: Model registry instance
        """
        self.feature_service = feature_service
        self.model_registry = model_registry
    
    def predict_match(
        self,
        team1_id: int,
        team2_id: int,
        venue_id: int,
        model_name: str = "match_predictor",
    ) -> Dict:
        """Predict match outcome.
        
        Args:
            team1_id: First team ID
            team2_id: Second team ID
            venue_id: Venue ID
            model_name: Model name to use
            
        Returns:
            Dictionary with prediction results
        """
        # Get model
        model = self.model_registry.get_model(model_name)
        if not model:
            raise ValueError(f"Model {model_name} not found")
        
        # Build features
        features = self.feature_service.build_match_features(team1_id, team2_id, venue_id)
        
        # Make prediction
        prediction = model.predict_from_vector(features)
        
        return prediction
    
    def predict_player_performance(
        self,
        player_id: int,
        model_type: str = "runs",  # 'runs' or 'wickets'
        phase: Optional[str] = None,
    ) -> Dict:
        """Predict player performance.
        
        Args:
            player_id: Player ID
            model_type: Model type ('runs' or 'wickets')
            phase: Match phase (optional)
            
        Returns:
            Dictionary with prediction results
        """
        # Get model
        model_name = f"player_{model_type}_regressor"
        model = self.model_registry.get_model(model_name)
        if not model:
            raise ValueError(f"Model {model_name} not found")
        
        # Build features
        features = self.feature_service.build_player_features(player_id, phase)
        
        # Make prediction (simplified - would need proper model interface)
        # For now, return features as placeholder
        return {
            "player_id": player_id,
            "predicted_value": 0.0,  # Would be actual prediction
            "features": features,
        }
    
    def get_feature_importance(
        self,
        model_name: str,
        top_k: int = 10,
    ) -> List[Dict[str, float]]:
        """Get feature importance for a model.
        
        Args:
            model_name: Model name
            top_k: Number of top features to return
            
        Returns:
            List of feature importance dictionaries
        """
        model = self.model_registry.get_model(model_name)
        if not model:
            raise ValueError(f"Model {model_name} not found")
        
        # Get feature importances
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
            feature_names = getattr(model, "feature_names", [])
            
            # Combine and sort
            importance_map = [
                {"feature": name, "importance": float(imp)}
                for name, imp in zip(feature_names, importances)
            ]
            importance_map.sort(key=lambda x: x["importance"], reverse=True)
            
            return importance_map[:top_k]
        
        return []

