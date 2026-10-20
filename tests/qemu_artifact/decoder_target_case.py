"""Real target probes/ownership/Tk against finite HF/LF socket transcripts."""
from contextlib import ExitStack
from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import patch

from strict_transport import ConnectionTranscript


def run(root, pump, firmware):
    import actstack
    import activity_main
    import executor
    import ics_decoder
    from _constants import KEY_M1, KEY_M2, KEY_OK

    ui_thread = get_ident()
    violations, threads, checks, wires = [], [], [], []
    frame = ics_decoder.calculate_wiegand26_parity(165, 1551)
    capture = ics_decoder.parse_block(
        ('$A_CARD_START$\nBit#:26\nFC#:165\nID#:1551\nwiedata#:{}\nBlk7#:1122334455667788\n'
         '$A_CARD_STOP$\n').format(format(frame, '026b')))
    command = ('hf iclass rdbl b 6 k {}' if firmware == 'original'
               else 'hf iclass rdbl --blk 6 -k {}')
    hf1, hf2 = [command.format(key) for key in ('AFA785A7DAB33378', '2020666666668888')]
    good = ('block 06 : 11 22 33 44 55 66 77 88\n' if firmware == 'original'
            else '[+] block 6/0x06 : 11 22 33 44 55 66 77 88\n') + 'Nikola.D: 0\n'
    absent = 'Authentication failed\nNikola.D: 0\n'
    lock, armed, waited = executor.LOCK_THREAD, Event(), Event()

    def require(condition, message):
        if not condition:
            violations.append(message)
            raise AssertionError(message)

    class ObservedLock:
        def acquire(self, *args, **kwargs):
            if armed.is_set():
                armed.clear()
                acquired = lock.acquire(blocking=False)
                if acquired:
                    lock.release()
                require(not acquired, 'New poll did not wait for the previous PM3 owner')
                waited.set()
            return lock.acquire(*args, **kwargs)

        def release(self):
            lock.release()

        def __enter__(self):
            self.acquire()
            return self

        def __exit__(self, *args):
            self.release()

    def guarded(method):
        def call(*args, **kwargs):
            require(get_ident() == ui_thread, 'Target worker touched Tk')
            return method(*args, **kwargs)
        return call

    def start(cls, stack):
        activity = actstack.start_activity(cls)
        if hasattr(activity, '_detect_thread'):
            activity._detect_thread.join(2)
            require(not activity._detect_thread.is_alive(), 'Discovery did not settle')
        activity._cancel_decoder_session()
        canvas = activity.getCanvas()
        for name in ('after', 'after_cancel', 'create_text'):
            stack.enter_context(patch.object(canvas, name, guarded(getattr(canvas, name))))
        original_start = activity.startBGTask

        def launch(job):
            thread = original_start(job)
            threads.append(thread)
            return thread

        stack.enter_context(patch.object(activity, 'startBGTask', launch))
        activity._source_data = capture
        activity._target_type = None
        activity._state = activity.STATE_WAIT_BLANK
        return activity

    def install(steps, stack):
        wire = ConnectionTranscript(steps)
        wires.append(wire)
        socket_api = SimpleNamespace(socket=lambda *a: wire.new_socket(), AF_INET=2,
                                     SOCK_STREAM=1, timeout=TimeoutError)
        stack.enter_context(patch.object(executor, 'socket', socket_api))
        stack.enter_context(patch.object(executor, '_socket_instance', None))
        stack.enter_context(patch.object(executor, '_pipeline_needs_cleanup', False))
        return wire

    def join():
        for thread in threads:
            thread.join(2)
            require(not thread.is_alive(), 'Target worker failed to finish without Tk')
        threads[:] = []
        require(not violations, repr(violations))

    with ExitStack() as stack:
        stack.enter_context(patch.object(ics_decoder, 'detect_decoder', lambda **kw: None))
        stack.enter_context(patch.object(executor, 'LOCK_THREAD', ObservedLock()))
        for name in ('after', 'after_cancel'):
            stack.enter_context(patch.object(root, name, guarded(getattr(root, name))))
        try:
            for cls in (activity_main.ICSDecoderActivity, activity_main.IClassSEActivity):
                wire = install([dict(command=hf1, response=absent, blocked=True),
                                dict(command=hf1, response=good)], stack)
                activity = start(cls, stack)
                activity._start_target_poll()
                pump(lambda: wire.entered.is_set())
                beat = []
                root.after(1, lambda: beat.append(True))
                pump(lambda: bool(beat))
                activity._poll_target()  # Single-flight and disabled Write while probing.
                activity.onKeyEvent(KEY_OK)
                activity.onKeyEvent(KEY_M2)
                require(len(threads) == 1 and activity._state == activity.STATE_WAIT_BLANK,
                        'Polling overlapped another probe/write')
                checks.append(cls.__name__ + '/responsive-single-flight')
                activity.onKeyEvent(KEY_M1)
                expected = (activity.STATE_DECODED if cls is activity_main.ICSDecoderActivity
                            else activity.STATE_DESTROYED)
                require(activity._state == expected, 'Back waited for the held PM3 response')
                require(not wire.release.is_set(), 'Response was released before Back')
                checks.append(cls.__name__ + '/back-before-response')
                if cls is activity_main.ICSDecoderActivity:
                    activity._start_write()
                else:
                    activity = start(cls, stack)
                    activity._start_target_poll()
                waited.clear()
                armed.set()
                pump(lambda: waited.is_set())
                require(len(wire.commands) == 1, 'Re-entry issued a command before cleanup')
                wire.release.set()
                join()
                pump(lambda: activity._target_type is not None)
                require(activity._target_type == 'hf_iclass', 'Stale poll replaced the fresh target')
                wire.verify()
                checks.append(cls.__name__ + '/owned-reentry')
                actstack.finish_activity()

            wire = install([dict(command=hf1, response=absent), dict(command=hf2, response=absent),
                            dict(command='lf t55xx detect',
                                 response='Chip type......... T55x7\nNikola.D: 0\n')], stack)
            activity = start(activity_main.ICSDecoderActivity, stack)
            activity._poll_target()
            join()
            pump(lambda: activity._target_type is not None)
            require(activity._target_type == 'lf_t5577' and activity._target_write_available(),
                    'HF-to-LF fallback did not find a writable LF target')
            wire.verify()
            checks.append('HF-to-LF-order')
            actstack.finish_activity()
        finally:
            for wire in wires:
                wire.release.set()
            join()
        require(not violations, repr(violations))
    activity = actstack.start_activity(activity_main.ICSDecoderActivity)
    return activity, dict(checks=checks, violations=violations,
                         transcripts=[dict(commands=wire.commands, violations=wire.violations,
                                           connections=wire.connections) for wire in wires],
                         substitutions=['PM3 socket: exact synthetic HF/LF responses',
                                        'accessory discovery: absent; credential: parsed fixture'])
