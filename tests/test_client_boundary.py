from pathlib import Path


def test_client_has_no_direct_server_core_imports():
    root = Path(__file__).resolve().parents[1]
    client_root = root / "clients" / "cli" / "bangstats_cli"
    forbidden_tokens = [
        "from bangstats_server",
        "import bangstats_server",
    ]

    py_files = sorted(client_root.rglob("*.py"))
    assert py_files, "No client python files found to validate boundaries."

    violations: list[str] = []
    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in content:
                violations.append(f"{py_file.relative_to(root)} -> {token}")

    assert not violations, "Client/server boundary violated:\n" + "\n".join(violations)
