from fastapi import APIRouter, Response, Query
from io import BytesIO
from PIL import Image

from src.digital_twin.dem_draper import DEMTerrainDraper
from src.digital_twin.subsurface_mesh import SubsurfaceMeshBuilder
from src.digital_twin.vertical_exaggeration import VerticalExaggerationEngine
from src.digital_twin.dgms_exporter import DGMSReportExporter
from src.normalizer.cad_parser import CADMineParser

router = APIRouter(prefix="/api/v1/twin", tags=["3D Subsurface Digital Twin (5.3)"])

dem_draper = DEMTerrainDraper()
subsurface_builder = SubsurfaceMeshBuilder()
cad_parser = CADMineParser()

@router.get("/{tenant_id}/{site_id}/scene")
async def get_digital_twin_scene(
    tenant_id: str,
    site_id: str,
    vertical_exaggeration: float = Query(25.0, ge=10.0, le=50.0),
    include_subsurface_cad: bool = True
):
    """
    Returns 3D Digital Twin scene manifest containing surface DEM heightfield,
    translucent volumetric underground workings, and DGMS scale ruler specification.
    """
    # 500m x 500m concession bounds around Jharia
    bounds_utm = (442000.0, 2631500.0, 442600.0, 2632100.0)
    dem_mesh = dem_draper.generate_surface_dem_mesh(bounds_utm, grid_resolution_m=40.0)

    cad_layout = None
    if include_subsurface_cad:
        cad_layout = cad_parser.generate_synthetic_bord_and_pillar_layout(
            center_utm=(442300.0, 2631800.0),
            seam_depth_m=180.0
        )

    manifest = subsurface_builder.build_scene_manifest(
        site_id=site_id,
        cad_layout=cad_layout,
        dem_mesh=dem_mesh,
        vertical_exaggeration=vertical_exaggeration
    )
    manifest["tenant_id"] = tenant_id
    manifest["scale_ruler_spec"] = VerticalExaggerationEngine.generate_scale_ruler_spec(vertical_exaggeration)
    return manifest

@router.get("/{tenant_id}/{site_id}/cross-section")
async def get_stratigraphic_cross_section(
    tenant_id: str,
    site_id: str,
    x1: float = 442100.0,
    y1: float = 2631500.0,
    x2: float = 442600.0,
    y2: float = 2632000.0,
    vertical_exaggeration: float = 25.0
):
    """
    Computes 2D vertical stratigraphic cross-section cutting through surface terrain,
    overburden strata, and extraction seam along survey line (x1,y1) -> (x2,y2).
    """
    from src.digital_twin.cross_section import StratigraphicCrossSectionEngine
    return StratigraphicCrossSectionEngine.compute_vertical_cross_section(
        start_point_utm=(x1, y1),
        end_point_utm=(x2, y2),
        vertical_exaggeration=vertical_exaggeration
    )


@router.get("/{tenant_id}/{site_id}/export-dgms-report")
async def export_dgms_report_snapshot(
    tenant_id: str,
    site_id: str,
    vertical_exaggeration: float = 25.0
):
    """
    Generates high-resolution static rendering snapshot for statutory DGMS inspection reports.
    """
    # Create sample high-res snapshot
    map_canvas = Image.new("RGBA", (1280, 720), (30, 41, 59, 255))
    report_img = DGMSReportExporter.compile_audit_report_image(
        map_image=map_canvas,
        site_id=site_id,
        site_name="Jharia Coalfield Concession Block 7",
        vertical_exaggeration=vertical_exaggeration,
        active_zones=[{"zone_id": f"ZONE-{site_id}-C", "severity": "warning"}]
    )

    bio = BytesIO()
    report_img.save(bio, format="PNG", optimize=True)
    return Response(
        content=bio.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=DGMS_Report_{site_id}.png"}
    )
