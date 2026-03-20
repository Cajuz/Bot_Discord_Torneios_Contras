import discord
import asyncio
from utils.logger import logger
from services.channel_service import LOGS_TROCA_CARGO_CHANNEL



class Troca_cargo:
    def __init__(self ,bot):
        self.bot = bot
    async def send_on_troca_cargo(self, before: discord.Member, after: discord.Member):
        logger.info(f"[CARGO] Detectado | user={after.id}")
        if not after.guild:
            return
        canal = discord.utils.find(
            lambda c: (
                isinstance(c, discord.TextChannel) and
                c.name.lower().strip() == LOGS_TROCA_CARGO_CHANNEL.lower().strip()),after.guild.channels
        )
        if not canal:
            logger.warning("[CARGO] Canal não encontrado")
            return
        try:
            cargos_adicionados = [
                r for r in after.roles
                if r not in before.roles and r.name != "@everyone"
            ]
            cargos_removidos = [
                r for r in before.roles
                if r not in after.roles and r.name != "@everyone"
            ]
            if not cargos_adicionados and not cargos_removidos:
                return
            await asyncio.sleep(1)
            executor = after  
            try:
                async for entry in after.guild.audit_logs(
                    limit=5,
                    action=discord.AuditLogAction.member_role_update
                ):
                    if not entry.target:
                        continue
                    if entry.target.id == after.id:
                        executor = entry.user
                        break
            except Exception as e:
                logger.warning(f"[CARGO] Falha audit log: {e}")
            timestamp = int(discord.utils.utcnow().timestamp())
            embed = discord.Embed(title="Alteração de Cargos",color=0x2b2d31)
            embed.add_field(name="👤 Usuário",value=after.mention,inline=True)
            embed.add_field(name="🛠️ Responsável",value=executor.mention if executor else "Desconhecido",inline=True)
            if cargos_adicionados:
                embed.add_field(name="🟢 Cargos Adicionados",value="\n".join(r.mention for r in cargos_adicionados)[:1024],inline=False)
            if cargos_removidos:embed.add_field(name="🔴 Cargos Removidos",value="\n".join(r.mention for r in cargos_removidos)[:1024],inline=False)
            embed.add_field(name="⏰ Data",value=f"<t:{timestamp}:F>",inline=True)
            embed.set_thumbnail(url=after.display_avatar.url)
            embed.set_footer(text="Sistema de Logs • Cargos")
            await canal.send(embed=embed)
            logger.info("[CARGO] Log enviado com sucesso")
        except Exception as e:
            logger.error(f"[CARGO] Erro geral: {e}")








def build_troca_cargo_log_embed():
    embed = discord.Embed(
        title="Troca de Cargo",description=("Todas as alterações de cargo serão registradas aqui.\n\n"),
        color=0x2b2d31)
    embed.add_field(
        name= "Registro troca de cargo",
        value=("• Adição de cargos\n""• Remoção de cargos\n""• Usuário afetado\n"
               "• Responsável pela ação\n""• Data e hora"),inline=False)
    embed.set_footer(text="Sistema de Logs • Cargo")
    return embed
