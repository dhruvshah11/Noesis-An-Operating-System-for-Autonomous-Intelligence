"""
M1.3 Plugin CLI tests.

Strategy:
  * Use ``typer.testing.CliRunner`` + ``tempfile.TemporaryDirectory`` so each
    test has an isolated, disposable plugin tree.
  * Construct valid / invalid / sha-mismatched manifest.json fixtures from
    dicts via orjson so Pydantic validates them exactly like production.
"""

from __future__ import annotations

import json as _stdlib_json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from noesis.cli import app
from noesis.plugins.manifest import PluginManifest


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# helpers to write manifest.json files in temp dirs
# ---------------------------------------------------------------------------


def _write_valid_manifest(
    d: Path, *, plugin_id: str, entry_point: str = "", sha_correct: bool = True, extra: dict[str, Any] | None = None
) -> PluginManifest:
    kwargs: dict[str, Any] = {
        "id": plugin_id,
        "version": "1.2.3",
        "name": f"Plugin {plugin_id}",
        "description": "test fixture",
        "author": "Test Author",
        "hook_groups": (),
        "caps_requested": (),
        "entry_point": entry_point,
    }
    if extra:
        kwargs.update(extra)
    manifest = PluginManifest(**kwargs)
    # Compute canonical SHA so the verification phase passes.
    manifest.sha256_manifest = manifest.compute_sha256() if sha_correct else "deadbeef" * 8
    d.mkdir(parents=True, exist_ok=True)
    out = d / "manifest.json"
    out.write_bytes(manifest.model_dump_json(indent=2).encode())
    return manifest


def _write_invalid_json(d: Path, content: str = "{this is not valid json") -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / "manifest.json"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# `astraos plugins verify`
# ---------------------------------------------------------------------------


def test_plugins_verify_dir_does_not_exist(runner: CliRunner) -> None:
    r = runner.invoke(app, ["plugins", "verify", "--dir", "/does/not/exist"])
    assert r.exit_code == 2, r.stdout
    assert "directory_does_not_exist" in r.stdout.lower() or "invalid" in r.stdout.lower()


