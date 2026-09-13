import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from config.settings import settings

logger = logging.getLogger("core.storage")


@dataclass
class LocalState:
    """
    Everything Core needs to remember between restarts, scoped to THIS
    account (section 62: account-specific state lives here, not globally -
    Duo isolation starts here). Never put secrets in this file
    - the Telegram session lives in its own .session file (section 45),
    never here, and never logged (section 65).
    """

    device_id: int | None = None
    account_id: int | None = None
    store_bot_pinned: bool = False
    plan_code: str = "free"
    module_limit: int = 10
    custom_modules_enabled: bool = False
    server_access: bool = False

    @staticmethod
    def _path() -> Path:
        return settings.data_dir / "state.json"

    @classmethod
    def load(cls) -> "LocalState":
        path = cls._path()
        if not path.exists():
            return cls()
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            # Remove the legacy prefix field without losing
            # device/account pairing from an old state.json.
            data.pop("prefix", None)

            return cls(**data)
        except Exception:
            logger.exception("Could not read local state, starting fresh")
            return cls()

    def save(self) -> None:
        with self._path().open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    def apply_entitlement(self, snapshot: dict) -> None:
        """Section 48: this is exactly the cached entitlement Core falls
        back to if a later heartbeat fails."""
        self.plan_code = snapshot["plan_code"]
        self.module_limit = snapshot["module_limit"]
        self.custom_modules_enabled = snapshot["custom_modules_enabled"]
        self.server_access = snapshot["server_access"]
