"""Menu visibility, focus and lifecycle with controlled background completion."""
from types import SimpleNamespace

import pytest
import actstack
from _constants import KEY_UP, KEY_DOWN
from actmain import MainActivity
from tests.ui.conftest import MockCanvas


@pytest.fixture
def menu():
    actstack._reset()
    actstack._canvas_factory = MockCanvas
    activity = actstack.start_activity(MainActivity)
    yield activity
    activity.onPause()
    actstack._reset()


def actions(menu):
    return [item[2] for item in menu._menu_items]


def deliver(menu, workers, present):
    menu._decoder_presence = SimpleNamespace(check=lambda cancelled, observation: present)
    # A previous poll can still be waiting in the deferred scheduler, including
    # a cancelled worker from before onPause. Finish it before the new check.
    if menu._decoder_worker is not None and menu._decoder_worker.is_alive():
        menu._decoder_worker.run()
    menu.getCanvas().advance(1000)
    workers[-1].run()
    menu.getCanvas().advance(1000)


def test_absent_then_connected_then_unplugged_preserves_settings_focus(menu, activity_workers):
    assert 'iclass_se' not in actions(menu)
    menu.lv_main_page.setSelection(actions(menu).index('settings_menu'))
    deliver(menu, activity_workers, True)
    assert actions(menu)[-2:] == ['iclass_se', 'settings_menu']
    assert actions(menu)[menu.lv_main_page.selection()] == 'settings_menu'
    assert menu.lv_main_page._icons[-2] == '47'
    assert menu.lv_main_page._items[-2] == 'ICS Decoder'
    deliver(menu, activity_workers, False)
    assert 'iclass_se' not in actions(menu)
    assert actions(menu)[menu.lv_main_page.selection()] == 'settings_menu'
    assert menu.lv_main_page.getPageCount() == 3


def test_disconnecting_selected_decoder_leaves_valid_selection(menu, activity_workers):
    deliver(menu, activity_workers, True)
    menu.lv_main_page.setSelection(actions(menu).index('iclass_se'))
    deliver(menu, activity_workers, False)
    assert actions(menu)[menu.lv_main_page.selection()] == 'settings_menu'


def test_return_to_connected_decoder_restores_focus_after_revalidation(menu, activity_workers):
    deliver(menu, activity_workers, True)
    menu.lv_main_page.setSelection(actions(menu).index('iclass_se'))
    menu.onPause()
    menu.onResume()
    assert 'iclass_se' not in actions(menu)  # stale presence is never displayed
    deliver(menu, activity_workers, True)
    assert actions(menu)[menu.lv_main_page.selection()] == 'iclass_se'


def test_unplug_while_away_discards_restore_intent(menu, activity_workers):
    deliver(menu, activity_workers, True)
    menu.lv_main_page.setSelection(actions(menu).index('iclass_se'))
    menu.onPause()
    menu.onResume()
    deliver(menu, activity_workers, False)
    assert 'iclass_se' not in actions(menu)
    deliver(menu, activity_workers, True)
    assert actions(menu)[menu.lv_main_page.selection()] == 'settings_menu'


@pytest.mark.parametrize('key', [KEY_UP, KEY_DOWN])
def test_navigation_while_revalidating_takes_priority(menu, activity_workers, key):
    deliver(menu, activity_workers, True)
    menu.lv_main_page.setSelection(actions(menu).index('iclass_se'))
    menu.onPause()
    menu.onResume()
    menu.onKeyEvent(key)
    chosen = actions(menu)[menu.lv_main_page.selection()]
    deliver(menu, activity_workers, True)
    assert actions(menu)[menu.lv_main_page.selection()] == chosen


@pytest.mark.parametrize('finish', ['onPause', 'onDestroy'])
def test_late_result_cannot_restore_menu_or_schedule_after_exit(menu, activity_workers, finish):
    menu._decoder_presence = SimpleNamespace(check=lambda cancelled, observation: True)
    menu.getCanvas().advance(250)
    worker = activity_workers[-1]
    getattr(menu, finish)()
    worker.run()
    menu.getCanvas().advance(3000)
    assert 'iclass_se' not in actions(menu)
    assert menu._decoder_timer is None
    assert len(activity_workers) == 1


