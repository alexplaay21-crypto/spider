# Userbot Core — Moon Userbot

Telethon (MTProto). Covers Stages 4-7 from the master prompt: startup,
Telegram login, local session storage, pairing with Backend, heartbeat,
the Module Manager (install/enable/disable/update/remove, backup+
rollback), the command queue poller, and now Custom Modules - which
reuse the exact same `module_manager/security.py` and `install()` path
official modules already go through, just fed by a different download
source (see below).

## Requirements

- Python 3.12+
- A Telegram `api_id` / `api_hash` from https://my.telegram.org
- A running Backend (see `../backend`), reachable at `BACKEND_URL`

## Installation

### Termux (Android)

```bash
pkg install python
pip install -r requirements.txt --break-system-packages
```

### Linux / Windows

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

```bash
cp .env.example .env
```

`CORE_AUTH_TOKEN` must be the exact same value as Backend's
`CORE_INTERNAL_TOKEN`. `STORE_BOT_USERNAME` is Moon Bot's own `@username`
(no `@`) - only used for the auto-subscribe+pin step below.

## Telegram authorization

```bash
python main.py
```

On first run, Core prints a local URL:

```
>>> Open this on a browser on THIS device to log in: http://127.0.0.1:8765/AbCdEf...
```

Open it in a normal browser **on the same device** (or tunnel it, see
below for VPS) and you'll get a small login page: phone number → the
code Telegram sends you → your 2FA password if you have one set. None
of it (phone, code, password, or the resulting session) is ever sent to
Backend or Moon Bot (sections 44-45); it's stored locally in
`data/userbot.session`, and nothing outside this machine ever reads it.

**This is a local web page, not a Telegram Mini App, on purpose.** A
real Mini App reports its form data back to the bot/backend through
Telegram's own WebApp bridge (`Telegram.WebApp.sendData()`) - that's how
Mini Apps are designed to work, and it would route the phone/code/
password through the same infrastructure sections 44-45 keep them away
from. `telegram/local_auth_server.py` only ever binds to
`LOCAL_AUTH_HOST` (127.0.0.1 by default) and talks directly to the
Telethon client in this same process - there's no server on the other
end to report to.

- **Termux**: `127.0.0.1` works as-is if you open the browser on the
  same phone.
- **VPS**: `127.0.0.1` won't be reachable from your laptop directly -
  tunnel it instead: `ssh -L 8765:localhost:8765 user@your-vps` , then
  open the same URL Core printed in your own browser. Don't change
  `LOCAL_AUTH_HOST` to `0.0.0.0` to "make it easier" - that exposes a
  live login form to the whole internet during the login window, which
  defeats the entire point of keeping this local.
- The URL includes a random per-run token (`secrets.token_urlsafe(16)`)
  specifically so another process or user on a shared machine can't
  stumble onto the login page during that window even if they guess the
  port.
- Prefer the old terminal prompts? Set `AUTH_METHOD=terminal` in `.env`
  - both code paths stay in `telegram/client.py`.

## Connecting to Backend (pairing)

Right after login, Core prints a one-time code:

```
>>> Enter this code in Moon Bot to finish connecting: AB12CD34
```

Send that code to Moon Bot from whichever Telegram account you normally
use to talk to it - **not necessarily the account Core just logged into**.
Core then polls Backend every 5 seconds until the code is redeemed
(or it expires, `PAIRING_CODE_TTL_MINUTES` on the Backend side).

### Auto-subscribe + pin

Once paired, Core checks whether this account has ever messaged Moon Bot
before; if not, it sends `/start` on your behalf so Bot API can message
you later (Telegram won't let a bot message an account that's never
messaged it first), then pins that chat in your own chat list. This
happens once - it's tracked so a later run won't re-pin it if you unpin
it yourself. If Telegram's pinned-chat limit is already maxed out, this
step just logs a warning and moves on; it never blocks startup.

## Module Manager

```
.modules                    -> list what's installed, 🟢 enabled / 🔴 disabled
.install <module_id>        -> license check -> Backend authorizes -> download -> verify -> load
.uninstall <module_id>      -> unload, delete files, tell Backend (purchase/license untouched)
.enable <module_id> / .disable <module_id>
.update <module_id>         -> backup -> download new version -> load -> rollback on failure
```

