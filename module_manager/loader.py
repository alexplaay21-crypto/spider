import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

logger = logging.getLogger("core.module_loader")

_active_modules: dict[str, object] = {}

# Section 34: "timeout" is one of the isolation measures listed - this
# covers a hanging setup() call. It does NOT cover a module's event
# handlers running forever after setup() returns - see the README for
# what real isolation (separate process, resource limits) would still
# need on top of this.
SETUP_TIMEOUT_SECONDS = 15


def _entrypoint_path(module_dir: Path) -> Path:
    return module_dir / "main.py"


async def load(module_id: str, module_dir: Path, client) -> bool:
    """
    Convention (not specified in the master prompt - documented here
    since it had to be decided somewhere): a module is a `main.py` inside
    its own folder, exposing an async `setup(client)` that registers
    whatever event handlers it needs, and optionally an async
    `teardown()`. Section 26: a module raising during load must disable
    it and log it, never crash Core. Section 34: setup() gets a hard
    timeout since a custom module is untrusted code.
    """
    entrypoint = _entrypoint_path(module_dir)
    if not entrypoint.exists():
        logger.error("Module %s has no main.py entrypoint", module_id)
        return False

    spec = importlib.util.spec_from_file_location(f"moon_module_{module_id}", entrypoint)
    if spec is None or spec.loader is None:
        logger.error("Could not build an import spec for module %s", module_id)
        return False

    py_module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(py_module)
        if hasattr(py_module, "setup"):
            await asyncio.wait_for(py_module.setup(client), timeout=SETUP_TIMEOUT_SECONDS)
        _active_modules[module_id] = py_module
        sys.modules[f"moon_module_{module_id}"] = py_module
        return True
    except asyncio.TimeoutError:
        logger.error("Module %s setup() timed out after %ss - leaving it disabled", module_id, SETUP_TIMEOUT_SECONDS)
        return False
    except Exception:
        logger.exception("Module %s raised during load/setup - leaving it disabled", module_id)
        return False


async def unload(module_id: str) -> None:
    py_module = _active_modules.pop(module_id, None)
    sys.modules.pop(f"moon_module_{module_id}", None)
    if py_module is not None and hasattr(py_module, "teardown"):
        try:
            await py_module.teardown()
        except Exception:
            logger.exception("Module %s raised during teardown", module_id)


def is_loaded(module_id: str) -> bool:
    return module_id in _active_modules
