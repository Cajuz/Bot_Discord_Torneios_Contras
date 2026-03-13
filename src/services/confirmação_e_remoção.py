import discord
from datetime import datetime, timedelta
from utils.logger import logger



class ConfirmMediatorService:

    def __init__(self, db, mediator_role_name):
        self.db = db
        self.mediator_role_name = mediator_role_name
        self.payment_collection = db.get_collection("payment_confirmations")
        self.mediator_collection = db.get_collection("mediators")

    async def confirm(self, ctx, membro: discord.Member):

        guild = ctx.guild
        cargo_mediador = discord.utils.get(guild.roles, name=self.mediator_role_name)

        if not cargo_mediador:
            await ctx.send(f"❌ Cargo `{self.mediator_role_name}` não encontrado.")
            return

        benefit_days = 7
        confirmation_date = datetime.utcnow()
        expires_at = confirmation_date + timedelta(days=benefit_days)

        # =========================
        # CONFIRMAR PAGAMENTO
        # =========================

        await self.payment_collection.update_one(
            {"discord_id": str(membro.id)},
            {
                "$set": {
                    "discord_id": str(membro.id),
                    "username": membro.name,
                    "plan": "semanal",
                    "benefit_days": benefit_days,
                    "confirmation_date": confirmation_date,
                    "expires_at": expires_at,
                    "confirmed_by_admin": str(ctx.author),
                    "active": True
                }
            },
            upsert=True
        )

        # =========================
        # CRIAR MEDIADOR
        # =========================

        mediator_exists = await self.mediator_collection.find_one(
            {"discord_id": str(membro.id)}
        )

        if not mediator_exists:

            await self.mediator_collection.insert_one({
                "discord_id": str(membro.id),
                "username": membro.name,
                "created_at": confirmation_date,
                "is_active": True
            })

        # =========================
        # DAR CARGO
        # =========================

        if cargo_mediador not in membro.roles:

            try:
                await membro.add_roles(
                    cargo_mediador,
                    reason=f"Aprovado por {ctx.author}"
                )

            except discord.Forbidden:
                await ctx.send("❌ Não foi possível adicionar o cargo.")
                return

        await ctx.send(f"✅ {membro.mention} agora é um mediador.")

class RemoveMediatorService:

    def __init__(self, db, mediator_role_name):
        self.db = db
        self.mediator_role_name = mediator_role_name
        self.payment_collection = db.get_collection("payment_confirmations")
        self.mediator_collection = db.get_collection("mediators")

    async def remove(self, ctx, membro: discord.Member):

        guild = ctx.guild
        cargo_mediador = discord.utils.get(guild.roles, name=self.mediator_role_name)

        if not cargo_mediador:
            await ctx.send(f"❌ Cargo `{self.mediator_role_name}` não encontrado.")
            return

        cargo_msg = ""

        # =========================
        # REMOVER CARGO
        # =========================

        if cargo_mediador in membro.roles:

            try:

                await membro.remove_roles(
                    cargo_mediador,
                    reason=f"Removido por {ctx.author}"
                )

                cargo_msg = f"✅ Cargo removido de {membro.mention}"

            except discord.Forbidden:

                cargo_msg = "❌ Não tenho permissão para remover o cargo."

            except Exception as e:

                cargo_msg = f"❌ Erro ao remover cargo: {e}"

        else:

            cargo_msg = f"⚠️ {membro.mention} não possui cargo de mediador."

        # =========================
        # ATUALIZAR BANCO
        # =========================

        result_payment = await self.payment_collection.update_one(
            {"discord_id": str(membro.id)},
            {"$set": {"active": False}}
        )

        result_mediator = await self.mediator_collection.update_one(
            {"discord_id": str(membro.id)},
            {"$set": {"is_active": False}}
        )

        logger.info(
            f"Mediador removido: {membro.id} | payment:{result_payment.modified_count} mediator:{result_mediator.modified_count}"
        )

        await ctx.send(
            f"{cargo_msg}\n✅ Status do mediador atualizado no banco."
        )

        # =========================
        # DM PARA USUÁRIO
        # =========================

        try:

            await membro.send(
                "❌ Seu cargo de mediador foi removido e seu plano foi desativado."
            )

        except discord.Forbidden:

            logger.warning(f"Não foi possível enviar DM para {membro.id}")