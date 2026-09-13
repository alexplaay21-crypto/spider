import asyncio
import logging
import secrets

from aiohttp import web
from telethon.errors import SessionPasswordNeededError

logger = logging.getLogger("core.local_auth")

_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Moon Userbot - Login</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 420px; margin: 60px auto;
         padding: 0 16px; color: #222; }}
  h2 {{ margin-bottom: 4px; }}
  input {{ width: 100%; padding: 12px; font-size: 16px; margin: 8px 0;
           box-sizing: border-box; border: 1px solid #ccc; border-radius: 6px; }}
  button {{ width: 100%; padding: 12px; font-size: 16px; background: #2AABEE;
            color: white; border: none; border-radius: 6px; cursor: pointer; }}
  .error {{ color: #c0392b; }}
  .info {{ color: #666; font-size: 14px; }}
</style>
</head>
<body>
<h2>🌙 Moon Userbot</h2>
{body}
</body>
</html>"""


class LocalAuthServer:
    """
    Temporary Telegram login page.

    The server binds to Railway's internal 0.0.0.0:$PORT,
    while the generated link uses the public HTTPS Railway domain.

    Phone number, Telegram code and 2FA password are handled directly
    by this Core process and are never sent to the Moon Backend or Bot.
    """

    def __init__(
        self,
        client,
        host: str,
        port: int,
        public_base_url: str = "",
    ) -> None:
        self._client = client
        self._host = host
        self._port = port
        self._public_base_url = public_base_url.rstrip("/")
        self._token = secrets.token_urlsafe(24)
        self._phone: str | None = None
        self._done = asyncio.Event()
        self._runner: web.AppRunner | None = None

    def _url(self, suffix: str = "") -> str:
        return f"/{self._token}{suffix}"

    def _public_login_url(self) -> str:
        if self._public_base_url:
            return f"{self._public_base_url}{self._url()}"

        # Local/Termux fallback.
        return f"http://127.0.0.1:{self._port}{self._url()}"

    async def wait_for_login(self) -> None:
        app = web.Application()

        app.router.add_get(self._url(), self._handle_index)
        app.router.add_post(self._url("/phone"), self._handle_phone)
        app.router.add_post(self._url("/code"), self._handle_code)
        app.router.add_post(self._url("/password"), self._handle_password)

        self._runner = web.AppRunner(app)
        await self._runner.setup()

        site = web.TCPSite(
            self._runner,
            self._host,
            self._port,
        )
        await site.start()

        login_url = self._public_login_url()

        print("\n" + "=" * 60)
        print("🌙 Moon Userbot Telegram Login")
        print(f"Open this URL:\n{login_url}")
        print("=" * 60 + "\n")

        logger.info(
            "Temporary Telegram login page running on %s:%s",
            self._host,
            self._port,
        )

        try:
            await self._done.wait()
        finally:
            await self._runner.cleanup()
            logger.info("Telegram login server stopped")

    def _render(self, body: str) -> web.Response:
        return web.Response(
            text=_PAGE.format(body=body),
            content_type="text/html",
        )

    def _phone_form(self, error: str = "") -> str:
        error_html = f'<p class="error">{error}</p>' if error else ""

        return f"""{error_html}
        <p class="info">Enter your phone number, with country code.</p>
        <form method="post" action="{self._url('/phone')}">
            <input name="phone" placeholder="+15551234567" required>
            <button type="submit">Send code</button>
        </form>"""

    def _code_form(self, error: str = "") -> str:
        error_html = f'<p class="error">{error}</p>' if error else ""

        return f"""{error_html}
        <p class="info">Enter the login code Telegram just sent you.</p>
        <form method="post" action="{self._url('/code')}">
            <input name="code" inputmode="numeric" placeholder="12345" required>
            <button type="submit">Confirm</button>
        </form>"""

    def _password_form(self, error: str = "") -> str:
        error_html = f'<p class="error">{error}</p>' if error else ""

        return f"""{error_html}
        <p class="info">This account has a two-factor password set.</p>
        <form method="post" action="{self._url('/password')}">
            <input name="password" type="password" placeholder="Password" required>
            <button type="submit">Confirm</button>
        </form>"""

    async def _handle_index(self, request: web.Request) -> web.Response:
        return self._render(self._phone_form())

    async def _handle_phone(self, request: web.Request) -> web.Response:
        data = await request.post()
        phone = str(data.get("phone", "")).strip()

        if not phone:
            return self._render(
                self._phone_form("Phone number is required.")
            )

        try:
            await self._client.send_code_request(phone)
        except Exception as exc:
            logger.exception("send_code_request failed")
            return self._render(
                self._phone_form(f"Error: {exc}")
            )

        self._phone = phone
        return self._render(self._code_form())

    async def _handle_code(self, request: web.Request) -> web.Response:
        data = await request.post()
        code = str(data.get("code", "")).strip()

        try:
            await self._client.sign_in(
                phone=self._phone,
                code=code,
            )
        except SessionPasswordNeededError:
            return self._render(self._password_form())
        except Exception as exc:
            logger.exception("sign_in with code failed")
            return self._render(
                self._code_form(f"Error: {exc}")
            )

        self._done.set()

        return self._render(
            "<p>✅ Logged in! You can close this page and return to Moon Userbot.</p>"
        )

    async def _handle_password(self, request: web.Request) -> web.Response:
        data = await request.post()
        password = str(data.get("password", ""))

        try:
            await self._client.sign_in(password=password)
        except Exception as exc:
            logger.exception("sign_in with password failed")
            return self._render(
                self._password_form(f"Error: {exc}")
            )

        self._done.set()

        return self._render(
            "<p>✅ Logged in! You can close this page and return to Moon Userbot.</p>"
        )
