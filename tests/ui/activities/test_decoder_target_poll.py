"""Blank-target polling must leave Tk responsive and retain PM3 ownership."""
from threading import Event, Thread as RealThread, get_ident
from types import SimpleNamespace

import pytest

import actstack
import executor
import ics_decoder
from _constants import KEY_M1, KEY_M2, KEY_OK, KEY_PWR
from activity_main import ICSDecoderActivity, IClassSEActivity
from tests.ui.activities.test_decoder_workers import worker_ui, join_workers
from tests.ui.activities.test_ics_decoder import validated_capture
from tests.qemu_artifact.strict_transport import ConnectionTranscript
from tests.ui.test_pm3_operation_ownership import ownership_probe

REAL_DETECT_TARGET = ics_decoder.detect_target


@pytest.mark.parametrize('cls', [ICSDecoderActivity, IClassSEActivity])
@pytest.mark.parametrize('key', [KEY_M1, KEY_PWR])
def test_held_target_poll_leaves_back_responsive_and_discards_late_result(worker_ui, monkeypatch, cls, key):
    bus = worker_ui
    activity = bus.start(cls)
    ui_thread = get_ident()
    violations = []

    def detect():
        if get_ident() == ui_thread:
            violations.append('target detection ran on Tk')
            raise AssertionError(violations[-1])
        bus.entered.set()
        assert bus.release.wait(3)
        return 'hf_iclass'

    monkeypatch.setattr(ics_decoder, 'detect_target', detect)
    activity._target_type = None
    activity._state = activity.STATE_WAIT_BLANK
    activity._start_target_poll()
    activity.getCanvas().advance(1000)
    assert violations == []  # Cannot be swallowed by detection's exception handler.
    assert bus.entered.wait(2)
    beat = []
    activity.getCanvas().after(1, lambda: beat.append(True))
    activity.getCanvas().advance(10)
    assert beat == [True]
    activity._poll_target()  # Duplicate callbacks must not start overlapping probes.
    activity.onKeyEvent(KEY_OK)
    activity.onKeyEvent(KEY_M2)
    assert len(bus.threads) == 1
    assert activity._state == activity.STATE_WAIT_BLANK
    assert bus.calls == []
    activity.onKeyEvent(key)
    expected = activity.STATE_DECODED if cls is ICSDecoderActivity else activity.STATE_DESTROYED
    assert activity._state == expected
    assert not bus.release.is_set()
    bus.release.set()
    join_workers(bus)
    activity.getCanvas().advance(100)
    assert activity._state == expected
    assert activity._target_type is None
    assert activity._target_poll_timer is None


@pytest.mark.parametrize('cls', [ICSDecoderActivity, IClassSEActivity])
def test_target_result_changes_ui_only_when_delivered(worker_ui, cls):
    bus = worker_ui
    activity = bus.start(cls)
    activity._state = activity.STATE_WAIT_BLANK
    activity._target_type = None
    activity._poll_target()
    join_workers(bus)
    assert activity._target_type is None
    activity.getCanvas().advance(50)
    assert activity._target_type == 'hf_iclass'
    assert activity._target_poll_timer is None
    activity.onKeyEvent(KEY_OK)
    join_workers(bus)
    activity.getCanvas().advance(50)
    assert activity._state == activity.STATE_RESULT and activity._last_write_ok
    assert len(bus.calls) == 1


@pytest.fixture
def target_wire(monkeypatch, worker_ui):
    """Real detection/parser/executor with strict, separately owned sockets."""
    wires = []
    monkeypatch.setattr(ics_decoder, 'detect_target', REAL_DETECT_TARGET)
    for name, value in {
        '_socket_instance': None, '_pipeline_needs_cleanup': False,
        '_pipeline_uncertain': False, '_consecutive_reworks': 0,
        'CONTENT_OUT_IN__TXT_CACHE': '', 'LABEL_PM3_CMD_TASK_RUNNING': False,
        'LABEL_PM3_CMD_TASK_STOPPING': False, 'pm3_compat': None, 'pm3_localize': None,
    }.items():
        monkeypatch.setattr(executor, name, value)

    def install(steps):
        wire = ConnectionTranscript(steps)
        wires.append(wire)
        monkeypatch.setattr(executor, 'socket', SimpleNamespace(
            socket=lambda *a: wire.new_socket(), AF_INET=2, SOCK_STREAM=1, timeout=TimeoutError))
        return wire

    yield install
    for wire in wires:
        wire.release.set()
    join_workers(worker_ui)
    for wire in wires:
        wire.verify()