def test_pause_resume_rejects_inflight_result_and_keeps_one_worker(menu, activity_workers):
    menu._decoder_presence = SimpleNamespace(check=lambda cancelled, observation: True)
    menu.getCanvas().advance(250)
    old = activity_workers[-1]
    menu.onPause()
    menu.onResume()
    menu.getCanvas().advance(250)
    assert activity_workers == [old]
    old.run()
    menu.getCanvas().advance(1000)
    assert 'iclass_se' not in actions(menu)
    assert len(activity_workers) == 2
    activity_workers[-1].run()
    menu.getCanvas().advance(1000)
    assert 'iclass_se' in actions(menu)


def test_detection_error_hides_entry_without_crashing_ui(menu, activity_workers):
    def fail(cancelled, observation):
        raise OSError('USB unavailable')
    menu._decoder_presence = SimpleNamespace(check=fail)
    menu.getCanvas().advance(250)
    activity_workers[-1].run()
    menu.getCanvas().advance(1000)
    assert 'iclass_se' not in actions(menu)
    assert menu.resumed


def test_resume_starts_new_observation_but_continuous_polls_share_it(menu, activity_workers):
    observations = []

    def check(cancelled, observation):
        observations.append(observation)
        return False

    menu._decoder_presence = SimpleNamespace(check=check)
    menu.getCanvas().advance(250)
    activity_workers[-1].run()
    menu.getCanvas().advance(1000)
    activity_workers[-1].run()
    assert len(observations) == 2 and observations[0] is observations[1]
    menu.onPause()
    menu.onResume()
    menu.getCanvas().advance(250)
    activity_workers[-1].run()
    assert len(observations) == 3 and observations[-1] is not observations[0]


@pytest.mark.parametrize('initial_reply', [b'ISE\r\n', b'other\r\n'])
def test_windows_menu_rechecks_same_com_after_paused_replacement(
        menu, activity_workers, monkeypatch, initial_reply):
    import ics_decoder
    bus = SimpleNamespace(reply=initial_reply, opened=[], handles=[])

    def open_port(path):
        bus.opened.append(path)
        handle = SimpleNamespace(closed=False)
        handle.reset_input_buffer = lambda: None
        handle.write = lambda _: None
        handle.readline = lambda _: bus.reply
        handle.close = lambda: setattr(handle, 'closed', True)
        bus.handles.append(handle)
        return handle

    monkeypatch.setattr(ics_decoder.sys, 'platform', 'win32')
    monkeypatch.setattr(ics_decoder, 'serial', object())
    monkeypatch.setattr(ics_decoder, '_comports', lambda: [SimpleNamespace(device='COM7')])
    monkeypatch.setattr(ics_decoder, '_open_serial', open_port)
    monkeypatch.setattr(ics_decoder.time, 'sleep', lambda _: None)
    monkeypatch.setattr(ics_decoder, '_log', lambda _: None)
    menu._decoder_presence = ics_decoder.DecoderPresence()

    def poll_once():
        if menu._decoder_worker is not None and menu._decoder_worker.is_alive():
            menu._decoder_worker.run()
        menu.getCanvas().advance(1000)
        activity_workers[-1].run()
        menu.getCanvas().advance(1000)

    for _ in range(4):
        poll_once()
    was_decoder = initial_reply == b'ISE\r\n'
    assert ('iclass_se' in actions(menu)) == was_decoder
    prior = 1 if was_decoder else 3
    assert bus.opened == ['COM7'] * prior
    menu.onPause()
    bus.reply = b'other\r\n' if was_decoder else b'ISE\r\n'
    menu.onResume()
    poll_once()
    assert ('iclass_se' in actions(menu)) != was_decoder
    assert bus.opened == ['COM7'] * (prior + 1)
    assert all(handle.closed for handle in bus.handles)
