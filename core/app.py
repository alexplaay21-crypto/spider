import asyncio
import logging

from telethon import events
from telethon.tl import functions

from api.backend_client import backend_client
from auth.pairing import ensure_paired
from config.settings import settings
from core.command_processor import command_loop
from core.commands import handle_command
from core.version import CORE_VERSION
from module_manager.loader import load as load_module
from module_manager.manager import module_dir
from storage.local_state import LocalState
from storage.module_registry import ModuleRegistry
from telegram.client import build_client

logger = logging.getLogger("core.app")


async def _auto_subscribe_and_pin(client, state: LocalState) -> None:
    """
    The auto-subscribe+pin addition: after a successful login, make sure
    this account has actually opened a chat with Moon Bot (Bot API can't
    message an account that never messaged it first) and pin that chat -
    once, not on every run, so it doesn't fight the user if they unpin it
    themselves later.
    """
    if state.store_bot_pinned or not settings.STORE_BOT_USERNAME:
        return

    try:
        bot_entity = await client.get_entity(settings.STORE_BOT_USERNAME)

        history = await client.get_messages(bot_entity, limit=1)
        if not history:
            await client.send_message(bot_entity, "/start")

        input_peer = await client.get_input_entity(bot_entity)
        await client(functions.messages.ToggleDialogPinRequest(peer=input_peer, pinned=True))

        state.store_bot_pinned = True
        state.save()
        await backend_client.set_store_bot_pinned(state.account_id, True)
        logger.info("Opened and pinned the Moon Bot chat")
    except Exception:
        # This is a nice-to-have, not core functionality (same spirit as
        # section 26's module isolation) - never let it take Core down.
        # Covers e.g. Telegram's cap on pinned chats or a misconfigured
        # STORE_BOT_USERNAME.
        logger.exception("Could not auto-subscribe/pin Moon Bot - continuing without it")


async def _heartbeat_loop(state: LocalState) -> None:
    while True:
        try:
            snapshot = await backend_client.heartbeat(state.device_id, CORE_VERSION, "online")
            state.apply_entitlement(snapshot)
            state.save()
            logger.info("Heartbeat ok - plan=%s", snapshot["plan_code"])
        except Exception:
            # Section 48: Backend being briefly unreachable is not fatal -
            # keep using the last cached entitlement until it recovers.
            logger.warning("Heartbeat failed - using cached entitlement for now", exc_info=True)
        await asyncio.sleep(settings.HEARTBEAT_INTERVAL_SECONDS)


async def _load_installed_modules(registry: ModuleRegistry, client) -> None:
    """Reload whatever was enabled before Core last stopped (section 24:
    'running' is a real state that survives restarts, not just a status
    string)."""
    for entry in registry.all():
        if not entry.enabled:
            continue
        ok = await load_module(entry.module_id, module_dir(entry.module_id), client)
        if not ok:
            logger.warning("Module %s failed to reload on startup - left disabled", entry.module_id)


async def run() -> None:
    state = LocalState.load()
    registry = ModuleRegistry()
    client = await build_client()
    me = await client.get_me()
    logger.info("Logged in as %s (id=%s)", me.username or me.first_name, me.id)

    if state.device_id is None or state.account_id is None:
        await ensure_paired(state, me.id, CORE_VERSION)

    await _auto_subscribe_and_pin(client, state)
    await _load_installed_modules(registry, client)

    @client.on(events.NewMessage(outgoing=True))
    async def _on_own_message(event) -> None:
        if event.raw_text:
            await handle_command(event, state, registry, client)

    heartbeat_task = asyncio.create_task(_heartbeat_loop(state))
    commands_task = asyncio.create_task(command_loop(state, registry, client))
    logger.info("Moon Userbot is running (account_id=%s)", state.account_id)

    try:
        await client.run_until_disconnected()
    finally:
        heartbeat_task.cancel()
        commands_task.cancel()
        await backend_client.close()
