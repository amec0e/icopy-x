"""Real worker threads with UI delivery held until the test advances Tk."""
from threading import Event, Thread as RealThread, get_ident
from types import SimpleNamespace

import pytest

import actstack
import ics_credentials
import ics_decoder
from _constants import KEY_OK
from activity_main import ICSDecoderActivity, IClassSEActivity
from tests.ui.activities.test_ics_decoder import captured
from tests.ui.conftest import MockCanvas


@pytest.fixture
def worker_ui(monkeypatch, tmp_path):
    import threading

    actstack._reset()
    ui_thread = get_ident()
    bus = SimpleNamespace(threads=[], violations=[], calls=[], release=Event(),
                          entered=Event())

    def assert_ui():
        if get_ident() != ui_thread:
            bus.violations.append('worker touched Tk')
            raise AssertionError(bus.violations[-1])

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

    class Worker(RealThread):
        def start(self):
            bus.threads.append(self)
            super().start()

    saved = ics_credentials.SavedCredentials(str(tmp_path / 'saved'))
    monkeypatch.setattr(ics_credentials, 'SavedCredentials', lambda: saved)
    monkeypatch.setattr(threading, 'Thread', Worker)
    monkeypatch.setattr(ics_decoder, 'detect_decoder', lambda **kw: None)
    monkeypatch.setattr(ics_decoder, 'detect_target', lambda: 'hf_iclass')
    monkeypatch.setattr(ics_decoder, 'write_to_card',
                        lambda block: bus.calls.append(('write', block)) or True)
    monkeypatch.setattr(ics_decoder, 'verify_target_card',
                        lambda target, source: (True, 'Verified'))
    monkeypatch.setattr(ics_decoder, 'read_card', lambda port: captured())
    actstack._canvas_factory = Canvas

    def start(cls):
        activity = actstack.start_activity(cls)
        for thread in bus.threads:
            thread.join(3)
            assert not thread.is_alive()
        activity._cancel_decoder_session()
        bus.threads.clear()
        canvas = activity.getCanvas()
        actstack._root = SimpleNamespace(after=canvas.after, after_cancel=canvas.after_cancel)
        activity._source_data = captured()
        activity._target_type = 'hf_iclass'
        bus.activity = activity
        return activity

    bus.start = start
    yield bus
    bus.release.set()
    for thread in bus.threads:
        thread.join(3)
        assert not thread.is_alive()
    if hasattr(bus, 'activity'):
        bus.activity.onDestroy()
    actstack._reset()
    # Outside production exception handlers: a swallowed Tk assertion still fails.
    assert bus.violations == []


def join_workers(bus):
    assert bus.threads
    for thread in bus.threads:
        thread.join(3)
        assert not thread.is_alive()


@pytest.mark.parametrize('cls', [ICSDecoderActivity, IClassSEActivity])
@pytest.mark.parametrize('operation', ['read', 'write', 'verify'])
def test_workers_only_publish_data_until_ui_delivery(worker_ui, cls, operation):
    bus = worker_ui
    activity = bus.start(cls)
    if operation == 'read':
        activity._ser = SimpleNamespace(close=lambda: None)
        activity._source_data = None
        activity._state = activity.STATE_READING
        activity._poll_decoder()
        pending = activity.STATE_READING
    elif operation == 'write':
        activity._state = activity.STATE_WAIT_BLANK
        activity._target_poll_timer = activity.getCanvas().after(1000, lambda: None)
        activity.onKeyEvent(KEY_OK)
        pending = activity.STATE_WRITING
    else:
        activity._state = activity.STATE_RESULT
        activity._do_verify()
        pending = activity.STATE_WRITING
    join_workers(bus)
    assert bus.violations == []
    assert activity._state == pending
    assert activity._last_write_ok is False
    assert activity._verify_success is None
    if operation == 'read':
        assert activity._source_data is None
    activity.getCanvas().advance(50)
    if operation == 'read':
        assert activity._source_data == captured()
        assert activity._state == (activity.STATE_DECODED if cls is ICSDecoderActivity
                                   else activity.STATE_WAIT_BLANK)
    else:
        assert activity._state == activity.STATE_RESULT
        assert (activity._last_write_ok if operation == 'write'
                else activity._verify_success) is True


