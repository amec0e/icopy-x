"""Real discovery threads, held Tk delivery, and observable serial ownership."""
from threading import Event, Thread as RealThread
from types import SimpleNamespace

import pytest

import actstack
import ics_credentials
import ics_decoder
from activity_main import ICSDecoderActivity, IClassSEActivity
from tests.ui.conftest import MockCanvas


@pytest.fixture
def discovery(monkeypatch, tmp_path):
    import threading
    actstack._reset()
    actstack._canvas_factory = MockCanvas
    saved = ics_credentials.SavedCredentials(str(tmp_path / 'saved'))
    monkeypatch.setattr(ics_credentials, 'SavedCredentials', lambda: saved)
    monkeypatch.setattr(threading, 'Thread', RealThread)
    monkeypatch.setattr(ics_decoder.sys, 'platform', 'linux')
    monkeypatch.setattr(ics_decoder.time, 'sleep', lambda _: None)
    monkeypatch.setattr(ics_decoder, 'serial', object())
    monkeypatch.setattr(ics_decoder.glob, 'glob', lambda _: ['/dev/ttyACM1'])
    monkeypatch.setattr(ics_decoder, '_log', lambda _: None)
    bus = SimpleNamespace(handles=[], overlaps=[], callbacks=[], hold=False,
                          entered=Event(), release=Event(), queued=Event())

    def open_port(path):
        if any(not h.closed for h in bus.handles):
            bus.overlaps.append(path)
        handle = SimpleNamespace(closed=False, writes=[])
        handle.reset_input_buffer = lambda: None
        handle.write = handle.writes.append
        handle.close = lambda: setattr(handle, 'closed', True)

        def response(size):
            bus.entered.set()
            if bus.hold:
                assert bus.release.wait(3)
            return b'ISE\r\n'

        handle.readline = response
        bus.handles.append(handle)
        return handle

    def after(delay, callback, *args):
        bus.callbacks.append((callback, args))
        bus.queued.set()
        return len(bus.callbacks)

    monkeypatch.setattr(ics_decoder, '_open_serial', open_port)
    activity = actstack.start_activity(ICSDecoderActivity)
    # The actual worker queues its result here; the test controls Tk delivery.
    actstack._root = SimpleNamespace(after=after, after_cancel=lambda _: None)
    bus.activity = activity
    yield bus
    bus.release.set()
    worker = bus.activity._detect_thread
    if worker is not None:
        worker.join(3)
        assert not worker.is_alive()
    bus.activity.onDestroy()
    actstack._reset()


def test_pending_tk_delivery_cannot_overlap_menu_probe(discovery):
    bus = discovery
    activity = bus.activity
    activity._start_read()
    assert bus.queued.wait(3)
    activity._detect_thread.join(3)
    assert activity._ser is None  # Tk has not adopted the result yet.
    assert ics_decoder.detect_decoder(quiet=True) is None
    assert len(bus.handles) == 1
    assert bus.overlaps == []
    activity._back()
    assert bus.handles[0].closed
    callback, args = bus.callbacks[0]
    callback(*args)
    assert activity._state == activity.STATE_HOME
    assert activity._ser is None
    next_handle = ics_decoder.detect_decoder(quiet=True)
    assert next_handle is bus.handles[1]
    next_handle.close()
    assert bus.overlaps == []


def test_destroy_releases_handle_even_if_tk_never_delivers(discovery):
    bus = discovery
    bus.activity._start_read()
    assert bus.queued.wait(3)
    bus.activity._detect_thread.join(3)
    bus.activity.onDestroy()
    assert bus.handles[0].closed
    callback, args = bus.callbacks[0]
    callback(*args)
    assert bus.activity._state == bus.activity.STATE_DESTROYED
    assert bus.activity._ser is None
    next_handle = ics_decoder.detect_decoder(quiet=True)
    assert next_handle is bus.handles[1]
    next_handle.close()
    assert bus.overlaps == []


def test_back_during_handshake_closes_before_menu_can_open(discovery):
    bus = discovery
    bus.hold = True
    bus.activity._start_read()
    assert bus.entered.wait(3)
    bus.activity._back()
    assert not bus.release.is_set()
    bus.release.set()
    bus.activity._detect_thread.join(3)
    assert bus.handles[0].closed
    next_handle = ics_decoder.detect_decoder(quiet=True)
    assert next_handle is bus.handles[1]
    next_handle.close()
    assert bus.overlaps == []


def test_failed_tk_enqueue_releases_pending_handle(discovery):
    bus = discovery

    def destroyed_root(*args):
        raise RuntimeError('Tk root destroyed')

    actstack._root.after = destroyed_root
    bus.activity._start_read()
    bus.activity._detect_thread.join(3)
    assert not bus.activity._detect_thread.is_alive()
    assert bus.handles[0].closed
    next_handle = ics_decoder.detect_decoder(quiet=True)
    assert next_handle is bus.handles[1]
    next_handle.close()
    assert bus.overlaps == []


def test_legacy_activity_also_owns_pending_handle_until_destroy(discovery):
    bus = discovery
    bus.activity.onDestroy()
    bus.activity = actstack.start_activity(IClassSEActivity)
    assert bus.queued.wait(3)
    bus.activity._detect_thread.join(3)
    assert ics_decoder.detect_decoder(quiet=True) is None
    assert len(bus.handles) == 1
    bus.activity.onDestroy()
    assert bus.handles[0].closed
    callback, args = bus.callbacks[0]
    callback(*args)
    assert bus.activity._state == bus.activity.STATE_DESTROYED
    next_handle = ics_decoder.detect_decoder(quiet=True)
    assert next_handle is bus.handles[1]
    next_handle.close()
    assert bus.overlaps == []
