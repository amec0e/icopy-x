"""Linux device-helper contracts; never touches real /dev, SSH or application."""
import importlib.util
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
    with pytest.raises(ValueError, match='Unexpected screen'):
        device.press(tmp_path, dict(action_id='a' * 32, key='OK', expected=['Read']))
    assert not list(tmp_path.glob('*.json'))


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
        with pytest.raises(ValueError, match='Unexpected screen'):
            device.press(tmp_path, request)
        assert sent == [] and not list(tmp_path.glob('*.json'))