Everything goes through `license.client.has_access()` first (a live
`POST /licenses/check` call - Core never trusts a locally cached "plan"
for this, section 30/56). A module is a folder under `MODULES_DIRECTORY`
containing a `main.py` with an async `setup(client)` function (and
optionally `teardown()`) - this convention isn't specified in the master
prompt beyond the manifest metadata, so I picked the simplest thing that
works and documented it here; happy to change it if you have a different
module interface in mind (e.g. a class-based one closer to
Hikka/PagerMaid's module style).

`.install`/`.update` also work for Store-triggered actions now (Stage 6)
via the command queue below - typing the module_id by hand is just the
other way in.

## Command queue

Alongside the heartbeat, Core runs a second loop (10s interval) polling
`GET /commands/pending` for its account. This is how Moon Bot's Store
and My Modules screens ever get Core to actually do something (section
51 - Bot never talks to Core directly). Each command maps straight onto
the Module Manager functions above; success/failure is reported back via
`POST /commands/{id}/complete`.

## Custom Modules (Stage 7)

`.install <module_id>` and the Store's install button both work
identically for custom modules as for official ones - no separate code
path. The only difference is *where the bytes come from*:
official modules have a `package_url` pointing at external hosting;
custom modules have Backend host the bytes itself and hand back a
relative path instead (`/modules/{id}/versions/{v}/download`).
`module_manager/manager.py`'s `_download()` tells the two apart by
whether the URL starts with `http`.

Everything from Stage 5 - `module_manager/security.py`'s ZIP validation,
the license check, the module-limit check, backup+rollback on update -
applies unchanged. This is deliberate: technical ZIP validation is not a
code security review (section 34), and a custom module is exactly as
untrusted after passing it as before.

**What isolation actually exists right now, and what doesn't (please
read this before enabling custom modules for real users):**

- ✅ A module that raises during `setup()` gets logged and disabled,
  never crashes Core (section 26).
- ✅ `setup()` now has a 15-second timeout (`SETUP_TIMEOUT_SECONDS` in
  `module_manager/loader.py`) - a hanging custom module can't block
  startup forever.
- ✅ ZIP extraction is path-traversal/symlink-safe
  (`module_manager/security.py`, tested against real attack payloads).
- ❌ **Modules run in the same Python process as Core, not a separate
  one.** A module's code can `import os`, read `.env`, or reach into
  `config.settings`/`backend_client` directly - nothing currently stops
  it. Section 34 asks for a separate process, limited permissions,
  resource control, and secret-hiding; none of that is implemented.
- ❌ Once `setup()` returns, any event handlers it registered run with
  no timeout or resource limit of their own - the 15s cap only covers
  the initial call.

Building real isolation properly (subprocess + restricted IPC, or a
container/VM per module) is a meaningfully sized project on its own,
not something that fits naturally as an add-on to a single Telethon
process running on someone's Termux install. I did not want to claim
this is handled when it structurally isn't - if custom modules are
going out to real users before that work happens, that's a genuine risk
worth deciding on explicitly rather than by default.

## Duo (a second account)

Just run Core again against a second Telegram account's phone number
(different machine, or the same one in a second folder with its own
`DATA_DIRECTORY`). Pair it the same way - send the new code to Moon Bot
from your usual account. Backend decides whether this becomes account #1
or #2 based on whether you already have a primary account and an active
Duo subscription; if you don't have Duo yet, pairing fails with a clear
`duo_required_for_second_account` error instead of silently allowing it.

## Backend connection & offline behaviour

Every `HEARTBEAT_INTERVAL_SECONDS` (default 300s), Core reports in and
caches whatever Backend returns (plan, module limit, custom-VIP flag,
expiry) to `data/state.json`. If a heartbeat fails, Core logs a
warning and keeps using the last cached values rather than treating a
network blip as "your subscription is gone" (section 48's grace period -
there's no separate expiry countdown on the cache yet; it just holds the
last known-good state until the next successful heartbeat).

## Testing

```bash
pytest
```

