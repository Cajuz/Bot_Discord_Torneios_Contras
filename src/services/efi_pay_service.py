"""
 Renovação automática de mediadores via PIX Efí Pay.

SDK é OPCIONAL — o bot roda normalmente sem ele.
Para ativar: pip install efipay
"""
from __future__ import annotations
import hashlib
import os
from typing import Optional

from utils.datetime_utils import utcnow
from utils.logger import logger

try:
    from efipay import EfiPay
    _EFI_AVAILABLE = True
except ImportError:
    try:
        from gerencianet import Gerencianet as EfiPay
        _EFI_AVAILABLE = True
    except ImportError:
        _EFI_AVAILABLE = False
        logger.warning(
            "[EfiPay] SDK não instalado. Renovação automática desativada. "
            "Para ativar: pip install efipay"
        )


class EfiPayService:

    def __init__(self):
        self._client = None

    def is_available(self) -> bool:
        return _EFI_AVAILABLE and bool(os.getenv("EFI_CLIENT_ID"))

    def _get_client(self):
        if not _EFI_AVAILABLE:
            raise RuntimeError("SDK Efí Pay não instalado. Execute: pip install efipay")
        if self._client:
            return self._client
        sandbox = os.getenv("EFI_SANDBOX", "true").lower() == "true"
        self._client = EfiPay({
            "client_id":     os.getenv("EFI_CLIENT_ID", ""),
            "client_secret": os.getenv("EFI_CLIENT_SECRET", ""),
            "sandbox":       sandbox,
        })
        return self._client

    async def create_charge(
        self,
        mediator_id: str,
        value: float,
        plan_days: int = 30,
        description: str = "Renovação mediador",
    ) -> Optional[dict]:
        if not self.is_available():
            logger.warning("[EfiPay] SDK não disponível — cobrança não gerada.")
            return None
        from config.database import db
        try:
            gn      = self._get_client()
            pix_key = os.getenv("EFI_PIX_KEY", "")
            txid    = _make_txid(mediator_id)
            body = {
                "calendario": {"expiracao": 900},
                "devedor":    {},
                "valor":      {"original": f"{value:.2f}"},
                "chave":      pix_key,
                "infoAdicionais": [
                    {"nome": "mediador_id", "valor": mediator_id},
                    {"nome": "plan_days",   "valor": str(plan_days)},
                ],
            }
            result  = gn.pix_create_immediate_charge(params={"txid": txid}, body=body)
            loc_id  = result.get("loc", {}).get("id")
            qr_data = {}
            if loc_id:
                qr_data = gn.pix_generate_qrcode(params={"id": loc_id})

            charge = {
                "txid":       txid,
                "qr_code":    qr_data.get("imagemQrcode", ""),
                "copia_cola": qr_data.get("qrcode", ""),
                "status":     result.get("status", "ATIVA"),
                "value":      value,
                "plan_days":  plan_days,
            }
            await db.get_collection("mediator_renewals").update_one(
                {"txid": txid},
                {"$set": {
                    "mediator_id": mediator_id,
                    "txid":        txid,
                    "value":       value,
                    "plan_days":   plan_days,
                    "status":      "ATIVA",
                    "created_at":  utcnow(),
                }},
                upsert=True,
            )
            return charge
        except Exception as e:
            logger.error(f"[EfiPay] Erro ao criar cobrança: {e}")
            return None

    async def check_payment(self, txid: str) -> dict:
        if not self.is_available():
            return {"txid": txid, "status": "SDK_INDISPONIVEL", "pago": False}
        try:
            gn     = self._get_client()
            result = gn.pix_detail_immediate_charge(params={"txid": txid})
            status = result.get("status", "ATIVA")
            return {"txid": txid, "status": status, "pago": status == "CONCLUIDA"}
        except Exception as e:
            logger.error(f"[EfiPay] Erro ao consultar {txid}: {e}")
            return {"txid": txid, "status": "ERRO", "pago": False}

    async def confirm_renewal(self, txid: str) -> bool:
        """Confirma renovação no banco. Reseta expiry_notified para evitar DM duplicada."""
        from config.database import db
        from datetime import timedelta
        doc = await db.get_collection("mediator_renewals").find_one({"txid": txid})
        if not doc or doc.get("confirmed"):
            return False
        plan_days   = doc.get("plan_days", 30)
        mediator_id = doc.get("mediator_id")
        new_expiry  = utcnow() + timedelta(days=plan_days)
        await db.get_collection("mediators").update_one(
            {"user_id": int(mediator_id)},
            {"$set": {
                "expiration_date": new_expiry,
                "last_renewal_at": utcnow(),
                "renewal_price":   doc.get("value", 0),
                "is_active":       True,
                "expiry_notified": False,
            }}
        )
        await db.get_collection("mediator_renewals").update_one(
            {"txid": txid},
            {"$set": {"confirmed": True, "confirmed_at": utcnow()}}
        )
        return True


def _make_txid(mediator_id: str) -> str:
    raw = f"{mediator_id}{utcnow().timestamp()}"
    return hashlib.md5(raw.encode()).hexdigest()[:35]


efi_pay_service = EfiPayService()