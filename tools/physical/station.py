"""Resumable maintainer station. See docs/PHYSICAL_TESTING.md before use."""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
MAX_OUTPUT = 2 * 1024 * 1024
# Also support private controllers that load station.py by file location.
_screen_spec = importlib.util.spec_from_file_location('_icopy_screen', HERE / 'screen.py')
_screen = importlib.util.module_from_spec(_screen_spec)
_screen_spec.loader.exec_module(_screen)
screen_matches = _screen.screen_matches


def device_source():
    # The helper runs without an installed repository on the device. Ship the
    # same small matcher used by host polling, rather than duplicating guards.
    matcher = (HERE / 'screen.py').read_text(encoding='utf-8')
    return ('import sys, types\n'
            '_screen = types.ModuleType("screen")\n'
            'exec(' + repr(matcher) + ', _screen.__dict__)\n'
            'sys.modules["screen"] = _screen\n' +
            (HERE / 'device.py').read_text(encoding='utf-8'))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fingerprint(key):
    return 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')


class SSH:
    def __init__(self, profile):
        self.profile = profile

    def call(self, session, operation, **kwargs):
        import paramiko
        expected = self.profile['ssh_sha256']
        class Pinned(paramiko.MissingHostKeyPolicy):
            def missing_host_key(self, client, hostname, key):
                if fingerprint(key) != expected:
                    raise ValueError('SSH host key does not match pinned fingerprint')
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(Pinned())
        request = dict(kwargs, operation=operation, session=session)
        payload = base64.b64encode(json.dumps(request).encode()).decode()
        source = device_source()
        source += '\nmain(' + repr(payload) + ')\n'
        encoded = base64.b64encode(source.encode()).decode()
        command = 'python3 -c "import base64;exec(base64.b64decode(\'' + encoded + '\'))"'
        try:
            password_env = self.profile.get('password_env')
            password = os.environ[password_env] if password_env else None
            client.connect(self.profile['host'], port=self.profile.get('port', 22),
                           username=self.profile['user'], password=password,
                           key_filename=self.profile.get('key_file'),
                           look_for_keys=False, allow_agent=False,
                           disabled_algorithms={'keys': ['ssh-rsa', 'ssh-dss'],
                                                'pubkeys': ['ssh-rsa', 'ssh-dss']},
                           timeout=8, auth_timeout=8, banner_timeout=8)
            _, stdout, _ = client.exec_command(command, timeout=35)
            channel = stdout.channel
            output, errors = bytearray(), bytearray()
            deadline = time.monotonic() + 35
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('SSH helper deadline; action may have run')
                if channel.recv_ready():
                    output.extend(channel.recv(65536))
                if channel.recv_stderr_ready():
                    errors.extend(channel.recv_stderr(65536))
                if len(output) + len(errors) > MAX_OUTPUT:
                    raise ValueError('SSH output exceeds limit')
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    break
                time.sleep(.01)
            if channel.recv_exit_status() != 0:
                raise RuntimeError(errors.decode(errors='replace'))
            return json.loads(output)
        finally:
            client.close()


def ports():
    from serial.tools import list_ports
    return [dict(device=p.device, vid=p.vid, pid=p.pid, serial=p.serial_number,
                 location=p.location) for p in list_ports.comports()]


def select_port(before, current, usb):
    old = {item['device'] for item in before}
    matches = [p for p in current if p['device'] not in old and
               p['vid'] == usb['vid'] and p['pid'] == usb['pid'] and
               (not usb.get('serial') or p['serial'] == usb['serial']) and
               (not usb.get('location') or p['location'] == usb['location'])]
    if len(matches) != 1:
        raise ValueError('Expected exactly one new matching USB serial device')
    return matches[0]


def client_args(client, port, command):
    # No arbitrary commands, scripts, shell or automatic flashing.
    if command not in ('hw version', 'hw status'):
        raise ValueError('Command is not in the read-only allowlist')
    if client['style'] == 'iceman':
        return [client['path'], '-p', port, '-c', command]
    if client['style'] == 'factory':
        return [client['path'], port, '-c', command]
    raise ValueError('Unknown client command-line style')


