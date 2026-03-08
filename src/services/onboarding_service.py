import asyncio
import discord
from typing import Optional
from datetime import datetime

from config.database import db
from config.rules import ServerRules
from models.user import User
from views.rules_view import RulesView
from services.captcha_service import CaptchaService  
from utils.logger import logger, log_success


MEMBER_ROLE_NAME   = "Membro"
RULES_CHANNEL_NAME = "📜regras"


class OnboardingService:

    def __init__(self, bot: discord.Client):
        self.bot                      = bot
        self.verification_channel_id: Optional[int] = None
        self.verified_role_id: Optional[int]        = None
        self._pending_onboarding: set[int] = set()

    def set_verification_channel(self, channel_id: int):
        self.verification_channel_id = channel_id

    def set_verified_role(self, role_id: int):
        self.verified_role_id = role_id

    # ─────────────────────────────────────────────
    # Entrada de novo membro
    # ─────────────────────────────────────────────

    async def handle_new_member(self, member: discord.Member, is_test: bool = False):
        try:
            if member.id in self._pending_onboarding and not is_test:
                logger.warning(f"Onboarding já em andamento para {member.name} — ignorando duplicata")
                return

            collection = db.get_collection('users')
            existing   = await collection.find_one({'discord_id': str(member.id)})

            if existing and existing.get('has_accepted_rules') and not is_test:
                await self._grant_access(member)
                try:
                    rules_channel = discord.utils.get(member.guild.text_channels, name=RULES_CHANNEL_NAME)
                    if rules_channel:
                        await rules_channel.send(
                            f"👋 Bem-vindo de volta, {member.mention}! Acesso restaurado.",
                            delete_after=30
                        )
                except Exception:
                    pass
                logger.info(f"Membro {member.name} retornou — acesso concedido")
                return

            if not is_test:
                if not existing:
                    user_doc = User.create_document(str(member.id), member.name)
                    await collection.insert_one(user_doc)
                else:
                    await collection.update_one(
                        {'discord_id': str(member.id)},
                        {'$set': {
                            'username':           member.name,
                            'joined_at':          datetime.utcnow(),
                            'is_active':          True,
                            'onboarding_result':  'pendente',
                            'captcha_status':     'pendente',  # ✅ reseta captcha
                            'has_accepted_rules': False,
                        }}
                    )

            self._pending_onboarding.add(member.id)
            await self._send_rules_dm(member, is_test=is_test)
            log_success(f"Membro {member.name} — regras enviadas via DM")

        except Exception as e:
            self._pending_onboarding.discard(member.id)
            logger.error(f"Erro ao processar novo membro {member.name}: {e}")

    # ─────────────────────────────────────────────
    # Envio das regras via DM
    # ─────────────────────────────────────────────

    async def _send_rules_dm(self, member: discord.Member, is_test: bool = False):
        try:
            view  = RulesView(self, member, timeout=300, is_test=is_test)
            embed = ServerRules.get_rules_embed()

            rules_channel = discord.utils.get(member.guild.text_channels, name=RULES_CHANNEL_NAME)

            if not is_test and rules_channel:
                await rules_channel.send(
                    f"👋 {member.mention} entrou no servidor!\n"
                    f"📩 Enviamos as regras na sua **DM** — você tem **5 minutos** para aceitar.",
                    delete_after=310
                )

            try:
                message      = await member.send(embed=embed, view=view)
                view.message = message
            except discord.Forbidden:
                self._pending_onboarding.discard(member.id)
                logger.warning(f"DM bloqueada para {member.name}")

                if is_test:
                    logger.info(f"[TESTE] DM bloqueada para {member.name} — pulando kick")
                    return

                if await self._has_member_role(member):
                    logger.info(f"DM bloqueada mas {member.name} já tem cargo Membro — não kickando")
                    return

                if rules_channel:
                    try:
                        await rules_channel.send(
                            f"⚠️ {member.mention} não tem DM aberta e foi removido.\n"
                            f"Habilite DMs de membros do servidor e entre novamente.",
                            delete_after=30
                        )
                    except Exception:
                        pass

                await self.kick_member(
                    member,
                    reason="DM bloqueada — não foi possível enviar as regras",
                    result='dm_bloqueada'
                )

        except Exception as e:
            self._pending_onboarding.discard(member.id)
            logger.error(f"Erro ao enviar regras via DM para {member.name}: {e}")

    # ─────────────────────────────────────────────
    # Fluxo CAPTCHA ✅ novo
    # ─────────────────────────────────────────────

    async def run_captcha_flow(self, member: discord.Member, is_test: bool = False):
        """
        Inicia o fluxo de verificação CAPTCHA após o membro aceitar as regras.
        Chamado como asyncio.create_task() a partir da RulesView.
        """
        try:
            dm_channel = member.dm_channel or await member.create_dm()
            success, result = await self._run_captcha_loop(member, dm_channel)

            collection = db.get_collection('users')

            if success:
                await collection.update_one(
                    {'discord_id': str(member.id)},
                    {'$set': {
                        'captcha_status': 'aprovado',
                        'updated_at':     datetime.utcnow()
                    }}
                )
                await dm_channel.send(embed=CaptchaService.get_success_embed())

                if is_test:
                    logger.info(f"[TESTE] CAPTCHA aprovado para {member.name} — pulando grant")
                    welcome_embed = ServerRules.get_welcome_embed(member)
                    await dm_channel.send(embed=welcome_embed)
                    self.clear_pending(member.id)
                    return

                ok = await self.accept_rules(member)
                if ok:
                    welcome_embed = ServerRules.get_welcome_embed(member)
                    await dm_channel.send(embed=welcome_embed)

            else:
                # result: 'captcha_timeout' ou 'captcha_falhou'
                captcha_status = 'timeout' if result == 'captcha_timeout' else 'falhou'
                await collection.update_one(
                    {'discord_id': str(member.id)},
                    {'$set': {
                        'captcha_status': captcha_status,
                        'updated_at':     datetime.utcnow()
                    }}
                )

                if is_test:
                    logger.info(f"[TESTE] CAPTCHA falhou para {member.name} ({result}) — kick ignorado")
                    self.clear_pending(member.id)
                    return

                self._pending_onboarding.discard(member.id)
                await self.kick_member(
                    member,
                    reason=f"Falhou na verificação CAPTCHA ({result})",
                    result=result
                )

        except Exception as e:
            logger.error(f"Erro no captcha_flow de {member.name}: {e}")
            self._pending_onboarding.discard(member.id)

    async def _run_captcha_loop(
        self, member: discord.Member, dm_channel: discord.DMChannel
    ) -> tuple[bool, str]:
        """
        Executa o loop de tentativas do CAPTCHA.
        Retorna (True, 'aprovado') ou (False, 'captcha_falhou'|'captcha_timeout').
        """
        for attempt in range(1, CaptchaService.MAX_ATTEMPTS + 1):
            code         = CaptchaService.generate_code()
            image_buffer = CaptchaService.generate_image(code)
            embed        = CaptchaService.get_captcha_embed(attempt, CaptchaService.MAX_ATTEMPTS)
            file         = discord.File(fp=image_buffer, filename="captcha.png")

            await dm_channel.send(embed=embed, file=file)

            def check(m: discord.Message) -> bool:
                return (
                    m.author.id == member.id
                    and isinstance(m.channel, discord.DMChannel)
                    and not m.author.bot
                )

            try:
                msg = await self.bot.wait_for(
                    'message',
                    check=check,
                    timeout=float(CaptchaService.TIMEOUT_SECS)
                )

                if msg.content.strip().upper() == code.upper():
                    return True, 'aprovado'

                # Resposta errada
                attempts_left = CaptchaService.MAX_ATTEMPTS - attempt
                if attempts_left > 0:
                    await dm_channel.send(embed=CaptchaService.get_error_embed(attempts_left))
                    await asyncio.sleep(1)  # pequena pausa antes do próximo CAPTCHA

            except asyncio.TimeoutError:
                await dm_channel.send(embed=CaptchaService.get_timeout_embed())
                return False, 'captcha_timeout'

        # Esgotou todas as tentativas
        await dm_channel.send(embed=CaptchaService.get_failed_embed())
        return False, 'captcha_falhou'

    # ─────────────────────────────────────────────
    # Aceitar regras (chamado após CAPTCHA aprovado)
    # ─────────────────────────────────────────────

    async def accept_rules(self, member: discord.Member) -> bool:
        try:
            collection = db.get_collection('users')
            await collection.update_one(
                {'discord_id': str(member.id)},
                {'$set': {
                    'has_accepted_rules':  True,
                    'onboarding_result':   'aceito',
                    'rules_accepted_at':   datetime.utcnow(),
                    'updated_at':          datetime.utcnow(),
                }},
                upsert=True
            )
            self._pending_onboarding.discard(member.id)
            await self._grant_access(member)
            log_success(f"Usuário {member.name} aceitou as regras e passou no CAPTCHA")
            return True

        except Exception as e:
            logger.error(f"Erro ao processar aceitação de {member.name}: {e}")
            return False

    # ─────────────────────────────────────────────
    # Conceder acesso (cargo Membro)
    # ─────────────────────────────────────────────

    async def _grant_access(self, member: discord.Member):
        try:
            guild = member.guild
            role  = None

            if self.verified_role_id:
                role = guild.get_role(self.verified_role_id)

            if not role:
                role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)

            if role:
                if role not in member.roles:
                    await member.add_roles(role, reason="Aceitou as regras e passou no CAPTCHA")
                    logger.info(f"Cargo '{role.name}' atribuído a {member.name}")
                else:
                    logger.info(f"Cargo '{role.name}' já estava em {member.name}")
            else:
                logger.warning(
                    f"Cargo '{MEMBER_ROLE_NAME}' não encontrado. "
                    f"Use !setupcanais para criá-lo."
                )

        except Exception as e:
            logger.error(f"Erro ao conceder acesso a {member.name}: {e}")

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    async def _has_member_role(self, member: discord.Member) -> bool:
        guild = member.guild
        role  = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)
        return role is not None and role in member.roles

    def is_pending_onboarding(self, member_id: int) -> bool:
        return member_id in self._pending_onboarding

    def clear_pending(self, member_id: int):
        self._pending_onboarding.discard(member_id)

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
        result['role'] = member_role

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
                topic="Leia as regras e aguarde a DM para entrar no servidor.",
                reason="Canal de regras — onboarding"
            )
            logger.info(f"Canal '{RULES_CHANNEL_NAME}' criado")

        async for msg in rules_channel.history(limit=10):
            if msg.author == guild.me and msg.embeds:
                await msg.delete()
                break

        rules_embed = ServerRules.get_rules_embed()
        info_embed  = discord.Embed(
            title="📩 Como funciona o acesso",
            description=(
                "**1.** Ao entrar no servidor, você receberá uma **DM** com os botões de aceitar/recusar.\n"
                "**2.** Você tem **5 minutos** para responder.\n"
                "**3.** Se aceitar → você receberá um **CAPTCHA** para verificação.\n"
                "**4.** Se passar no CAPTCHA → recebe o cargo **Membro** e acessa todos os canais.\n"
                "**5.** Se recusar ou não responder → será removido automaticamente.\n\n"
                "⚠️ **Certifique-se de ter as DMs abertas para membros deste servidor!**"
            ),
            color=discord.Color.gold()
        )
        await rules_channel.send(embeds=[rules_embed, info_embed])

        result['channel'] = rules_channel
        return result

    # ─────────────────────────────────────────────
    # Kick
    # ─────────────────────────────────────────────

    async def kick_member(
        self,
        member: discord.Member,
        reason: str,
        result: str = 'recusado'
    ):
        try:
            if await self._has_member_role(member):
                logger.warning(f"kick_member ignorado — {member.name} já tem cargo Membro")
                return

            if getattr(getattr(member, 'guild_permissions', None), 'administrator', False):
                logger.warning(f"kick_member ignorado — {member.name} é administrador")
                return

            await member.kick(reason=reason)

            collection = db.get_collection('users')
            await collection.update_one(
                {'discord_id': str(member.id)},
                {'$set': {
                    'is_active':         False,
                    'onboarding_result': result,
                    'updated_at':        datetime.utcnow()
                }}
            )
            self._pending_onboarding.discard(member.id)
            logger.info(f"Membro {member.name} removido ({result}): {reason}")

        except discord.Forbidden:
            logger.error(f"Sem permissão para kickar {member.name}")
        except Exception as e:
            logger.error(f"Erro ao remover {member.name}: {e}")

    # ─────────────────────────────────────────────
    # Stats
    # ─────────────────────────────────────────────

    async def get_user_stats(self, discord_id: str) -> Optional[User]:
        try:
            collection = db.get_collection('users')
            user_doc   = await collection.find_one({'discord_id': discord_id})
            return User(user_doc) if user_doc else None
        except Exception as e:
            logger.error(f"Erro ao buscar usuário {discord_id}: {e}")
            return None
