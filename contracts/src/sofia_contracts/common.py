"""Tipos compartidos por todos los contratos (idioma, país, moneda, rutas, reglas de política)."""

from typing import Literal

Language = Literal["es", "pt"]
Country = Literal["MX", "CO", "AR"]
Currency = Literal["MXN", "COP", "ARS", "USD"]

# Ruta final de un turno o de un caso. El harness compara `route_final` contra `expected_route` (§9.5)
# sin traducciones (propuesta AG #7 para el D1).
Route = Literal["auto", "clarify", "abstain", "escalate", "deny", "reauth"]

# Ruta que devuelve el motor de política de SIM en `POST /disputes/eligibility` (§9.2).
PolicyRoute = Literal["auto", "human", "deny"]

# Reglas de la política sintética del equipo (§8.3, CON-02).
RuleId = Literal["POL-1", "POL-2", "POL-3", "POL-4", "POL-5", "POL-6", "POL-7"]

SystemVersion = Literal["proposed", "baseline"]
