"""Gestor de inyección de fallas controladas para tests y robustez (REQ-15, REQ-16)."""

import logging
from dataclasses import dataclass

from fastapi import HTTPException

logger = logging.getLogger("sofia_services.faults")


@dataclass
class EndpointFault:
    status: int = 500
    times: int = 1


class FaultManager:
    def __init__(self) -> None:
        self.endpoint_faults: dict[str, list[int]] = {}
        self.drop_writes: bool = False

    def inject_http_error(self, method: str, path: str, status: int = 500, times: int = 1) -> None:
        key = f"{method.upper()} {path}"
        self.endpoint_faults.setdefault(key, []).extend([status] * times)
        logger.warning("Fault injected: %s status=%d times=%d", key, status, times)

    def check_endpoint(self, method: str, path: str) -> None:
        """Verifica si hay una falla inyectada para el endpoint dado.

        Soporta match exacto ("GET /transactions/TX123") y match parametrizado ("GET /transactions/{id}").
        """
        method_upper = method.upper()
        candidates = [f"{method_upper} {path}"]
        # Si path tiene ID como /transactions/TX123 o /disputes/DSP123 o /handoffs/HO123
        parts = path.strip("/").split("/")
        if len(parts) == 2:
            candidates.append(f"{method_upper} /{parts[0]}/{{id}}")

        for key in candidates:
            queue = self.endpoint_faults.get(key)
            if queue:
                status_code = queue.pop(0)
                logger.warning("Triggering injected fault: %s -> HTTP %d", key, status_code)
                raise HTTPException(status_code=status_code, detail="fault_injected")

    def set_drop_writes(self, enabled: bool = True) -> None:
        self.drop_writes = enabled
        logger.warning("Fault drop_writes set to %s", enabled)

    def reset(self) -> None:
        self.endpoint_faults.clear()
        self.drop_writes = False
        logger.info("Faults reset")


fault_manager = FaultManager()
