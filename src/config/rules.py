import discord


class ServerRules:
    """Configuração das regras do servidor"""

    RULES_TITLE = "📜 Regras do Servidor — TSUKI-SERVER"

    RULES_TEXT = """
**Bem-vindo(a) ao TSUKI-SERVER!**

Leia com atenção antes de entrar no servidor.

**1️⃣ Respeito Mútuo**
• Trate todos com respeito
• Não toleramos discriminação, racismo ou assédio
• Mantenha um ambiente saudável e amigável

**2️⃣ Comunicação**
• Use os canais certos para cada assunto
• Sem spam, flood ou mensagens repetitivas
• Não use CAPS LOCK excessivamente

**3️⃣ Partidas e Mediação**
• Respeite as decisões dos mediadores
• Não abandone partidas sem aviso prévio
• Jogue de forma justa e honesta
• Pague e receba prêmios dentro do tópico da partida

**4️⃣ Conteúdo Proibido**
• Sem conteúdo NSFW
• Proibido links suspeitos ou maliciosos
• Sem propaganda sem autorização da staff

**5️⃣ Punições**
• Avisos → Mute → Kick → Ban
• Infrações graves resultam em ban imediato
• Todos os casos são analisados pela staff

**6️⃣ Suporte**
• Use o canal de suporte para dúvidas
• Seja claro e objetivo ao pedir ajuda

**━━━━━━━━━━━━━━━━━━━━━━━━**

Ao clicar em **✅ Aceito as Regras** você concorda com todas as diretrizes acima.

> ⏰ Você tem **5 minutos** para aceitar.
> Após esse tempo, você será removido automaticamente.
"""

    CONFIRMATION_TITLE = "⚠️ Tem certeza que não aceita?"
    CONFIRMATION_TEXT = """
**Você está prestes a recusar as regras.**

Caso não aceite, **você será expulso automaticamente** do servidor.

O que deseja fazer?
"""

    WELCOME_TITLE = "✅ Bem-vindo(a) ao TSUKI-SERVER!"
    WELCOME_TEXT = """
**Parabéns! Você agora é um Membro oficial!**

🎮 **Canais Disponíveis:**
• Canais de partidas por modo e plataforma
• `#chat` — Conversa geral
• `#suporte` — Tire suas dúvidas
• `#avisos` — Fique por dentro das novidades

📋 **Comandos Úteis:**
• `!help` — Ver todos os comandos
• `!perfil` — Ver seu perfil

**Boa sorte nas partidas!** 🏆
"""

    @staticmethod
    def get_rules_embed() -> discord.Embed:
        embed = discord.Embed(
            title=ServerRules.RULES_TITLE,
            description=ServerRules.RULES_TEXT,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Leia com atenção • Você tem 5 minutos para aceitar")
        return embed

    @staticmethod
    def get_confirmation_embed() -> discord.Embed:
        embed = discord.Embed(
            title=ServerRules.CONFIRMATION_TITLE,
            description=ServerRules.CONFIRMATION_TEXT,
            color=discord.Color.red()
        )
        embed.set_footer(text="Esta ação é irreversível")
        return embed

    @staticmethod
    def get_welcome_embed(member: discord.Member) -> discord.Embed:
        embed = discord.Embed(
            title=ServerRules.WELCOME_TITLE,
            description=ServerRules.WELCOME_TEXT,
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Membro desde {discord.utils.utcnow().strftime('%d/%m/%Y')}")
        return embed
