import discord
from typing import Optional
from datetime import datetime

from config.database import db
from config.rules import ServerRules
from models.user import User
from views.rules_view import RulesView
from utils.logger import logger, log_success

class OnboardingService:
    """Serviço de onboarding de novos membros"""
    
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.verification_channel_id: Optional[int] = None
        self.verified_role_id: Optional[int] = None
    
    def set_verification_channel(self, channel_id: int):
        """Definir canal de verificação"""
        self.verification_channel_id = channel_id
        logger.info(f"Canal de verificação definido: {channel_id}")
    
    def set_verified_role(self, role_id: int):
        """Definir cargo de verificado"""
        self.verified_role_id = role_id
        logger.info(f"Cargo de verificado definido: {role_id}")
    
    async def handle_new_member(self, member: discord.Member):
        """Processar novo membro"""
        try:
            # Verificar se já existe no banco
            collection = db.get_collection('users')
            existing = await collection.find_one({'discord_id': str(member.id)})
            
            if existing and existing.get('has_accepted_rules'):
                # Usuário já aceitou regras anteriormente
                await self._grant_access(member)
                logger.info(f"Usuário {member.name} retornou - acesso concedido automaticamente")
                return
            
            # Criar/atualizar registro do usuário
            if not existing:
                user_doc = User.create_document(str(member.id), member.name)
                await collection.insert_one(user_doc)
            else:
                await collection.update_one(
                    {'discord_id': str(member.id)},
                    {'$set': {'username': member.name, 'joined_at': datetime.now()}}
                )
            
            # Enviar regras
            await self._send_rules(member)
            
            log_success(f"Novo membro: {member.name} - Regras enviadas")
        
        except Exception as e:
            logger.error(f"Erro ao processar novo membro {member.name}: {e}")
    
    async def _send_rules(self, member: discord.Member):
        """Enviar regras para o membro"""
        try:
            # Criar embed das regras
            rules_embed = ServerRules.get_rules_embed()
            
            # Criar view com botões
            view = RulesView(self, member)
            
            # Enviar no canal de verificação ou DM
            if self.verification_channel_id:
                channel = self.bot.get_channel(self.verification_channel_id)
                if channel:
                    message = await channel.send(
                        content=f"👋 {member.mention}, bem-vindo(a)! Por favor, leia as regras:",
                        embed=rules_embed,
                        view=view
                    )
                    view.message = message
                    return
            
            # Fallback: enviar DM
            try:
                message = await member.send(embed=rules_embed, view=view)
                view.message = message
            except discord.Forbidden:
                logger.warning(f"Não foi possível enviar DM para {member.name}")
        
        except Exception as e:
            logger.error(f"Erro ao enviar regras para {member.name}: {e}")
    
    async def accept_rules(self, member: discord.Member) -> bool:
        """Processar aceitação das regras"""
        try:
            collection = db.get_collection('users')
            
            # Atualizar no banco
            user_doc = await collection.find_one({'discord_id': str(member.id)})
            if not user_doc:
                logger.error(f"Usuário {member.name} não encontrado no banco")
                return False
            
            user = User(user_doc)
            user.accept_rules()
            
            await collection.update_one(
                {'discord_id': str(member.id)},
                {'$set': user.to_dict()}
            )
            
            # Conceder acesso ao servidor
            await self._grant_access(member)
            
            log_success(f"Usuário {member.name} aceitou as regras")
            return True
        
        except Exception as e:
            logger.error(f"Erro ao processar aceitação de {member.name}: {e}")
            return False
    
    async def _grant_access(self, member: discord.Member):
        """Conceder acesso aos canais do servidor"""
        try:
            if self.verified_role_id:
                guild = member.guild
                role = guild.get_role(self.verified_role_id)
                
                if role:
                    await member.add_roles(role, reason="Aceitou as regras do servidor")
                    logger.info(f"Cargo de verificado atribuído a {member.name}")
                else:
                    logger.warning(f"Cargo de verificado não encontrado (ID: {self.verified_role_id})")
            else:
                logger.warning("ID do cargo de verificado não configurado")
        
        except Exception as e:
            logger.error(f"Erro ao conceder acesso a {member.name}: {e}")
    
    async def kick_member(self, member: discord.Member, reason: str):
        """Expulsar membro do servidor"""
        try:
            await member.kick(reason=reason)
            
            # Atualizar status no banco
            collection = db.get_collection('users')
            await collection.update_one(
                {'discord_id': str(member.id)},
                {'$set': {'is_active': False, 'updated_at': datetime.now()}}
            )
            
            logger.info(f"Membro {member.name} expulso: {reason}")
        
        except Exception as e:
            logger.error(f"Erro ao expulsar {member.name}: {e}")
    
    async def get_user_stats(self, discord_id: str) -> Optional[User]:
        """Obter estatísticas do usuário"""
        try:
            collection = db.get_collection('users')
            user_doc = await collection.find_one({'discord_id': discord_id})
            
            if user_doc:
                return User(user_doc)
            return None
        
        except Exception as e:
            logger.error(f"Erro ao buscar usuário {discord_id}: {e}")
            return None