def run_client(client, port, command, output):
    if sha256(Path(client['path'])) != client['sha256']:
        raise ValueError('Host PM3 client hash mismatch')
    args = client_args(client, port, command)
    with output.open('xb') as stream:
        child = subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT,
                                 cwd=str(Path(client['path']).resolve().parent),
                                 stdin=subprocess.DEVNULL)
        deadline = time.monotonic() + 30
        try:
            while child.poll() is None:
                if time.monotonic() >= deadline or output.stat().st_size > MAX_OUTPUT:
                    raise TimeoutError('Host PM3 client deadline/output limit')
                time.sleep(.05)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
    text = output.read_text(encoding='utf-8', errors='replace')
    if child.returncode or len(text) > MAX_OUTPUT:
        raise ValueError('Host PM3 client failed')
    return text


def require_text(expected, actual):
    if not expected or not all(isinstance(item, str) and item.strip() and item in actual for item in expected):
        raise ValueError('Required evidence missing')


def verify_probe(text, expected):
    require_text(expected, text)
    if re.search(r'chip mismatch|cannot communicate|failed to communicate|device / fw mismatch|'
                 r'ARM firmware does not match|'
                 r'no proxmark3|unknown command|not connected', text, re.IGNORECASE):
        raise ValueError('PM3 probe reported a compatibility/communication failure')


def verify_read(before, after, fixture, observed):
    require_text(fixture['success_texts'], observed)
    uid = re.sub('[^0-9A-F]', '', fixture['uid'].upper())
    lines = [re.sub('[^0-9A-F]', '', line.upper()) for text in observed for line in text.splitlines()]
    if len(uid) < 8 or not any(uid in line for line in lines):
        raise ValueError('Expected card identity missing')
    changed = [v for k, v in after.items() if k.endswith(fixture['suffix']) and v != before.get(k)]
    if len(changed) != 1:
        raise ValueError('Expected exactly one newly written card dump')
    actual = changed[0]
    if actual['sha256'] != fixture['sha256'] or actual['size'] != fixture['size']:
        raise ValueError('Card dump differs from independently enrolled fixture')


class ScreenGuardRefused(ValueError):
    """The device durably recorded that its final guard prevented input."""


