"""
analise_fila.py — Aliases de compatibilidade para o serviço de fila.
A implementação real está em match_queue_service.py.
"""
from services.match_queue_service import match_queue_service, MatchQueueService

# Aliases usados por outros módulos que importam deste arquivo
queue_analysis_service = match_queue_service
analise_fila_service   = match_queue_service