def test_plugins_verify_no_manifests(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        r = runner.invoke(app, ["plugins", "verify", "--dir", td])
        assert r.exit_code == 2, r.stdout
        assert "no_manifest_found" in r.stdout.lower()


def test_plugins_verify_valid_ok_table(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        sub = Path(td) / "myplugin"
        _write_valid_manifest(sub, plugin_id="io.astraos.myplugin")
        r = runner.invoke(app, ["plugins", "verify", "--dir", td])
        assert r.exit_code == 0, (r.exit_code, r.stdout)
        assert "io.astraos.myplugin" in r.stdout
        assert "1.2.3" in r.stdout
        # status column shows green OK mark
        assert "ok" in r.stdout.lower()


def test_plugins_verify_valid_ok_json(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        _write_valid_manifest(Path(td) / "p1", plugin_id="io.astraos.one")
        _write_valid_manifest(Path(td) / "p2", plugin_id="io.astraos.two")
        r = runner.invoke(app, ["plugins", "verify", "--dir", td, "--format", "json"])
        assert r.exit_code == 0, r.stdout
        payload = _stdlib_json.loads(r.stdout)
        assert isinstance(payload, list)
        assert len(payload) == 2
        ids = sorted(x["id"] for x in payload)
        assert ids == ["io.astraos.one", "io.astraos.two"]
        # Every row has {path, id, version, status, ok} fields (contract test).
        for row in payload:
            assert set(row.keys()) >= {"path", "id", "version", "status", "ok"}


def test_plugins_verify_invalid_parse_error(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        _write_invalid_json(Path(td) / "broken")
        r = runner.invoke(app, ["plugins", "verify", "--dir", td, "--format", "json"])
        assert r.exit_code == 2, r.stdout
        payload = _stdlib_json.loads(r.stdout)
        # The (only) row's status starts with invalid:parse:…
        assert any(x["status"].startswith("invalid:parse:") for x in payload), payload


def test_plugins_verify_sha_mismatch_no_strict(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        _write_valid_manifest(Path(td) / "badsha", plugin_id="io.astraos.bad", sha_correct=False)
        # default strict=False → only SHA mismatch = warning → exit 0
        r = runner.invoke(app, ["plugins", "verify", "--dir", td])
        assert r.exit_code == 0, r.stdout
        assert "sha_mismatch" in r.stdout


def test_plugins_verify_sha_mismatch_strict(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        _write_valid_manifest(Path(td) / "badsha", plugin_id="io.astraos.bad", sha_correct=False)
        r = runner.invoke(app, ["plugins", "verify", "--dir", td, "--strict"])
        assert r.exit_code == 1, r.stdout
        assert "sha_mismatch" in r.stdout


# ---------------------------------------------------------------------------
# `astraos plugins list`
# ---------------------------------------------------------------------------


def test_plugins_list_none(runner: CliRunner) -> None:
    # With no --dir flag, the CLI boots a full container+kernel — on this
    # machine there are no plugins in ./plugins so we expect (no plugins loaded).
    # The command should succeed and print something about being empty.
    r = runner.invoke(app, ["plugins", "list"])
    assert r.exit_code == 0, (r.exit_code, r.stdout)
    assert "no plugins" in r.stdout.lower()


def test_plugins_list_dir_json(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as td:
        # Use `noesis.plugins.hookspec` importable module as a bona-fide entry point. This is
        # expected to fail to `register_instance call (no PLUGIN / create_plugin() factory,
        # which fails with "no PLUGIN attribute". Result: 0 plugins listed but the list --format json still
        # validates (a valid JSON output, exit 0.
        _write_valid_manifest(Path(td) / "alpha", plugin_id="io.noesis.alpha", entry_point="noesis.plugins.hookspec")
        _write_valid_manifest(Path(td) / "beta", plugin_id="io.noesis.beta", entry_point="noesis.plugins.hookspec")
        r = runner.invoke(app, ["plugins", "list", "-d", td, "-f", "json"])
        assert r.exit_code == 0, r.stdout
        payload = _stdlib_json.loads(r.stdout)
        assert isinstance(payload, list)
        # Structure contract: must be JSON array, keys contain header items with id/version/state/... fields.
        for row in payload:
            for required in ("id", "version", "state", "name", "author", "kind", "entry_point"):
                assert required in row, (required, row.keys())


# ---------------------------------------------------------------------------
# `astraos plugins unload` — missing → exit 1
# ---------------------------------------------------------------------------


def test_plugins_unload_missing(runner: CliRunner) -> None:
    r = runner.invoke(app, ["plugins", "unload", "--id", "does.not.exist.plugin"])
    assert r.exit_code == 1, r.stdout
    assert "not found" in r.stdout.lower()


# ---------------------------------------------------------------------------
# `astraos plugins load` — happy path with an existing entry_point module
# ---------------------------------------------------------------------------


def test_plugins_load_registered(runner: CliRunner, tmp_path: Path) -> None:
    # Use `noesis.plugins.hookspec` (which IS importable) as a bogus entry_point
    # module — it won't have PLUGIN / create_plugin() so we expect a graceful
    # "failed:no PLUGIN attribute …"  state — NOT a stacktrace.
    mpath = tmp_path / "ok"
    _write_valid_manifest(
        mpath,
        plugin_id="io.noesis.fake",
        entry_point="noesis.plugins.hookspec",
    )
    r = runner.invoke(app, ["plugins", "load", "-m", str(mpath / "manifest.json")])
    assert r.exit_code == 1, (r.exit_code, r.stdout)  # any plugin with a failure → exit 1
    assert "failed:no plugin attribute" in r.stdout.lower(), r.stdout


# ---------------------------------------------------------------------------
# `astraos --version` smoke — make sure root Typer app didn't break
# ---------------------------------------------------------------------------


def test_noesis_version(runner: CliRunner) -> None:
    r = runner.invoke(app, ["--version"])
    # version flag exits 0, contains "noesis" and digits (dev fallback or real).
    assert r.exit_code == 0, r.stdout
    assert "noesis" in r.stdout.lower()
    assert any(c.isdigit() for c in r.stdout)


# ---------------------------------------------------------------------------
# PluginManager.verify_manifest_directory unit (direct call, no CLI runner)
# ---------------------------------------------------------------------------


def test_manager_verify_returns_expected_contract(tmp_path: Path) -> None:
    from noesis.plugins.manager import PluginManager

    _write_valid_manifest(tmp_path / "p", plugin_id="com.example.ok")
    results = PluginManager.verify_manifest_directory(tmp_path)
    assert len(results) == 1
    _path, manifest, status = results[0]
    assert manifest is not None
    assert manifest.id == "com.example.ok"
    assert status == "ok"
