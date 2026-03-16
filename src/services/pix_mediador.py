import discord
from typing import Dict, Any
from bson import ObjectId

from config.database import db
from utils.datetime_utils import utcnow


class MediatorPix:
    def __init__(self, data: Dict[str, Any]):
        self._id = data.get("_id") if isinstance(data.get("_id"), ObjectId) else None
        self.discord_id = data.get("discord_id")
        self.username = data.get("username")
        self.pix_key = data.get("pix_key")
        self.created_at = data.get("created_at", utcnow())
        self.updated_at = data.get("updated_at", utcnow())

    def update_pix(self, pix_key: str):
        self.pix_key = pix_key
        self.updated_at = utcnow()

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "discord_id": self.discord_id,
            "username": self.username,
            "pix_key": self.pix_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self._id:
            data["_id"] = self._id
        return data

    @staticmethod
    def create_document(discord_id: str, username: str, pix_key: str) -> Dict[str, Any]:
        now = utcnow()
        return {
            "discord_id": discord_id,
            "username": username,
            "pix_key": pix_key,
            "created_at": now,
            "updated_at": now,
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
                "Use o botão abaixo para cadastrar ou atualizar sua chave PIX."
            ),
            inline=False
        )

        embed.add_field(
            name="🔄 Atualizar chave",
            value=(
                "Se você enviar novamente, sua chave PIX será **atualizada automaticamente**."
            ),
            inline=False
        )

        embed.add_field(
            name="🔒 Segurança",
            value=(
                "Sua chave é armazenada no sistema do bot para ser utilizada no pagamento das mediações."
            ),
            inline=False
        )

        embed.set_footer(text="Sistema de Mediação")
        return embed


class MediatorPixModal(discord.ui.Modal, title="Cadastro de Chave PIX"):
    pix_key = discord.ui.TextInput(
        label="Digite sua chave PIX",
        placeholder="CPF, Email, Telefone ou Chave Aleatória",
        required=True,
        max_length=120
    )

    async def on_submit(self, interaction: discord.Interaction):
        pix = self.pix_key.value.strip()

        allowed_roles = {"Controller", "Mediador", "Mediator", "Admin"}
        user_role_names = {role.name for role in interaction.user.roles}

        if not user_role_names.intersection(allowed_roles):
            await interaction.response.send_message(
                "❌ Apenas mediadores ativos ou administradores podem cadastrar uma chave PIX.",
                ephemeral=True
            )
            return

        collection = db.get_collection("mediator_pix")
        now = utcnow()

        existing = await collection.find_one({"discord_id": str(interaction.user.id)})

        if existing:
            await collection.update_one(
                {"discord_id": str(interaction.user.id)},
                {
                    "$set": {
                        "username": str(interaction.user),
                        "pix_key": pix,
                        "updated_at": now,
                    }
                }
            )
            message = f"✅ Sua chave PIX foi atualizada com sucesso:\n`{pix}`"
        else:
            doc = MediatorPix.create_document(
                discord_id=str(interaction.user.id),
                username=str(interaction.user),
                pix_key=pix,
            )
            await collection.insert_one(doc)
            message = f"✅ Sua chave PIX foi cadastrada com sucesso:\n`{pix}`"

        await interaction.response.send_message(message, ephemeral=True)


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
