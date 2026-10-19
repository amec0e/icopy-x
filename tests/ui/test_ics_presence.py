"""Exercise actual enumeration/Who discovery with fake USB and serial I/O."""
import os
from types import SimpleNamespace

import pytest
import ics_decoder as decoder


@pytest.fixture
def usb(monkeypatch):
    bus = SimpleNamespace(ports={}, opened=[], handles=[], cancel=False)

    def open_port(path):
        bus.opened.append(path)
        data = bus.ports[path]
        handle = SimpleNamespace(closed=False, writes=[])
        handle.reset_input_buffer = lambda: None
        handle.write = handle.writes.append

        def readline(size):
            assert size == 32
            response = data['reply']
            if callable(response):
                return response()
            if isinstance(response, Exception):
                raise response
            return response

        handle.readline = readline
        handle.close = lambda: setattr(handle, 'closed', True)
        bus.handles.append(handle)
        return handle

    def stat(path):
        if path not in bus.ports:
            raise FileNotFoundError(path)
        return SimpleNamespace(st_ino=bus.ports[path].get('inode', 1), st_ctime_ns=1)

    monkeypatch.setattr(decoder.sys, 'platform', 'linux')
    monkeypatch.setattr(decoder, 'os', SimpleNamespace(path=os.path, stat=stat))
    monkeypatch.setattr(decoder, 'serial', object())
    monkeypatch.setattr(decoder.glob, 'glob', lambda pattern: list(bus.ports))
    monkeypatch.setattr(decoder, '_open_serial', open_port)
    monkeypatch.setattr(decoder.time, 'sleep', lambda _: None)
    monkeypatch.setattr(decoder, '_log', lambda _: None)
    return bus


def test_internal_pm3_and_alias_never_opened(usb, monkeypatch):
    usb.ports = {'/dev/ttyACM0': {'reply': b'ISE\r\n'},
                 '/dev/ttyUSB9': {'reply': b'ISE\r\n'}}
    monkeypatch.setattr(decoder.os, 'path', SimpleNamespace(realpath=lambda p:
        '/dev/ttyACM0' if p == '/dev/ttyUSB9' else p))
    assert decoder.decoder_ports() == []
    # Even an explicitly supplied candidate must pass the opening guard.
    assert decoder.detect_decoder(list(usb.ports)) is None
    assert not decoder.DecoderPresence().check(lambda: False)
    assert usb.opened == []


@pytest.mark.parametrize('reply', [b'', b'NOISE\r\n', b'ISE extra\r\n',
                                  b'\xffISE\r\n', b' ISE\r\n', OSError('unplug')])
def test_non_decoder_never_visible_and_probe_attempts_are_bounded(usb, reply):
    usb.ports = {'/dev/ttyACM1': {'reply': reply}}
    presence = decoder.DecoderPresence()
    for _ in range(8):
        assert not presence.check(lambda: False)
    assert len(usb.opened) == 3
    assert all(handle.closed for handle in usb.handles)


def test_hotplug_unplug_and_replaced_device_at_same_path(usb):
    presence = decoder.DecoderPresence()
    assert not presence.check(lambda: False)
    usb.ports['/dev/ttyACM1'] = {'reply': b'ISE\r\n', 'inode': 1}
    assert presence.check(lambda: False)
    assert usb.handles[0].writes == [b'Who\r\n']
    assert usb.handles[0].closed
    assert presence.check(lambda: False)
    assert usb.opened == ['/dev/ttyACM1']  # passive while same attachment remains
    usb.ports['/dev/ttyACM1'] = {'reply': b'other\r\n', 'inode': 2}
    assert not presence.check(lambda: False)
    usb.ports.clear()
    assert not presence.check(lambda: False)
    usb.ports['/dev/ttyACM1'] = {'reply': b'ISE\r\n', 'inode': 3}
    assert presence.check(lambda: False)
    assert all(handle.closed for handle in usb.handles)


def test_startup_timeout_retries_then_confirms(usb):
    usb.ports['/dev/ttyACM1'] = {'reply': b''}
    presence = decoder.DecoderPresence()
    assert not presence.check(lambda: False)
    usb.ports['/dev/ttyACM1']['reply'] = b'ISE\r\n'
    assert presence.check(lambda: False)
    assert len(usb.opened) == 2


def test_cancellation_during_handshake_closes_handle_and_discards_identity(usb):
    def reply():
        usb.cancel = True
        return b'ISE\r\n'
    usb.ports['/dev/ttyACM1'] = {'reply': reply}
    assert not decoder.DecoderPresence().check(lambda: usb.cancel)
    assert usb.handles[0].closed


def test_unplug_during_handshake_does_not_publish_stale_presence(usb):
    def reply():
        usb.ports.clear()
        return b'ISE\r\n'
    usb.ports['/dev/ttyACM1'] = {'reply': reply}
    assert not decoder.DecoderPresence().check(lambda: False)
    assert usb.handles[0].closed


@pytest.mark.parametrize('enumeration', [None, lambda: [],
    lambda: (_ for _ in ()).throw(OSError('enumeration unavailable'))])
def test_windows_enumeration_failure_never_guesses_ports(usb, monkeypatch, enumeration):
    monkeypatch.setattr(decoder.sys, 'platform', 'win32')
    monkeypatch.setattr(decoder, '_comports', enumeration)
    assert decoder.detect_decoder() is None
    assert usb.opened == []
