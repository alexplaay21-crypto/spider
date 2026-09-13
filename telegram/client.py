import logging

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config.settings import settings
from telegram.local_auth_server import LocalAuthServer

logger = logging.getLogger("core.telegram")


def _session_path() -> str:
    return str(settings.data_dir / "userbot")  # Telethon appends ".session"


async def build_client() -> TelegramClient:
    """
    Creates (or resumes) the local Telegram session. On a fresh session
    this walks through phone/OTP/2FA entirely inside this process
    (section 44) - Backend and Moon Bot never see the phone number, the
    OTP, or the 2FA password, and the resulting .session file never
    leaves this machine (section 45). AUTH_METHOD picks whether that
    happens via a local web page (default) or the old terminal prompts.
    """
    client = TelegramClient(_session_path(), settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        if settings.AUTH_METHOD == "terminal":
            await _interactive_login(client)
        else:
            server = LocalAuthServer(
                client,
                settings.LOCAL_AUTH_HOST,
                settings.railway_port,
                settings.public_base_url,
            )
            await server.wait_for_login()
        logger.info("Telegram login successful - session stored locally at %s.session", _session_path())

    return client


async def _interactive_login(client: TelegramClient) -> None:
    phone = input("Phone number (with country code, e.g. +15551234567): ").strip()
    await client.send_code_request(phone)
    code = input("Code you received in Telegram: ").strip()
    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        password = input("Two-factor password: ").strip()
        await client.sign_in(password=password)
