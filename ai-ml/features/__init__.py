"""
SubSense Layer 4 Feature Engineering Pipeline Package.
Computes 12-dimensional engineered feature vectors with RobustScaler normalization.
"""

from .constants import FEATURE_VECTOR_DIM, FEATURE_NAMES, SENSOR_ATTRIBUTION_MAPPING
from .geometry_loader import MineGeometryLoader, haversine_distance_m
from .pipeline import FeaturePipeline

__all__ = [
    "FEATURE_VECTOR_DIM",
    "FEATURE_NAMES",
    "SENSOR_ATTRIBUTION_MAPPING",
    "MineGeometryLoader",
    "haversine_distance_m",
    "FeaturePipeline",
]
