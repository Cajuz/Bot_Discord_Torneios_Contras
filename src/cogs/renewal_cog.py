"""
renewal_cog.py — F13: Renovação automática de mediadores via PIX Efí Pay.

Fluxo:
  • #renovacao-mediadores — painel fixo com botão Renovar (abre modal)
  • DM do mediador        — cobrança privada com QR Code + Validar + Cancelar
  • Timeout 10 min        — cancela automaticamente se não pagar
  • Task 12h              — avisa D-3, D-1, e licenças já vencidas
  • Task 24h              — expira mediadores vencidos, remove cargo Controller
  • Webhook /webhook/efi  — confirmação automática da Efí Pay
"""
from __future__ import annotations
import io
import os
import base64
import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.logger import logger
from utils.datetime_utils import utcnow
from services.channel_service import (
    RENOVACAO_CHANNEL,
    LOGS_MEDIADORES_CHANNEL,
    CONTROLLER_ROLE_NAME,
)

THEME_COLOR = 0xFFD54F


class RenewalCog(commands.Cog, name="Renovação"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not self.check_expiring.is_running():
            self.check_expiring.start()
        if not self.expire_mediators.is_running():
            self.expire_mediators.start()

    # ─────────────────────────────────────────
    # Task 12h — avisos D-3, D-1 e vencidos
    # ─────────────────────────────────────────
    @tasks.loop(hours=12)
    async def check_expiring(self):
        from config.database import db
        from datetime import timedelta
        now        = utcnow()
        collection = db.get_collection("mediators")

        for days_left in (3, 1):
            window_start = now + timedelta(days=days_left) - timedelta(hours=6)
            window_end   = now + timedelta(days=days_left) + timedelta(hours=6)
            docs = await collection.find({
                "expiration_date": {"$gte": window_start, "$lte": window_end},
                "is_active": True,
            }).to_list(None)

            for doc in docs:
                try:
                    user = await self.bot.fetch_user(int(doc["user_id"]))
                    embed = discord.Embed(
                        title="Aviso de Vencimento — Licença de Mediador",
                        description=(
                            f"Sua licença vence em **{days_left} dia(s)**.\n\n"
                            f"Acesse o canal **#{RENOVACAO_CHANNEL}** e clique "
                            "em **Renovar Licença** para gerar seu QR Code."
                        ),
                        color=0xFFA726
                    )
                    embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
                    await user.send(embed=embed)
                    logger.info(f"[Renewal] Aviso D-{days_left} → {doc.get('username')}")
                except Exception as e:
                    logger.warning(f"[Renewal] Erro DM aviso: {e}")

        # Licenças já vencidas — notifica uma vez
        from datetime import timedelta
        vencidas = await collection.find({
            "expiration_date": {"$gte": now - timedelta(days=7), "$lt": now},
            "is_active":        True,
            "expiry_notified":  {"$ne": True},
        }).to_list(None)

        for doc in vencidas:
            try:
                user = await self.bot.fetch_user(int(doc["user_id"]))
                embed = discord.Embed(
                    title="Licença Vencida — Mediador",
                    description=(
                        "Sua licença de mediador **venceu**.\n\n"
                        f"Renove no canal **#{RENOVACAO_CHANNEL}** "
                        "para continuar mediando partidas."
                    ),
                    color=0xE74C3C
                )
                embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
                await user.send(embed=embed)
                await collection.update_one(
                    {"user_id": doc["user_id"]},
                    {"$set": {"expiry_notified": True}}
                )
            except Exception as e:
                logger.warning(f"[Renewal] Erro DM vencido: {e}")

    @check_expiring.before_loop
    async def before_check_expiring(self):
        await self.bot.wait_until_ready()

    # ─────────────────────────────────────────
    # Task 24h — expira mediadores vencidos
    # ─────────────────────────────────────────
    @tasks.loop(hours=24)
    async def expire_mediators(self):
        from config.database import db
        now  = utcnow()
        col  = db.get_collection("mediators")
        docs = await col.find({
            "expiration_date": {"$lt": now},
            "is_active":        True,
        }).to_list(None)

        for doc in docs:
            uid = doc.get("user_id")
            await col.update_one(
                {"user_id": uid},
                {"$set": {"is_active": False, "in_queue": False, "updated_at": now}}
            )
            try:
                from services.mediator_queue import mediator_queue
                mediator_queue.queue.remove(uid)
            except (ValueError, AttributeError):
                pass

            for guild in self.bot.guilds:
                member = guild.get_member(uid)
                if member:
                    role = discord.utils.get(guild.roles, name=CONTROLLER_ROLE_NAME)
                    if role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Licença vencida")
                        except discord.Forbidden:
                            pass

                log_ch = discord.utils.get(guild.text_channels, name=LOGS_MEDIADORES_CHANNEL)
                if log_ch:
                    await log_ch.send(embed=discord.Embed(
                        description=(
                            f"<@{uid}> teve a licença expirada e o cargo "
                            f"`{CONTROLLER_ROLE_NAME}` removido automaticamente."
                        ),
                        color=0xE74C3C
                    ))

            try:
                user = await self.bot.fetch_user(uid)
                await user.send(embed=discord.Embed(
                    title="Cargo Removido — Licença Vencida",
                    description=(
                        f"Seu cargo **{CONTROLLER_ROLE_NAME}** foi removido "
                        "pois sua licença venceu.\n\n"
                        f"Renove no canal **#{RENOVACAO_CHANNEL}** para recuperar o acesso."
                    ),
                    color=0xE74C3C
                ))
            except Exception:
                pass

    @expire_mediators.before_loop
    async def before_expire_mediators(self):
        await self.bot.wait_until_ready()

    # ─────────────────────────────────────────
    # /renovar — slash alternativo
    # ─────────────────────────────────────────
    @app_commands.command(name="renovar", description="Renove sua licença de mediador via PIX")
    @app_commands.describe(dias="Plano: 7, 15 ou 30 dias")
    @app_commands.checks.has_any_role("Controller", "Mediador", "Mediator")
    async def renovar(self, interaction: discord.Interaction, dias: int = 30):
        if dias not in (7, 15, 30):
            await interaction.response.send_message(
                "Planos disponíveis: `7`, `15` ou `30` dias.", ephemeral=True)
            return
        await interaction.response.send_modal(_RenovacaoModal(dias=dias, bot=self.bot))

    # ─────────────────────────────────────────
    # !renovar_mediador — Admin gera para outro
    # ─────────────────────────────────────────
    @commands.command(name="renovar_mediador")
    @commands.has_permissions(administrator=True)
    async def renovar_mediador(
        self, ctx: commands.Context,
        member: discord.Member,
        dias: int = 30,
        valor: float = 25.00,
    ):
        await ctx.reply(f"⏳ Gerando cobrança para {member.mention}...")
        from services.efi_pay_service import efi_pay_service
        charge = await efi_pay_service.create_charge(
            mediator_id=str(member.id), value=valor, plan_days=dias)
        if not charge:
            await ctx.reply("❌ Erro ao gerar cobrança.")
            return

        sent = await _send_charge_dm(member, charge, dias, valor, self.bot)
        if sent:
            await ctx.reply(
                f"✅ Cobrança de R$ {valor:.2f} enviada por DM para {member.mention}.")
        else:
            await ctx.reply(
                f"❌ Não foi possível enviar DM para {member.mention}. "
                "Verifique se ele aceita mensagens diretas.")


# ═══════════════════════════════════════════════════════════════
# Modal — escolha do plano
# ═══════════════════════════════════════════════════════════════

class _RenovacaoModal(discord.ui.Modal, title="Renovar Licença de Mediador"):

    plano = discord.ui.TextInput(
        label="Plano (7, 15 ou 30 dias)",
        placeholder="Digite 7, 15 ou 30",
        min_length=1,
        max_length=2,
    )

    def __init__(self, dias: int = 30, bot: discord.Client = None):
        super().__init__()
        self.bot = bot
        self.plano.default = str(dias)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            dias = int(self.plano.value.strip())
            if dias not in (7, 15, 30):
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Plano inválido. Digite 7, 15 ou 30.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        from services.efi_pay_service import efi_pay_service
        price  = float(os.getenv(f"RENEWAL_PRICE_{dias}D", "25.00"))
        charge = await efi_pay_service.create_charge(
            mediator_id=str(interaction.user.id),
            value=price, plan_days=dias,
            description=f"Renovação {dias}d — {interaction.user.name}",
        )
        if not charge:
            await interaction.followup.send(
                "Erro ao gerar cobrança. Tente novamente.", ephemeral=True)
            return

        sent = await _send_charge_dm(
            interaction.user, charge, dias, price, interaction.client)
        if sent:
            await interaction.followup.send(
                "Cobrança gerada e enviada para sua **DM**. "
                "Você tem **10 minutos** para pagar antes de expirar.",
                ephemeral=True)
        else:
            await interaction.followup.send(
                "Não foi possível enviar sua DM. "
                "Verifique se aceita mensagens diretas e tente novamente.",
                ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# View — botões na DM com timeout de 10 minutos
# ═══════════════════════════════════════════════════════════════

class _RenewalValidateView(discord.ui.View):

    def __init__(self, txid: str, bot: discord.Client, mediator_id: str):
        super().__init__(timeout=600)  # 10 minutos
        self.txid        = txid
        self.bot         = bot
        self.mediator_id = mediator_id
        self.message: discord.Message | None = None

    async def on_timeout(self):
        """Cancela automaticamente após 10 minutos sem pagamento."""
        for b in self.children:
            b.disabled = True

        embed = discord.Embed(
            title="Cobrança Expirada",
            description=(
                "O tempo para pagamento encerrou.\n\n"
                f"Acesse o canal **#{RENOVACAO_CHANNEL}** e clique em "
                "**Renovar Licença** para gerar uma nova cobrança."
            ),
            color=0xE74C3C,
        )
        embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))

        try:
            if self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception:
            pass

        try:
            from config.database import db
            await db.get_collection("mediator_renewals").update_one(
                {"txid": self.txid},
                {"$set": {"status": "EXPIRADA", "expired_at": utcnow()}}
            )
        except Exception:
            pass

    @discord.ui.button(label="Validar Pagamento",
                       style=discord.ButtonStyle.success, emoji="✅")
    async def validate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        from services.efi_pay_service import efi_pay_service
        result = await efi_pay_service.check_payment(self.txid)
        if result.get("pago"):
            await _confirm_and_update(
                interaction=interaction,
                txid=self.txid,
                mediator_id=self.mediator_id,
                bot=self.bot,
                view=self,
            )
            return
        await interaction.followup.send(
            embed=discord.Embed(
                description=(
                    f"Pagamento ainda não confirmado.\n"
                    f"Status: `{result.get('status', '—')}`\n"
                    "Tente novamente em instantes."
                ),
                color=0xFFA726,
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Cancelar",
                       style=discord.ButtonStyle.danger, emoji="✖")
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        for b in self.children:
            b.disabled = True
        await interaction.message.edit(
            embed=discord.Embed(
                description="Cobrança cancelada.",
                color=0xE74C3C),
            view=self)
        await interaction.response.send_message("Cobrança cancelada.", ephemeral=True)

        try:
            from config.database import db
            await db.get_collection("mediator_renewals").update_one(
                {"txid": self.txid},
                {"$set": {"status": "CANCELADA", "cancelled_at": utcnow()}}
            )
        except Exception:
            pass
        self.stop()


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

async def _send_charge_dm(
    user: discord.User | discord.Member,
    charge: dict,
    dias: int,
    price: float,
    bot: discord.Client,
) -> bool:
    """Envia cobrança completa por DM. Retorna True se enviou."""
    embed = discord.Embed(
        title=f"Renovação de Licença — {dias} dias",
        description=(
            "Sua cobrança foi gerada. Efetue o pagamento e clique em "
            "**Validar Pagamento** abaixo.\n\n"
            "A cobrança expira automaticamente em **10 minutos**."
        ),
        color=THEME_COLOR,
    )
    embed.add_field(name="Plano",  value=f"`{dias} dias`",  inline=True)
    embed.add_field(name="Valor",  value=f"R$ {price:.2f}", inline=True)
    embed.add_field(
        name="Pix Copia e Cola",
        value=f"```{charge.get('copia_cola', '—')}```",
        inline=False,
    )
    embed.set_footer(text=f"TxID: {charge['txid']} | Expira em 10 min")

    view  = _RenewalValidateView(
        txid=charge["txid"], bot=bot, mediator_id=str(user.id))
    files = []
    qr_b64 = charge.get("qr_code", "")
    if qr_b64:
        try:
            img_bytes = base64.b64decode(qr_b64)
            files.append(discord.File(io.BytesIO(img_bytes), filename="qrcode.png"))
            embed.set_image(url="attachment://qrcode.png")
        except Exception:
            pass

    try:
        msg          = await user.send(embed=embed, view=view, files=files)
        view.message = msg  # guarda referência para on_timeout editar
        return True
    except discord.Forbidden:
        return False


async def _confirm_and_update(
    interaction: discord.Interaction | None,
    txid: str,
    mediator_id: str,
    bot: discord.Client,
    view: _RenewalValidateView | None = None,
):
    """Confirma renovação, restaura cargo e atualiza a mensagem na DM."""
    from services.efi_pay_service import efi_pay_service
    from config.database import db

    confirmed = await efi_pay_service.confirm_renewal(txid)
    if not confirmed:
        if interaction:
            await interaction.followup.send(
                "Renovação já processada ou erro interno.", ephemeral=True)
        return

    # Reativa mediador no banco
    await db.get_collection("mediators").update_one(
        {"user_id": int(mediator_id)},
        {"$set": {"is_active": True, "expiry_notified": False, "updated_at": utcnow()}}
    )

    # Devolve cargo Controller
    for guild in bot.guilds:
        member = guild.get_member(int(mediator_id))
        if member:
            role = discord.utils.get(guild.roles, name=CONTROLLER_ROLE_NAME)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Licença renovada")
                except discord.Forbidden:
                    pass

        log_ch = discord.utils.get(guild.text_channels, name=LOGS_MEDIADORES_CHANNEL)
        if log_ch:
            await log_ch.send(embed=discord.Embed(
                description=f"<@{mediator_id}> renovou a licença. TxID: `{txid}`",
                color=THEME_COLOR,
            ))

    # Atualiza mensagem na DM
    if interaction and view:
        for b in view.children:
            b.disabled = True
        success_embed = discord.Embed(
            title="Pagamento Confirmado",
            description=f"Licença renovada com sucesso!\nTxID: `{txid}`",
            color=0x27AE60,
        )
        success_embed.set_footer(text=utcnow().strftime("%d/%m/%Y %H:%M UTC"))
        await interaction.message.edit(embed=success_embed, view=view)
        await interaction.followup.send("Licença renovada!", ephemeral=True)
        view.stop()

    # DM de confirmação final
    try:
        user = await bot.fetch_user(int(mediator_id))
        await user.send(embed=discord.Embed(
            title="Licença Renovada",
            description="Sua licença foi renovada com sucesso! Bem-vindo de volta.",
            color=0x27AE60,
        ))
    except Exception:
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(RenewalCog(bot))