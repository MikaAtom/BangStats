from bangstats_cli.menus import user_login


class _LegacyApi:
    def __init__(self, mode: str):
        self.mode = mode

    def login(self, username: str, password: str):
        raise RuntimeError("Account requires password setup. Use legacy password setup with your game ID.")

    def legacy_login(self, username: str, game_id: str):
        return {"user": {"id": 7, "username": username, "server": "en"}}

    def legacy_password_setup(self, username: str, game_id: str, password: str):
        return {"user": {"id": 7, "username": username, "server": "en"}}

    def register(self, payload):
        raise AssertionError("register should not be called")


def test_user_login_supports_temporary_legacy_login(monkeypatch, capsys):
    answers = iter(["3", "legacy_user", "gid_123"])
    passwords = iter([])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("bangstats_cli.menus.getpass", lambda prompt="": next(passwords))

    user = user_login(_LegacyApi(mode="legacy-login"))
    assert user["username"] == "legacy_user"
    output = capsys.readouterr().out
    assert "legacy login" in output.lower()
    assert "logged in via legacy flow" in output.lower()


def test_user_login_supports_legacy_password_setup(monkeypatch, capsys):
    answers = iter(["4", "legacy_user", "gid_123"])
    passwords = iter(["new-secret"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("bangstats_cli.menus.getpass", lambda prompt="": next(passwords))

    user = user_login(_LegacyApi(mode="legacy-setup"))
    assert user["username"] == "legacy_user"
    output = capsys.readouterr().out
    assert "password set and logged in" in output.lower()


def test_user_login_blank_password_points_to_legacy_options(monkeypatch, capsys):
    answers = iter(["1", "legacy_user"])
    passwords = iter([""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr("bangstats_cli.menus.getpass", lambda prompt="": next(passwords))

    try:
        user_login(_LegacyApi(mode="legacy-login"))
    except StopIteration:
        pass
    output = capsys.readouterr().out
    assert "choose option 3 or 4 for legacy accounts" in output.lower()
