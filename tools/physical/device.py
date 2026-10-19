"""Bounded, standard-library device helper, sent over pinned SSH by station.py.

No application hooks and no raw UART writes. A short key is inserted into the
existing HMI input queue. The durable action record prevents blind replay.
"""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import termios
import time

from screen import require_screen

ROOT = Path('/home/pi/icopy-validation')  # root filesystem survives USB handover
LIVE = Path('/home/pi/ipk_app_main')
DUMPS = Path('/mnt/upan/dump')
KEYS = {key: 'KEY' + key + '_PRES!' for key in
        ('UP', 'DOWN', 'LEFT', 'RIGHT', 'OK', 'M1', 'M2')}
KEYS.update(PWR='KEY_PWR_CAN_PRES!', ALL='KEY_ALL_PRES!')
IDENTITY_FILES = ('app.py', 'lib/executor.py', 'main/rftask.py',
                  'lib/hfmfuread.py', 'pm3/proxmark3')


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))
    descriptor = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def digest(path):
    with path.open('rb') as stream:
        result = hashlib.sha256()
        for data in iter(lambda: stream.read(65536), b''):
            result.update(data)
    return result.hexdigest()


def command(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=8, check=False)
    if len(result.stdout) > 1024 * 1024:
        raise ValueError('Diagnostic output exceeds limit')
    return {'status': result.returncode, 'output': result.stdout.decode(errors='replace')}


def identity():
    files = {}
    for name in IDENTITY_FILES:
        path = LIVE / name
        files[name] = digest(path) if path.is_file() else None
    return {'machine_id': Path('/etc/machine-id').read_text().strip(),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'files': files, 'python': sys.version,
            'service': command(['systemctl', 'is-active', 'icopy'])}


def texts():
    import tkinter as tk
    root = tk.Tk(screenName=':0')
    root.withdraw()
    try:
        # One Tcl event: widgets cannot disappear between independent queries.
        script = '''
        set pending [list .]; set result [list]
        while {[llength $pending]} {
          set path [lindex $pending 0]; set pending [lrange $pending 1 end]
          if {![winfo ismapped $path]} {continue}
          if {[winfo class $path] eq "Canvas"} {
            foreach item [$path find all] {
              if {[$path type $item] eq "text" && [$path itemcget $item -state] ne "hidden"} {
                lappend result [$path itemcget $item -text]
              }
            }
          }
          foreach child [winfo children $path] {lappend pending $child}
        }
        return $result
        '''
        return list(root.tk.splitlist(root.tk.call(
            'send', 'tk', root.tk.call('list', 'apply', ('', script)))))
    finally:
        root.destroy()


def inject(key):
    raw = (KEYS[key] + '\r\n').encode('ascii')
    descriptor = os.open('/dev/ttyS0', os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        for byte in raw:
            fcntl.ioctl(descriptor, termios.TIOCSTI, bytes([byte]))
    finally:
        os.close(descriptor)


def press(session, request):
    action = request['action_id']
    if not re.fullmatch('[0-9a-f]{32}', action) or request['key'] not in KEYS:
        raise ValueError('Invalid action')
    path = session / (action + '.json')
    if path.exists():
        raise ValueError('Action already attempted; observe, do not replay')
    observed = texts()
    require_screen(request['expected'], observed)
    record = dict(request, before=observed, status='INTENT', time=time.time())
    atomic_json(path, record)
    inject(request['key'])
    # This acknowledges input queuing, not application processing.
    record['status'] = 'QUEUED'
    atomic_json(path, record)
    return record


def dumps():
    result = {}
    for path in DUMPS.rglob('*'):
        if path.is_symlink() or not path.is_file():
            continue
        if len(result) >= 10000:
            raise ValueError('Dump inventory exceeds limit')
        info = path.stat()
        if info.st_size > 1024 * 1024:
            raise ValueError('Oversized dump')
        result[str(path.relative_to(DUMPS))] = {
            'sha256': digest(path), 'size': info.st_size, 'mtime_ns': info.st_mtime_ns}
    return result


def logs():
    socat = Path('/root/pcmode_socat.log')
    tail = b''
    if socat.exists():
        with socat.open('rb') as stream:
            stream.seek(max(0, socat.stat().st_size - 65536))
            tail = stream.read(65536)
    return {'journal': command(['journalctl', '-u', 'icopy', '-n', '200', '--no-pager']),
            'processes': command(['ps', '-eo', 'pid,ppid,args']),
            'socat': tail.decode(errors='replace'), 'identity': identity()}


def handle(request):
    token = request['session']
    if not re.fullmatch('[0-9a-f]{32}', token):
        raise ValueError('Invalid session')
    if request['operation'] == 'inspect':
        return identity()
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Kernel lock serializes even two controllers using the same session token.
    with (ROOT / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lease = ROOT / 'owner.json'
        owner = json.loads(lease.read_text()) if lease.exists() else None
        operation = request['operation']
        if operation == 'begin' and owner is None:
            owner = {'session': token, 'started': time.time()}
            atomic_json(lease, owner)
        if owner is None or owner['session'] != token:
            raise ValueError('Device leased to another session or lease missing')
        session = ROOT / token
        session.mkdir(mode=0o700, exist_ok=True)
        if operation == 'release':
            lease.unlink()
            return {'released': True}
        if operation == 'begin':
            result = identity()
        elif operation == 'observe':
            result = {'texts': texts(), 'identity': identity()}
            if request.get('frame'):
                with open('/dev/fb1', 'rb') as stream:
                    frame = stream.read(115200)
                if len(frame) != 115200:
                    raise ValueError('Unexpected framebuffer size')
                result['frame'] = base64.b64encode(frame).decode('ascii')
        elif operation == 'key':
            result = press(session, request)
        elif operation == 'dumps':
            result = dumps()
        elif operation in ('prepare_pc', 'collect'):
            result = logs()
        else:
            raise ValueError('Unsupported operation')
        atomic_json(session / (operation + '-latest.json'), result)
        return result


def main(encoded):
    # Includes Tcl send, input and subprocess waits. SSH channel loss must not
    # leave an unbounded observer running on the device.
    signal.signal(signal.SIGALRM, lambda *_: sys.exit('Device helper deadline'))
    signal.alarm(30)
    request = json.loads(base64.b64decode(encoded))
    print(json.dumps(handle(request)))
