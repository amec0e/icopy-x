"""Real discovery threads, held UI delivery, and observable serial ownership."""
from threading import Event, Thread as RealThread, get_ident
from types import SimpleNamespace
import queue

import pytest

import actstack
import ics_credentials
import ics_decoder
from activity_main import ICSDecoderActivity, IClassSEActivity
from tests.ui.conftest import MockCanvas


@pytest.fixture
def discovery(monkeypatch, tmp_path):
    import threading
    import activity_main
    actstack._reset()
    saved = ics_credentials.SavedCredentials(str(tmp_path / 'saved'))
    monkeypatch.setattr(ics_credentials, 'SavedCredentials', lambda: saved)
    monkeypatch.setattr(threading, 'Thread', RealThread)
    monkeypatch.setattr(ics_decoder.sys, 'platform', 'linux')
    monkeypatch.setattr(ics_decoder.time, 'sleep', lambda _: None)
    monkeypatch.setattr(ics_decoder, 'serial', object())
    monkeypatch.setattr(ics_decoder.glob, 'glob', lambda _: ['/dev/ttyACM1'])
    monkeypatch.setattr(ics_decoder, '_log', lambda _: None)
    bus = SimpleNamespace(handles=[], overlaps=[], hold=False, ui_violations=[],
                          entered=Event(), release=Event(), queued=Event())
    ui_thread = get_ident()

    def assert_ui():
        if get_ident() != ui_thread:
            bus.ui_violations.append(get_ident())
            raise AssertionError('Worker touched Tk')

    class Canvas(MockCanvas):
        def after(self, *args, **kwargs):
            assert_ui()
            return super().after(*args, **kwargs)

        def after_cancel(self, *args, **kwargs):
            assert_ui()
            return super().after_cancel(*args, **kwargs)

        def create_text(self, *args, **kwargs):
            assert_ui()
            return super().create_text(*args, **kwargs)

    class ResultQueue(queue.Queue):
        def put(self, item):
            super().put(item)
            bus.queued.set()

    monkeypatch.setattr(activity_main, 'queue', SimpleNamespace(Queue=ResultQueue))
    actstack._canvas_factory = Canvas

    def open_port(path):
        if any(not h.closed for h in bus.handles):
            bus.overlaps.append(path)
        handle = SimpleNamespace(closed=False, writes=[], close_failures=0, close_calls=0)
        handle.reset_input_buffer = lambda: None
        handle.write = handle.writes.append

        def close():
            handle.close_calls += 1
            if handle.close_failures:
                handle.close_failures -= 1
                raise OSError('transient close failure')
            handle.closed = True

        def response(size):
            bus.entered.set()
            if bus.hold:
                assert bus.release.wait(3)
            return b'ISE\r\n'

        handle.close = close
        handle.readline = response
        bus.handles.append(handle)
        return handle

    def after(*args):
        assert_ui()
        return 'root-timer'

    monkeypatch.setattr(ics_decoder, '_open_serial', open_port)
    bus.activity = actstack.start_activity(ICSDecoderActivity)
    actstack._root = SimpleNamespace(after=after, after_cancel=lambda _: assert_ui())
    yield bus
    bus.release.set()
    worker = bus.activity._detect_thread
    if worker is not None:
        worker.join(3)
        assert not worker.is_alive()
    bus.activity.onDestroy()
    for handle in bus.handles:
        handle.close_failures = 0
        if not handle.closed:
            ics_decoder.close_decoder(handle)
    actstack._reset()
    assert bus.ui_violations == []  # Cannot be swallowed by production catches.
    assert bus.overlaps == []
    assert not ics_decoder._failed_closes
    assert ics_decoder._active_session is None


def complete_worker(bus):
    assert bus.queued.wait(3)
    bus.activity._detect_thread.join(3)
    assert not bus.activity._detect_thread.is_alive()


def probe_again(bus):
    handle = ics_decoder.detect_decoder(quiet=True)
    assert handle is bus.handles[-1]
    assert bus.overlaps == []
    ics_decoder.close_decoder(handle)


def test_pending_tk_delivery_cannot_overlap_menu_probe(discovery):
    bus = discovery
    activity = bus.activity
    activity._start_read()
    complete_worker(bus)
    assert activity._ser is None
    assert ics_decoder.detect_decoder(quiet=True) is None
    assert len(bus.handles) == 1
    activity._back()
    assert bus.handles[0].closed
    activity.getCanvas().advance(50)
    assert activity._state == activity.STATE_HOME
    assert activity._ser is None
    probe_again(bus)
    assert len(bus.handles) == 2


