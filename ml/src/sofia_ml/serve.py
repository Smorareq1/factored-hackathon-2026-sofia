"""Router HTTP service (§9.3). The agent calls it through ROUTER_URL.

`POST /predict` follows `sofia_contracts.router`: {text, language_hint?} -> IntentPrediction.
Serves the hybrid router (`sofia_ml.router`): keyword rules first, the model trained at startup for the rest.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sofia_contracts.router import IntentPrediction, RouterRequest
from sofia_ml.router import RECOMMENDED_CONFIDENCE_THRESHOLD, HybridRouter

router = HybridRouter.from_corpus()

app = FastAPI(title="S.O.F.I.A. — intent router", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("CORS_ORIGINS", "").split(",") if o],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str | float]:
    return {
        "status": "ok",
        "service": "router",
        "router_version": router.version,
        "recommended_confidence_threshold": RECOMMENDED_CONFIDENCE_THRESHOLD,
    }


@app.post("/predict", response_model=IntentPrediction)
def predict(request: RouterRequest) -> IntentPrediction:
    return router.predict(request.text, request.language_hint)
