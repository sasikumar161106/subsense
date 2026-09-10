from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.api.router_inference import router as router_inference
from src.api.router_kriging import router as router_kriging
from src.api.router_insar import router as router_insar
from src.api.router_feedback import router as router_feedback

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    print("[SubSense Layer 4] AI/ML Data Inference Layer initialized and ready.")
    yield
    # Shutdown cleanup
    print("[SubSense Layer 4] AI/ML Data Inference Layer shutting down.")

app = FastAPI(
    title="SubSense AI/ML Data Inference Layer (Layer 4)",
    description=(
        "Cloud-side analytical intelligence pipeline for the SubSense real-time underground mine "
        "subsidence monitoring platform. Performs unsupervised anomaly detection, GNN spatial correlation, "
        "LSTM progression forecasting, Ordinary Kriging continuous risk surface generation, InSAR fusion, "
        "and automated false-alarm retraining."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for cross-layer dashboard and microservices integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(router_inference)
app.include_router(router_kriging)
app.include_router(router_insar)
app.include_router(router_feedback)

@app.get("/")
async def root():
    return {
        "service": "SubSense AI/ML Data Inference Layer (Layer 4)",
        "status": "online",
        "docs": "/docs",
        "endpoints": [
            "/api/v1/inference/run",
            "/api/v1/inference/health",
            "/api/v1/kriging/surface",
            "/api/v1/insar/cross-validate",
            "/api/v1/feedback/submit",
            "/api/v1/feedback/retrain/trigger",
            "/api/v1/feedback/models/registry",
        ]
    }
