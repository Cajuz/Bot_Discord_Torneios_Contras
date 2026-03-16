"""
permission_service.py — Mantido para compatibilidade de imports.
A lógica real agora está em services/channel_service.py.
"""
from services.channel_service import permission_service, PermissionService

__all__ = ["permission_service", "PermissionService"]