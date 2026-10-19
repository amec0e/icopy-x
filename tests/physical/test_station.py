import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('station', ROOT / 'tools/physical/station.py')
station = importlib.util.module_from_spec(spec)
spec.loader.exec_module(station)


IDENTITY = dict(machine_id='device-one', boot_id='boot-one', files={'app.py': 'a' * 64},
                service=dict(status=0, output='active'))


class FakeDevice:
    def __init__(self):
        self.calls = []
        self.screen = ['PC-Mode', 'Start']
        self.identity = copy.deepcopy(IDENTITY)
        self.fail_key = False

    def call(self, session, operation, **kwargs):
        self.calls.append((operation, kwargs))
        if operation == 'observe':
            result = dict(identity=self.identity, texts=self.screen)
            if kwargs.get('frame'):
                result['frame'] = station.base64.b64encode(bytes(115200)).decode()
            return result
        if operation == 'key':
            if self.fail_key:
                raise TimeoutError('connection vanished')
            return dict(status='QUEUED')
        return dict(identity=self.identity)


@pytest.fixture
def controller(tmp_path):
    profile = {'host': 'private'}
    state = dict(id='a' * 32, phase='SSH', cases=[], identity=IDENTITY,
                 profile_sha256=station.hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest())
    station.save(tmp_path / 'session.json', state)
    return station.Station(tmp_path, profile, FakeDevice())


def test_profile_edit_during_session_rejected(controller):
    with pytest.raises(ValueError, match='Profile changed'):
        station.Station(controller.directory, {'host': 'other'})


@pytest.mark.parametrize('change', [dict(machine_id='other'), dict(boot_id='rebooted'),
                                  dict(files={'app.py': 'b' * 64}), dict(service={'status': 3})])
def test_return_to_wrong_or_changed_device_rejected(controller, change):
    identity = dict(IDENTITY, **change)
    with pytest.raises(ValueError):
        controller.check_identity(identity)


def test_unknown_action_persists_across_restart_and_is_not_replayed(controller):
    controller.transport.fail_key = True
    with pytest.raises(TimeoutError):
        controller.key('M1', ['PC-Mode', 'Start'])
    restarted = station.Station(controller.directory, controller.profile, controller.transport)
    with pytest.raises(ValueError, match='Uncertain action'):
        restarted.key('M1', ['PC-Mode', 'Start'])
    assert len([c for c in controller.transport.calls if c[0] == 'key']) == 1
    assert restarted.state['uncertain_action']


def test_handover_intent_precedes_key_and_disconnect_is_not_retried(controller, monkeypatch):
    monkeypatch.setattr(station, 'ports', lambda: [])
    controller.transport.fail_key = True
    with pytest.raises(TimeoutError):
        controller.prepare_pc()
    restarted = station.Station(controller.directory, controller.profile, controller.transport)
    assert restarted.state['phase'] == 'HANDOVER'
    assert restarted.state['pc_status'] == 'INCOMPLETE'
    with pytest.raises(ValueError, match='already attempted'):
        restarted.prepare_pc()


@pytest.fixture
def usb():
    return dict(device='COM9', vid=0x1234, pid=0x5678, serial='one', location='port-one')


def test_existing_unrelated_ambiguous_usb_never_selected(usb):
    expected = dict(vid=usb['vid'], pid=usb['pid'], serial=usb['serial'])
    assert station.select_port([], [usb], expected) == usb
    for before, current in [([usb], [usb]), ([], []), ([], [dict(usb, pid=1)]),
                            ([], [dict(usb, serial='other')]), ([], [usb, dict(usb, device='COM10')])]:
        with pytest.raises(ValueError):
            station.select_port(before, current, expected)


def test_serial_failure_does_not_allow_retry(controller, monkeypatch, usb):
    controller.profile.update(usb=dict(vid=usb['vid'], pid=usb['pid']), client={})
    controller.state.update(phase='HANDOVER', ports_before=[])
    monkeypatch.setattr(station, 'ports', lambda: [usb])
    def failed(*args):
        raise TimeoutError('lost serial')
    monkeypatch.setattr(station, 'run_client', failed)
    with pytest.raises(TimeoutError):
        controller.serial(True)
    assert controller.state['phase'] == 'SERIAL_ATTEMPTED'
    with pytest.raises(ValueError):
        controller.serial(True)


