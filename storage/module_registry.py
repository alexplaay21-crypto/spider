import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from config.settings import settings

logger = logging.getLogger("core.module_registry")


@dataclass
class InstalledModule:
    module_id: str
    version: str
    enabled: bool = True


class ModuleRegistry:
    """
    Core's own local record of what's actually on disk - separate from
    Backend's module_installations table, which stays the authoritative
    permission source (section 89). This is just "what do I need to load
    on startup" so Core doesn't have to ask Backend before it can even
    start running installed modules.
    """

    def __init__(self) -> None:
        self._modules: dict[str, InstalledModule] = {}
        self._load()

    @staticmethod
    def _path() -> Path:
        return settings.data_dir / "modules.json"

    def _load(self) -> None:
        path = self._path()
        if not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            self._modules = {k: InstalledModule(**v) for k, v in raw.items()}
        except Exception:
            logger.exception("Could not read local module registry, starting empty")
            self._modules = {}

    def save(self) -> None:
        with self._path().open("w", encoding="utf-8") as f:
            json.dump({k: asdict(v) for k, v in self._modules.items()}, f, indent=2)

    def get(self, module_id: str) -> InstalledModule | None:
        return self._modules.get(module_id)

    def all(self) -> list[InstalledModule]:
        return list(self._modules.values())

    def set(self, entry: InstalledModule) -> None:
        self._modules[entry.module_id] = entry
        self.save()

    def remove(self, module_id: str) -> None:
        self._modules.pop(module_id, None)
        self.save()
