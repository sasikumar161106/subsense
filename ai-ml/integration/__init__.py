"""
SubSense Downstream Integration Layer.
Wires AI/ML scoring and geostatistics outputs downstream to:
1. Alert_System (Rule Engine, Siren Dispatch, DGMS Ledger)
2. GIS Layer (2D Slippy Tile Rendering, 3D Digital Twin)
"""

from .alert_dispatcher import (
    to_alert_system_contract,
    dispatch_to_alert_system,
    to_gis_raster_contract,
    dispatch_to_gis,
)

__all__ = [
    "to_alert_system_contract",
    "dispatch_to_alert_system",
    "to_gis_raster_contract",
    "dispatch_to_gis",
]
