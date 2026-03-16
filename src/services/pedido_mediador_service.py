from datetime import datetime
from utils.datetime_utils import utcnow


class MediatorManager:
    def __init__(self, db, mediator_role_name=None, benefit_days: int = 7):
        self.db = db

        if isinstance(mediator_role_name, int):
            self.mediator_role_name = None
            self.benefit_days = mediator_role_name
        else:
            self.mediator_role_name = mediator_role_name
            self.benefit_days = benefit_days

        self.payment_collection = db.get_collection("payment_confirmations")
        self.mediator_collection = db.get_collection("mediators")

    async def get_active_mediators(self):
        mediators = []

        cursor = self.payment_collection.find({
            "confirmation_date": {"$ne": None},
            "active": True
        })

        async for mediator in cursor:
            mediators.append(mediator)

        return mediators

    def calculate_days_remaining(self, mediator):
        reference_date = (
            mediator.get("confirmation_date")
            or mediator.get("role_received_date")
        )

        if not reference_date:
            return 0

        if isinstance(reference_date, str):
            reference_date = datetime.fromisoformat(reference_date)

        elapsed_days = (utcnow() - reference_date).days
        remaining_days = self.benefit_days - elapsed_days
        return max(remaining_days, 0)

    async def get_mediators_with_days(self):
        mediator_list = []
        mediators = await self.get_active_mediators()

        for mediator in mediators:
            days_remaining = self.calculate_days_remaining(mediator)

            mediator_list.append({
                "username": mediator.get("username"),
                "discord_id": mediator.get("discord_id"),
                "days_remaining": days_remaining
            })

        return mediator_list

    async def expire_mediators(self):
        mediators = await self.get_active_mediators()

        for mediator in mediators:
            days_remaining = self.calculate_days_remaining(mediator)

            if days_remaining <= 0:
                discord_id = mediator.get("discord_id")

                await self.payment_collection.update_one(
                    {"discord_id": discord_id},
                    {"$set": {"active": False, "updated_at": utcnow()}}
                )

                await self.mediator_collection.update_one(
                    {"discord_id": discord_id},
                    {"$set": {"is_active": False, "updated_at": utcnow()}}
                )

    async def count_active_mediators(self):
        return await self.payment_collection.count_documents({
            "confirmation_date": {"$ne": None},
            "active": True
        })
