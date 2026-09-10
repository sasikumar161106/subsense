from typing import List
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid

class PolygonSmoother:
    """
    SubSense Polygon Smoothing & Topology Filter (Section 5.2 & Section 9).
    Applies:
      1. Morphological closing filter (dilation followed by erosion) to smooth erratic necks.
      2. Strict minimum area cutoff (>= 250 m²) to suppress sensor noise micro-islands.
      3. Visvalingam-Whyatt / Douglas-Peucker simplification (preserves topology, reduces vertex count).
      4. GEOS topological validity verification (zero self-intersections).
    """
    @classmethod
    def filter_and_smooth(
        cls,
        polygons: List[Polygon],
        min_area_sq_m: float = 250.0,
        simplify_tolerance_m: float = 1.5,
        morph_close_dist_m: float = 3.0
    ) -> List[Polygon]:
        cleaned_polygons: List[Polygon] = []

        for raw_poly in polygons:
            if raw_poly.is_empty:
                continue

            # Ensure validity first
            valid_p = make_valid(raw_poly)
            sub_polys = []
            if isinstance(valid_p, Polygon):
                sub_polys = [valid_p]
            elif isinstance(valid_p, MultiPolygon):
                sub_polys = [p for p in valid_p.geoms if not p.is_empty]

            for p in sub_polys:
                # 1. Morphological closing filter (buffer out then in)
                if morph_close_dist_m > 0:
                    try:
                        closed_p = p.buffer(morph_close_dist_m, join_style='round').buffer(-morph_close_dist_m, join_style='round')
                        if not closed_p.is_empty:
                            p = closed_p
                    except Exception:
                        pass

                # Re-validate geometry
                p = make_valid(p)
                cand_list = [p] if isinstance(p, Polygon) else list(p.geoms)

                for cand in cand_list:
                    # 2. Strict minimum area threshold cutoff (>= 250 m²)
                    if cand.area < min_area_sq_m:
                        continue

                    # 3. Topology-preserving simplification
                    simplified = cand.simplify(simplify_tolerance_m, preserve_topology=True)
                    if simplified.is_empty or simplified.area < min_area_sq_m:
                        continue

                    # 4. Strict topology verification
                    final_p = make_valid(simplified)
                    if isinstance(final_p, Polygon) and final_p.is_valid:
                        cleaned_polygons.append(final_p)
                    elif isinstance(final_p, MultiPolygon):
                        for fp in final_p.geoms:
                            if fp.area >= min_area_sq_m and fp.is_valid:
                                cleaned_polygons.append(fp)

        return cleaned_polygons
