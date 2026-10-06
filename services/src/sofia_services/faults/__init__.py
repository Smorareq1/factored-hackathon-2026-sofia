"""Inyección controlada de fallas (latencia, 500, drop_writes) para probar reintentos y fallback."""

from sofia_services.faults.manager import FaultManager, fault_manager

__all__ = ["FaultManager", "fault_manager"]