`tests/test_local_state.py` and `tests/test_module_security.py` are
pure stdlib (+ pydantic-settings for the former) - no Telethon, no
network. I actually executed both, logic and all, in this sandbox by
either faking the one missing dependency or using nothing but
`zipfile`/`pathlib` directly: real path-traversal payloads, absolute
paths, oversized/malformed archives, and file-count bombs were all
thrown at `module_manager/security.py` and correctly rejected, with
nothing left behind on disk - the same code path Custom Modules now use
too. I did the same for `telegram/local_auth_server.py` by stubbing
`aiohttp.web`: verified the random per-run token is actually random and
sufficiently long, that every route is correctly scoped under it, that
form actions point at the right token-scoped paths, and that error
messages render into the form instead of crashing the handler. What I
could not verify is the actual HTTP server binding/serving behavior
(needs real `aiohttp`) or a real browser walking through the phone →
code → password flow end to end - please run `python main.py`, open the
printed URL, and confirm a real login completes and the resulting
session persists across a restart. I also stubbed out `httpx`/`telethon`/
`pydantic_settings` just enough to import `core.app` end-to-end and
confirm the whole module
graph has no circular imports or missing names, including the new
command_processor and the download-source branching in
`module_manager/manager.py`. I could not exercise the actual Telegram
login, the live pairing loop, `messages.toggleDialogPin`, the command
polling loop against a real Backend, or an actual custom-module upload
end to end - please run `python main.py` for real, publish a small test
module, and try both `.install` and a Store-triggered install/update/
disable, and tell me if anything breaks.

## Design decisions worth double-checking

1. **`.gitignore` drops `storage/` from the doc's literal section-12
   template.** That template assumes no source folder is named
   `storage/`, but section 4 requires exactly that package (for
   `local_state.py`). Ignoring it would have silently excluded real code
   from git. `data/` and `modules_data/` (the actual runtime dirs) stay
   ignored.
2. **MIT license, not the proprietary one used in `backend`/
   `telegram-store-bot`.** Core is the one component people actually
   download and run with real access to their own Telegram account -
   open-sourcing it (the way Hikka/PagerMaid and similar projects do)
   can be a genuine trust signal given how much the rest of the doc
   emphasizes warning people about that risk. If you'd rather keep it
   closed, swap in the same "all rights reserved" notice as the other
   two repos.
3. **Auto-subscribe+pin failures are swallowed, not fatal** - same
   isolation philosophy as section 26's module errors, just applied to
   this one startup step instead of a module.
4. **No `.restart` yet** - restarting a long-running asyncio process
   from inside itself needs either a process supervisor or an os.exec
   re-launch, and that felt like it belonged with actual deployment
   tooling (systemd/pm2/Termux:Boot) rather than guessed at here. It
   currently replies honestly that it isn't wired up.
5. **`main.py:setup(client)` is my own convention, not the doc's** -
   the master prompt specifies module *metadata* (manifest fields) but
   never how a module's actual code plugs into Core. I picked the
   simplest thing that could work; this is exactly the kind of
   "technical reality forced a decision" case section 2/105 asks to be
   documented rather than silently guessed.
6. **`/modules/install|uninstall|toggle` and `GET /modules/{id}` on
   Backend now accept either the Bot's or Core's service token**, not
   just the Bot's - Core needs `package_url` to download a module, and
   needs to trigger the authorize-then-record step itself since Moon
   Bot's Store UI (where a user would normally tap "Install") doesn't
   exist yet. This was a small Backend change alongside this stage -
   re-download `backend.zip` if you grabbed it before now.
7. **Update failures roll back to the exact previous version**, not to
   "uninstalled" - the backup directory is only deleted after the new
   version has proven it can load.
8. **Custom module IDs are namespaced per-account on Backend**
   (`custom.<account_id>.<name>`), not the raw name someone types - two
   different customers can both call their module "autoreply" without
   colliding. Core doesn't need to know or care about this; it just
   installs whatever module_id Backend/the command tells it to.
9. **Local login page instead of a Telegram Mini App, by explicit
   choice** (the person specifically asked for this after I flagged why
   a bot-chat or Mini-App-based login would be unsafe - see
   `telegram/local_auth_server.py`'s docstring for the technical reason
   a real Mini App doesn't actually solve that problem). No HTML
   escaping was added on the error-message reflection since this page
   only ever talks to the same person authenticating themselves on
   localhost - there's no other party to attack. That reasoning breaks
   if `LOCAL_AUTH_HOST` is ever changed to `0.0.0.0`; don't do that.

## What's next

Stage 8: proper Duo UX (currently Duo *works* - pairing a second account
already routes correctly - but nothing here or in the Bot has a way to
switch between two active accounts in one conversation yet). Also worth
real attention before going further: the isolation gaps called out
above under Custom Modules - subprocess-level sandboxing would be the
natural next investment if custom modules see real usage.
