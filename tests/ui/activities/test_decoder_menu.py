"""Menu visibility, focus and lifecycle with controlled background completion."""
from types import SimpleNamespace

import pytest
import actstack
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
    menu._decoder_presence = SimpleNamespace(check=lambda cancelled: present)
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


@pytest.mark.parametrize('finish', ['onPause', 'onDestroy'])
def test_late_result_cannot_restore_menu_or_schedule_after_exit(menu, activity_workers, finish):
    menu._decoder_presence = SimpleNamespace(check=lambda cancelled: True)
    menu.getCanvas().advance(250)
    worker = activity_workers[-1]
    getattr(menu, finish)()
    worker.run()
    menu.getCanvas().advance(3000)
    assert 'iclass_se' not in actions(menu)
    assert menu._decoder_timer is None
    assert len(activity_workers) == 1


def test_pause_resume_rejects_inflight_result_and_keeps_one_worker(menu, activity_workers):
    menu._decoder_presence = SimpleNamespace(check=lambda cancelled: True)
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
    def fail(cancelled):
        raise OSError('USB unavailable')
    menu._decoder_presence = SimpleNamespace(check=fail)
    menu.getCanvas().advance(250)
    activity_workers[-1].run()
    menu.getCanvas().advance(1000)
    assert 'iclass_se' not in actions(menu)
    assert menu.resumed
