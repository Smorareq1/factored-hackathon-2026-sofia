"""Servicio HTTP del router (§9.3). El agente lo consume vía ROUTER_URL.

`POST /predict` cumple `sofia_contracts.router`: {text, language_hint?} -> IntentPrediction.
v0 sirve las reglas (`baseline_rules`); cuando exista un modelo en MODEL_DIR se carga aquí sin cambiar el contrato.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sofia_contracts.router import IntentPrediction, RouterRequest
from sofia_ml.baseline_rules import RULES_ROUTER_VERSION, predict_rules

app = FastAPI(title="S.O.F.I.A. — router de intención", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("CORS_ORIGINS", "").split(",") if o],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "router", "router_version": RULES_ROUTER_VERSION}


@app.post("/predict", response_model=IntentPrediction)
def predict(request: RouterRequest) -> IntentPrediction:
    return predict_rules(request.text, request.language_hint)