def test_serial_requires_explicit_operator_ack(controller):
    controller.state['phase'] = 'HANDOVER'
    with pytest.raises(ValueError):
        controller.serial(False)
    with pytest.raises(ValueError):
        controller.returned(False)


@pytest.mark.parametrize('usb_passed,return_read,expected', [(True, True, 'PASS'),
    (False, True, 'INCOMPLETE'), (True, False, 'INCOMPLETE'), (False, False, 'INCOMPLETE')])
def test_pc_pass_requires_serial_and_return_read(controller, usb_passed, return_read, expected):
    controller.state.update(phase='RETURNED', usb_passed=usb_passed, return_read=return_read)
    controller.finish()
    assert controller.state['pc_status'] == expected
    assert controller.state['phase'] == 'CLOSED'


def test_cannot_release_device_while_handover_pending(controller):
    controller.state['phase'] = 'HANDOVER'
    with pytest.raises(ValueError):
        controller.finish()
    assert not controller.transport.calls


def test_missing_usb_evidence_still_allows_ssh_recovery(controller):
    controller.state['phase'] = 'SERIAL_ATTEMPTED'
    controller.returned(True)
    assert controller.state['phase'] == 'RETURNED'
    assert not controller.state['usb_passed']


@pytest.fixture
def fixture():
    return dict(success_texts=['Read successful', 'File saved'], uid='01234567',
                suffix='.bin', sha256='a' * 64, size=1024)


def test_read_requires_fresh_exact_dump_and_card_identity(fixture):
    actual = dict(sha256='a' * 64, size=1024, mtime_ns=1)
    texts = ['Read successful', 'File saved', 'UID: 01 23 45 67']
    station.verify_read({}, {'new.bin': actual}, fixture, texts)
    for before, after, observed in [({'new.bin': actual}, {'new.bin': actual}, texts),
        ({}, {}, texts), ({}, {'new.bin': dict(actual, size=0)}, texts),
        ({}, {'new.bin': dict(actual, sha256='b' * 64)}, texts),
        ({}, {'new.bin': actual, 'extra.bin': actual}, texts),
        ({}, {'new.bin': actual}, texts[:2]),
        ({}, {'new.bin': actual}, ['Read Failed!'])]:
        with pytest.raises(ValueError):
            station.verify_read(before, after, fixture, observed)


@pytest.mark.parametrize('cancel,changed_on_cancel', [(False, False), (True, False), (True, True)])
def test_read_session_requires_dump_and_cancel_then_fresh_read(controller, fixture, monkeypatch,
                                                             cancel, changed_on_cancel):
    fixture.update(start_texts=['Selected Classic 1K'], busy_texts=['Reading...'])
    success = fixture['success_texts'] + ['UID: 01 23 45 67']
    screens = [fixture['start_texts']]
    if cancel:
        screens += [fixture['busy_texts'], fixture['start_texts']]
    screens += [success, success]
    actual = {'new.bin': dict(sha256='a' * 64, size=1024, mtime_ns=1)}
    inventories = [{}] + ([actual if changed_on_cancel else {}] if cancel else []) + [actual]
    original_call = controller.transport.call

    def call(session, operation, **kwargs):
        if operation == 'observe':
            controller.transport.screen = screens.pop(0)
        result = original_call(session, operation, **kwargs)
        return inventories.pop(0) if operation == 'dumps' else result

    monkeypatch.setattr(controller.transport, 'call', call)
    monkeypatch.setattr(station.time, 'sleep', lambda _: None)
    controller.state['phase'] = 'RETURNED'
    if changed_on_cancel:
        with pytest.raises(ValueError, match='Cancellation changed'):
            controller.read_card(fixture, cancel=True)
        assert controller.state['cases'][-1]['status'] == 'FAIL'
        assert not controller.state.get('return_read')
    else:
        controller.read_card(fixture, cancel=cancel)
        case = controller.state['cases'][-1]
        assert case['status'] == 'PASS' and case['after'] == actual
        assert controller.state['return_read'] == case['id']
        assert not screens and not inventories
    keys = [data['key'] for operation, data in controller.transport.calls if operation == 'key']
    assert keys == (['OK', 'PWR'] if changed_on_cancel else ['OK', 'PWR', 'OK'] if cancel else ['OK'])


