"""
pedido_mediador_service.py

Gerencia o ciclo de vida de contratos de mediadores:
  - Plano semanal com valor lido do .env (MEDIATOR_WEEKLY_PRICE)
  - EfiPay OPCIONAL: se credenciais não estiverem configuradas,
    gera cobrança manual (admin confirma manualmente)
  - Cargo 'Mediador' atribuído automaticamente após pagamento confirmado
  - Log automático em #logs-pagamentos a cada evento de pagamento

NOTA: O fluxo de seleção/pedido de mediador é externo ao servidor.
      Este serviço cuida apenas do cadastro e gestão de contratos.
"""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Optional, TYPE_CHECKING

import discord

from config.database import db
from utils.datetime_utils import utcnow
from utils.logger import logger, log_success
from services.channel_service import (
    LOGS_PAGAMENTOS_CHANNEL,
    MEDIADOR_ROLE_NAME,
    ADM_ROLE_NAME,
    CONTROLLER_ROLE_NAME,
)

if TYPE_CHECKING:
    pass

# ── Configuração via ENV ─────────────────────────────────────────────────
def _get_weekly_price() -> float:
    """Lê o valor do plano semanal da ENV. Fallback: 50.00 se não configurado."""
    raw = os.getenv("MEDIATOR_WEEKLY_PRICE", "50.00")
    try:
        return float(raw)
    except ValueError:
        logger.warning(
            f"[MediadorService] MEDIATOR_WEEKLY_PRICE inválido ('{raw}') — usando R$50,00"
        )
        return 50.00


PLAN_DAYS    = 7          # plano semanal fixo
PLAN_LABEL   = "Semanal"  # label amigável


def _efi_available() -> bool:
    """Retorna True se as credenciais EfiPay estão configuradas no .env."""
    return bool(
        os.getenv("EFI_CLIENT_ID")
        and os.getenv("EFI_CLIENT_SECRET")
        and os.getenv("EFI_PIX_KEY")
    )


# ── Helpers de log ────────────────────────────────────────────────────────
async def log_pagamento(
    guild: discord.Guild,
    embed: discord.Embed,
) -> None:
    """
    Posta um embed de log no canal #logs-pagamentos.
    Falha silenciosa: nunca bloqueia o fluxo principal.
    """
    try:
        ch = discord.utils.get(guild.text_channels, name=LOGS_PAGAMENTOS_CHANNEL)
        if ch:
            await ch.send(embed=embed)
        else:
            logger.warning(
                f"[MediadorService] Canal '{LOGS_PAGAMENTOS_CHANNEL}' não encontrado — "
                "execute /setupcanais para criá-lo."
            )
    except Exception as e:
        logger.error(f"[MediadorService] Erro ao logar pagamento: {e}")


def _build_payment_log_embed(
    event: str,
    discord_id: str,
    username: str,
    value: float,
    expiration: str,
    method: str = "manual",
    extra: str = "",
) -> discord.Embed:
    color_map = {
        "contrato":  0x27AE60,   # verde
        "renovacao": 0x3498DB,   # azul
        "expirado":  0xE74C3C,   # vermelho
        "cancelado": 0x95A5A6,   # cinza
    }
    color = color_map.get(event.lower(), 0xFFD54F)
    label_map = {
        "contrato":  "🟢 Novo Contrato",
        "renovacao": "🔄 Renovação",
        "expirado":  "🔴 Contrato Expirado",
        "cancelado": "⚪ Cancelado",
    }
    title = label_map.get(event.lower(), f"💰 Pagamento: {event}")

    embed = discord.Embed(title=title, color=color, timestamp=utcnow())
    embed.add_field(name="Mediador",     value=f"<@{discord_id}> `{username}`", inline=True)
    embed.add_field(name="Valor",        value=f"R$ {value:.2f}",               inline=True)
    embed.add_field(name="Plano",        value=f"{PLAN_LABEL} ({PLAN_DAYS}d)",   inline=True)
    embed.add_field(name="Expira em",    value=expiration,                        inline=True)
    embed.add_field(name="Método",       value=method,                            inline=True)
    if extra:
        embed.add_field(name="Obs", value=extra, inline=False)
    embed.set_footer(text="X1 Frifas · logs-pagamentos")
    return embed


