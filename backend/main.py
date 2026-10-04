from fastapi import FastAPI
from backend.api.regions import router as regions_router
from backend.api.routes import router as api_router

app = FastAPI(title="SatRelief-Route API")
app.include_router(api_router)
app.include_router(regions_router)
