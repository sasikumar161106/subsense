from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config.settings import settings
from src.api.router_tiles import router as tiles_router
from src.api.router_zones import router as zones_router
from src.api.router_insar import router as insar_router
from src.api.router_digital_twin import router as twin_router
from src.api.router_replay import router as replay_router
from src.api.router_stream import router as stream_router
from src.api.router_raster import router as raster_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="SubSense Layer 5: Spatial & GIS Rendering Stack (SUBSENSE-TDD-GIS-005 Rev 2.1). "
                "Delivers real-time 2D deformation heatmaps, risk-zone contour tracking, "
                "3D subsurface digital twins, Sentinel-1 InSAR overlays, and What-If subsidence simulations."
)

# CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Site-ID", "X-Layer", "X-Tile-Z", "X-Tile-X", "X-Tile-Y",
        "X-Data-Currency-Seconds", "X-Is-Stale", "X-Kriging-Variance-Included"
    ]
)

# Mount API Routers
app.include_router(tiles_router)
app.include_router(zones_router)
app.include_router(insar_router)
app.include_router(twin_router)
app.include_router(replay_router)
app.include_router(stream_router)
app.include_router(raster_router)


# Mount web frontend static directory if exists
web_dir = Path(__file__).resolve().parent.parent.parent / "web"
if web_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(web_dir), html=True), name="web_dashboard")

@app.get("/health", tags=["Health & Status"])
async def healthcheck():
    return {
        "status": "HEALTHY",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "compliance": "DGMS Geotechnical GIS Guidelines",
        "environment": settings.ENVIRONMENT
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8001, reload=True)
