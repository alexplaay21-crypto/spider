import httpx

from config.settings import settings


class BackendClient:
    """All calls carry X-Service-Token: CORE_AUTH_TOKEN, matching Backend's
    require_core_token dependency (section 50)."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.BACKEND_URL,
            headers={"X-Service-Token": settings.CORE_AUTH_TOKEN},
            timeout=15.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def ping(self) -> bool:
        resp = await self._client.get("/auth/core/ping")
        return resp.status_code == 200

    async def pair_init(self, telegram_user_id: int, device_name: str, core_version: str) -> dict:
        resp = await self._client.post(
            "/devices/pair/init",
            json={"telegram_user_id": telegram_user_id, "device_name": device_name, "core_version": core_version},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_device(self, device_id: int) -> dict:
        resp = await self._client.get(f"/devices/{device_id}")
        resp.raise_for_status()
        return resp.json()

    async def heartbeat(self, device_id: int, core_version: str, status: str) -> dict:
        resp = await self._client.post(
            "/devices/heartbeat",
            json={"device_id": device_id, "core_version": core_version, "status": status},
        )
        resp.raise_for_status()
        return resp.json()

    async def set_store_bot_pinned(self, account_id: int, pinned: bool) -> dict:
        resp = await self._client.post(
            "/accounts/store-bot-pin", params={"account_id": account_id, "pinned": pinned}
        )
        resp.raise_for_status()
        return resp.json()

    async def check_license(self, account_id: int, module_id: str) -> dict:
        resp = await self._client.post("/licenses/check", json={"account_id": account_id, "module_id": module_id})
        resp.raise_for_status()
        return resp.json()

    async def download_package(self, relative_path: str) -> bytes:
        """Custom modules (Stage 7) are Backend-hosted, not on an
        external URL - this reuses the authenticated Core session rather
        than a bare request, since the bytes are private to one account."""
        resp = await self._client.get(relative_path)
        resp.raise_for_status()
        return resp.content

    async def get_module(self, module_id: str) -> dict:
        """Includes package_url - this is how Core knows where to
        download a module from (Stage 5)."""
        resp = await self._client.get(f"/modules/{module_id}")
        resp.raise_for_status()
        return resp.json()

    async def install_module(self, account_id: int, module_id: str) -> dict:
        resp = await self._client.post(
            "/modules/install", json={"account_id": account_id, "module_id": module_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def uninstall_module(self, account_id: int, module_id: str) -> dict:
        resp = await self._client.post(
            "/modules/uninstall", json={"account_id": account_id, "module_id": module_id}
        )
        resp.raise_for_status()
        return resp.json()

    async def toggle_module(self, account_id: int, module_id: str, enabled: bool) -> dict:
        resp = await self._client.post(
            "/modules/toggle",
            json={"account_id": account_id, "module_id": module_id, "enabled": enabled},
        )
        resp.raise_for_status()
        return resp.json()

    async def pending_commands(self, account_id: int) -> list[dict]:
        resp = await self._client.get("/commands/pending", params={"account_id": account_id})
        resp.raise_for_status()
        return resp.json()

    async def complete_command(self, command_id: str, status: str) -> dict:
        resp = await self._client.post(f"/commands/{command_id}/complete", json={"status": status})
        resp.raise_for_status()
        return resp.json()


backend_client = BackendClient()
