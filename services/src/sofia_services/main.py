"""App FastAPI de la API bancaria simulada (SIM, §9.2)."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sofia_services.routes import api_router

app = FastAPI(
    title="S.O.F.I.A. — API bancaria simulada",
    description="Servicio bancario determinístico: auth + OTP, permisos, motor de política POL-1..POL-7, auditoría",
    version="0.1.0",
)

cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bank-api"}