def test_ui_failure_with_punctuation_is_detected(controller):
    controller.transport.screen = ['Read Failed!']
    with pytest.raises(ValueError, match='Read Failed'):
        controller.wait(['Read successful'], 1)


@pytest.mark.parametrize('changed', ['ChkDIC...7/32keys', 'Read successful'])
def test_cancel_rechecks_changing_counter_and_refuses_completed_phase(controller, fixture, monkeypatch, changed):
    from tools.physical.screen import require_screen
    fixture.update(start_texts=['Selected Classic 1K'],
                   busy_texts=[{'template': 'ChkDIC...{n}/32keys'}])
    controller.transport.screen = fixture['start_texts']
    success = fixture['success_texts'] + ['UID: 01 23 45 67']
    actual = {'new.bin': dict(sha256='a' * 64, size=1024, mtime_ns=1)}
    keys = []
    original_call = controller.transport.call

    def call(session, operation, **kwargs):
        if operation == 'key':
            if kwargs['key'] == 'PWR':
                # Counter/phase changed after host observation, before device guard.
                controller.transport.screen = [changed]
            require_screen(kwargs['expected'], controller.transport.screen)
            keys.append(kwargs['key'])
            controller.transport.screen = (fixture['start_texts'] if kwargs['key'] == 'PWR'
                else ['ChkDIC...0/32keys'] if len(keys) == 1 else success)
        result = original_call(session, operation, **kwargs)
        return (actual if len(keys) == 3 else {}) if operation == 'dumps' else result

    monkeypatch.setattr(controller.transport, 'call', call)
    monkeypatch.setattr(station.time, 'sleep', lambda _: None)
    if changed.startswith('ChkDIC'):
        controller.read_card(fixture, cancel=True)
        assert keys == ['OK', 'PWR', 'OK']
        assert controller.state['cases'][-1]['status'] == 'PASS'
    else:
        with pytest.raises(ValueError, match='Unexpected screen'):
            controller.read_card(fixture, cancel=True)
        assert keys == ['OK']
        assert controller.state['uncertain_action']


def test_late_successful_observation_cannot_pass_recovery_deadline(controller, monkeypatch):
    controller.transport.screen = ['Read successful']
    clock = iter([0, 0, 6])
    monkeypatch.setattr(station.time, 'monotonic', lambda: next(clock))
    with pytest.raises(TimeoutError, match='UI deadline'):
        controller.wait(['Read successful'], 5)


def test_cancel_deadline_includes_delayed_input_acknowledgement(controller, fixture, monkeypatch):
    fixture.update(start_texts=['Selected Classic 1K'], busy_texts=['Reading...'])
    controller.transport.screen = fixture['start_texts']
    clock = [0]
    original_call = controller.transport.call

    def call(session, operation, **kwargs):
        if operation == 'key':
            if kwargs['key'] == 'PWR':
                clock[0] += 6  # Input may run promptly; its SSH reply is late.
                controller.transport.screen = fixture['start_texts']
            else:
                if clock[0]:
                    pytest.fail('Late cancellation acknowledgement incorrectly permitted another read')
                controller.transport.screen = fixture['busy_texts']
        result = original_call(session, operation, **kwargs)
        return {} if operation == 'dumps' else result

    monkeypatch.setattr(controller.transport, 'call', call)
    monkeypatch.setattr(station.time, 'monotonic', lambda: clock[0])
    with pytest.raises(TimeoutError, match='UI deadline'):
        controller.read_card(fixture, cancel=True)
    assert controller.state['cases'][-1]['status'] == 'HARNESS_ERROR'
    assert [data['key'] for operation, data in controller.transport.calls if operation == 'key'] == ['OK', 'PWR']


def test_client_commands_are_fixed_no_shell_or_flash():
    for style in ('factory', 'iceman'):
        args = station.client_args(dict(path='client with spaces.exe', style=style), 'COM9', 'hw version')
        assert args[0] == 'client with spaces.exe'
        assert args[-1] == 'hw version'
        with pytest.raises(ValueError):
            station.client_args(dict(path='client', style=style), 'COM9', 'hw reset; flash')


