"""Log de auditoría de cada decisión y acción bancaria (REQ-16, REQ-19)."""

from sofia_services.audit.logger import AuditRecord, AuditTrail, audit_trail

__all__ = ["AuditRecord", "AuditTrail", "audit_trail"]
