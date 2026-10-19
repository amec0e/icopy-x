# -*- coding: utf-8 -*-
"""Behavioural tests for i18n packaging (workstream: packaging).

Spec under test (tools/build_ipk.py):

  * The IPK must ship the language files under ``data/lang/``.  Data
    collection previously walked only the top level of ``data/`` (an
    ``os.listdir`` + ``os.path.isfile`` scan), so ``data/lang/*.json`` was
    silently omitted.
  * Data collection must now include the ``data/lang/`` subtree
    *recursively*, preserving the ``data/lang/`` prefix in the IPK path
    (e.g. ``data/lang/en.json`` -> ``data/lang/en.json``).
  * The spec allows this to be done either by making ``collect_data``
    recurse or by adding a dedicated collector wired into ``build_ipk``;
    therefore these tests assert the observable packaged result (the IPK
    manifest / archive contents), never the internal shape of any one
    collector.
  * Concrete acceptance (from the spec): a dry run
        python tools/build_ipk.py --sn UNIVERSAL --no-flash --no-trojan --dry-run
    lists both ``data/lang/en.json`` and ``data/lang/fr.json``.

These expectations are derived from the spec, not from the current
implementation: each test fails if the behaviour is wrong.
"""

import importlib.util
import os
import subprocess
import sys
import zipfile

import pytest


# ---------------------------------------------------------------------------
# Locations derived from the repo layout (independent of the module)
# ---------------------------------------------------------------------------

# tests/ui/test_i18n_packaging.py -> repo root is three levels up.
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BUILD_IPK_PATH = os.path.join(_REPO_ROOT, "tools", "build_ipk.py")


