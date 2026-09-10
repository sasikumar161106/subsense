from typing import List, Dict, Tuple, Optional
import numpy as np
from datetime import datetime
from src.schemas.insar_contracts import InSARLocation, InSARDiscrepancyMarker, InSAROverlayPayload

class InSARCrossValidator:
    """
    Sentinel-1 InSAR Satellite Macro-Cross Validation Engine (Section 2, 7, 11).
    Fuses periodic coarse-resolution satellite interferometry with real-time ground sensors
    to provide an independent macro-scale sanity check and discover unmonitored subsidence basins.
    """

    def __init__(
        self,
        velocity_discrepancy_threshold_mm_year: float = 15.0,
        unmonitored_threshold_mm_year: float = -18.0,
    ):
        self.velocity_discrepancy_threshold = velocity_discrepancy_threshold_mm_year
        self.unmonitored_threshold = unmonitored_threshold_mm_year

    def cross_validate(
        self,
        site_id: str,
        insar_velocity_grid: np.ndarray,  # [H, W] in mm/yr
        bounds_utm: Tuple[float, float, float, float],
        ground_mesh_coords: Dict[str, Tuple[float, float]],
        ground_risk_grid: np.ndarray,     # [H, W] in [0, 1]
        pass_date: str = "2026-09-08",
    ) -> InSAROverlayPayload:
        """
        Cross-validates satellite LOS velocity against ground sensor risk estimates.
        Returns InSAROverlayPayload with identified discrepancy markers.
        """
        min_x, min_y, max_x, max_y = bounds_utm
        h, w = insar_velocity_grid.shape
        xs = np.linspace(min_x, max_x, w)
        ys = np.linspace(min_y, max_y, h)

        markers: List[InSARDiscrepancyMarker] = []
        marker_count = 1

        # Mesh bounding polygon check
        mesh_xs = [c[0] for c in ground_mesh_coords.values()]
        mesh_ys = [c[1] for c in ground_mesh_coords.values()]
        if mesh_xs and mesh_ys:
            mesh_min_x, mesh_max_x = min(mesh_xs), max(mesh_xs)
            mesh_min_y, mesh_max_y = min(mesh_ys), max(mesh_ys)
        else:
            mesh_min_x, mesh_max_x = min_x, max_x
            mesh_min_y, mesh_max_y = min_y, max_y

        # Scan grid for anomalies
        step = max(1, h // 5)
        for r in range(0, h, step):
            for c in range(0, w, step):
                vel = float(insar_velocity_grid[r, c])
                pt_x = float(xs[c])
                pt_y = float(ys[r])

                # Approximate UTM to WGS84 for Jharia (EPSG:32645)
                # lon ≈ 86.4335 + (pt_x - 442450) * 0.00001
                # lat ≈ 23.7915 + (pt_y - 2631700) * 0.000009
                lat = 23.7915 + (pt_y - 2631700.0) * 0.000009
                lon = 86.4335 + (pt_x - 442450.0) * 0.000010

                # Check 1: Satellite detects subsidence outside ground mesh boundary
                is_outside_mesh = (pt_x < mesh_min_x - 50.0 or pt_x > mesh_max_x + 50.0 or
                                   pt_y < mesh_min_y - 50.0 or pt_y > mesh_max_y + 50.0)

                if is_outside_mesh and vel < self.unmonitored_threshold:
                    markers.append(
                        InSARDiscrepancyMarker(
                            annotation_id=f"INSAR-DISC-{site_id}-{marker_count:03d}",
                            site_id=site_id,
                            location=InSARLocation(lat=float(round(lat, 5)), lon=float(round(lon, 5))),
                            insar_acquisition_date=pass_date,
                            discrepancy_type="satellite_motion_unmonitored_by_ground_mesh",
                            los_velocity_mm_year=float(round(vel, 1)),
                            description=f"Sentinel-1 detects subsidence basin ({vel:.1f} mm/yr) outside active ground mesh perimeter.",
                            recommended_action="Deploy supplementary wireless ground mesh nodes or extend geotechnical borehole survey.",
                        )
                    )
                    marker_count += 1

                # Check 2: High ground sensor risk with zero satellite movement
                elif not is_outside_mesh:
                    ground_risk = float(ground_risk_grid[r, c])
                    if ground_risk > 0.75 and abs(vel) < 3.0:
                        markers.append(
                            InSARDiscrepancyMarker(
                                annotation_id=f"INSAR-DISC-{site_id}-{marker_count:03d}",
                                site_id=site_id,
                                location=InSARLocation(lat=float(round(lat, 5)), lon=float(round(lon, 5))),
                                insar_acquisition_date=pass_date,
                                discrepancy_type="sensor_satellite_velocity_mismatch",
                                los_velocity_mm_year=float(round(vel, 1)),
                                description=f"Ground mesh indicates elevated strain ({ground_risk:.2f}) but Sentinel-1 LOS velocity is neutral ({vel:.1f} mm/yr).",
                                recommended_action="Cross-check against atmospheric noise or verify underground void depth attenuating surface velocity.",
                            )
                        )
                        marker_count += 1

        hatched_geojson = {
            "type": "Feature",
            "properties": {"pass_date": pass_date, "satellite": "Sentinel-1A"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [86.430, 23.788],
                    [86.440, 23.788],
                    [86.440, 23.796],
                    [86.430, 23.796],
                    [86.430, 23.788],
                ]]
            }
        }

        return InSAROverlayPayload(
            site_id=site_id,
            pass_date=pass_date,
            satellite_mission="Sentinel-1A",
            markers=markers,
            hatched_polygon_geojson=hatched_geojson,
        )
