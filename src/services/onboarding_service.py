import asyncio
import discord
from typing import Optional
from datetime import datetime

from config.database import db
from config.rules import ServerRules
from models.user import User
from views.rules_view import RulesView
from utils.logger import logger, log_success


MEMBER_ROLE_NAME   = "Membro"
RULES_CHANNEL_NAME = "📜regras"


class OnboardingService:
    """Serviço de onboarding de novos membros"""

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.verification_channel_id: Optional[int] = None
        self.verified_role_id: Optional[int] = None

    def set_verification_channel(self, channel_id: int):
        self.verification_channel_id = channel_id
        logger.info(f"Canal de verificação definido: {channel_id}")

    def set_verified_role(self, role_id: int):
        self.verified_role_id = role_id
        logger.info(f"Cargo de verificado definido: {role_id}")

    # ─────────────────────────────────────────────
    # Entrada de novo membro
    # ─────────────────────────────────────────────

    async def handle_new_member(self, member: discord.Member):
        """Processa novo membro: cria registro e envia regras via DM"""
        try:
            collection = db.get_collection('users')
            existing   = await collection.find_one({'discord_id': str(member.id)})

            # Membro retornou e já aceitou antes → concede acesso direto
            if existing and existing.get('has_accepted_rules'):
                await self._grant_access(member)
                logger.info(f"Membro {member.name} retornou — acesso concedido")
                return

            # Cria ou atualiza registro
            if not existing:
                user_doc = User.create_document(str(member.id), member.name)
                await collection.insert_one(user_doc)
            else:
                # Retornou mas não havia aceitado — reseta para pendente
                await collection.update_one(
                    {'discord_id': str(member.id)},
                    {'$set': {
                        'username':          member.name,
                        'joined_at':         datetime.utcnow(),
                        'is_active':         True,
                        'onboarding_result': 'pendente'  # ✅ reseta ao retornar
                    }}
                )

            await self._send_rules_dm(member)
            log_success(f"Novo membro: {member.name} — regras enviadas via DM")

        except Exception as e:
            logger.error(f"Erro ao processar novo membro {member.name}: {e}")

    # ─────────────────────────────────────────────
    # Envio das regras via DM
    # ─────────────────────────────────────────────

    async def _send_rules_dm(self, member: discord.Member):
        """
        Envia as regras na DM com botões de aceitar/recusar.
        Se DM bloqueada, kicca com result='dm_bloqueada'.
        """
        try:
            view  = RulesView(self, member, timeout=300)
            embed = ServerRules.get_rules_embed()

            rules_channel = discord.utils.get(member.guild.text_channels, name=RULES_CHANNEL_NAME)
            if rules_channel:
                await rules_channel.send(
                    f"👋 {member.mention} entrou no servidor!\n"
                    f"📩 Enviamos as regras na sua **DM** — você tem **5 minutos** para aceitar.",
                    delete_after=310
                )

            try:
                message      = await member.send(embed=embed, view=view)
                view.message = message
            except discord.Forbidden:
                logger.warning(f"DM bloqueada para {member.name} — kickando")
                try:
                    if rules_channel:
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
                    result='dm_bloqueada'  # ✅
                )

        except Exception as e:
            logger.error(f"Erro ao enviar regras via DM para {member.name}: {e}")

    # ─────────────────────────────────────────────
    # Aceitar regras
    # ─────────────────────────────────────────────

    async def accept_rules(self, member: discord.Member) -> bool:
        """Processa aceitação das regras e concede cargo Membro"""
        try:
            collection = db.get_collection('users')
            user_doc   = await collection.find_one({'discord_id': str(member.id)})

            if not user_doc:
                logger.error(f"Usuário {member.name} não encontrado no banco")
                return False

            user = User(user_doc)
            user.accept_rules()

            doc = user.to_dict()
            doc.pop('_id', None)              # ✅ remove _id para não dar erro no $set
            doc['onboarding_result'] = 'aceito'  # ✅ grava resultado

            await collection.update_one(
                {'discord_id': str(member.id)},
                {'$set': doc}
            )

            await self._grant_access(member)
            log_success(f"Usuário {member.name} aceitou as regras")
            return True

        except Exception as e:
            logger.error(f"Erro ao processar aceitação de {member.name}: {e}")
            return False

    # ─────────────────────────────────────────────
    # Conceder acesso (cargo Membro)
    # ─────────────────────────────────────────────

    async def _grant_access(self, member: discord.Member):
        """Adiciona o cargo 'Membro' ao usuário"""
        try:
            guild = member.guild

            role = None
            if self.verified_role_id:
                role = guild.get_role(self.verified_role_id)

            if not role:
                role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)

            if role:
                await member.add_roles(role, reason="Aceitou as regras do servidor")
                logger.info(f"Cargo '{role.name}' atribuído a {member.name}")
            else:
                logger.warning(
                    f"Cargo '{MEMBER_ROLE_NAME}' não encontrado. "
                    f"Use !setupmembro para criá-lo."
                )

        except Exception as e:
            logger.error(f"Erro ao conceder acesso a {member.name}: {e}")

    # ─────────────────────────────────────────────
    # Setup do cargo e canal (admin)
    # ─────────────────────────────────────────────

    async def setup_member_role_and_rules_channel(self, guild: discord.Guild) -> dict:
        result = {}

        # ── Cargo Membro ──────────────────────────────────────────
        existing_role = discord.utils.get(guild.roles, name=MEMBER_ROLE_NAME)
        if existing_role:
            member_role = existing_role
            logger.info(f"Cargo '{MEMBER_ROLE_NAME}' já existe")
        else:
            member_role = await guild.create_role(
                name=MEMBER_ROLE_NAME,
                color=discord.Color.green(),
                mentionable=False,
                reason="Cargo de acesso padrão — concedido após aceitar regras"
            )
            logger.info(f"Cargo '{MEMBER_ROLE_NAME}' criado")

        self.verified_role_id = member_role.id
        result['role'] = member_role

        # ── Canal #📜regras ───────────────────────────────────────
        existing_channel = discord.utils.get(guild.text_channels, name=RULES_CHANNEL_NAME)
        if existing_channel:
            rules_channel = existing_channel
            logger.info(f"Canal '{RULES_CHANNEL_NAME}' já existe")
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

        result['channel'] = rules_channel

        # ── Posta as regras fixas no canal ────────────────────────
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
                "**3.** Se aceitar → recebe o cargo **Membro** e acessa todos os canais.\n"
                "**4.** Se recusar ou não responder → será removido automaticamente.\n\n"
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
        result: str = 'recusado'  # ✅ novo parâmetro — padrão 'recusado'
    ):
        try:
            await member.kick(reason=reason)
            collection = db.get_collection('users')
            await collection.update_one(
                {'discord_id': str(member.id)},
                {'$set': {
                    'is_active':          False,
                    'onboarding_result':  result,  # ✅ grava 'recusado' | 'timeout' | 'dm_bloqueada'
                    'updated_at':         datetime.utcnow()
                }}
            )
            logger.info(f"Membro {member.name} removido ({result}): {reason}")
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
