"""GOLDSETU FastAPI process. Index migrations run explicitly, never at startup."""
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.db.connection import open_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    client, database = open_database()
    await client.admin.command("ping")
    app.state.mongo_client = client
    app.state.database = database
    try:
        yield
    finally:
        await client.close()


app = FastAPI(title="GOLDSETU API", version="1.0.0", openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs", lifespan=lifespan)
origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001,capacitor://localhost").split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Device-ID"])
app.include_router(router)


@app.get("/health/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
async def ready() -> dict[str, str]:
    # Startup pings Atlas; full readiness checks can be extended with dependency health.
    return {"status": "ready"}
