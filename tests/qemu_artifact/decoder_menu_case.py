"""Hardware substitution only: actual ARM discovery, workers and Tk stay real."""
from types import SimpleNamespace
from unittest.mock import patch
import os


class SerialEvidence:
    """Keep violations outside application catches, including failed opens."""

    def __init__(self, ports):
        self.ports = ports
        self.opened = []
        self.handles = []
        self.violations = []

    def require(self, condition, message):
        if not condition:
            self.violations.append(message)
            raise OSError(message)  # The real application may legitimately catch this.

    def assert_clean(self):
        assert not self.violations, '; '.join(self.violations)

    def open(self, path, baud, timeout, write_timeout):
        self.opened.append(path)
        self.require(path != '/dev/ttyACM0', 'Accessory discovery touched the PM3')
        self.require(baud == 115200 and timeout == write_timeout == 1.2,
                     'Unexpected decoder serial configuration')
        evidence = self

        class Port:
            def __init__(self):
                self.reply = evidence.ports[path][1]
                self.closed = False

            def reset_input_buffer(self):
                pass

            def write(self, data):
                evidence.require(data == b'Who\r\n', 'Unexpected decoder handshake')

            def readline(self, size):
                evidence.require(size == 32, 'Unbounded decoder identity response')
                return self.reply

            def close(self):
                self.closed = True

        handle = Port()
        self.handles.append(handle)
        return handle


def run(main, root, pump):
    import ics_decoder
    import serial

    ports = {'/dev/ttyACM0': (1, b'ISE\r\n'), '/dev/ttyACM1': (2, b'other\r\n')}
    evidence = SerialEvidence(ports)
    opened, handles = evidence.opened, evidence.handles
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

    def actions():
        return [item[2] for item in main._menu_items]

    def checked_pump(predicate):
        def checked():
            evidence.assert_clean()
            return predicate()
        pump(checked)
        evidence.assert_clean()

    with patch.object(ics_decoder.glob, 'glob', inventory), \
            patch.object(ics_decoder, 'os', SimpleNamespace(path=os.path, stat=stat)), \
            patch.object(serial, 'Serial', evidence.open):
        assert 'iclass_se' not in actions()
        # Wait for one rejected hardware probe to complete.
        checked_pump(lambda: bool(handles) and handles[-1].closed)
        assert 'iclass_se' not in actions()
        main.lv_main_page.setSelection(actions().index('settings_menu'))
        ports['/dev/ttyACM1'] = (3, b'ISE\r\n')
        checked_pump(lambda: 'iclass_se' in actions())
        assert actions()[main.lv_main_page.selection()] == 'settings_menu'
        assert main.lv_main_page._items[-2] == 'ICS Decoder'
        assert all(handle.closed for handle in handles)
        ports.pop('/dev/ttyACM1')
        checked_pump(lambda: 'iclass_se' not in actions())
        assert actions()[main.lv_main_page.selection()] == 'settings_menu'
        assert main.lv_main_page.getPageCount() == 3
        assert '/dev/ttyACM0' not in opened
        main.onPause()
        checked_pump(lambda: not main._decoder_worker.is_alive())
        assert main._decoder_timer is None
        assert all(handle.closed for handle in handles)
