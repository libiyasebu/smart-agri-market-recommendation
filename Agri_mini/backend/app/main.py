from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes.prediction import router as prediction_router
from app.api.routes.transport import router as transport_router
from app.api.routes.spoilage import router as spoilage_router
from app.api.routes.profit import router as profit_router
from app.api.routes.recommendation import router as recommendation_router
from app.api.routes.ceda_prediction import router as ceda_prediction_router
from app.api.routes.ceda_recommendation import router as ceda_recommendation_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API for AI-Based Agricultural Price Prediction, Transport Cost Optimization, Spoilage Risk Estimation, and TOPSIS Market Recommendation.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration to enable communication with the web dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Register API routers
app.include_router(prediction_router)
app.include_router(transport_router)
app.include_router(spoilage_router)
app.include_router(profit_router)
app.include_router(recommendation_router)
app.include_router(ceda_prediction_router)
app.include_router(ceda_recommendation_router)

# Mount Frontend Dashboard
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(frontend_dir), html=True), name="dashboard")


@app.get("/", tags=["General"])
def read_root():
    """Root endpoint providing system status and documentation links."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "health_check": "/health",
        "dashboard": "/dashboard",
        "endpoints": {
            "price_prediction": "/api/v1/predict/price",
            "transport_estimation": "/api/v1/transport/estimate",
            "spoilage_estimation": "/api/v1/spoilage/estimate",
            "profit_evaluation": "/api/v1/profit/evaluate",
            "market_recommendation": "/api/v1/recommend/markets",
        },
    }


@app.get("/health", tags=["Monitoring"])
def health_check():
    """Health check endpoint to verify backend service availability."""
    return {
        "status": "healthy",
        "service": "agri-price-transport-optimization-api",
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/system/info", tags=["Monitoring"])
def get_system_info():
    """Returns runtime system information, active ML model specs, and enabled modules."""
    return {
        "project_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_version": "v1",
        "production_model": "Random Forest (Tuned)",
        "feature_count": 54,
        "target_variable": "modal_price (INR/quintal)",
        "modules": [
            "Market Price Prediction (Random Forest)",
            "Logistics & Freight Costing (OSRM Engine)",
            "Agro-Meteorological Spoilage Risk (Open-Meteo)",
            "Expected Profit & Net Return Evaluation",
            "Multi-Market Recommendation (TOPSIS Decision Solver)",
        ],
        "database": "PostgreSQL (agri_mini_db)",
        "status": "operational",
    }

