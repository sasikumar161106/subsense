import numpy as np
from typing import Tuple, Dict, Any, List, Optional
from src.normalizer.crs_normalizer import SpatialDataNormalizer

class DEMTerrainDraper:
    """
    SubSense DEM Surface Terrain Draper (Section 5.3).
    Drapes the live deformation heatmap raster onto the 1m-5m Digital Elevation Model (DEM),
    generating 3D terrain heightfields and textured mesh geometry for CesiumJS.
    """
    def __init__(self, normalizer: Optional[SpatialDataNormalizer] = None):
        self.normalizer = normalizer or SpatialDataNormalizer()

    def generate_surface_dem_mesh(
        self,
        bounds_utm: Tuple[float, float, float, float],  # (min_x, min_y, max_x, max_y)
        grid_resolution_m: float = 20.0,
        base_elevation_m: float = 220.0,
        synthetic_hilliness: float = 12.0
    ) -> Dict[str, Any]:
        """
        Creates regular grid DEM mesh in UTM with terrain undulation.
        Returns vertex positions [X, Y, Z], texture coordinates [u, v], and triangle indices.
        """
        min_x, min_y, max_x, max_y = bounds_utm
        nx = int(np.ceil((max_x - min_x) / grid_resolution_m)) + 1
        ny = int(np.ceil((max_y - min_y) / grid_resolution_m)) + 1

        xs = np.linspace(min_x, max_x, nx)
        ys = np.linspace(min_y, max_y, ny)
        X, Y = np.meshgrid(xs, ys)

        # Gentle natural terrain undulation + mining ridge profile
        Z = base_elevation_m + synthetic_hilliness * (
            np.sin((X - min_x) / 300.0) * np.cos((Y - min_y) / 300.0) +
            0.5 * np.sin((X - min_x) / 120.0)
        )

        vertices = []
        tex_coords = []
        wgs84_coords = []

        for j in range(ny):
            for i in range(nx):
                x_val = float(X[j, i])
                y_val = float(Y[j, i])
                z_val = float(Z[j, i])
                vertices.append([x_val, y_val, z_val])
                u = (x_val - min_x) / (max_x - min_x)
                v = (y_val - min_y) / (max_y - min_y)
                tex_coords.append([u, v])
                lon, lat = self.normalizer.utm_to_wgs84(x_val, y_val)
                wgs84_coords.append([lon, lat, z_val])

        # Triangle indices (2 triangles per quad)
        indices = []
        for j in range(ny - 1):
            for i in range(nx - 1):
                idx0 = j * nx + i
                idx1 = j * nx + (i + 1)
                idx2 = (j + 1) * nx + (i + 1)
                idx3 = (j + 1) * nx + i
                # Triangle 1
                indices.extend([idx0, idx1, idx2])
                # Triangle 2
                indices.extend([idx0, idx2, idx3])

        return {
            "nx": nx,
            "ny": ny,
            "vertex_count": len(vertices),
            "triangle_count": len(indices) // 3,
            "bounds_utm": bounds_utm,
            "elevation_min_m": float(np.min(Z)),
            "elevation_max_m": float(np.max(Z)),
            "vertices_utm": vertices,
            "vertices_wgs84": wgs84_coords,
            "tex_coords": tex_coords,
            "indices": indices
        }
