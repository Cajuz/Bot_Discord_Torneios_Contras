import random
import io
import discord
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CAPTCHA_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # sem 0,O,1,I,l


class CaptchaService:
    CODE_LENGTH  = 5
    MAX_ATTEMPTS = 3
    TIMEOUT_SECS = 120  # 2 minutos por tentativa

    @staticmethod
    def generate_code() -> str:
        return ''.join(random.choices(CAPTCHA_CHARS, k=CaptchaService.CODE_LENGTH))

    @staticmethod
    def generate_image(code: str) -> io.BytesIO:
        width, height = 280, 90
        bg_color = (
            random.randint(230, 255),
            random.randint(230, 255),
            random.randint(230, 255)
        )
        img  = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # Linhas de ruído
        for _ in range(8):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            color = (
                random.randint(80, 180),
                random.randint(80, 180),
                random.randint(80, 180)
            )
            draw.line([(x1, y1), (x2, y2)], fill=color, width=2)

        # Fonte
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48
            )
        except Exception:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
            except Exception:
                font = ImageFont.load_default()

        # Caracteres com posição e cor variadas
        x_offset = 10
        for char in code:
            color    = (
                random.randint(10, 80),
                random.randint(10, 80),
                random.randint(10, 80)
            )
            y_offset = random.randint(8, 28)
            draw.text((x_offset, y_offset), char, fill=color, font=font)
            x_offset += random.randint(48, 56)

        # Pontos de ruído
        for _ in range(300):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            draw.point((x, y), fill=(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            ))

        img    = img.filter(ImageFilter.GaussianBlur(radius=0.7))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

    # ── Embeds ────────────────────────────────────────────────────

    @staticmethod
    def get_captcha_embed(attempt: int, max_attempts: int) -> discord.Embed:
        embed = discord.Embed(
            title="🔐 Verificação CAPTCHA",
            description=(
                f"Para completar seu acesso, **digite o código** que aparece na imagem.\n\n"
                f"📌 **Instruções:**\n"
                f"• O código tem **{CaptchaService.CODE_LENGTH} caracteres** (letras e números)\n"
                f"• Não diferencia maiúsculas/minúsculas\n"
                f"• Você tem **{CaptchaService.TIMEOUT_SECS // 60} minutos** para responder\n\n"
                f"🔄 Tentativa **{attempt}/{max_attempts}**"
            ),
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://captcha.png")
        embed.set_footer(text="TSUKI-SERVER • Verificação automática")
        return embed

    @staticmethod
    def get_error_embed(attempts_left: int) -> discord.Embed:
        return discord.Embed(
            title="❌ Código Incorreto",
            description=(
                f"O código digitado não corresponde à imagem.\n\n"
                f"🔄 Tentativas restantes: **{attempts_left}**\n"
                f"Um novo CAPTCHA será enviado em instantes..."
            ),
            color=discord.Color.orange()
        )

    @staticmethod
    def get_success_embed() -> discord.Embed:
        return discord.Embed(
            title="✅ CAPTCHA Verificado!",
            description="Código correto! Liberando seu acesso...",
            color=discord.Color.green()
        )

    @staticmethod
    def get_timeout_embed() -> discord.Embed:
        return discord.Embed(
            title="⏰ Tempo Esgotado — CAPTCHA",
            description=(
                "Você não respondeu ao CAPTCHA dentro de **2 minutos**.\n"
                "Você foi removido automaticamente.\n\n"
                "Pode entrar no servidor novamente para tentar de novo."
            ),
            color=discord.Color.red()
        )

    @staticmethod
    def get_failed_embed() -> discord.Embed:
        return discord.Embed(
            title="🚫 Verificação Falhou",
            description=(
                "Você esgotou todas as **3 tentativas** do CAPTCHA.\n"
                "Você foi removido automaticamente.\n\n"
                "Pode entrar no servidor novamente para tentar de novo."
            ),
            color=discord.Color.red()
        )