HF1 = 'hf iclass rdbl --blk 6 -k AFA785A7DAB33378'
HF2 = 'hf iclass rdbl --blk 6 -k 2020666666668888'
GOOD = 'block 6/0x06 : 11 22 33 44 55 66 77 88\nNikola.D: 0\n'
ABSENT = 'Authentication failed\nNikola.D: 0\n'


@pytest.mark.parametrize('cls', [ICSDecoderActivity, IClassSEActivity])
def test_cancelled_real_probe_cannot_try_next_key_or_lf(worker_ui, target_wire, cls):
    bus = worker_ui
    activity = bus.start(cls)
    wire = target_wire([dict(command=HF1, response=ABSENT, blocked=True)])
    activity._state = activity.STATE_WAIT_BLANK
    activity._target_type = None
    activity._poll_target()
    assert wire.entered.wait(2)
    activity.onKeyEvent(KEY_M1)
    wire.release.set()
    join_workers(bus)
    activity.getCanvas().advance(50)
    assert len(wire.commands) == 1
    assert activity._target_type is None


def test_reentry_waits_for_old_response_and_uses_fresh_result(worker_ui, target_wire, ownership_probe):
    bus = worker_ui
    activity = bus.start(ICSDecoderActivity)
    wire = target_wire([
        dict(command=HF1, response=ABSENT, blocked=True),
        dict(command=HF1, response=GOOD),
    ])
    activity._state = activity.STATE_DECODED
    activity._start_write()
    activity.getCanvas().advance(1000)
    assert wire.entered.wait(2)
    activity._back()
    activity._start_write()
    ownership_probe[0].set()
    activity.getCanvas().advance(1000)
    assert ownership_probe[1].wait(2)
    assert ownership_probe[2] == [True], 'Re-entry did not wait for the previous owner'
    assert len(bus.threads) == 2
    assert len(wire.commands) == 1
    assert activity._target_type is None
    wire.release.set()
    join_workers(bus)
    activity.getCanvas().advance(50)
    assert activity._target_type == 'hf_iclass'
    assert len(wire.commands) == 2 and len(wire.sockets) == 2


def test_back_cancels_waiting_poll_without_cancelling_another_owner(worker_ui, monkeypatch, ownership_probe):
    activity = worker_ui.start(ICSDecoderActivity)
    owner_started, owner_release, owner_cancelled = Event(), Event(), Event()
    calls = []

    def own_pm3():
        with executor.pm3_operation(owner_cancelled):
            owner_started.set()
            assert owner_release.wait(3)

    owner = RealThread(target=own_pm3, daemon=True)
    owner.start()
    try:
        assert owner_started.wait(2)
        monkeypatch.setattr(ics_decoder, 'detect_target', lambda: calls.append('probe'))
        activity._state = activity.STATE_WAIT_BLANK
        ownership_probe[0].set()
        activity._poll_target()
        assert ownership_probe[1].wait(2)
        assert ownership_probe[2] == [True]
        activity._back()
        join_workers(worker_ui)  # Must finish while the original owner is still held.
        assert calls == []
        assert not owner_release.is_set() and not owner_cancelled.is_set()
        assert executor._active_operation is owner_cancelled
    finally:
        owner_release.set()
        owner.join(3)
        assert not owner.is_alive()


def test_back_before_queued_poll_runs_sends_nothing(worker_ui, monkeypatch):
    activity = worker_ui.start(ICSDecoderActivity)
    jobs, calls = [], []
    monkeypatch.setattr(activity, 'startBGTask', jobs.append)
    monkeypatch.setattr(ics_decoder, 'detect_target', lambda: calls.append('probe'))
    activity._state = activity.STATE_WAIT_BLANK
    activity._poll_target()
    activity._back()
    jobs[0]()
    activity.getCanvas().advance(100)
    assert calls == []
    assert activity._target_poll_timer is None
    assert activity._state == activity.STATE_DECODED


