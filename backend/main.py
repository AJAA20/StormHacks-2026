from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from backend.api.regions import router as regions_router
from backend.api.routes import router as api_router
from backend.api.ws import router as ws_router
from backend.simulation.scheduler import start_background_scheduler

app = FastAPI(title="SatRelief-Route API")
app.include_router(api_router)
app.include_router(regions_router)
app.include_router(ws_router)


@app.on_event("startup")
def _on_startup() -> None:
    start_background_scheduler()