class Station:
    def __init__(self, directory, profile, transport=None):
        self.directory = directory
        self.profile = profile
        self.transport = transport or SSH(profile)
        self.path = directory / 'session.json'
        self.state = read(self.path)
        if self.state['profile_sha256'] != hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest():
            raise ValueError('Profile changed during session; restore the original profile')

    def store(self):
        save(self.path, self.state)

    def call(self, operation, **kwargs):
        return self.transport.call(self.state['id'], operation, **kwargs)

    def check_identity(self, identity):
        original = self.state['identity']
        for key in ('machine_id', 'boot_id', 'files'):
            if identity[key] != original[key]:
                raise ValueError('Device boot/application identity changed: ' + key)
        if identity['service']['status'] != 0:
            raise ValueError('Application service is not active')

    def observe(self, frame=False):
        result = self.call('observe', frame=frame)
        self.check_identity(result['identity'])
        name = 'observe-' + uuid.uuid4().hex
        if frame:
            from PIL import Image
            raw = base64.b64decode(result.pop('frame'), validate=True)
            if len(raw) != 115200:
                raise ValueError('Invalid framebuffer length')
            Image.frombytes('RGB', (240, 240), raw, 'raw', 'BGR;16').save(self.directory / (name + '.png'))
        save(self.directory / (name + '.json'), result)
        return result['texts']

    def key(self, key, expected):
        # Persist first; even an interrupted request cannot be retried by resume.
        if self.state.get('uncertain_action'):
            raise ValueError('Uncertain action; observe and explicitly acknowledge before continuing')
        action = uuid.uuid4().hex
        self.state['uncertain_action'] = action
        self.store()
        result = self.call('key', key=key, expected=expected, action_id=action)
        save(self.directory / ('action-' + action + '.json'), result)
        if result.get('status') == 'REFUSED':
            self.state['uncertain_action'] = None
            self.store()
            raise ScreenGuardRefused('Unexpected screen; no key sent; see action-' + action + '.json')
        if result.get('status') != 'QUEUED':
            raise RuntimeError('Unrecognized input acknowledgement; action remains uncertain')
        self.state['uncertain_action'] = None
        self.store()

    def wait(self, expected, timeout):
        screen_matches(expected, [])  # Reject malformed guards before polling.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            observed = self.observe()
            # A slow SSH observation must not turn a late recovery into a pass.
            # The transport has its own bound, but the case deadline is tighter.
            if time.monotonic() >= deadline:
                raise TimeoutError('UI deadline')
            if any('read failed' in text.lower() for text in observed):
                raise ValueError('Device reported Read Failed')
            if screen_matches(expected, observed):
                return observed
            time.sleep(.25)
        raise TimeoutError('UI deadline')

    def read_card(self, fixture, cancel=False):
        if self.state['phase'] not in ('SSH', 'RETURNED'):
            raise ValueError('Read requires SSH phase')
        for field in ('start_texts', 'success_texts') + (('busy_texts',) if cancel else ()):
            screen_matches(fixture[field], [])  # Validate before sending any key.
        case_id = uuid.uuid4().hex
        case = dict(id=case_id, kind='cancel-read' if cancel else 'read', status='INCOMPLETE')
        self.state['cases'].append(case)
        self.store()
        try:
            self.observe(frame=True)
            before = self.call('dumps')
            self.key('OK', fixture['start_texts'])
            if cancel:
                self.wait(fixture['busy_texts'], 15)
                cancel_started = time.monotonic()
                self.key('PWR', fixture['busy_texts'])
                self.wait(fixture['start_texts'], 5 - (time.monotonic() - cancel_started))
                cancelled = self.call('dumps')
                if cancelled != before:
                    raise ValueError('Cancellation changed the dump inventory')
                self.key('OK', fixture['start_texts'])
            observed = self.wait(fixture['success_texts'], fixture.get('timeout', 150))
            time.sleep(.5)  # screen/file settle, bounded by host operation
            after = self.call('dumps')
            verify_read(before, after, fixture, observed)
            self.observe(frame=True)
            case.update(status='PASS', before=before, after=after)
            if self.state['phase'] == 'RETURNED':
                self.state['return_read'] = case_id
        except Exception as error:
            case.update(status='FAIL' if isinstance(error, ValueError) and
                        not isinstance(error, ScreenGuardRefused) else 'HARNESS_ERROR', error=str(error))
            raise
        finally:
            self.store()

    def prepare_pc(self):
        if self.state['phase'] != 'SSH':
            raise ValueError('PC-mode start already attempted; never replay it')
        self.observe(frame=True)
        prepared = self.call('prepare_pc')
        self.check_identity(prepared['identity'])
        save(self.directory / 'pc-before.json', prepared)
        self.state.update(phase='HANDOVER', ports_before=ports(), pc_status='INCOMPLETE')
        self.store()  # expected disconnect is durable BEFORE M1
        self.key('M1', ['PC-Mode', 'Start'])

    def serial(self, acknowledged):
        if not acknowledged or self.state['phase'] != 'HANDOVER':
            raise ValueError('Requires HANDOVER and explicit cable-swap acknowledgement')
        # Any ambiguous switch is resolved by the operator observing the running
        # PC-mode screen and the new USB identity, not by resending M1.
        port = select_port(self.state['ports_before'], ports(), self.profile['usb'])
        self.state.update(phase='SERIAL_ATTEMPTED', usb=port, uncertain_action=None)
        self.store()
        text = run_client(self.profile['client'], port['device'], 'hw version', self.directory / 'pc-version.txt')
        verify_probe(text, self.profile['client']['version_contains'])
        text = run_client(self.profile['client'], port['device'], 'hw status', self.directory / 'pc-status.txt')
        verify_probe(text, self.profile['client']['status_contains'])
        self.state.update(phase='USB_TESTED', pc_status='AWAITING_RETURN')
        self.store()

    def returned(self, acknowledged):
        if not acknowledged or self.state['phase'] not in ('HANDOVER', 'SERIAL_ATTEMPTED', 'USB_TESTED'):
            raise ValueError('Requires explicit physical exit and restored-hub acknowledgement')
        result = self.call('collect')
        self.check_identity(result['identity'])
        save(self.directory / 'pc-after.json', result)
        self.observe(frame=True)
        self.state.update(phase='RETURNED', usb_passed=self.state['phase'] == 'USB_TESTED')
        self.store()

    def finish(self):
        if self.state['phase'] == 'RETURNED':
            self.state['pc_status'] = ('PASS' if self.state.get('usb_passed') and
                                       self.state.get('return_read') else 'INCOMPLETE')
        if self.state['phase'] not in ('SSH', 'RETURNED') or self.state.get('uncertain_action'):
            raise ValueError('Return to SSH and resolve uncertain input before closing')
        collected = self.call('collect')
        self.check_identity(collected['identity'])
        save(self.directory / 'final-logs.json', collected)
        self.call('release')
        self.state['phase'] = 'CLOSED'
        self.store()

    def begin(self):
        if self.state['phase'] != 'NEW':
            raise ValueError('Session already initialized')
        identity = self.call('begin')  # same-session lease acquisition is idempotent
        self.state['identity'] = identity
        self.store()
        if identity['machine_id'] != self.profile['machine_id'] or identity['files'] != self.profile['application_files']:
            raise ValueError('Device/application does not match enrolled profile; lease retained')
        self.check_identity(identity)
        self.state['phase'] = 'SSH'
        self.store()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('operation', choices=('inspect', 'begin', 'resume-begin', 'observe', 'key', 'read', 'cancel-read',
        'pc-start', 'pc-usb', 'pc-return', 'acknowledge', 'finish', 'report'))
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--key', choices=('UP', 'DOWN', 'LEFT', 'RIGHT', 'OK', 'M1', 'M2', 'PWR', 'ALL'))
    parser.add_argument('--expect', action='append', default=[])
    parser.add_argument('--operator-confirmed', action='store_true')
    args = parser.parse_args()
    profile = read(args.profile)
    if args.operation == 'inspect':
        print(json.dumps(SSH(profile).call(uuid.uuid4().hex, 'inspect'), indent=2))
        return
    if args.operation == 'begin':
        args.session.mkdir(parents=True, exist_ok=False)
        state = dict(id=uuid.uuid4().hex, profile_sha256=hashlib.sha256(
            json.dumps(profile, sort_keys=True).encode()).hexdigest(), phase='NEW', cases=[])
        save(args.session / 'session.json', state)
    # Deliberately no automatic stale-lock takeover after controller crashes.
    lock = args.session / 'controller.lock'
    with lock.open('x') as stream:
        stream.write(str(os.getpid()))
    try:
        station = Station(args.session, profile)
        if args.operation in ('begin', 'resume-begin'):
            station.begin()
        elif args.operation == 'observe':
            print(json.dumps(station.observe(frame=True)))
        elif args.operation == 'key':
            if station.state['phase'] not in ('SSH', 'RETURNED') or not args.key or not args.expect:
                parser.error('key requires SSH phase, --key and --expect')
            station.observe()
            station.key(args.key, args.expect)
        elif args.operation in ('read', 'cancel-read'):
            if not args.fixture:
                parser.error('--fixture is required')
            station.read_card(read(args.fixture), args.operation == 'cancel-read')
        elif args.operation == 'pc-start':
            station.prepare_pc()
        elif args.operation == 'pc-usb':
            station.serial(args.operator_confirmed)
        elif args.operation == 'pc-return':
            station.returned(args.operator_confirmed)
        elif args.operation == 'acknowledge':
            if not args.operator_confirmed or station.state['phase'] not in ('SSH', 'RETURNED'):
                parser.error('acknowledge requires SSH and --operator-confirmed')
            station.observe(frame=True)
            station.state['uncertain_action'] = None
            station.store()
        elif args.operation == 'finish':
            station.finish()
        else:
            print(json.dumps(station.state, indent=2))
    finally:
        lock.unlink()


if __name__ == '__main__':
    main()