def _load_build_ipk():
    """Import tools/build_ipk.py as a module (tools/ is not on sys.path)."""
    spec = importlib.util.spec_from_file_location(
        "build_ipk_under_test", _BUILD_IPK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def build_ipk_mod():
    return _load_build_ipk()


def _write(path, data="{}"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)


# ---------------------------------------------------------------------------
# 1. Spec's literal acceptance: the real dry run lists both language files.
# ---------------------------------------------------------------------------

def _run_dry_run():
    proc = subprocess.run(
        [sys.executable, _BUILD_IPK_PATH,
         "--sn", "UNIVERSAL", "--no-flash", "--no-trojan", "--dry-run"],
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc


def test_dry_run_command_succeeds():
    """The documented dry-run invocation must exit 0."""
    proc = _run_dry_run()
    assert proc.returncode == 0, (
        "dry run exited non-zero:\n" + proc.stdout)


def test_dry_run_lists_english_lang_file():
    """The real dry run must list data/lang/en.json (prefix preserved)."""
    proc = _run_dry_run()
    assert "data/lang/en.json" in proc.stdout, (
        "data/lang/en.json missing from dry-run manifest:\n" + proc.stdout)


def test_dry_run_lists_french_lang_file():
    """The real dry run must list data/lang/fr.json (spec acceptance)."""
    proc = _run_dry_run()
    assert "data/lang/fr.json" in proc.stdout, (
        "data/lang/fr.json missing from dry-run manifest:\n" + proc.stdout)


# ---------------------------------------------------------------------------
# 2. Mechanism: build_ipk ships the WHOLE data/lang/ subtree, recursively,
#    with the data/lang/ prefix preserved — proven against a controlled data
#    tree so the result is deterministic and independent of repo content and
#    of which collection strategy the implementation chose.
# ---------------------------------------------------------------------------

def _isolate_to_data_only(mod, monkeypatch, data_dir, empty_dir):
    """Point every source root at an empty dir except DATA_DIR.

    The other collectors guard on os.path.isdir / os.path.exists and return
    nothing. The caller supplies the required factory client/Lua pair, so
    the archive adds only those inputs and the version stamp to the data.
    """
    monkeypatch.setattr(mod, "DATA_DIR", data_dir)
    for attr in ("REPO_ROOT", "SRC_LIB", "SRC_MIDDLEWARE", "SRC_SCREENS",
                 "ORIG_SO_LIB", "ORIG_SO_MAIN", "SRC_MAIN", "RES_DIR",
                 "PLUGINS_DIR", "BUILD_DIR"):
        monkeypatch.setattr(mod, attr, empty_dir)


def _built_namelist(mod, monkeypatch, tmp_path, data_dir):
    empty_dir = str(tmp_path / "empty")
    os.makedirs(empty_dir, exist_ok=True)
    _isolate_to_data_only(mod, monkeypatch, data_dir, empty_dir)
    artifact_dir = tmp_path / "build"
    artifact_dir.mkdir()
    for name in ("factory_proxmark3", "factory_lua.zip"):
        (artifact_dir / name).write_bytes(name.encode())
    monkeypatch.setattr(mod, "BUILD_DIR", str(artifact_dir))

    out_ipk = str(tmp_path / "out.ipk")
    ok = mod.build_ipk(out_ipk, serial_number="UNIVERSAL", dry_run=False,
                       trojan=False, include_flash=False)
    assert ok is True, "build_ipk reported failure"
    assert os.path.exists(out_ipk), "no IPK was written"
    with zipfile.ZipFile(out_ipk, "r") as zf:
        names = set(zf.namelist())
        contents = {n: zf.read(n) for n in names if n.startswith("data/")}
    return names, contents


def test_lang_subtree_shipped_recursively(build_ipk_mod, monkeypatch, tmp_path):
    """Every data/lang/*.json — at any depth — lands in the IPK with the
    data/lang/ prefix preserved."""
    data_dir = str(tmp_path / "data")
    _write(os.path.join(data_dir, "conf.ini"), "[x]\n")
    _write(os.path.join(data_dir, "lang", "en.json"), '{"_name": "English"}')
    _write(os.path.join(data_dir, "lang", "fr.json"), '{"_name": "Francais"}')
    # A nested file proves the collection recurses to arbitrary depth,
    # not just one level under data/lang/.
    _write(os.path.join(data_dir, "lang", "extra", "de.json"),
           '{"_name": "Deutsch"}')

    names, _ = _built_namelist(build_ipk_mod, monkeypatch, tmp_path, data_dir)

    assert "data/lang/en.json" in names
    assert "data/lang/fr.json" in names
    assert "data/lang/extra/de.json" in names


def test_lang_files_carry_exact_prefix(build_ipk_mod, monkeypatch, tmp_path):
    """The prefix must be exactly 'data/lang/' — not 'lang/', not
    'data/data/lang/', and the basename must be unchanged."""
    data_dir = str(tmp_path / "data")
    _write(os.path.join(data_dir, "lang", "fr.json"), '{"_name": "Francais"}')

    names, _ = _built_namelist(build_ipk_mod, monkeypatch, tmp_path, data_dir)

    lang_entries = [n for n in names if n.endswith("fr.json")]
    assert lang_entries == ["data/lang/fr.json"], (
        "fr.json shipped under an unexpected path: %r" % lang_entries)


def test_lang_file_contents_are_shipped_verbatim(build_ipk_mod, monkeypatch,
                                                  tmp_path):
    """The archived language file must be the real source bytes, not an
    empty placeholder."""
    data_dir = str(tmp_path / "data")
    payload = '{"_name": "Francais", "title": {"hello": "Bonjour"}}'
    _write(os.path.join(data_dir, "lang", "fr.json"), payload)

    _, contents = _built_namelist(build_ipk_mod, monkeypatch, tmp_path, data_dir)

    assert contents["data/lang/fr.json"] == payload.encode("utf-8")


def test_top_level_data_files_still_shipped(build_ipk_mod, monkeypatch,
                                            tmp_path):
    """Extending collection to the subtree must NOT drop the pre-existing
    top-level data files (e.g. data/conf.ini)."""
    data_dir = str(tmp_path / "data")
    _write(os.path.join(data_dir, "conf.ini"), "[general]\n")
    _write(os.path.join(data_dir, "lang", "en.json"), '{"_name": "English"}')

    names, _ = _built_namelist(build_ipk_mod, monkeypatch, tmp_path, data_dir)

    assert "data/conf.ini" in names
    assert "data/lang/en.json" in names