def test_incompatible_target_retries_then_enables_compatible_family(worker_ui, monkeypatch):
    activity = worker_ui.start(ICSDecoderActivity)
    activity._source_data = validated_capture()  # LF-capable, no legacy HF block.
    targets = iter(['hf_iclass', 'lf_t5577'])
    monkeypatch.setattr(ics_decoder, 'detect_target', lambda: next(targets))
    activity._state = activity.STATE_WAIT_BLANK
    activity._poll_target()
    join_workers(worker_ui)
    activity.getCanvas().advance(50)
    assert activity._target_type == 'hf_iclass'
    assert not activity._target_write_available()
    activity.getCanvas().advance(1000)
    join_workers(worker_ui)
    activity.getCanvas().advance(50)
    assert activity._target_type == 'lf_t5577'
    assert activity._target_write_available()
    assert activity._target_poll_timer is None


@pytest.mark.parametrize('response,target', [
    ('Chip type......... T55x7\nNikola.D: 0\n', 'lf_t5577'),
    ('No T55xx chip found\nNikola.D: 0\n', None),
])
def test_real_probe_keeps_hf_then_lf_order(worker_ui, target_wire, response, target):
    activity = worker_ui.start(ICSDecoderActivity)
    activity._source_data = validated_capture()
    target_wire([dict(command=HF1, response=ABSENT), dict(command=HF2, response=ABSENT),
                 dict(command='lf t55xx detect', response=response)])
    activity._state = activity.STATE_WAIT_BLANK
    activity._target_type = None
    activity._poll_target()
    join_workers(worker_ui)
    activity.getCanvas().advance(50)
    assert activity._target_type == target
    assert (activity._target_poll_timer is None) == (target is not None)


@pytest.mark.parametrize('failure', ['absent', 'exception', 'startup'])
def test_failed_poll_schedules_one_retry_on_ui(worker_ui, monkeypatch, failure):
    bus = worker_ui
    activity = bus.start(ICSDecoderActivity)

    def fail(*args):
        raise OSError('probe failed')

    monkeypatch.setattr(ics_decoder, 'detect_target', fail if failure == 'exception' else lambda: None)
    if failure == 'startup':
        monkeypatch.setattr(activity, 'startBGTask', fail)
    activity._state = activity.STATE_WAIT_BLANK
    activity._target_type = None
    activity._poll_target()
    if failure != 'startup':
        join_workers(bus)
    activity.getCanvas().advance(50)
    assert activity._target_poll_timer is not None
    assert not activity._target_in_flight
    assert activity._target_type is None
    activity._back()
    activity.getCanvas().advance(2000)
    assert activity._target_poll_timer is None


@pytest.mark.parametrize('firmware', ['iceman', 'original'])
def test_qemu_target_fixture_exercises_real_protocols_before_arm_run(worker_ui, target_wire,
                                                                   monkeypatch, firmware):
    import sys
    import time
    import pm3_compat
    from tests.qemu_artifact import strict_transport
    monkeypatch.setitem(sys.modules, 'strict_transport', strict_transport)
    from tests.qemu_artifact import decoder_target_case

    worker_ui.start(ICSDecoderActivity)  # Parent/root timer surface for MockCanvas.
    monkeypatch.setattr(executor, 'pm3_compat', pm3_compat)
    monkeypatch.setattr(pm3_compat, '_current_version', firmware)

    def pump(predicate):
        deadline = time.monotonic() + 4
        while not predicate():
            assert time.monotonic() < deadline, 'Harness condition did not complete'
            for activity in list(actstack._ACTIVITY_STACK):
                activity.getCanvas().advance(10)
            Event().wait(.001)

    try:
        activity, evidence = decoder_target_case.run(actstack._root, pump, firmware)
        assert activity._state == activity.STATE_HOME
        assert len(evidence['checks']) == 7 and not evidence['violations']
        assert [len(wire['commands']) for wire in evidence['transcripts']] == [2, 2, 3]
        assert not any(wire['violations'] for wire in evidence['transcripts'])
    finally:
        while actstack.get_current_activity() is not None:
            actstack.finish_activity()
