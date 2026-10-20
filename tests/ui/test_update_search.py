"""Regression tests for update.search() / _scan_fw_dir() macOS handling.

macOS writes an AppleDouble sidecar (``._<name>``) next to every file copied
onto the iCopy-X USB volume.  Because ``._icopy-x-flash.ipk`` sorts ahead of
``icopy-x-flash.ipk``, the updater used to select the sidecar and fail the
flash with error 0x05 (issue #10).  These tests pin the fix so it cannot
silently regress.
"""

import os
import zipfile

import pytest

import update


def _touch(path, data=b"stub"):
    with open(path, "wb") as f:
        f.write(data)


def test_search_ignores_appledouble_sidecar(tmp_path):
    real = os.path.join(str(tmp_path), "icopy-x-flash.ipk")
    sidecar = os.path.join(str(tmp_path), "._icopy-x-flash.ipk")
    _touch(real)
    _touch(sidecar)

    # Sanity check: the sidecar sorts first — the exact condition that used
    # to make search() pick the wrong file.
    assert sorted(os.listdir(str(tmp_path)))[0] == "._icopy-x-flash.ipk"

    assert update.search(str(tmp_path)) == real


def test_search_returns_none_when_only_sidecar(tmp_path):
    _touch(os.path.join(str(tmp_path), "._icopy-x-flash.ipk"))
    assert update.search(str(tmp_path)) is None


def test_search_finds_real_ipk_without_sidecar(tmp_path):
    real = os.path.join(str(tmp_path), "update.ipk")
    _touch(real)
    assert update.search(str(tmp_path)) == real


def test_orphaned_older_sidecar_cannot_replace_current_package(tmp_path, monkeypatch):
    """Issue #10 follow-up: metadata remains after deleting an older IPK."""
    monkeypatch.setattr(update, '_found_ipk', None)
    real = tmp_path / 'newest.ipk'
    with zipfile.ZipFile(real, 'w') as archive:
        for name in ('app.py', 'lib/version.py', 'main/install.py'):
            archive.writestr(name, '# Package structure fixture; never installed.\n')
    (tmp_path / '._newest.ipk').write_bytes(b'AppleDouble metadata')
    (tmp_path / '._older.ipk').write_bytes(b'Orphaned AppleDouble metadata')
    assert not (tmp_path / 'older.ipk').exists()
    assert update.search(str(tmp_path)) == str(real)
    assert update.checkPkg()


def test_only_orphaned_sidecar_clears_previous_package_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(update, '_found_ipk', None)
    real = tmp_path / 'older.ipk'
    real.write_bytes(b'old package')
    (tmp_path / '._older.ipk').write_bytes(b'Orphaned AppleDouble metadata')
    assert update.search(str(tmp_path)) == str(real)
    real.unlink()
    assert update.search(str(tmp_path)) is None
    with pytest.raises(RuntimeError, match='No IPK found'):
        update.checkPkg()


def test_is_hidden():
    assert update._is_hidden("._icopy-x-flash.ipk")
    assert update._is_hidden(".DS_Store")
    assert not update._is_hidden("icopy-x-flash.ipk")
    assert not update._is_hidden("update.ipk")


def test_scan_fw_dir_ignores_appledouble(tmp_path, monkeypatch):
    fw = os.path.join(str(tmp_path), "fw")
    os.mkdir(fw)
    _touch(os.path.join(fw, "fullimage.pm3"))
    _touch(os.path.join(fw, "._fullimage.pm3"))
    monkeypatch.setattr(update, "_FW_PATH", fw + os.sep)

    results = update._scan_fw_dir(None, ".pm3")
    names = sorted(os.path.basename(r) for r in results)
    assert names == ["fullimage.pm3"]
