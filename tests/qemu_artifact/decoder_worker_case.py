"""Packaged decoder activities, real ARM threads and Tk; no accessory/RF claims."""
from contextlib import ExitStack
from threading import Event, get_ident
from unittest.mock import patch


def run(root, pump):
    import actstack
    import activity_main
    import ics_decoder
    from _constants import KEY_OK

    ui_thread = get_ident()
    violations, checks, commands = [], [], []
    frame = ics_decoder.calculate_wiegand26_parity(165, 1551)
    response = ('$A_CARD_START$\nBit#:26\nFC#:165\nID#:1551\nwiedata#:{}\n'
                'Blk7#:1122334455667788\n$A_CARD_STOP$\n').format(format(frame, '026b'))
    capture = ics_decoder.parse_block(response)

    def require(condition, message):
        if not condition:
            violations.append(message)
            raise AssertionError(message)

    def guarded(method):
        def call(*args, **kwargs):
            require(get_ident() == ui_thread, 'Decoder worker touched Tk')
            return method(*args, **kwargs)
        return call

    class Port:
        is_open = True
        timeout = 1.2

        def write(self, command):
            commands.append(command.decode())
            require(command == b'RD\r\n', 'Unexpected decoder read command')
            self.lines = iter(response.encode().splitlines(keepends=True))

        def readline(self):
            return next(self.lines, b'')

        def close(self):
            self.is_open = False

    def write(block):
        require(block == capture['blk7'], 'Changed credential reached writer')
        commands.append('write HF')
        return True

    def verify(target, source):
        require(target == 'hf_iclass' and source == capture, 'Changed verification input')
        commands.append('verify HF')
        return True, 'Verified'

    def join(threads):
        for thread in threads:
            thread.join(2)
            require(not thread.is_alive(), 'Worker waited for Tk delivery')
        require(not violations, repr(violations))
        threads[:] = []

    with patch.object(ics_decoder, 'detect_decoder', lambda **kw: None), \
            patch.object(ics_decoder, 'detect_target', lambda: 'hf_iclass'), \
            patch.object(ics_decoder, 'write_to_card', write), \
            patch.object(ics_decoder, 'verify_target_card', verify):
        for cls in (activity_main.ICSDecoderActivity, activity_main.IClassSEActivity):
            activity = actstack.start_activity(cls)
            canvas = activity.getCanvas()
            threads = []
            original_start = activity.startBGTask

            def start(job):
                thread = original_start(job)
                threads.append(thread)
                return thread

            if hasattr(activity, '_detect_thread'):
                activity._detect_thread.join(2)
                require(not activity._detect_thread.is_alive(), 'Discovery did not settle')
            activity._cancel_decoder_session()
            with ExitStack() as stack:
                for owner, name in ((root, 'after'), (root, 'after_cancel'),
                                    (canvas, 'after'), (canvas, 'after_cancel'),
                                    (canvas, 'create_text')):
                    stack.enter_context(patch.object(owner, name, guarded(getattr(owner, name))))
                stack.enter_context(patch.object(activity, 'startBGTask', start))
                activity._ser = Port()
                activity._source_data = None
                activity._state = activity.STATE_READING
                activity._poll_decoder()
                join(threads)  # Deliberately withhold the UI loop until work finishes.
                require(activity._source_data is None, 'Worker changed read result')
                pump(lambda: activity._source_data is not None)
                require(activity._source_data == capture, 'Wrong decoded credential')
                checks.append(cls.__name__ + '/read')

                activity._state = activity.STATE_WAIT_BLANK
                activity._target_type = 'hf_iclass'
                activity.onKeyEvent(KEY_OK)
                join(threads)
                require(activity._state == activity.STATE_WRITING and not activity._last_write_ok,
                        'Worker changed write result')
                pump(lambda: activity._state == activity.STATE_RESULT)
                require(activity._last_write_ok, 'Write did not finish')
                checks.append(cls.__name__ + '/write')

                activity._do_verify()
                join(threads)
                require(activity._verify_success is None, 'Worker changed verification result')
                pump(lambda: activity._state == activity.STATE_RESULT)
                require(activity._verify_success is True, 'Verify did not finish')
                checks.append(cls.__name__ + '/verify')

                entered, release = Event(), Event()

                def detect():
                    entered.set()
                    require(release.wait(2), 'Held detection was not released')
                    return 'hf_iclass'

                before = list(commands)
                try:
                    with patch.object(ics_decoder, 'detect_target', detect):
                        activity._do_write()
                        require(entered.wait(2), 'Worker never started detection')
                        actstack.finish_activity()
                        release.set()
                        join(threads)
                    require(commands == before, 'Closed activity dispatched a write')
                    require(activity._state == activity.STATE_DESTROYED, 'Late result revived UI')
                    checks.append(cls.__name__ + '/exit-during-detection')
                finally:
                    release.set()
            require(not violations, repr(violations))
    # Leave a normal home activity for the caller's standard PWR/cleanup checks.
    activity = actstack.start_activity(activity_main.ICSDecoderActivity)
    return activity, dict(checks=checks, commands=commands, violations=violations,
                         substitutions=['decoder serial RD fixture; real read_card/parser',
                                        'target detection and HF writer/verifier result boundaries'])
