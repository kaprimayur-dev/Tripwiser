from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.health import router as health_router
from app.api.v1.routes import router as routes_router
from app.api.v1.stations import router as stations_router
from app.api.v1.bachelor import router as bachelor_router
from app.api.v1.trains import router as trains_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(routes_router, prefix="/api/v1")
app.include_router(stations_router, prefix="/api/v1")
app.include_router(bachelor_router, prefix="/api/v1")
app.include_router(trains_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs"
    }
