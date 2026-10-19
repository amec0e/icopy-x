"""Hardware substitution only: actual ARM discovery, workers and Tk stay real."""
from types import SimpleNamespace
from unittest.mock import patch
import os


def run(main, root, pump):
    import ics_decoder
    import serial

    ports = {'/dev/ttyACM0': (1, b'ISE\r\n'), '/dev/ttyACM1': (2, b'other\r\n')}
    opened, handles = [], []
    original_glob = ics_decoder.glob.glob

    def inventory(pattern, *args, **kwargs):
        if pattern == '/dev/ttyACM*':
            return list(ports)
        if pattern == '/dev/ttyUSB*':
            return []
        return original_glob(pattern, *args, **kwargs)

    def stat(path):
        if path not in ports:
            raise FileNotFoundError(path)
        return SimpleNamespace(st_ino=ports[path][0], st_ctime_ns=1)

    class Port:
        def __init__(self, path, baud, timeout, write_timeout):
            assert path != '/dev/ttyACM0', 'Accessory discovery touched the PM3'
            assert baud == 115200 and timeout == write_timeout == 1.2
            self.reply = ports[path][1]
            self.closed = False
            opened.append(path)
            handles.append(self)

        def reset_input_buffer(self):
            pass

        def write(self, data):
            assert data == b'Who\r\n'

        def readline(self, size):
            assert size == 32
            return self.reply

        def close(self):
            self.closed = True

    def actions():
        return [item[2] for item in main._menu_items]

    with patch.object(ics_decoder.glob, 'glob', inventory), \
            patch.object(ics_decoder, 'os', SimpleNamespace(path=os.path, stat=stat)), \
            patch.object(serial, 'Serial', Port):
        assert 'iclass_se' not in actions()
        # Wait for one rejected hardware probe to complete.
        pump(lambda: bool(handles) and handles[-1].closed)
        assert 'iclass_se' not in actions()
        main.lv_main_page.setSelection(actions().index('settings_menu'))
        ports['/dev/ttyACM1'] = (3, b'ISE\r\n')
        pump(lambda: 'iclass_se' in actions())
        assert actions()[main.lv_main_page.selection()] == 'settings_menu'
        assert main.lv_main_page._items[-2] == 'ICS Decoder'
        assert all(handle.closed for handle in handles)
        ports.pop('/dev/ttyACM1')
        pump(lambda: 'iclass_se' not in actions())
        assert actions()[main.lv_main_page.selection()] == 'settings_menu'
        assert main.lv_main_page.getPageCount() == 3
        assert '/dev/ttyACM0' not in opened
        main.onPause()
        pump(lambda: not main._decoder_worker.is_alive())
        assert main._decoder_timer is None
        assert all(handle.closed for handle in handles)
