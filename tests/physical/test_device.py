"""Linux device-helper contracts; never touches real /dev, SSH or application."""
import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='Device helper runs only on Linux')


@pytest.fixture
def device(tmp_path, monkeypatch):
    if sys.platform == 'win32':
        pytest.skip('Linux device helper')
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'tools/physical'))
    spec = importlib.util.spec_from_file_location('device', Path(__file__).resolve().parents[2] / 'tools/physical/device.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path / 'sessions')
    monkeypatch.setattr(module, 'identity', lambda: {'machine_id': 'device'})
    monkeypatch.setattr(module, 'texts', lambda: ['PC-Mode', 'Start'])
    return module


def test_remote_lease_survives_process_restart_and_refuses_other_controller(device):
    token = 'a' * 32
    device.handle(dict(session=token, operation='begin'))
    with pytest.raises(ValueError, match='leased'):
        device.handle(dict(session='b' * 32, operation='begin'))
    assert device.handle(dict(session=token, operation='begin'))['machine_id'] == 'device'
    device.handle(dict(session=token, operation='release'))
    device.handle(dict(session='b' * 32, operation='begin'))


def test_remote_journal_blocks_retry_after_partial_injection(device, monkeypatch, tmp_path):
    session = tmp_path / 'actions'
    session.mkdir()
    calls = []
    def partial(key):
        calls.append(key)
        raise OSError('partial tty injection')
    monkeypatch.setattr(device, 'inject', partial)
    request = dict(action_id='a' * 32, key='M1', expected=['PC-Mode', 'Start'])
    with pytest.raises(OSError):
        device.press(session, request)
    with pytest.raises(ValueError, match='already attempted'):
        device.press(session, request)
    assert calls == ['M1']
    assert 'INTENT' in (session / ('a' * 32 + '.json')).read_text()


def test_wrong_screen_never_injects(device, monkeypatch, tmp_path):
    def unexpected(key):
        pytest.fail('Injected on wrong screen')
    monkeypatch.setattr(device, 'inject', unexpected)
    request = dict(action_id='a' * 32, key='OK', expected=['Read'])
    result = device.press(tmp_path, request)
    assert result['status'] == 'REFUSED'
    assert result['before'] == ['PC-Mode', 'Start']
    assert json.loads((tmp_path / ('a' * 32 + '.json')).read_text()) == result
    monkeypatch.setattr(device, 'texts', lambda: ['Read'])
    with pytest.raises(ValueError, match='already attempted'):
        device.press(tmp_path, request)


def test_key_ack_means_queued_and_all_named_buttons_use_hmi_queue(device, monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(device, 'inject', sent.append)
    for index, key in enumerate(device.KEYS):
        result = device.press(tmp_path, dict(action_id=format(index, '032x'), key=key, expected=['PC-Mode']))
        assert result['status'] == 'QUEUED'
    assert set(sent) == {'UP', 'DOWN', 'LEFT', 'RIGHT', 'OK', 'M1', 'M2', 'PWR', 'ALL'}


def test_inspection_does_not_claim_device(device):
    device.handle(dict(session='a' * 32, operation='inspect'))
    assert not device.ROOT.exists()


def test_shipped_helper_includes_matcher_without_repository_on_python_path(monkeypatch):
    from tools.physical.station import device_source
    monkeypatch.delitem(sys.modules, 'screen', raising=False)
    namespace = {'__name__': 'shipped_helper'}
    exec(compile(device_source(), '<device-helper>', 'exec'), namespace)
    namespace['require_screen']([{'template': 'ChkDIC...{n}/32keys'}], ['ChkDIC...7/32keys'])
    with pytest.raises(ValueError, match='Unexpected screen'):
        namespace['require_screen']([{'template': 'ChkDIC...{n}/32keys'}], ['Read successful'])


@pytest.mark.parametrize('observed,allowed', [
    (['ChkDIC...7/32keys'], True),
    (['ChkDIC...31/32keys'], True),
    (['Read', 'Successful!', 'File saved'], False),
    (['ChkDIC...7/64keys'], False),
    (['prefix ChkDIC...7/32keys'], False),
])
def test_numeric_progress_guard_rechecks_before_input(device, monkeypatch, tmp_path, observed, allowed):
    sent = []
    monkeypatch.setattr(device, 'texts', lambda: observed)
    monkeypatch.setattr(device, 'inject', sent.append)
    request = dict(action_id='a' * 32, key='PWR',
                   expected=[{'template': 'ChkDIC...{n}/32keys'}])
    if allowed:
        assert device.press(tmp_path, request)['before'] == observed
        assert sent == ['PWR']
    else:
        result = device.press(tmp_path, request)
        assert result['status'] == 'REFUSED' and result['before'] == observed
        assert sent == []


@pytest.fixture
def local_cancel(device, monkeypatch, tmp_path):
    clock = [0.0]
    sent = []
    screens = [['Selected Classic'], ['ChkDIC...0/32keys'],
               ['ChkDIC...7/32keys'], ['Selected Classic']]
    request = dict(action_id='b' * 32, start_texts=['Selected Classic'],
                   busy_texts=[{'template': 'ChkDIC...{n}/32keys'}])
    @contextmanager
    def observer():
        yield lambda: screens.pop(0) if len(screens) > 1 else screens[0]
    monkeypatch.setattr(device, 'text_observer', observer)
    monkeypatch.setattr(device.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(device.time, 'sleep', lambda delay: clock.__setitem__(0, clock[0] + delay))
    monkeypatch.setattr(device, 'inject', sent.append)
    return request, screens, clock, sent


def test_local_cancel_has_fresh_guard_durable_intents_and_no_replay(device, local_cancel, monkeypatch, tmp_path):
    request, screens, clock, sent = local_cancel
    path = tmp_path / (request['action_id'] + '.json')
    def inject(key):
        saved = json.loads(path.read_text())
        assert saved['stage'] == ('START_INTENT' if key == 'OK' else 'CANCEL_INTENT')
        sent.append(key)
    monkeypatch.setattr(device, 'inject', inject)
    result = device.cancel_read_local(tmp_path, request)
    assert result['status'] == 'CANCELLED'
    assert result['cancel_before'] == ['ChkDIC...7/32keys']
    assert sent == ['OK', 'PWR']
    assert json.loads(path.read_text()) == result
    with pytest.raises(ValueError, match='already attempted'):
        device.cancel_read_local(tmp_path, request)
    assert sent == ['OK', 'PWR']


@pytest.mark.parametrize('stage', ['initial', 'final'])
def test_local_cancel_refuses_wrong_screen_without_unintended_input(device, local_cancel, tmp_path, stage):
    request, screens, clock, sent = local_cancel
    screens[0 if stage == 'initial' else 2] = ['Successful!', 'File saved']
    result = device.cancel_read_local(tmp_path, request)
    assert result['status'] == 'HARNESS_ERROR'
    assert result['error_type'] == 'ValueError'
    assert sent == ([] if stage == 'initial' else ['OK'])
    assert result['start_before' if stage == 'initial' else 'cancel_before'] == ['Successful!', 'File saved']


@pytest.mark.parametrize('stage', ['busy', 'return'])
def test_local_cancel_deadlines_do_not_restart_or_repeat_input(device, local_cancel, tmp_path, stage):
    request, screens, clock, sent = local_cancel
    if stage == 'busy':
        screens[:] = [['Selected Classic'], ['Scanning...']]
    else:
        screens[-1] = ['ChkDIC...8/32keys']
    result = device.cancel_read_local(tmp_path, request)
    assert result['status'] == 'HARNESS_ERROR' and result['error_type'] == 'TimeoutError'
    assert sent == (['OK'] if stage == 'busy' else ['OK', 'PWR'])
    assert (15 <= clock[0] < 15.1) if stage == 'busy' else (5 <= clock[0] < 5.1)


def test_local_cancel_slow_final_guard_prevents_late_input(device, local_cancel, monkeypatch, tmp_path):
    request, screens, clock, sent = local_cancel
    @contextmanager
    def slow_observer():
        def observe():
            value = screens.pop(0)
            if value == ['ChkDIC...7/32keys']:
                clock[0] += 6
            return value
        yield observe
    monkeypatch.setattr(device, 'text_observer', slow_observer)
    result = device.cancel_read_local(tmp_path, request)
    assert result['status'] == 'HARNESS_ERROR' and result['error_type'] == 'TimeoutError'
    assert sent == ['OK']


def test_local_cancel_late_success_is_not_a_pass(device, local_cancel, monkeypatch, tmp_path):
    request, screens, clock, sent = local_cancel
    @contextmanager
    def slow_observer():
        def observe():
            value = screens.pop(0)
            if len(screens) == 0:
                clock[0] += 6
            return value
        yield observe
    monkeypatch.setattr(device, 'text_observer', slow_observer)
    result = device.cancel_read_local(tmp_path, request)
    assert result['status'] == 'HARNESS_ERROR' and result['error_type'] == 'TimeoutError'
    assert sent == ['OK', 'PWR']


def test_local_cancel_partial_injection_cannot_be_replayed(device, local_cancel, monkeypatch, tmp_path):
    request, screens, clock, sent = local_cancel
    def partial(key):
        sent.append(key)
        raise OSError('partial injection')
    monkeypatch.setattr(device, 'inject', partial)
    result = device.cancel_read_local(tmp_path, request)
    assert result['status'] == 'HARNESS_ERROR' and result['stage'] == 'START_INTENT'
    with pytest.raises(ValueError, match='already attempted'):
        device.cancel_read_local(tmp_path, request)
    assert sent == ['OK']
