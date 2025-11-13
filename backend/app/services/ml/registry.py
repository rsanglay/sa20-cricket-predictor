"""ML model registry service."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.ml.models.match_predictor import MatchPredictor

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for managing ML models."""
    
    def __init__(self):
        """Initialize model registry."""
        self.models: Dict[str, any] = {}
        self.model_path = Path(settings.MODEL_PATH)
        if not self.model_path.is_absolute():
            self.model_path = Path(__file__).resolve().parents[4] / self.model_path
        self._load_models()
    
    def _load_models(self) -> None:
        """Load all available models."""
        try:
            # Load match predictor
            match_model_path = self.model_path / "match_predictor.pkl"
            match_features_path = self.model_path / "match_predictor_features.json"
            
            if match_model_path.exists() and match_features_path.exists():
                match_predictor = MatchPredictor()
                match_predictor.load_artifacts(match_model_path, match_features_path)
                self.models["match_predictor"] = match_predictor
                logger.info("Match predictor model loaded")
            else:
                logger.warning("Match predictor model not found")
        
        except Exception as e:
            logger.error(f"Error loading models: {e}", exc_info=True)
    
    def get_model(self, model_name: str) -> Optional[any]:
        """Get a model by name.
        
        Args:
            model_name: Model name
            
        Returns:
            Model instance or None
        """
        return self.models.get(model_name)
    
    def register_model(self, model_name: str, model: any) -> None:
        """Register a model.
        
        Args:
            model_name: Model name
            model: Model instance
        """
        self.models[model_name] = model
        logger.info(f"Registered model: {model_name}")
    
    def list_models(self) -> List[str]:
        """List all registered models.
        
        Returns:
            List of model names
        """
        return list(self.models.keys())
    
    def reload_model(self, model_name: str) -> bool:
        """Reload a model from disk.
        
        Args:
            model_name: Model name
            
        Returns:
            True if reloaded successfully, False otherwise
        """
        try:
            if model_name == "match_predictor":
                match_model_path = self.model_path / "match_predictor.pkl"
                match_features_path = self.model_path / "match_predictor_features.json"
                
                if match_model_path.exists() and match_features_path.exists():
                    match_predictor = MatchPredictor()
                    match_predictor.load_artifacts(match_model_path, match_features_path)
                    self.models["match_predictor"] = match_predictor
                    logger.info(f"Reloaded model: {model_name}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error reloading model {model_name}: {e}", exc_info=True)
            return False

