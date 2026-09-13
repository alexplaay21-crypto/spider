import logging

from module_manager import manager as module_manager
from storage.local_state import LocalState
from storage.module_registry import ModuleRegistry

logger = logging.getLogger("core.commands")


async def handle_command(event, state: LocalState, registry: ModuleRegistry, client) -> None:
    text = event.raw_text.strip()
    if not text:
        return

    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""

    if command == "help":
        await event.edit(_help_text())
    elif command == "modules":
        await _cmd_modules(event, registry)
    elif command == "install":
        await _cmd_install(event, state, registry, client, argument)
    elif command == "uninstall":
        await _cmd_uninstall(event, state, registry, argument)
    elif command == "enable":
        await _cmd_enable(event, state, registry, client, argument)
    elif command == "disable":
        await _cmd_disable(event, state, registry, argument)
    elif command == "update":
        await _cmd_update(event, state, registry, client, argument)
    elif command == "restart":
        await event.edit("🔄 Restarting is not wired up yet in this stage.")


def _help_text() -> str:
    return (
        "Moon Userbot\n\n"
        "help — this message\n"
        "modules — list installed modules\n"
        "install <module_id> — install an official module\n"
        "uninstall <module_id>\n"
        "enable <module_id> / disable <module_id>\n"
        "update <module_id>\n"
    )


async def _cmd_modules(event, registry: ModuleRegistry) -> None:
    installed = registry.all()
    if not installed:
        await event.edit("📦 No modules installed yet.")
        return
    lines = ["📦 Installed modules:\n"]
    for m in installed:
        mark = "🟢" if m.enabled else "🔴"
        lines.append(f"{mark} {m.module_id} v{m.version}")
    await event.edit("\n".join(lines))


async def _cmd_install(event, state: LocalState, registry: ModuleRegistry, client, module_id: str) -> None:
    if not module_id:
        await event.edit("Usage: `install <module_id>`")
        return
    await event.edit(f"⏳ Installing {module_id}...")
    try:
        await module_manager.install(state, registry, client, module_id)
    except module_manager.ModuleManagerError as exc:
        await event.edit(f"❌ Could not install {module_id}: {exc}")
        return
    except Exception:
        logger.exception("Unexpected error installing %s", module_id)
        await event.edit(f"❌ Could not install {module_id} (see logs).")
        return
    await event.edit(f"✅ {module_id} installed and running.")


async def _cmd_uninstall(event, state: LocalState, registry: ModuleRegistry, module_id: str) -> None:
    if not module_id:
        await event.edit("Usage: `uninstall <module_id>`")
        return
    try:
        await module_manager.remove(state, registry, module_id)
    except module_manager.ModuleManagerError as exc:
        await event.edit(f"❌ Could not uninstall {module_id}: {exc}")
        return
    except Exception:
        logger.exception("Unexpected error uninstalling %s", module_id)
        await event.edit(f"❌ Could not uninstall {module_id} (see logs).")
        return
    await event.edit(f"✅ {module_id} uninstalled.")


async def _cmd_enable(event, state: LocalState, registry: ModuleRegistry, client, module_id: str) -> None:
    if not module_id:
        await event.edit("Usage: `enable <module_id>`")
        return
    try:
        entry = registry.get(module_id)
        if not entry:
            await event.edit(f"❌ Module {module_id} is not installed.")
            return
        entry.enabled = True
        registry.save()
        await module_manager.enable(state, registry, client, module_id)
        await event.edit(f"🟢 {module_id} enabled.")
    except Exception:
        logger.exception("Unexpected error enabling %s", module_id)
        await event.edit(f"❌ Could not enable {module_id}.")


async def _cmd_disable(event, state: LocalState, registry: ModuleRegistry, module_id: str) -> None:
    if not module_id:
        await event.edit("Usage: `disable <module_id>`")
        return
    try:
        await module_manager.disable(state, registry, module_id)
        await event.edit(f"🔴 {module_id} disabled.")
    except Exception:
        logger.exception("Unexpected error disabling %s", module_id)
        await event.edit(f"❌ Could not disable {module_id}.")


async def _cmd_update(event, state: LocalState, registry: ModuleRegistry, client, module_id: str) -> None:
    if not module_id:
        await event.edit("Usage: `update <module_id>`")
        return
    try:
        await module_manager.update(state, registry, client, module_id)
        await event.edit(f"✅ {module_id} updated.")
    except Exception as exc:
        logger.exception("Unexpected error updating %s", module_id)
        await event.edit(f"❌ Could not update {module_id}: {exc}")
