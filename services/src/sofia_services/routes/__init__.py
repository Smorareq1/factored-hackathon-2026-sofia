"""Endpoints de §9.2: session, transactions, disputes, handoff, admin."""

from fastapi import APIRouter

from sofia_services.routes.admin import router as admin_router
from sofia_services.routes.disputes import router as disputes_router
from sofia_services.routes.handoff import router as handoff_router
from sofia_services.routes.session import router as session_router
from sofia_services.routes.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(session_router)
api_router.include_router(transactions_router)
api_router.include_router(disputes_router)
api_router.include_router(handoff_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
