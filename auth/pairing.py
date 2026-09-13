import asyncio
import logging

from api.backend_client import backend_client
from config.settings import settings
from storage.local_state import LocalState

logger = logging.getLogger("core.pairing")

_POLL_INTERVAL_SECONDS = 5


async def ensure_paired(state: LocalState, telegram_user_id: int, core_version: str) -> None:
    """
    Core generates the code and shows it locally; the customer redeems it
    via Moon Bot using whichever Telegram account they normally talk to
    the bot with (not necessarily this one - see Backend's
    confirm_pairing docstring for why that's fine and how Duo's second
    account relies on it). This blocks, polling Backend, until that
    happens or the code expires.
    """
    if state.device_id is not None:
        device = await backend_client.get_device(state.device_id)
        if device["status"] == "active" and device.get("account_id"):
            state.account_id = device["account_id"]
            state.save()
            return
        # A previous run generated a code that was never redeemed or has
        # since expired - fall through and generate a fresh one below.

    init = await backend_client.pair_init(telegram_user_id, settings.DEVICE_NAME, core_version)
    state.device_id = init["device_id"]
    state.save()

    print(f"\n>>> Enter this code in Moon Bot to finish connecting: {init['pairing_code']}\n")
    logger.info("Waiting for pairing confirmation (code expires %s)", init["expires_at"])

    while True:
        device = await backend_client.get_device(state.device_id)
        if device["status"] == "active" and device.get("account_id"):
            state.account_id = device["account_id"]
            state.save()
            logger.info("Paired successfully - account_id=%s", state.account_id)
            return
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
