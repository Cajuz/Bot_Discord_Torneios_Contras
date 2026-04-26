"""
OnboardingService — Fluxo de entrada de novos membros 100% in-server.
Sem dependência de DM. Canal temporário privado por usuário.
"""
import asyncio
import re
import discord
from typing import Optional
from config.database import db
from config.rules import ServerRules
from models.user import User
from utils.datetime_utils import utcnow
from utils.logger import logger, log_success


MEMBER_ROLE_NAME        = "Membro"
RULES_CHANNEL_NAME      = "📜regras"
VERIFY_CATEGORY_NAME    = "✅ Verificação"
VERIFY_CHANNEL_TIMEOUT  = 600  # 10 minutos


class OnboardingService:

    def __init__(self, bot: discord.Client):
        self.bot                      = bot
        self.verified_role_id: Optional[int] = None
        # Cache rápido — rebuildo do DB no restore_state()
        self._pending_onboarding: set[int] = set()
        # BUG1-FIX: mapeia member_id → asyncio.Task do cleanup para cancelamento
        self._cleanup_tasks: dict[int, asyncio.Task] = {}
        # BUG2-FIX: mapeia member_id → TextChannel de verificação ativo
        self._verify_channels: dict[int, discord.TextChannel] = {}

    # ─────────────────────────────────────────────
    # Restaurar estado no restart
    # ─────────────────────────────────────────────

    async def restore_state(self, guild: discord.Guild):
        """
        Chamado no on_ready — restaura verified_role_id e _pending_onboarding
        a partir do DB para garantir resiliência a restarts.
        BUG4-FIX: ignora users que não estão mais no servidor.
        """
        role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)
        if role:
            self.verified_role_id = role.id
            logger.info(f"[Onboarding] verified_role_id restaurado: {role.id}")

        collection = db.get_collection("users")
        pendentes  = await collection.find({
            "has_accepted_rules": False,
            "is_active":          True,
            "onboarding_result":  "pendente"
        }).to_list(None)

        restaurados = 0
        for doc in pendentes:
            member_id = int(doc["discord_id"])
            # BUG4-FIX: só adiciona ao set se o membro ainda está no servidor
            member = guild.get_member(member_id)
            if member is None:
                # Membro saiu — marca como inativo no DB e ignora
                await collection.update_one(
                    {"discord_id": str(member_id)},
                    {"$set": {"is_active": False, "onboarding_result": "saiu", "updated_at": utcnow()}}
                )
                logger.info(f"[Onboarding] restore_state: membro {member_id} não está no servidor — marcado como 'saiu'")
                continue
            self._pending_onboarding.add(member_id)
            restaurados += 1

        logger.info(f"[Onboarding] {restaurados} onboardings pendentes restaurados (válidos)")

        # BUG2-FIX: limpa canais órfãos de verificação que sobraram de restarts anteriores
        await self._cleanup_orphan_channels(guild)

    async def _cleanup_orphan_channels(self, guild: discord.Guild):
        """Remove canais verify-* cujo membro não está mais no servidor ou já tem cargo Membro."""
        category = discord.utils.get(guild.categories, name=VERIFY_CATEGORY_NAME)
        if not category:
            return
        role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)
        removed = 0
        for ch in list(category.channels):
            if not ch.name.startswith("verify-"):
                continue
            # Tenta identificar o membro pelo overwrites do canal
            member_in_channel = None
            for target, overwrite in ch.overwrites.items():
                if isinstance(target, discord.Member) and overwrite.read_messages:
                    member_in_channel = target
                    break
            if member_in_channel is None or (role and role in member_in_channel.roles):
                try:
                    await ch.delete(reason="Onboarding: canal órfão removido no restore")
                    removed += 1
                except Exception as e:
                    logger.warning(f"[Onboarding] Erro ao deletar canal órfão {ch.name}: {e}")
        if removed:
            logger.info(f"[Onboarding] {removed} canais órfãos de verificação removidos")

    # ─────────────────────────────────────────────
    # Entrada de novo membro — IN-SERVER
    # ─────────────────────────────────────────────

    async def handle_new_member(self, member: discord.Member, is_test: bool = False):
        try:
            # BUG1+BUG3-FIX: se havia cleanup task pendente deste membro, cancela antes de tudo
            self._cancel_cleanup_task(member.id)

            if member.id in self._pending_onboarding and not is_test:
                # BUG3-FIX: em vez de ignorar, verifica se o canal ainda existe
                # Se não existe mais (saiu e voltou), limpa e reinicia normalmente
                existing_ch = self._verify_channels.get(member.id)
                if existing_ch:
                    try:
                        # tenta acessar o canal — se lançar exceção, ele foi deletado
                        _ = existing_ch.id
                        # canal ainda existe: genuinamente duplicado (dois on_member_join)
                        logger.warning(f"[Onboarding] Canal ativo detectado para {member.name} — ignorando duplicata")
                        return
                    except Exception:
                        pass
                # Canal não existe mais — limpa o estado e reinicia
                self._pending_onboarding.discard(member.id)
                self._verify_channels.pop(member.id, None)
                logger.info(f"[Onboarding] {member.name} retornou com state pendente mas sem canal — reiniciando onboarding")

            collection = db.get_collection("users")
            existing   = await collection.find_one({"discord_id": str(member.id)})

            # Membro retornando com regras já aceitas
            if existing and existing.get("has_accepted_rules") and not is_test:
                await self._grant_access(member)
                logger.info(f"[Onboarding] {member.name} retornou — acesso restaurado")
                return

            # Upsert no DB — reseta estado para novo onboarding
            if not is_test:
                user_doc = {
                    "discord_id":         str(member.id),
                    "username":           member.name,
                    "joined_at":          utcnow(),
                    "is_active":          True,
                    "onboarding_result":  "pendente",
                    "captcha_status":     "pendente",
                    "has_accepted_rules": False,
                }
                await collection.update_one(
                    {"discord_id": str(member.id)},
                    {"$set": user_doc},
                    upsert=True
                )

            self._pending_onboarding.add(member.id)
            await self._create_verification_channel(member, is_test=is_test)
            log_success(f"[Onboarding] Canal de verificação criado para {member.name}")

        except Exception as e:
            self._pending_onboarding.discard(member.id)
            self._verify_channels.pop(member.id, None)
            logger.error(f"[Onboarding] Erro ao processar {member.name}: {e}", exc_info=True)

    # ─────────────────────────────────────────────
    # Limpeza ao membro SAIR do servidor
    # ─────────────────────────────────────────────

    async def handle_member_leave(self, member: discord.Member):
        """
        BUG2+BUG3-FIX: chamado pelo on_member_remove do main.py.
        Cancela cleanup task, limpa pending set e deleta canal de verificação.
        """
        self._cancel_cleanup_task(member.id)
        self._pending_onboarding.discard(member.id)

        # Deleta canal de verificação se ainda existir
        ch = self._verify_channels.pop(member.id, None)
        if ch:
            try:
                await ch.delete(reason=f"Membro {member.name} saiu durante o onboarding")
                logger.info(f"[Onboarding] Canal de verificação de {member.name} removido (saiu do servidor)")
            except Exception as e:
                logger.warning(f"[Onboarding] Erro ao deletar canal de {member.name}: {e}")

        # Atualiza DB se o onboarding estava pendente
        try:
            doc = await db.get_collection("users").find_one({"discord_id": str(member.id)})
            if doc and doc.get("onboarding_result") == "pendente":
                await db.get_collection("users").update_one(
                    {"discord_id": str(member.id)},
                    {"$set": {"is_active": False, "onboarding_result": "saiu", "updated_at": utcnow()}}
                )
        except Exception as e:
            logger.warning(f"[Onboarding] Erro ao atualizar DB no member_leave de {member.name}: {e}")

    # ─────────────────────────────────────────────
    # Cria canal de verificação privado in-server
    # ─────────────────────────────────────────────

    async def _create_verification_channel(self, member: discord.Member, is_test: bool = False):
        guild    = member.guild
        category = discord.utils.get(guild.categories, name=VERIFY_CATEGORY_NAME)

        if not category:
            category = await guild.create_category(
                VERIFY_CATEGORY_NAME,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False)
                }
            )

        # Nome sanitizado — evita caracteres problemáticos do Discord
        safe_name = re.sub(r"[^a-z0-9\-]", "", member.name.lower())[:20] or str(member.id)
        ch_name   = f"verify-{safe_name}-{str(member.id)[-4:]}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member:             discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                add_reactions=False
            ),
            guild.me:           discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_messages=True
            ),
        }

        try:
            channel = await guild.create_text_channel(
                name=ch_name,
                category=category,
                overwrites=overwrites,
                topic=f"Verificação de {member.display_name}"
            )
        except discord.Forbidden:
            logger.error("[Onboarding] Sem permissão para criar canal de verificação")
            self._pending_onboarding.discard(member.id)
            return
        except discord.HTTPException as e:
            logger.error(f"[Onboarding] Erro HTTP ao criar canal: {e}")
            self._pending_onboarding.discard(member.id)
            return

        # BUG2-FIX: registra canal no cache
        self._verify_channels[member.id] = channel

        from views.rules_view import RulesView

        embed        = ServerRules.get_rules_embed()
        view         = RulesView(self, member, channel=channel, timeout=VERIFY_CHANNEL_TIMEOUT, is_test=is_test)
        message      = await channel.send(
            content=f"👋 Bem-vindo, {member.mention}! Leia as regras e clique em **Aceitar** para entrar.",
            embed=embed,
            view=view
        )
        view.message = message

        # BUG1-FIX: guarda referência da task para poder cancelar
        task = asyncio.create_task(
            self._cleanup_verification_channel(channel, member, VERIFY_CHANNEL_TIMEOUT)
        )
        self._cleanup_tasks[member.id] = task

    async def _cleanup_verification_channel(
        self, channel: discord.TextChannel, member: discord.Member, delay: int
    ):
        try:
            await asyncio.sleep(delay + 5)
            try:
                if not await self._has_member_role(member):
                    # Verifica se o membro ainda está no servidor
                    guild_member = member.guild.get_member(member.id)
                    if guild_member is None:
                        # Já saiu — handle_member_leave já cuidou disso
                        return
                    try:
                        await channel.send(
                            f"⏰ Tempo esgotado, {member.mention}. Você será removido.",
                            delete_after=5
                        )
                    except Exception:
                        pass
                    await asyncio.sleep(5)
                    await self.kick_member(
                        member,
                        reason="Não aceitou as regras no prazo",
                        result="timeout"
                    )
            except Exception:
                pass
        except asyncio.CancelledError:
            # BUG1-FIX: task cancelada por handle_member_leave ou re-join — normal
            logger.info(f"[Onboarding] Cleanup task cancelada para {member.name}")
            return
        finally:
            # BUG6-FIX: sempre tenta deletar o canal, independente do resultado
            self._verify_channels.pop(member.id, None)
            self._cleanup_tasks.pop(member.id, None)
            try:
                await channel.delete(reason="Verificação concluída/expirada")
            except Exception:
                pass

    def _cancel_cleanup_task(self, member_id: int):
        """BUG1-FIX: cancela task de cleanup de um membro se existir."""
        task = self._cleanup_tasks.pop(member_id, None)
        if task and not task.done():
            task.cancel()

    # ─────────────────────────────────────────────
    # CAPTCHA in-server via botões (sem DM!)
    # ─────────────────────────────────────────────

    async def run_captcha_flow(
        self, member: discord.Member, channel: discord.TextChannel, is_test: bool = False
    ):
        """
        Executa CAPTCHA diretamente no canal de verificação via botões.
        Sem digitação, sem DM — rápido e acessível.
        """
        from views.captcha_button_view import CaptchaButtonView

        for attempt in range(1, 4):
            view  = CaptchaButtonView(member=member, attempt=attempt)
            embed = discord.Embed(
                title="🔐 Verificação Rápida",
                description=(
                    f"**{view.question}**\n\n"
                    f"Clique na resposta correta abaixo.\n\n"
                    f"🔄 Tentativa **{attempt}/3**"
                ),
                color=discord.Color.blue()
            )
            msg = await channel.send(embed=embed, view=view)

            try:
                result = await view.wait_result(timeout=60.0)
            except asyncio.TimeoutError:
                await channel.send(embed=discord.Embed(
                    title="⏰ Tempo Esgotado",
                    description="Você não respondeu a tempo.",
                    color=discord.Color.red()
                ))
                await self.kick_member(member, reason="CAPTCHA timeout", result="captcha_timeout")
                return
            finally:
                try:
                    await msg.delete()
                except Exception:
                    pass

            if result:
                await db.get_collection("users").update_one(
                    {"discord_id": str(member.id)},
                    {"$set": {"captcha_status": "aprovado", "updated_at": utcnow()}}
                )
                if is_test:
                    logger.info(f"[TESTE] CAPTCHA aprovado para {member.name}")
                    self.clear_pending(member.id)
                    return
                await self.accept_rules(member, channel=channel)
                return
            else:
                if attempt < 3:
                    await channel.send(
                        embed=discord.Embed(
                            title="❌ Errado!",
                            description=f"Tente novamente. Tentativas restantes: **{3 - attempt}**",
                            color=discord.Color.orange()
                        ),
                        delete_after=5
                    )

        # Esgotou tentativas
        await channel.send(embed=discord.Embed(
            title="🚫 Verificação Falhou",
            description="Você esgotou todas as tentativas.",
            color=discord.Color.red()
        ))
        await self.kick_member(member, reason="CAPTCHA falhou", result="captcha_falhou")

    # ─────────────────────────────────────────────
    # Aceitar regras
    # ─────────────────────────────────────────────

    async def accept_rules(self, member: discord.Member, channel: discord.TextChannel = None) -> bool:
        try:
            await db.get_collection("users").update_one(
                {"discord_id": str(member.id)},
                {"$set": {
                    "has_accepted_rules": True,
                    "onboarding_result":  "aceito",
                    "rules_accepted_at":  utcnow(),
                    "updated_at":         utcnow(),
                }},
                upsert=True
            )
            # Limpa estado — cancela cleanup task (não precisará mais kickar)
            self._cancel_cleanup_task(member.id)
            self._pending_onboarding.discard(member.id)
            self._verify_channels.pop(member.id, None)
            await self._grant_access(member)
            log_success(f"[Onboarding] {member.name} completou o onboarding!")

            if channel:
                await channel.send(
                    embed=discord.Embed(
                        title="✅ Acesso Liberado!",
                        description=(
                            f"Bem-vindo ao servidor, {member.mention}! 🎉\n"
                            "Você já tem acesso a todos os canais."
                        ),
                        color=discord.Color.green()
                    ),
                    delete_after=10
                )
                await asyncio.sleep(10)
                # BUG6-FIX: tenta deletar independentemente de qualquer exceção anterior
                try:
                    await channel.delete(reason="Onboarding concluído")
                except Exception:
                    pass
            return True

        except Exception as e:
            logger.error(f"[Onboarding] Erro ao aceitar regras de {member.name}: {e}")
            return False

    # ─────────────────────────────────────────────
    # _grant_access — atribuir cargo Membro
    # ─────────────────────────────────────────────

    async def _grant_access(self, member: discord.Member):
        try:
            guild = member.guild
            role  = guild.get_role(self.verified_role_id) if self.verified_role_id else None

            if not role:
                role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)

            if not role:
                logger.error(
                    f"[Onboarding] Cargo '{MEMBER_ROLE_NAME}' não encontrado! "
                    f"Execute /setupcanais para recriá-lo."
                )
                return

            if role not in member.roles:
                await member.add_roles(role, reason="Onboarding concluído")
                logger.info(f"[Onboarding] Cargo '{role.name}' ✅ → {member.name}")
            # Atualiza ID em cache
            self.verified_role_id = role.id

        except discord.Forbidden:
            logger.error(f"[Onboarding] Sem permissão para adicionar cargo a {member.name}")
        except Exception as e:
            logger.error(f"[Onboarding] Erro em _grant_access: {e}")

    # ─────────────────────────────────────────────
    # kick_member
    # ─────────────────────────────────────────────

    async def kick_member(self, member: discord.Member, reason: str, result: str = "recusado"):
        try:
            if await self._has_member_role(member):
                logger.warning(f"[Onboarding] kick ignorado — {member.name} já tem cargo Membro")
                return
            if getattr(getattr(member, "guild_permissions", None), "administrator", False):
                logger.warning(f"[Onboarding] kick ignorado — {member.name} é admin")
                return

            # Verifica se membro ainda está no servidor
            guild_member = member.guild.get_member(member.id)
            if guild_member is None:
                logger.info(f"[Onboarding] kick ignorado — {member.name} não está mais no servidor")
                self._pending_onboarding.discard(member.id)
                return

            await member.kick(reason=reason)
            await db.get_collection("users").update_one(
                {"discord_id": str(member.id)},
                {"$set": {"is_active": False, "onboarding_result": result, "updated_at": utcnow()}}
            )
            self._pending_onboarding.discard(member.id)

        except discord.Forbidden:
            # BUG5-FIX: kick falhou por permissão — loga para alertas-adm
            logger.error(f"[Onboarding] Sem permissão para kickar {member.name}")
            await self._alert_kick_failed(member, reason)
        except Exception as e:
            logger.error(f"[Onboarding] Erro kick {member.name}: {e}")

    async def _alert_kick_failed(self, member: discord.Member, reason: str):
        """BUG5-FIX: avisa ADM quando kick falha por Forbidden."""
        try:
            guild   = member.guild
            log_ch  = discord.utils.get(guild.text_channels, name="alertas-adm")
            if log_ch:
                embed = discord.Embed(
                    title="⚠️ Falha ao remover membro (sem permissão)",
                    description=(
                        f"O bot não conseguiu kickar {member.mention} ({member.id}).\n"
                        f"**Motivo:** {reason}\n\n"
                        "Por favor, remova manualmente ou ajuste as permissões do bot."
                    ),
                    color=0xE74C3C,
                    timestamp=utcnow(),
                )
                embed.set_footer(text="Onboarding · Solar E-Sports")
                await log_ch.send(embed=embed)
        except Exception as e:
            logger.warning(f"[Onboarding] Erro ao enviar alerta de kick falho: {e}")

    # ─────────────────────────────────────────────
    # Setup do cargo e canal (admin)
    # ─────────────────────────────────────────────

    async def setup_member_role_and_rules_channel(self, guild: discord.Guild) -> dict:
        result = {}

        existing_role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)
        if existing_role:
            member_role = existing_role
        else:
            member_role = await guild.create_role(
                name=MEMBER_ROLE_NAME,
                color=discord.Color.green(),
                mentionable=False,
                reason="Cargo de acesso padrão — concedido após aceitar regras e passar no CAPTCHA"
            )
            logger.info(f"Cargo '{MEMBER_ROLE_NAME}' criado")

        self.verified_role_id = member_role.id
        result["role"] = member_role

        existing_channel = discord.utils.get(guild.text_channels, name=RULES_CHANNEL_NAME)
        if existing_channel:
            rules_channel = existing_channel
        else:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=False,
                    add_reactions=False
                ),
                member_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=False
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
            }
            rules_channel = await guild.create_text_channel(
                name=RULES_CHANNEL_NAME,
                overwrites=overwrites,
                topic="Leia as regras para entrar no servidor.",
                reason="Canal de regras — onboarding"
            )
            logger.info(f"Canal '{RULES_CHANNEL_NAME}' criado")

        async for msg in rules_channel.history(limit=10):
            if msg.author == guild.me and msg.embeds:
                await msg.delete()
                break

        rules_embed = ServerRules.get_rules_embed()
        info_embed  = discord.Embed(
            title="📋 Como funciona o acesso",
            description=(
                "**1.** Ao entrar, você recebe um **canal privado** de verificação.\n"
                "**2.** Leia as regras e clique em **Aceitar**.\n"
                "**3.** Responda um **CAPTCHA rápido** (clique no botão correto).\n"
                "**4.** Pronto! Você recebe o cargo **Membro** e acessa todos os canais.\n"
                "**5.** Se não responder em **10 minutos**, será removido automaticamente."
            ),
            color=discord.Color.gold()
        )
        await rules_channel.send(embeds=[rules_embed, info_embed])

        result["channel"] = rules_channel
        return result

    # ─────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────

    async def get_user_stats(self, discord_id: str) -> Optional[User]:
        try:
            collection = db.get_collection("users")
            user_doc   = await collection.find_one({"discord_id": discord_id})
            return User(user_doc) if user_doc else None
        except Exception as e:
            logger.error(f"Erro ao buscar usuário {discord_id}: {e}")
            return None

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    async def _has_member_role(self, member: discord.Member) -> bool:
        role = discord.utils.get(member.guild.roles, name=MEMBER_ROLE_NAME)
        return role is not None and role in member.roles

    def is_pending_onboarding(self, member_id: int) -> bool:
        return member_id in self._pending_onboarding

    def clear_pending(self, member_id: int):
        self._cancel_cleanup_task(member_id)
        self._pending_onboarding.discard(member_id)
        self._verify_channels.pop(member_id, None)
