"""
Dual-layer Raster and Vector Exporter for Universal Kriging outputs.
Generates GeoTIFF (Prediction & Variance bands) and GeoJSON for GIS integration.
"""

import json
import os
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import tifffile

from .universal_kriging import KrigingResult


class GeostatisticalRasterExporter:
    """
    Exports Universal Kriging outputs to:
      1. Dual-band or individual GeoTIFF rasters (Prediction & Kriging Estimation Variance)
      2. GeoJSON FeatureCollection with 10m grid cells
    """

    def __init__(self, crs_epsg: int = 32645):
        # Default EPSG 32645: WGS 84 / UTM Zone 45N (covers Jharia / Raniganj coalfields)
        self.crs_epsg = crs_epsg

    def export_geotiff(
        self,
        result: KrigingResult,
        output_filepath: str,
        export_variance: bool = True,
    ) -> str:
        """
        Exports kriging result to a GeoTIFF raster using tifffile with geotags.
        If export_variance is True, outputs a 2-band float32 GeoTIFF:
          Band 1: Predicted deformation (mm)
          Band 2: Estimation variance σ²_K (mm²)
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

        xmin, xmax, ymin, ymax = result.bounds_extent
        res_m = result.grid_resolution_m

        # Dimensions: result.predicted_field is (nY, nX)
        # Note: In standard GeoTIFF, row 0 corresponds to ymax (top-left origin),
        # so we flip vertically to align north-up
        pred_flip = np.flipud(result.predicted_field).astype(np.float32)
        var_flip = np.flipud(result.variance_field).astype(np.float32)

        if export_variance:
            # 2 bands: [Bands, Height, Width]
            raster_data = np.stack([pred_flip, var_flip], axis=0)
        else:
            raster_data = pred_flip

        # Construct GeoTIFF tags:
        # Tag 33550: ModelPixelScaleTag = (ScaleX, ScaleY, ScaleZ)
        # Tag 33922: ModelTiepointTag = (I, J, K, X, Y, Z)
        # Tag 34735: GeoKeyDirectoryTag
        pixel_scale = (float(res_m), float(res_m), 0.0)
        tie_point = (0.0, 0.0, 0.0, float(xmin), float(ymax), 0.0)
        
        # Standard GeoKeyDirectory: Projected CRS
        geokey_directory = (
            1, 1, 0, 4,         # Header: KeyDirectoryVersion, KeyRevision, MinorRevision, NumberOfKeys
            1024, 0, 1, 1,      # GTModelTypeGeoKey: ModelTypeProjected (1)
            1025, 0, 1, 1,      # GTRasterTypeGeoKey: RasterPixelIsArea (1)
            3072, 0, 1, self.crs_epsg, # ProjectedCSTypeGeoKey: EPSG code
        )

        extratags = [
            (33550, "d", 3, pixel_scale, False),
            (33922, "d", 6, tie_point, False),
            (34735, "H", len(geokey_directory), geokey_directory, False),
        ]

        tifffile.imwrite(
            output_filepath,
            raster_data,
            photometric="minisblack",
            extratags=extratags,
        )
        return output_filepath

    def export_geojson(
        self,
        result: KrigingResult,
        output_filepath: str,
        stride: int = 1,
    ) -> str:
        """
        Exports kriging grid to a GeoJSON FeatureCollection of 10m cells.
        Includes predicted subsidence, estimation variance, and confidence flag.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

        features = []
        res_m = result.grid_resolution_m
        half = res_m * 0.5

        y_indices = range(0, len(result.y_grid), stride)
        x_indices = range(0, len(result.x_grid), stride)

        for j in y_indices:
            y = float(result.y_grid[j])
            for i in x_indices:
                x = float(result.x_grid[i])
                pred_val = float(result.predicted_field[j, i])
                var_val = float(result.variance_field[j, i])
                std_val = float(result.std_dev_field[j, i])

                # Confidence: High if variance is low relative to measurement scale
                conf_score = float(1.0 / (1.0 + (std_val / 5.0)))

                # Polygon vertices for cell: [SW, SE, NE, NW, SW]
                coords = [
                    [x - half, y - half],
                    [x + half, y - half],
                    [x + half, y + half],
                    [x - half, y + half],
                    [x - half, y - half],
                ]

                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords],
                    },
                    "properties": {
                        "easting_m": x,
                        "northing_m": y,
                        "predicted_subsidence_mm": round(pred_val, 3),
                        "estimation_variance_mm2": round(var_val, 4),
                        "estimation_std_mm": round(std_val, 3),
                        "confidence_score": round(conf_score, 3),
                        "is_high_uncertainty": bool(std_val > 5.0),
                    },
                }
                features.append(feature)

        geojson_obj = {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": f"urn:ogc:def:crs:EPSG::{self.crs_epsg}"},
            },
            "features": features,
        }

        with open(output_filepath, "w", encoding="utf-8") as f:
            json.dump(geojson_obj, f, indent=2)

        return output_filepath
