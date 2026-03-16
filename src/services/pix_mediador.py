import discord
from datetime import datetime
from utils.datetime_utils import utcnow
from typing import Dict, Any
from bson import ObjectId


class MediatorPix:

    def __init__(self, data: Dict[str, Any]):

        self._id = data.get("_id") if isinstance(data.get("_id"), ObjectId) else None

        self.discord_id = data.get("discord_id")
        self.username = data.get("username")

        self.pix_key = data.get("pix_key")

        self.created_at = data.get("created_at", utcnow())
        self.updated_at = data.get("updated_at", utcnow())

    # =========================
    # ATUALIZAR PIX
    # =========================

    def update_pix(self, pix_key: str):

        self.pix_key = pix_key
        self.updated_at = utcnow()

    # =========================
    # CONVERTER PARA DICT
    # =========================

    def to_dict(self) -> Dict[str, Any]:

        data = {
            "discord_id": self.discord_id,
            "username": self.username,
            "pix_key": self.pix_key,
            "created_at": self.created_at,
            "updated_at": utcnow()
        }

        if self._id:
            data["_id"] = self._id

        return data

    # =========================
    # CRIAR DOCUMENTO
    # =========================

    @staticmethod
    def create_document(discord_id: str, username: str, pix_key: str) -> Dict[str, Any]:

        now = utcnow()

        return {
            "discord_id": discord_id,
            "username": username,
            "pix_key": pix_key,
            "created_at": now,
            "updated_at": now
        }
    


class MediatorPixEmbed:

    @staticmethod
    def cadastro_pix():

        embed = discord.Embed(
            title="💳 Cadastro de Chave PIX",
            description=(
                "Este canal é usado para registrar sua **chave PIX** "
                "para receber pagamentos das mediações.\n\n"
                "⚠️ Apenas **mediadores ativos** podem cadastrar uma chave."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="📌 Como cadastrar",
            value=(
                "Use o comando:\n\n"
                "`!pix sua_chave`\n\n"
                "Exemplo:\n"
                "`!pix email@gmail.com`"
            ),
            inline=False
        )

        embed.add_field(
            name="🔄 Atualizar chave",
            value=(
                "Se você enviar o comando novamente, "
                "sua chave PIX será **atualizada automaticamente**."
            ),
            inline=False
        )

        embed.add_field(
            name="🔒 Segurança",
            value=(
                "Sua chave é armazenada no sistema do bot "
                "para ser utilizada no pagamento das mediações."
            ),
            inline=False
        )

        embed.set_footer(
            text="Sistema de Mediação"
        )

        return embed
    
import discord


class MediatorPixView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Cadastrar / Atualizar PIX",
        emoji="💳",
        style=discord.ButtonStyle.green,
        custom_id="mediator_pix_button"
    )
    async def cadastrar_pix(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(MediatorPixModal())


import discord


class MediatorPixModal(discord.ui.Modal, title="Cadastro de Chave PIX"):

    pix_key = discord.ui.TextInput(
        label="Digite sua chave PIX",
        placeholder="CPF, Email, Telefone ou Chave Aleatória",
        required=True,
        max_length=120
    )

    async def on_submit(self, interaction: discord.Interaction):

        pix = self.pix_key.value

        await interaction.response.send_message(
            f"✅ Sua chave PIX foi registrada:\n`{pix}`",
            ephemeral=True
        )