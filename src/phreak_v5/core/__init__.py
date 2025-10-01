"""Core layer of the PHREAK v5 architecture."""
from .connection import ConnectionMatrix, LoopbackConnector
from .logging import AuditLoggingKernel
from .policy import PolicyEngine
from .router import CommandRouter
from .vault import SecurityVault

__all__ = [
    "ConnectionMatrix",
    "LoopbackConnector",
    "AuditLoggingKernel",
    "PolicyEngine",
    "CommandRouter",
    "SecurityVault",
]