@pytest.mark.parametrize('cls', [ICSDecoderActivity, IClassSEActivity])
@pytest.mark.parametrize('operation', ['write', 'verify'])
def test_destroy_during_detection_prevents_next_device_command(worker_ui, monkeypatch,
                                                               cls, operation):
    bus = worker_ui
    activity = bus.start(cls)

    def detect():
        bus.entered.set()
        assert bus.release.wait(3)
        return 'hf_iclass'

    monkeypatch.setattr(ics_decoder, 'detect_target', detect)
    monkeypatch.setattr(ics_decoder, 'verify_target_card',
                        lambda *args: bus.calls.append(('verify',)) or (True, 'Verified'))
    activity._state = activity.STATE_WAIT_BLANK
    if operation == 'write':
        activity.onKeyEvent(KEY_OK)
    else:
        activity._do_verify()
    assert bus.entered.wait(3)
    activity.onDestroy()
    bus.release.set()
    join_workers(bus)
    activity.getCanvas().advance(100)
    assert bus.calls == []
    assert activity._state == activity.STATE_DESTROYED
    assert activity._last_write_ok is False
    assert activity._verify_success is None


@pytest.mark.parametrize('cls', [ICSDecoderActivity, IClassSEActivity])
@pytest.mark.parametrize('operation', ['read', 'write', 'verify'])
def test_device_errors_finish_on_ui_thread(worker_ui, monkeypatch, cls, operation):
    bus = worker_ui
    activity = bus.start(cls)

    def fail(*args):
        raise OSError('device disconnected')

    if operation == 'read':
        monkeypatch.setattr(ics_decoder, 'read_card', fail)
        activity._ser = SimpleNamespace(close=lambda: None)
        activity._state = activity.STATE_READING
        activity._poll_decoder()
    elif operation == 'write':
        monkeypatch.setattr(ics_decoder, 'write_to_card', fail)
        activity._state = activity.STATE_WAIT_BLANK
        activity.onKeyEvent(KEY_OK)
    else:
        monkeypatch.setattr(ics_decoder, 'verify_target_card', fail)
        activity._do_verify()
    join_workers(bus)
    activity.getCanvas().advance(50)
    assert activity._operation is None
    if operation == 'read':
        assert activity._read_in_flight is False
        if cls is ICSDecoderActivity:
            assert activity._source_data['status'] == 'decoder_error'
            assert activity._state == activity.STATE_DECODED
        else:
            assert activity._state == activity.STATE_READING
            assert activity._poll_timer is not None  # Legacy retry behavior.
    else:
        assert activity._state == activity.STATE_RESULT
        assert not activity.isbusy()
        assert activity._last_write_ok is False
        if operation == 'verify':
            assert activity._verify_success is False
            assert activity._verify_msg == 'Verify error'


@pytest.mark.parametrize('operation', ['write', 'verify'])
def test_credential_and_target_are_snapshotted_before_worker_runs(worker_ui, monkeypatch, operation):
    bus = worker_ui
    activity = bus.start(ICSDecoderActivity)
    jobs = []
    monkeypatch.setattr(activity, 'startBGTask', jobs.append)
    observed = []
    monkeypatch.setattr(ics_decoder, 'verify_target_card',
                        lambda target, source: observed.append((target, source)) or (True, 'OK'))
    if operation == 'write':
        activity._do_write()
    else:
        activity._do_verify()
    activity._source_data['blk7'] = '0000000000000000'
    activity._source_data['raw_fields']['new'] = 'mutated'
    activity._target_type = 'lf_t5577'
    jobs[0]()
    assert activity._state == activity.STATE_WRITING
    activity.getCanvas().advance(50)
    if operation == 'write':
        assert bus.calls == [('write', captured()['blk7'])]
    else:
        assert observed == [('hf_iclass', captured())]