# ── Cargo automático ────────────────────────────────────────────────────────
async def grant_mediador_role(
    guild: discord.Guild,
    discord_id: str | int,
    reason: str = "Pagamento confirmado",
) -> bool:
    """
    Atribui o cargo 'Mediador' ao membro identificado por discord_id.
    
    Chamado automaticamente quando:
      - webhook EfiPay confirma pagamento (status=CONCLUIDA)
      - ADM confirma manualmente via botão no painel

    Retorna True se o cargo foi atribuído com sucesso.
    """
    try:
        member = guild.get_member(int(discord_id))
        if not member:
            try:
                member = await guild.fetch_member(int(discord_id))
            except discord.NotFound:
                logger.warning(
                    f"[MediadorService] grant_mediador_role: membro {discord_id} não encontrado"
                )
                return False

        role = discord.utils.get(guild.roles, name=MEDIADOR_ROLE_NAME)
        if not role:
            logger.error(
                f"[MediadorService] Cargo '{MEDIADOR_ROLE_NAME}' não existe no servidor. "
                "Execute /setupcanais para criá-lo."
            )
            return False

        if role in member.roles:
            logger.info(
                f"[MediadorService] {member.name} já possui o cargo '{MEDIADOR_ROLE_NAME}' — skip"
            )
            return True  # idempotente

        await member.add_roles(role, reason=reason)
        log_success(
            f"[MediadorService] Cargo '{MEDIADOR_ROLE_NAME}' atribuído a {member.name} — {reason}"
        )
        return True

    except discord.Forbidden:
        logger.error(
            f"[MediadorService] Sem permissão para atribuir cargo a {discord_id}"
        )
        return False
    except Exception as e:
        logger.error(f"[MediadorService] grant_mediador_role erro: {e}", exc_info=True)
        return False


async def revoke_mediador_role(
    guild: discord.Guild,
    discord_id: str | int,
    reason: str = "Contrato expirado",
) -> bool:
    """
    Remove o cargo 'Mediador' do membro.
    Chamado quando o contrato expira ou é cancelado.
    """
    try:
        member = guild.get_member(int(discord_id))
        if not member:
            try:
                member = await guild.fetch_member(int(discord_id))
            except discord.NotFound:
                logger.warning(
                    f"[MediadorService] revoke_mediador_role: membro {discord_id} não encontrado"
                )
                return False

        role = discord.utils.get(guild.roles, name=MEDIADOR_ROLE_NAME)
        if not role or role not in member.roles:
            return True  # já removido, idempotente

        await member.remove_roles(role, reason=reason)
        logger.info(
            f"[MediadorService] Cargo '{MEDIADOR_ROLE_NAME}' removido de {member.name} — {reason}"
        )
        return True

    except discord.Forbidden:
        logger.error(f"[MediadorService] Sem permissão para remover cargo de {discord_id}")
        return False
    except Exception as e:
        logger.error(f"[MediadorService] revoke_mediador_role erro: {e}", exc_info=True)
        return False