def test_wrong_client_hash_never_launches(tmp_path, monkeypatch):
    executable = tmp_path / 'client'
    executable.write_bytes(b'wrong client')
    def unexpected(*args, **kwargs):
        pytest.fail('Executed wrong client')
    monkeypatch.setattr(station.subprocess, 'Popen', unexpected)
    with pytest.raises(ValueError, match='hash mismatch'):
        station.run_client(dict(path=str(executable), sha256='a' * 64), 'COM9', 'hw version', tmp_path / 'out')


def test_ssh_host_key_pin():
    key = SimpleNamespace(asbytes=lambda: b'public key')
    assert station.fingerprint(key) == 'SHA256:' + station.base64.b64encode(
        station.hashlib.sha256(b'public key').digest()).decode().rstrip('=')


@pytest.mark.parametrize('wrong_pin,never_completes', [(False, False), (True, False), (False, True)])
def test_ssh_pin_deadline_and_both_output_streams(monkeypatch, wrong_pin, never_completes):
    key = SimpleNamespace(asbytes=lambda: b'public key')
    client = SimpleNamespace(closed=False, commands=[])
    channel = SimpleNamespace(out=[b'{"ok": true}'], err=[b'diagnostic'])
    channel.recv_ready = lambda: bool(channel.out)
    channel.recv_stderr_ready = lambda: bool(channel.err)
    channel.recv = lambda size: channel.out.pop(0)
    channel.recv_stderr = lambda size: channel.err.pop(0)
    channel.exit_status_ready = lambda: not never_completes
    channel.recv_exit_status = lambda: 0
    def connect(*args, **kwargs):
        assert kwargs['disabled_algorithms'] == {
            'keys': ['ssh-rsa', 'ssh-dss'], 'pubkeys': ['ssh-rsa', 'ssh-dss']}
        client.policy.missing_host_key(client, 'device', key)
    def execute(command, timeout):
        client.commands.append(command)
        return None, SimpleNamespace(channel=channel), None
    client.connect = connect
    client.exec_command = execute
    client.set_missing_host_key_policy = lambda policy: setattr(client, 'policy', policy)
    client.close = lambda: setattr(client, 'closed', True)
    monkeypatch.setitem(sys.modules, 'paramiko', SimpleNamespace(
        SSHClient=lambda: client, MissingHostKeyPolicy=object))
    clock = iter([0, 1, 40])
    monkeypatch.setattr(station.time, 'monotonic', lambda: next(clock))
    transport = station.SSH(dict(host='device', user='root',
        ssh_sha256='wrong' if wrong_pin else station.fingerprint(key)))
    if wrong_pin or never_completes:
        with pytest.raises(ValueError if wrong_pin else TimeoutError):
            transport.call('a' * 32, 'observe')
    else:
        assert transport.call('a' * 32, 'observe') == {'ok': True}
        assert not channel.out and not channel.err
    assert client.closed
    assert len(client.commands) == (0 if wrong_pin else 1)


def test_timed_out_client_is_killed_and_reaped(tmp_path, monkeypatch):
    path = tmp_path / 'client'
    path.write_bytes(b'fake client')
    child = SimpleNamespace(killed=False, reaped=False, returncode=None)
    child.poll = lambda: None
    child.kill = lambda: setattr(child, 'killed', True)
    child.wait = lambda timeout: setattr(child, 'reaped', True)
    monkeypatch.setattr(station.subprocess, 'Popen', lambda *a, **kw: child)
    clock = iter([0, 31])
    monkeypatch.setattr(station.time, 'monotonic', lambda: next(clock))
    with pytest.raises(TimeoutError):
        station.run_client(dict(path=str(path), sha256=station.sha256(path), style='iceman'),
                           'COM9', 'hw status', tmp_path / 'out')
    assert child.killed and child.reaped


def test_empty_evidence_marker_cannot_pass():
    with pytest.raises(ValueError):
        station.require_text([''], 'unrelated client banner')


@pytest.mark.parametrize('failure', ['FPGA firmware... chip mismatch', 'Cannot communicate with device',
                                  'ARM firmware does not match the source at the time the client was compiled',
                                  'Unknown command', 'Device / FW mismatch'])
def test_banner_plus_compatibility_error_is_not_a_pass(failure):
    with pytest.raises(ValueError, match='compatibility/communication'):
        station.verify_probe('expected FPGA identifier\n' + failure, ['expected FPGA identifier'])
