"""
mediator_register_view.py  v3

Fluxo:
  1. Apenas ADM ou Suporte clicam em "Cadastrar Mediador"
  2. STEP 1 — Modal: nome, doc (CPF ou RG), data nascimento, telefone, chave PIX
  3. STEP 2 — Modal: endereço (opcional), URL comprovante de pagamento (obrigatório),
                       URL contrato (opcional)
  4. Submissão final → salva banco + embed revisão em #aprovar-mediadores
  5. ADM Aprova → cargo Controller + registro em mediators (30 dias)
          ou Reprova → modal de motivo → DM ao candidato

Nota Discord: máximo 5 campos por modal → 2 modais encadeados.
"""
from __future__ import annotations

import re
import discord
from utils.datetime_utils import utcnow
from utils.logger import logger

THEME_COLOR     = 0xFFD54F
APROVAR_CHANNEL = "aprovar-mediadores"
CONTROLLER_ROLE = "Controller"
_ALLOWED_ROLES  = {"ADM", "Suporte"}

_RE_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


# ═══════════════════════════════════════════════════════════════
# View persistente — card fixo no canal de cadastro
# ═══════════════════════════════════════════════════════════════

class MediatorRegisterView(discord.ui.View):
    """Card fixo em #solicitacoes-mediador. Persiste entre reinicializações."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 Cadastrar Mediador",
        style=discord.ButtonStyle.secondary,
        custom_id="mediator_register:open_form",
    )
    async def open_form(self, interaction: discord.Interaction, _: discord.ui.Button):
        role_names = {r.name for r in interaction.user.roles}
        is_adm     = interaction.user.guild_permissions.administrator
        if not is_adm and not (role_names & _ALLOWED_ROLES):
            await interaction.response.send_message(
                "❌ Apenas **ADM** ou **Suporte** podem abrir o formulário de cadastro.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(_MediatorRegisterStep1())


# ═══════════════════════════════════════════════════════════════
# STEP 1 — dados pessoais (5 campos)
#   1. Nome completo         (obrigatório)
#   2. CPF ou RG             (obrigatório)
#   3. Data de nascimento    (obrigatório) — DD/MM/AAAA
#   4. Telefone / WhatsApp   (obrigatório)
#   5. Chave PIX             (obrigatório)
# ═══════════════════════════════════════════════════════════════

class _MediatorRegisterStep1(discord.ui.Modal, title="Cadastro de Mediador — Dados (1/2)"):

    nome_completo = discord.ui.TextInput(
        label="Nome completo *",
        placeholder="Ex: João da Silva",
        min_length=3,
        max_length=100,
        required=True,
    )
    documento = discord.ui.TextInput(
        label="CPF ou RG *",
        placeholder="CPF: 000.000.000-00  ou  RG: 00.000.000-0",
        min_length=8,
        max_length=20,
        required=True,
    )
    data_nascimento = discord.ui.TextInput(
        label="Data de nascimento * (DD/MM/AAAA)",
        placeholder="Ex: 15/03/1995",
        min_length=10,
        max_length=10,
        required=True,
    )
    telefone = discord.ui.TextInput(
        label="Telefone / WhatsApp *",
        placeholder="Ex: (11) 99999-8888",
        min_length=8,
        max_length=20,
        required=True,
    )
    chave_pix = discord.ui.TextInput(
        label="Chave PIX *",
        placeholder="CPF / e-mail / telefone / chave aleatória",
        min_length=5,
        max_length=150,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Valida data
        if not _RE_DATE.match(self.data_nascimento.value.strip()):
            await interaction.response.send_message(
                "❌ Data de nascimento inválida. Use o formato **DD/MM/AAAA**.",
                ephemeral=True,
            )
            return

        # Guarda dados do step 1 e abre step 2
        await interaction.response.send_modal(
            _MediatorRegisterStep2(
                nome=self.nome_completo.value.strip(),
                documento=self.documento.value.strip(),
                data_nasc=self.data_nascimento.value.strip(),
                telefone=self.telefone.value.strip(),
                pix=self.chave_pix.value.strip(),
            )
        )


# ═══════════════════════════════════════════════════════════════
# STEP 2 — endereço + documentos (3 campos ativos)
#   1. Endereço completo              (opcional)
#   2. URL comprovante de pagamento   (obrigatório)
#   3. URL contrato assinado          (opcional)
# ═══════════════════════════════════════════════════════════════

class _MediatorRegisterStep2(discord.ui.Modal, title="Cadastro de Mediador — Documentos (2/2)"):

    endereco = discord.ui.TextInput(
        label="Endereço completo (opcional)",
        placeholder="Rua, número, bairro, cidade — UF, CEP",
        max_length=300,
        required=False,
        style=discord.TextStyle.paragraph,
    )
    comprovante_url = discord.ui.TextInput(
        label="Link do comprovante de pagamento *",
        placeholder="Google Drive, Imgur, Gyazo — link público",
        min_length=10,
        max_length=500,
        required=True,
    )
    contrato_url = discord.ui.TextInput(
        label="Link do contrato assinado (opcional)",
        placeholder="Google Drive, DocuSign — link público",
        max_length=500,
        required=False,
    )

    def __init__(
        self,
        nome: str,
        documento: str,
        data_nasc: str,
        telefone: str,
        pix: str,
    ):
        super().__init__()
        # Dados vindos do step 1
        self._nome      = nome
        self._documento = documento
        self._data_nasc = data_nasc
        self._telefone  = telefone
        self._pix       = pix

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild  = interaction.guild
        author = interaction.user

        # ── Monta payload completo ────────────────────────────
        payload = {
            "registered_by":  str(author.id),
            "nome_completo":  self._nome,
            "documento":      self._documento,
            "data_nascimento": self._data_nasc,
            "telefone":       self._telefone,
            "chave_pix":      self._pix,
            "endereco":       self.endereco.value.strip() or None,
            "comprovante":    self.comprovante_url.value.strip(),
            "contrato":       self.contrato_url.value.strip() or None,
            "status":         "pendente",
            "submitted_at":   utcnow(),
        }

        # ── Salva/atualiza no banco (chave única = documento) ──
        try:
            from config.database import db
            await db.get_collection("mediator_applications").update_one(
                {"documento": self._documento},
                {"$set": payload},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"[MediatorRegister] DB error: {e}")

        # ── Embed de revisão para #aprovar-mediadores ──────────
        review_embed = discord.Embed(
            title="🆕  Nova Candidatura — Mediador",
            description=f"Cadastro realizado por {author.mention}.",
            color=THEME_COLOR,
            timestamp=utcnow(),
        )
        review_embed.add_field(name="Nome completo",       value=self._nome,                              inline=False)
        review_embed.add_field(name="CPF / RG",            value=f"||{self._documento}||",                inline=True)
        review_embed.add_field(name="Data de nascimento",  value=self._data_nasc,                         inline=True)
        review_embed.add_field(name="Telefone",            value=self._telefone,                          inline=True)
        review_embed.add_field(name="Chave PIX",           value=self._pix,                               inline=True)
        review_embed.add_field(
            name="Endereço",
            value=self.endereco.value.strip() or "*Não informado*",
            inline=False,
        )
        review_embed.add_field(
            name="Comprovante de pagamento",
            value=f"[🔗 Ver comprovante]({self.comprovante_url.value.strip()})",
            inline=True,
        )
        contrato_val = (
            f"[🔗 Ver contrato]({self.contrato_url.value.strip()})"
            if self.contrato_url.value.strip()
            else "*Não enviado*"
        )
        review_embed.add_field(name="Contrato", value=contrato_val, inline=True)
        review_embed.add_field(name="Registrado por", value=author.mention, inline=False)
        review_embed.set_footer(text="Use os botões abaixo para Aprovar ou Reprovar")

        ch = discord.utils.get(guild.text_channels, name=APROVAR_CHANNEL)
        if ch:
            await ch.send(
                embed=review_embed,
                view=_MediatorApprovalView(documento=self._documento),
            )
        else:
            logger.warning(f"[MediatorRegister] Canal #{APROVAR_CHANNEL} não encontrado.")

        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ Candidatura registrada!",
                description="O ADM foi notificado para revisão e aprovação.",
                color=0x27AE60,
            ),
            ephemeral=True,
        )


# ═══════════════════════════════════════════════════════════════
# View de aprovação — canal #aprovar-mediadores
# ═══════════════════════════════════════════════════════════════

class _MediatorApprovalView(discord.ui.View):

    def __init__(self, documento: str, discord_id: int | None = None):
        super().__init__(timeout=None)
        self.documento  = documento
        self.discord_id = discord_id

    @discord.ui.button(
        label="✅ Aprovar",
        style=discord.ButtonStyle.success,
        custom_id="mediator_register:approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return
        await interaction.response.send_modal(
            _ApproveDiscordModal(documento=self.documento, approval_view=self)
        )

    @discord.ui.button(
        label="❌ Reprovar",
        style=discord.ButtonStyle.danger,
        custom_id="mediator_register:reject",
    )
    async def reject(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Sem permissão.", ephemeral=True)
            return
        await interaction.response.send_modal(
            _RejectReasonModal(documento=self.documento, approval_view=self)
        )


class _ApproveDiscordModal(discord.ui.Modal, title="Aprovar Mediador — Informe o Discord ID"):

    discord_id_input = discord.ui.TextInput(
        label="Discord ID do mediador",
        placeholder="Ex: 123456789012345678",
        min_length=15,
        max_length=20,
        required=True,
    )

    def __init__(self, documento: str, approval_view: _MediatorApprovalView):
        super().__init__()
        self.documento     = documento
        self.approval_view = approval_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            uid = int(self.discord_id_input.value.strip())
        except ValueError:
            await interaction.followup.send("Discord ID inválido.", ephemeral=True)
            return

        guild  = interaction.guild
        member = guild.get_member(uid) or await guild.fetch_member(uid)

        role = discord.utils.get(guild.roles, name=CONTROLLER_ROLE)
        if member and role:
            try:
                await member.add_roles(role, reason=f"Aprovado por {interaction.user}")
            except discord.Forbidden:
                pass

        try:
            from config.database import db
            from datetime import timedelta
            now = utcnow()

            # Busca candidatura para pegar todos os dados
            app = await db.get_collection("mediator_applications").find_one(
                {"documento": self.documento}
            )

            await db.get_collection("mediator_applications").update_one(
                {"documento": self.documento},
                {
                    "$set": {
                        "user_id":     str(uid),
                        "username":    str(member) if member else str(uid),
                        "status":      "aprovado",
                        "approved_by": str(interaction.user),
                        "approved_at": now,
                    }
                },
            )

            # Cria/atualiza mediator com todos os campos do formulário
            mediator_payload = {
                "user_id":          uid,
                "username":         str(member) if member else str(uid),
                "documento":        self.documento,
                "is_active":        True,
                "in_queue":         False,
                "expiration_date":  now + timedelta(days=30),
                "updated_at":       now,
            }
            if app:
                mediator_payload.update({
                    "nome_completo":   app.get("nome_completo"),
                    "data_nascimento": app.get("data_nascimento"),
                    "telefone":        app.get("telefone"),
                    "chave_pix":       app.get("chave_pix"),
                    "endereco":        app.get("endereco"),
                    "comprovante":     app.get("comprovante"),
                    "contrato":        app.get("contrato"),
                })

            await db.get_collection("mediators").update_one(
                {"user_id": uid},
                {"$set": mediator_payload},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"[MediatorApproval] DB error: {e}")

        if member:
            try:
                await member.send(embed=discord.Embed(
                    title="🎉 Você foi aprovado como Mediador!",
                    description=(
                        "Bem-vindo à equipe **X1 Frifas**!\n"
                        f"O cargo **{CONTROLLER_ROLE}** foi atribuído à sua conta.\n\n"
                        "Fique atento ao canal de renovação para manter sua licença ativa."
                    ),
                    color=0x27AE60,
                ))
            except discord.Forbidden:
                pass

        for b in self.approval_view.children:
            b.disabled = True
        await interaction.message.edit(
            embed=interaction.message.embeds[0].set_footer(
                text=f"✅ Aprovado por {interaction.user} | Discord: {uid} | "
                     f"{utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
            ),
            view=self.approval_view,
        )


class _RejectReasonModal(discord.ui.Modal, title="Motivo da Reprovação"):

    motivo = discord.ui.TextInput(
        label="Motivo",
        placeholder="Descreva brevemente o motivo da reprovação",
        style=discord.TextStyle.paragraph,
        min_length=5,
        max_length=300,
    )
    discord_id_input = discord.ui.TextInput(
        label="Discord ID do candidato (para DM)",
        placeholder="Ex: 123456789012345678 — deixe vazio se não souber",
        required=False,
        max_length=20,
    )

    def __init__(self, documento: str, approval_view: _MediatorApprovalView):
        super().__init__()
        self.documento     = documento
        self.approval_view = approval_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        try:
            from config.database import db
            await db.get_collection("mediator_applications").update_one(
                {"documento": self.documento},
                {
                    "$set": {
                        "status":        "reprovado",
                        "rejected_by":   str(interaction.user),
                        "reject_reason": self.motivo.value.strip(),
                        "rejected_at":   utcnow(),
                    }
                },
            )
        except Exception as e:
            logger.error(f"[MediatorReject] DB error: {e}")

        raw_id = self.discord_id_input.value.strip()
        if raw_id:
            try:
                uid    = int(raw_id)
                member = interaction.guild.get_member(uid) or await interaction.guild.fetch_member(uid)
                if member:
                    await member.send(embed=discord.Embed(
                        title="Candidatura Reprovada — X1 Frifas",
                        description=(
                            "Infelizmente sua candidatura para mediador **não foi aprovada**.\n\n"
                            f"**Motivo:** {self.motivo.value.strip()}\n\n"
                            "Em caso de dúvidas, entre em contato com a administração."
                        ),
                        color=0xE74C3C,
                    ))
            except Exception:
                pass

        for b in self.approval_view.children:
            b.disabled = True
        await interaction.message.edit(
            embed=interaction.message.embeds[0].set_footer(
                text=f"❌ Reprovado por {interaction.user} | "
                     f"{utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
            ),
            view=self.approval_view,
        )
