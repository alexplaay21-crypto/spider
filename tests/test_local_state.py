from storage.local_state import LocalState


def test_round_trip(tmp_path, monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "DATA_DIRECTORY", str(tmp_path))

    state = LocalState(
        device_id=1,
        account_id=2,
        plan_code="pro",
        module_limit=20,
        custom_modules_enabled=True,
        server_access=True,
    )
    state.save()

    loaded = LocalState.load()

    assert loaded.device_id == 1
    assert loaded.account_id == 2
    assert loaded.plan_code == "pro"
    assert loaded.module_limit == 20
    assert loaded.custom_modules_enabled is True
    assert loaded.server_access is True
    assert not hasattr(loaded, "prefix")


def test_missing_state_file_returns_defaults(tmp_path, monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "DATA_DIRECTORY", str(tmp_path))

    state = LocalState.load()

    assert state.device_id is None
    assert state.account_id is None
    assert state.plan_code == "free"
    assert state.module_limit == 10
    assert not hasattr(state, "prefix")


def test_legacy_prefix_is_removed_without_losing_account(tmp_path, monkeypatch):
    from config.settings import settings

    monkeypatch.setattr(settings, "DATA_DIRECTORY", str(tmp_path))

    state_path = tmp_path / "state.json"
    state_path.write_text(
        """{
            "device_id": 123,
            "account_id": 456,
            "prefix": "!",
            "store_bot_pinned": true,
            "plan_code": "pro",
            "module_limit": 20,
            "custom_modules_enabled": true,
            "server_access": true
        }""",
        encoding="utf-8",
    )

    loaded = LocalState.load()

    assert loaded.device_id == 123
    assert loaded.account_id == 456
    assert loaded.store_bot_pinned is True
    assert loaded.plan_code == "pro"
    assert loaded.module_limit == 20
    assert loaded.custom_modules_enabled is True
    assert loaded.server_access is True
    assert not hasattr(loaded, "prefix")


def test_apply_entitlement():
    state = LocalState()

    state.apply_entitlement(
        {
            "plan_code": "pro",
            "module_limit": 20,
            "custom_modules_enabled": True,
            "server_access": True,
            # Backend may still return this legacy field for now.
            "prefix": "!",
        }
    )

    assert state.plan_code == "pro"
    assert state.module_limit == 20
    assert state.custom_modules_enabled is True
    assert state.server_access is True
    assert not hasattr(state, "prefix")
