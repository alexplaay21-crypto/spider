import logging
import shutil
from pathlib import Path

import httpx

from api.backend_client import backend_client
from config.settings import settings
from core.version import CORE_VERSION
from license.client import has_access
from module_manager.compat import is_compatible
from module_manager.loader import load as load_module
from module_manager.loader import unload as unload_module
from module_manager.security import validate_and_extract
from storage.local_state import LocalState
from storage.module_registry import InstalledModule, ModuleRegistry

logger = logging.getLogger("core.module_manager")


class ModuleManagerError(Exception):
    pass


def module_dir(module_id: str) -> Path:
    return settings.modules_dir / module_id


def _backup_dir(module_id: str) -> Path:
    return settings.modules_dir / f"{module_id}.backup"


async def _download(package_url: str) -> bytes:
    if package_url.startswith("http://") or package_url.startswith("https://"):
        # Officially-hosted module - an external URL, no Backend auth needed.
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(package_url)
            resp.raise_for_status()
            return resp.content
    # Custom module (Stage 7): a path relative to Backend itself, stored
    # privately per account - use the authenticated backend_client
    # session instead of a bare request.
    return await backend_client.download_package(package_url)


async def install(state: LocalState, registry: ModuleRegistry, client, module_id: str) -> None:
    """
    download -> verify -> install -> load (section 24), gated by
    Backend's authorization first (section 28): only after Backend says
    yes does Core touch the filesystem. If the local half fails anyway,
    this rolls the Backend-side record back too, so the two never drift
    out of sync.
    """
    allowed, reason = await has_access(state, module_id)
    if not allowed:
        raise ModuleManagerError(f"access_denied:{reason}")

    module = await backend_client.get_module(module_id)
    if not is_compatible(module.get("core_version_requirement"), CORE_VERSION):
        raise ModuleManagerError("incompatible_core_version")
    if not module.get("package_url"):
        raise ModuleManagerError("no_package_available")

    result = await backend_client.install_module(state.account_id, module_id)

    try:
        zip_bytes = await _download(module["package_url"])
        validate_and_extract(zip_bytes, module_dir(module_id))
        if not await load_module(module_id, module_dir(module_id), client):
            raise ModuleManagerError("module_failed_to_load")
    except Exception:
        logger.exception("Install failed after Backend authorized it - rolling back")
        shutil.rmtree(module_dir(module_id), ignore_errors=True)
        try:
            await backend_client.uninstall_module(state.account_id, module_id)
        except Exception:
            logger.exception("Could not roll back the Backend-side install record either")
        raise

    registry.set(InstalledModule(module_id=module_id, version=result["version"], enabled=True))
    logger.info("Installed module %s v%s", module_id, result["version"])


async def enable(state: LocalState, registry: ModuleRegistry, client, module_id: str) -> None:
    entry = registry.get(module_id)
    if entry is None:
        raise ModuleManagerError("not_installed")
    if not await load_module(module_id, module_dir(module_id), client):
        raise ModuleManagerError("module_failed_to_load")
    entry.enabled = True
    registry.set(entry)
    await backend_client.toggle_module(state.account_id, module_id, True)


async def disable(state: LocalState, registry: ModuleRegistry, module_id: str) -> None:
    entry = registry.get(module_id)
    if entry is None:
        raise ModuleManagerError("not_installed")
    await unload_module(module_id)
    entry.enabled = False
    registry.set(entry)
    await backend_client.toggle_module(state.account_id, module_id, False)


async def remove(state: LocalState, registry: ModuleRegistry, module_id: str) -> None:
    """Section 75: only the local install + files go away - the
    purchase/license on Backend stays untouched, so reinstalling later
    just works."""
    entry = registry.get(module_id)
    if entry is None:
        raise ModuleManagerError("not_installed")
    await unload_module(module_id)
    shutil.rmtree(module_dir(module_id), ignore_errors=True)
    registry.remove(module_id)
    await backend_client.uninstall_module(state.account_id, module_id)


async def update(state: LocalState, registry: ModuleRegistry, client, module_id: str) -> bool:
    """
    download new -> verify -> backup old -> install new -> load ->
    rollback on any failure (section 25) - the previous working version
    is never deleted until the new one has actually loaded successfully.
    Returns False if already on the latest version (a no-op, not an
    error).
    """
    entry = registry.get(module_id)
    if entry is None:
        raise ModuleManagerError("not_installed")

    module = await backend_client.get_module(module_id)
    new_version = module.get("current_version")
    if not new_version or new_version == entry.version:
        return False
    if not module.get("package_url"):
        raise ModuleManagerError("no_package_available")
    if not is_compatible(module.get("core_version_requirement"), CORE_VERSION):
        raise ModuleManagerError("incompatible_core_version")

    target_dir = module_dir(module_id)
    backup_dir = _backup_dir(module_id)
    shutil.rmtree(backup_dir, ignore_errors=True)
    if target_dir.exists():
        shutil.move(str(target_dir), str(backup_dir))

    try:
        zip_bytes = await _download(module["package_url"])
        validate_and_extract(zip_bytes, target_dir)
        await unload_module(module_id)
        if not await load_module(module_id, target_dir, client):
            raise ModuleManagerError("module_failed_to_load")
    except Exception:
        logger.exception("Update failed for %s - rolling back to the previous version", module_id)
        shutil.rmtree(target_dir, ignore_errors=True)
        if backup_dir.exists():
            shutil.move(str(backup_dir), str(target_dir))
            await load_module(module_id, target_dir, client)
        raise

    shutil.rmtree(backup_dir, ignore_errors=True)
    entry.version = new_version
    registry.set(entry)
    await backend_client.install_module(state.account_id, module_id)  # syncs the new version to Backend too
    logger.info("Updated module %s to v%s", module_id, new_version)
    return True
