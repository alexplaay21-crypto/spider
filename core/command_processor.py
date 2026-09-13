import asyncio
import logging

from api.backend_client import backend_client
from module_manager import manager as module_manager
from storage.local_state import LocalState
from storage.module_registry import ModuleRegistry

logger = logging.getLogger("core.command_processor")

_POLL_INTERVAL_SECONDS = 10


async def _execute(command: dict, state: LocalState, registry: ModuleRegistry, client) -> None:
    command_type = command["type"]
    module_id = (command.get("payload") or {}).get("module_id")

    try:
        if command_type == "install_module":
            await module_manager.install(state, registry, client, module_id)
        elif command_type == "uninstall_module":
            await module_manager.remove(state, registry, module_id)
        elif command_type == "enable_module":
            await module_manager.enable(state, registry, client, module_id)
        elif command_type == "disable_module":
            await module_manager.disable(state, registry, module_id)
        elif command_type == "update_module":
            await module_manager.update(state, registry, client, module_id)
        else:
            logger.warning("Unknown command type %s", command_type)
            await backend_client.complete_command(command["id"], "failed")
            return
        await backend_client.complete_command(command["id"], "success")
    except Exception:
        logger.exception("Command %s (%s) failed", command["id"], command_type)
        try:
            await backend_client.complete_command(command["id"], "failed")
        except Exception:
            logger.exception("Could not even report command %s as failed", command["id"])


async def command_loop(state: LocalState, registry: ModuleRegistry, client) -> None:
    while True:
        try:
            commands = await backend_client.pending_commands(state.account_id)
            for command in commands:
                await _execute(command, state, registry, client)
        except Exception:
            logger.warning("Command poll failed - will retry", exc_info=True)
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