def test_destroy_releases_handle_even_if_tk_never_delivers(discovery):
    bus = discovery
    bus.activity._start_read()
    complete_worker(bus)
    bus.activity.onDestroy()
    assert bus.handles[0].closed
    bus.activity.getCanvas().advance(50)
    assert bus.activity._state == bus.activity.STATE_DESTROYED
    assert bus.activity._ser is None
    probe_again(bus)


def test_back_during_handshake_closes_before_menu_can_open(discovery):
    bus = discovery
    bus.hold = True
    bus.activity._start_read()
    assert bus.entered.wait(3)
    bus.activity._back()
    assert not bus.release.is_set()
    bus.release.set()
    complete_worker(bus)
    assert bus.handles[0].closed
    probe_again(bus)


@pytest.mark.parametrize('legacy', [False, True])
def test_worker_failure_only_renders_on_ui_timer(discovery, monkeypatch, legacy):
    bus = discovery

    def fail(self):
        raise OSError('enumeration unavailable')

    monkeypatch.setattr(ics_decoder.DecoderSession, 'detect', fail)
    if legacy:
        bus.activity.onDestroy()
        bus.activity = actstack.start_activity(IClassSEActivity)
    else:
        bus.activity._start_read()
    complete_worker(bus)
    canvas = bus.activity.getCanvas()
    assert 'No decoder found!' not in canvas.get_all_text()
    canvas.advance(50)
    assert 'No decoder found!' in canvas.get_all_text()
    assert not bus.handles


@pytest.mark.parametrize('legacy', [False, True])
def test_success_only_adopted_on_ui_timer(discovery, legacy):
    bus = discovery
    if legacy:
        bus.activity.onDestroy()
        bus.activity = actstack.start_activity(IClassSEActivity)
    else:
        bus.activity._start_read()
    complete_worker(bus)
    assert bus.activity._ser is None
    bus.activity.getCanvas().advance(50)
    assert bus.activity._ser is bus.handles[0]
    assert bus.activity._state == bus.activity.STATE_READING


def test_legacy_activity_also_owns_pending_handle_until_destroy(discovery):
    bus = discovery
    bus.activity.onDestroy()
    bus.activity = actstack.start_activity(IClassSEActivity)
    complete_worker(bus)
    assert ics_decoder.detect_decoder(quiet=True) is None
    assert len(bus.handles) == 1
    bus.activity.onDestroy()
    assert bus.handles[0].closed
    bus.activity.getCanvas().advance(50)
    assert bus.activity._state == bus.activity.STATE_DESTROYED
    probe_again(bus)


def test_cancelled_late_result_recovers_failed_close_without_activity(discovery, monkeypatch):
    bus = discovery
    returned, publish = Event(), Event()
    original = ics_decoder.detect_decoder

    def held_result(**kwargs):
        handle = original(**kwargs)
        handle.close_failures = 1
        returned.set()
        assert publish.wait(3)
        return handle

    monkeypatch.setattr(ics_decoder, 'detect_decoder', held_result)
    bus.activity._start_read()
    try:
        assert returned.wait(3)
        bus.activity._back()
        assert bus.activity._decoder_session is None
    finally:
        publish.set()
        bus.activity._detect_thread.join(3)
    complete_worker(bus)
    assert not bus.handles[0].closed
    assert bus.handles[0].close_calls == 1
    monkeypatch.setattr(ics_decoder, 'detect_decoder', original)
    probe_again(bus)
    assert bus.handles[0].closed
    assert len(bus.handles) == 2
    bus.activity.getCanvas().advance(50)
    assert bus.activity._state == bus.activity.STATE_HOME


def test_legacy_destroy_failed_close_keeps_recoverable_owner(discovery):
    bus = discovery
    bus.activity.onDestroy()
    bus.activity = actstack.start_activity(IClassSEActivity)
    complete_worker(bus)
    bus.activity.getCanvas().advance(50)
    handle = bus.handles[0]
    handle.close_failures = 1
    bus.activity.onDestroy()
    assert handle.close_calls == 1  # No raw fallback bypassing ownership.
    assert not handle.closed
    probe_again(bus)
    assert handle.closed
    assert len(bus.handles) == 2
    bus.activity.getCanvas().advance(50)
    assert bus.activity._state == bus.activity.STATE_DESTROYED
