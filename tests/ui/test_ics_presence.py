"""Exercise actual enumeration/Who discovery with fake USB and serial I/O."""
import os
import threading
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


def test_menu_probe_releases_port_before_activity_can_open_it(usb):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def reply():
        calls.append(True)
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
        return b'ISE\r\n'

    usb.ports['/dev/ttyACM1'] = {'reply': reply}
    results, activity_handles = [], []
    presence = decoder.DecoderPresence()
    worker = threading.Thread(target=lambda: results.append(presence.check(lambda: usb.cancel)))
    activity = threading.Thread(target=lambda: activity_handles.append(decoder.detect_decoder()))
    try:
        worker.start()
        assert entered.wait(3)
        usb.cancel = True  # leaving the menu to open the decoder activity
        activity.start()
        assert len(usb.handles) == 1
    finally:
        release.set()
        worker.join(3)
        if activity.ident is not None:
            activity.join(3)
    assert not worker.is_alive() and not activity.is_alive()
    assert results == [False]
    assert usb.handles[0].closed
    assert activity_handles == [usb.handles[1]]
    assert not activity_handles[0].closed  # reading activity owns this handle
    activity_handles[0].close()


def test_successful_presence_probe_keeps_ownership_until_close(usb, monkeypatch):
    """Successful discovery must serialize cleanup as well as the handshake."""
    closing, release_close = threading.Event(), threading.Event()
    original_open = decoder._open_serial
    results = []

    def open_port(path):
        handle = original_open(path)
        original_close = handle.close

        def close():
            closing.set()
            assert release_close.wait(3)
            original_close()

        handle.close = close
        return handle

    monkeypatch.setattr(decoder, '_open_serial', open_port)
    usb.ports['/dev/ttyACM1'] = {'reply': b'ISE\r\n'}
    presence = decoder.DecoderPresence()
    worker = threading.Thread(target=lambda: results.append(presence.check(lambda: False)))
    try:
        worker.start()
        assert closing.wait(3)
        # This is the lock the reading activity acquires before opening a port.
        # Trying from another thread makes the former gap deterministic: the
        # handshake has returned but the presence handle has not closed yet.
        acquired = decoder._detection_lock.acquire(blocking=False)
        if acquired:
            decoder._detection_lock.release()
        assert not acquired, 'Reading activity could open the still-owned probe port'
    finally:
        release_close.set()
        worker.join(3)
    assert not worker.is_alive()
    assert results == [True]
    assert usb.handles[0].closed


def test_foreground_session_owns_handle_before_ui_delivery(usb):
    usb.ports['/dev/ttyACM1'] = {'reply': b'ISE\r\n'}
    session = decoder.DecoderSession()
    try:
        handle = session.detect()
        assert handle is usb.handles[0]
        assert not decoder.DecoderPresence().check(lambda: False)
        assert len(usb.opened) == 1
        assert not handle.closed
    finally:
        session.cancel()
    assert handle.closed
    assert decoder.DecoderPresence().check(lambda: False)
    assert len(usb.opened) == 2
    assert all(port.closed for port in usb.handles)


def test_foreground_cancel_does_not_wait_for_held_handshake(usb):
    entered, release = threading.Event(), threading.Event()
    cancelled = threading.Event()
    session = decoder.DecoderSession()
    results = []

    def reply():
        entered.set()
        assert release.wait(3)
        return b'ISE\r\n'

    usb.ports['/dev/ttyACM1'] = {'reply': reply}
    worker = threading.Thread(target=lambda: results.append(session.detect()))
    cancel_results = []

    def cancel():
        cancel_results.append(session.cancel())
        cancelled.set()

    cancelling = threading.Thread(target=cancel)
    try:
        worker.start()
        assert entered.wait(3)
        # The worker still holds discovery's lock, but no result is published.
        cancelling.start()
        assert cancelled.wait(1), 'Cancellation waited for serial I/O'
        assert cancel_results == [None]
        assert not release.is_set()
    finally:
        release.set()
        worker.join(3)
        if cancelling.ident is not None:
            cancelling.join(3)
        session.cancel()
    assert not worker.is_alive()
    assert results == [None]
    assert usb.handles[0].closed


def test_cancellation_at_discovery_return_closes_before_another_probe(usb, monkeypatch):
    usb.ports['/dev/ttyACM1'] = {'reply': b'ISE\r\n'}
    session = decoder.DecoderSession()
    original = decoder.detect_decoder

    def cancel_after_detect(**kwargs):
        handle = original(**kwargs)
        session.cancel()  # between detector return and result publication
        return handle

    monkeypatch.setattr(decoder, 'detect_decoder', cancel_after_detect)
    try:
        assert session.detect() is None
        assert usb.handles[0].closed
    finally:
        session.cancel()


def test_failed_close_keeps_exclusive_ownership_until_cleanup_succeeds(usb):
    usb.ports['/dev/ttyACM1'] = {'reply': b'ISE\r\n'}
    session = decoder.DecoderSession()
    handle = session.detect()
    close = handle.close

    def fail():
        raise OSError('close failed')

    handle.close = fail
    try:
        with pytest.raises(OSError, match='close failed'):
            session.cancel()
        assert decoder.detect_decoder() is None
        assert usb.opened == ['/dev/ttyACM1']
    finally:
        handle.close = close
        session.cancel()
    assert handle.closed
    assert decoder.DecoderPresence().check(lambda: False)


@pytest.mark.parametrize('enumeration', [None, lambda: [],
    lambda: (_ for _ in ()).throw(OSError('enumeration unavailable'))])
def test_windows_enumeration_failure_never_guesses_ports(usb, monkeypatch, enumeration):
    monkeypatch.setattr(decoder.sys, 'platform', 'win32')
    monkeypatch.setattr(decoder, '_comports', enumeration)
    assert decoder.detect_decoder() is None
    assert usb.opened == []