# ── MediatorManager ──────────────────────────────────────────────────────────
class MediatorManager:
    """
    Gerenciador de contratos de mediadores.

    Compatível com o legado (aceita db como 1º arg) mas agora usa
    db global. O parâmetro `db` é mantido por compatibilidade mas ignorado.
    """

    def __init__(self, _db=None, mediator_role_name=None, benefit_days: int = PLAN_DAYS):
        # Compat legado: primeiro arg podia ser int (benefit_days)
        if isinstance(mediator_role_name, int):
            self.benefit_days = mediator_role_name
        else:
            self.benefit_days = benefit_days

        self.payment_collection = db.get_collection("payment_confirmations")
        self.mediator_collection = db.get_collection("mediators")
        self.renewal_collection  = db.get_collection("mediator_renewals")

    # ── Leitura ───────────────────────────────────────────────────────

    async def get_active_mediators(self) -> list[dict]:
        cursor = self.payment_collection.find({
            "confirmation_date": {"$ne": None},
            "active": True,
        })
        return await cursor.to_list(None)

    def calculate_days_remaining(self, mediator: dict) -> int:
        reference_date = (
            mediator.get("confirmation_date")
            or mediator.get("role_received_date")
        )
        if not reference_date:
            return 0
        from datetime import datetime
        if isinstance(reference_date, str):
            reference_date = datetime.fromisoformat(reference_date)
        elapsed_days   = (utcnow() - reference_date).days
        remaining_days = self.benefit_days - elapsed_days
        return max(remaining_days, 0)

    async def get_mediators_with_days(self) -> list[dict]:
        result = []
        for m in await self.get_active_mediators():
            result.append({
                "username":       m.get("username"),
                "discord_id":     m.get("discord_id"),
                "days_remaining": self.calculate_days_remaining(m),
            })
        return result

    async def count_active_mediators(self) -> int:
        return await self.payment_collection.count_documents({
            "confirmation_date": {"$ne": None},
            "active": True,
        })

    # ── Criação de contrato ─────────────────────────────────────────────

    async def create_contract(
        self,
        discord_id: str,
        username: str,
        guild: Optional[discord.Guild] = None,
        confirmed_by: str = "api",
    ) -> dict:
        """
        Cria ou renova contrato semanal.
        
        - Atribui cargo Mediador automaticamente (se guild fornecido)
        - Loga em #logs-pagamentos
        - EfiPay: apenas se credenciais configuradas; caso contrário, registra como 'manual'
        """
        price      = _get_weekly_price()
        now        = utcnow()
        expires_at = now + timedelta(days=PLAN_DAYS)

        # Verifica se já tem contrato ativo (renovação)
        existing = await self.mediator_collection.find_one({"discord_id": discord_id})
        is_renewal = bool(existing and existing.get("is_active"))
        event_type = "renovacao" if is_renewal else "contrato"

        # Determina método de pagamento
        method = "EfiPay" if _efi_available() else "Manual"

        contract_doc = {
            "discord_id":       discord_id,
            "username":         username,
            "plan":             PLAN_LABEL,
            "plan_days":        PLAN_DAYS,
            "value":            price,
            "is_active":        True,
            "confirmed_by":     confirmed_by,
            "payment_method":   method,
            "confirmation_date": now,
            "expiration_date":  expires_at,
            "updated_at":       now,
        }

        # Upsert na coleção de mediadores
        await self.mediator_collection.update_one(
            {"discord_id": discord_id},
            {"$set": contract_doc},
            upsert=True,
        )

        # Registro na coleção de renovações (histórico)
        renewal_doc = {
            "discord_id":   discord_id,
            "username":     username,
            "value":        price,
            "plan":         PLAN_LABEL,
            "plan_days":    PLAN_DAYS,
            "method":       method,
            "status":       "CONCLUIDA",
            "paid_at":      now,
            "expires_at":   expires_at,
            "confirmed_by": confirmed_by,
        }
        await self.renewal_collection.insert_one(renewal_doc)

        # — Atribuir cargo Mediador automaticamente —
        if guild:
            role_ok = await grant_mediador_role(
                guild, discord_id,
                reason=f"Pagamento confirmado ({method}) — {event_type}"
            )
            if not role_ok:
                logger.warning(
                    f"[MediadorService] create_contract: cargo não atribuído a {discord_id}"
                )

        # — Log em #logs-pagamentos —
        if guild:
            log_embed = _build_payment_log_embed(
                event=event_type,
                discord_id=discord_id,
                username=username,
                value=price,
                expiration=expires_at.strftime("%d/%m/%Y %H:%M UTC"),
                method=method,
                extra=f"Confirmado por: {confirmed_by}",
            )
            await log_pagamento(guild, log_embed)

        log_success(
            f"[MediadorService] Contrato {event_type} — {username} ({discord_id}) — "
            f"R${price:.2f} — expira {expires_at.strftime('%d/%m/%Y')}"
        )
        return contract_doc

    # ── Expiração de contratos ─────────────────────────────────────────────

    async def expire_mediators(
        self,
        guild: Optional[discord.Guild] = None,
    ) -> list[str]:
        """
        Marca contratos expirados como inativos e revoga o cargo Mediador.
        Retorna lista de discord_ids processados.
        """
        expired_ids = []
        for mediator in await self.get_active_mediators():
            if self.calculate_days_remaining(mediator) <= 0:
                discord_id = mediator.get("discord_id")
                username   = mediator.get("username", "")

                await self.payment_collection.update_one(
                    {"discord_id": discord_id},
                    {"$set": {"active": False, "updated_at": utcnow()}}
                )
                await self.mediator_collection.update_one(
                    {"discord_id": discord_id},
                    {"$set": {"is_active": False, "updated_at": utcnow()}}
                )

                # — Revogar cargo —
                if guild:
                    await revoke_mediador_role(
                        guild, discord_id, reason="Contrato semanal expirado"
                    )
                    # Log de expiração
                    log_embed = _build_payment_log_embed(
                        event="expirado",
                        discord_id=discord_id,
                        username=username,
                        value=_get_weekly_price(),
                        expiration="Expirado",
                        method="sistema",
                    )
                    await log_pagamento(guild, log_embed)

                expired_ids.append(discord_id)
                logger.info(f"[MediadorService] Contrato expirado: {username} ({discord_id})")

        return expired_ids

    # ── Confirmação manual (ADM/painel) ───────────────────────────────────

    async def confirm_payment_manual(
        self,
        discord_id: str,
        username: str,
        confirmed_by_discord_id: str,
        guild: Optional[discord.Guild] = None,
    ) -> dict:
        """
        Confirma pagamento manualmente (ADM clica no botão do painel).
        Atribui cargo e loga em #logs-pagamentos.
        """
        contract = await self.create_contract(
            discord_id=discord_id,
            username=username,
            guild=guild,
            confirmed_by=f"manual:{confirmed_by_discord_id}",
        )

        # Registra confirmação na coleção de confirmações de pagamento
        await self.payment_collection.update_one(
            {"discord_id": discord_id},
            {"$set": {
                "confirmation_date":    utcnow(),
                "active":               True,
                "confirmed_by":         confirmed_by_discord_id,
                "updated_at":           utcnow(),
            }},
            upsert=True,
        )
        return contract

    # ── Confirmação via API / webhook (EfiPay ou outro) ──────────────────

    async def confirm_payment_api(
        self,
        discord_id: str,
        username: str,
        txid: str,
        value: float,
        guild: Optional[discord.Guild] = None,
    ) -> dict:
        """
        Chamado pelo webhook da API de pagamento (EfiPay ou outro).
        Verifica valor, cria contrato e atribui cargo.
        """
        expected_price = _get_weekly_price()
        if abs(value - expected_price) > 0.50:
            logger.warning(
                f"[MediadorService] confirm_payment_api: valor recebido R${value:.2f} "
                f"difere do esperado R${expected_price:.2f} (txid={txid})"
            )
            # Registra discrepância mas não bloqueia (ADM pode corrigir)

        # Salva txid no registro de pagamento
        await self.payment_collection.update_one(
            {"discord_id": discord_id},
            {"$set": {
                "txid":             txid,
                "paid_value":       value,
                "confirmation_date": utcnow(),
                "active":           True,
                "updated_at":       utcnow(),
            }},
            upsert=True,
        )

        contract = await self.create_contract(
            discord_id=discord_id,
            username=username,
            guild=guild,
            confirmed_by=f"api:txid={txid}",
        )
        return contract

    # ── Info ──────────────────────────────────────────────────────────────

    def get_plan_info(self) -> dict:
        """Retorna informações sobre o plano atual (para exibir em embeds)."""
        return {
            "label":      PLAN_LABEL,
            "days":       PLAN_DAYS,
            "price":      _get_weekly_price(),
            "efi_active": _efi_available(),
            "method":     "EfiPay" if _efi_available() else "Manual (PIX)",
        }


# Instância singleton — usada pelos cogs/views
mediator_manager = MediatorManager()
