"""Negative controls use the production detector's exception boundaries."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.qemu_artifact.decoder_menu_case import SerialEvidence


@pytest.fixture
def detector(monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'src/middleware/ics_decoder.py'
    spec = importlib.util.spec_from_file_location('decoder_guard_control', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.sys, 'platform', 'linux')
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    return module


def test_actual_guard_excludes_pm3_and_accepts_accessory(detector):
    evidence = SerialEvidence({'/dev/ttyACM0': (1, b'ISE\r\n'),
                               '/dev/ttyACM1': (2, b'ISE\r\n')})
    detector.serial = SimpleNamespace(Serial=evidence.open)
    handle = detector.detect_decoder(list(evidence.ports), quiet=True)
    assert evidence.opened == ['/dev/ttyACM1']
    assert handle is evidence.handles[0]
    handle.close()
    evidence.assert_clean()


def test_removed_pm3_guard_is_detected_despite_swallowed_open_error(detector, monkeypatch):
    evidence = SerialEvidence({'/dev/ttyACM0': (1, b'ISE\r\n')})
    detector.serial = SimpleNamespace(Serial=evidence.open)
    monkeypatch.setattr(detector, '_is_pm3_port', lambda _: False)
    assert detector.detect_decoder(list(evidence.ports), quiet=True) is None
    assert evidence.opened == ['/dev/ttyACM0']
    assert evidence.handles == []
    with pytest.raises(AssertionError, match='touched the PM3'):
        evidence.assert_clean()


@pytest.mark.parametrize('attribute,value,message', [
    ('_BAUD_RATE', 9600, 'serial configuration'),
    ('_READLINE_TIMEOUT', 30, 'serial configuration'),
    ('_CMD_WHO', 'RD\r\n', 'handshake'),
])
def test_swallowed_serial_contract_errors_still_fail_evidence(detector, monkeypatch,
                                                             attribute, value, message):
    evidence = SerialEvidence({'/dev/ttyACM1': (1, b'ISE\r\n')})
    detector.serial = SimpleNamespace(Serial=evidence.open)
    monkeypatch.setattr(detector, attribute, value)
    assert detector.detect_decoder(list(evidence.ports), quiet=True) is None
    with pytest.raises(AssertionError, match=message):
        evidence.assert_clean()


def test_swallowed_unbounded_read_still_fails_evidence():
    evidence = SerialEvidence({'/dev/ttyACM1': (1, b'ISE\r\n')})
    port = evidence.open('/dev/ttyACM1', 115200, 1.2, 1.2)
    try:
        port.readline(65536)
    except Exception:
        pass
    port.close()
    with pytest.raises(AssertionError, match='Unbounded'):
        evidence.assert_clean()