@pytest.mark.parametrize('operation', ['write', 'verify'])
def test_destroy_before_worker_runs_does_no_io(worker_ui, monkeypatch, operation):
    bus = worker_ui
    activity = bus.start(ICSDecoderActivity)
    jobs = []
    monkeypatch.setattr(activity, 'startBGTask', jobs.append)
    monkeypatch.setattr(ics_decoder, 'detect_target', lambda: bus.calls.append(('detect',)))
    activity._do_write() if operation == 'write' else activity._do_verify()
    activity.onDestroy()
    jobs[0]()
    activity.getCanvas().advance(50)
    assert bus.calls == []
    assert activity._state == activity.STATE_DESTROYED


@pytest.mark.parametrize('operation', ['write', 'verify'])
def test_already_dispatched_io_finishes_without_redrawing_after_destroy(worker_ui, monkeypatch, operation):
    bus = worker_ui
    activity = bus.start(ICSDecoderActivity)

    def held_io(*args):
        bus.calls.append(operation)
        bus.entered.set()
        assert bus.release.wait(3)
        return True if operation == 'write' else (True, 'Verified')

    monkeypatch.setattr(ics_decoder, 'write_to_card', held_io)
    monkeypatch.setattr(ics_decoder, 'verify_target_card', held_io)
    activity._do_write() if operation == 'write' else activity._do_verify()
    assert bus.entered.wait(3)
    activity.onDestroy()
    bus.release.set()
    join_workers(bus)
    activity.getCanvas().advance(100)
    assert bus.calls == [operation]  # No replay or claim of undoing dispatched I/O.
    assert activity._state == activity.STATE_DESTROYED
    assert activity._last_write_ok is False
    assert activity._verify_success is None


def test_stale_read_result_cannot_replace_new_read(worker_ui, monkeypatch):
    bus = worker_ui
    activity = bus.start(ICSDecoderActivity)
    old_port = SimpleNamespace(close=lambda: None)
    new_port = SimpleNamespace(close=lambda: None)
    current_capture = captured()
    current_capture['raw_response_text'] = 'new session'

    def held_read(port):
        if port is old_port:
            bus.entered.set()
            assert bus.release.wait(3)
            return captured()
        return current_capture

    monkeypatch.setattr(ics_decoder, 'read_card', held_read)
    activity._source_data = None
    activity._ser = old_port
    activity._state = activity.STATE_READING
    activity._poll_decoder()
    assert bus.entered.wait(3)
    activity._back()
    activity._ser = new_port
    activity._state = activity.STATE_READING
    activity._poll_decoder()
    bus.release.set()
    join_workers(bus)
    activity.getCanvas().advance(50)
    assert activity._source_data == current_capture
    assert activity._state == activity.STATE_DECODED


@pytest.mark.parametrize('operation', ['read', 'write', 'verify'])
def test_thread_start_failure_is_delivered_as_an_error(worker_ui, monkeypatch, operation):
    bus = worker_ui
    activity = bus.start(ICSDecoderActivity)

    def fail(job):
        raise RuntimeError('cannot start new thread')

    monkeypatch.setattr(activity, 'startBGTask', fail)
    if operation == 'read':
        activity._ser = SimpleNamespace(close=lambda: None)
        activity._state = activity.STATE_READING
        activity._poll_decoder()
    elif operation == 'write':
        activity._do_write()
    else:
        activity._do_verify()
    activity.getCanvas().advance(50)
    assert activity._operation is None
    assert not activity.isbusy()
    assert activity._state == (activity.STATE_DECODED if operation == 'read'
                               else activity.STATE_RESULT)
