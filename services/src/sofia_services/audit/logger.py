"""Log de auditoría estructurado para decisiones bancarias y acciones (REQ-16, REQ-19)."""

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("sofia_services.audit")


@dataclass
class AuditRecord:
    event: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    customer_id: str | None = None
    rule_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class AuditTrail:
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def record(
        self,
        event: str,
        *,
        customer_id: str | None = None,
        rule_id: str | None = None,
        **details: Any,
    ) -> AuditRecord:
        record = AuditRecord(event=event, customer_id=customer_id, rule_id=rule_id, details=details)
        self._records.append(record)
        logger.info(
            "AUDIT event=%s customer=%s rule=%s details=%s",
            event,
            customer_id,
            rule_id,
            details,
        )
        return record

    def list_records(self, customer_id: str | None = None) -> list[AuditRecord]:
        if customer_id:
            return [r for r in self._records if r.customer_id == customer_id]
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


audit_trail = AuditTrail()
