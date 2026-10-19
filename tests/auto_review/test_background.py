"""Background transport contracts: no network and no candidate execution."""
from copy import deepcopy
import json
import unittest
from unittest.mock import MagicMock, patch

from tools.auto_review import background, reviewer
from tools.auto_review.errors import ValidationError


class Clock:
    def __init__(self):
        self.now = 0

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.attempt = dict(client_request_id='fixture-client', outcome='in_flight')
        self.request = dict(model=reviewer.MODEL, background=True, store=False)
        self.saved = []

    def response(self, status='queued', **changes):
        value = dict(id='resp_fixture', model=reviewer.MODEL, background=True,
                     status=status, error=None, incomplete_details=None)
        value.update(changes)
        return value

    def run_response(self, send, checkpoint=None, deadline=360):
        def save():
            self.saved.append(deepcopy(self.attempt))
            if checkpoint:
                checkpoint()
        with patch.object(background.time, 'monotonic', self.clock.monotonic), \
                patch.object(background.time, 'sleep', self.clock.sleep):
            return background.run(self.request, 'fixture-key', 120, self.attempt,
                deadline, send, lambda value: reviewer.metadata(value, 'fixture'), checkpoint=save)

    def operations(self, send):
        return [('cancel' if call.kwargs['cancel'] else
                 'poll' if call.kwargs['response_id'] else 'submit') for call in send.call_args_list]

    def test_one_submit_polls_same_id_and_checkpoints_before_next_call(self):
        end = self.response('completed', usage=dict(input_tokens=123, output_tokens=45))
        def send(payload, key, timeout, **kwargs):
            self.assertLessEqual(timeout, 120)
            self.assertEqual(key, 'fixture-key')
            if payload is not None:
                self.assertTrue(payload['background'])
                self.assertFalse(payload['store'])
                return self.response()
            self.assertEqual(self.saved[-1]['response_id'], 'resp_fixture')
            self.assertEqual(kwargs['response_id'], 'resp_fixture')
            self.assertFalse(kwargs['cancel'])
            return self.response('in_progress') if self.clock.now == 2 else end
        sender = MagicMock(side_effect=send)
        self.assertEqual(self.run_response(sender), end)
        self.assertEqual(self.operations(sender), ['submit', 'poll', 'poll'])
        self.assertEqual(self.attempt['poll_count'], 2)
        self.assertEqual(self.attempt['cleanup']['outcome'], 'not_needed')
        self.assertEqual(self.attempt['terminal_response']['usage']['input_tokens'], 123)
        ids = [record['client_request_id'] for record in self.attempt['http_requests']]
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual([record['response_status'] for record in self.attempt['http_requests']],
                         ['queued', 'in_progress', 'completed'])
        self.assertNotIn('fixture-key', json.dumps(self.saved))

    def test_generation_can_exceed_old_120_second_wait_within_total_budget(self):
        sender = MagicMock(side_effect=lambda *a, **k: self.response(
            'completed' if self.clock.now >= 130 else 'in_progress'))
        self.assertEqual(self.run_response(sender)['status'], 'completed')
        self.assertEqual(self.clock.now, 130)
        self.assertEqual(self.operations(sender).count('submit'), 1)

    def test_poll_bound_scales_past_old_180_poll_limit(self):
        sender = MagicMock(side_effect=lambda *a, **k: self.response(
            'completed' if self.clock.now >= 400 else 'in_progress'))
        self.assertEqual(self.run_response(sender, deadline=5400)['status'], 'completed')
        self.assertEqual(self.clock.now, 400)
        self.assertEqual(self.attempt['poll_count'], 200)
        self.assertEqual(self.attempt['poll_limit'], 2700)
        self.assertEqual(self.operations(sender).count('submit'), 1)

    def test_lost_initial_acknowledgement_is_never_resubmitted(self):
        sender = MagicMock(side_effect=TimeoutError('sensitive failure'))
        with self.assertRaises(TimeoutError):
            self.run_response(sender)
        self.assertEqual(self.operations(sender), ['submit'])
        self.assertEqual(self.attempt['cleanup']['outcome'], 'unknown_response')
        self.assertNotIn('response_id', self.attempt)
        self.assertNotIn('sensitive failure', json.dumps(self.saved))

    def test_deadline_cancels_known_job_once_with_separate_cleanup_timeout(self):
        sender = MagicMock(side_effect=lambda *a, **k:
            self.response('cancelled') if k['cancel'] else self.response())
        with self.assertRaises(background.ReviewDeadline):
            self.run_response(sender, deadline=5)
        self.assertEqual(self.operations(sender), ['submit', 'poll', 'poll', 'cancel'])
        self.assertEqual(sender.call_args.args[2], background.CANCEL_TIMEOUT)
        self.assertEqual(self.attempt['cleanup']['outcome'], 'cancelled')

    def test_poll_failure_preserves_original_id_and_cancel_usage(self):
        sender = MagicMock(side_effect=[self.response(), OSError('private'),
            self.response('cancelled', usage={'input_tokens': 7, 'output_tokens': 3})])
        with self.assertRaises(OSError):
            self.run_response(sender)
        self.assertEqual(self.operations(sender), ['submit', 'poll', 'cancel'])
        self.assertEqual(self.attempt['terminal_response']['usage']['input_tokens'], 7)
        self.assertEqual(self.saved[-1]['cleanup']['outcome'], 'cancelled')

    def test_failed_cancel_or_pending_cancel_is_explicitly_unconfirmed(self):
        for cancellation in (OSError('private'), self.response('in_progress')):
            with self.subTest(cancellation=type(cancellation).__name__):
                sender = MagicMock(side_effect=[self.response(), TimeoutError(), cancellation])
                with self.assertRaises(TimeoutError):
                    self.run_response(sender)
                self.assertEqual(self.operations(sender), ['submit', 'poll', 'cancel'])
                self.assertEqual(self.attempt['cleanup']['outcome'], 'unconfirmed')

    def test_race_finishing_during_cancel_keeps_accounting_but_not_success(self):
        sender = MagicMock(side_effect=[self.response(), TimeoutError(),
            self.response('completed', usage={'input_tokens': 7, 'output_tokens': 3})])
        with self.assertRaises(TimeoutError):
            self.run_response(sender)
        self.assertEqual(self.attempt['cleanup']['outcome'], 'already_terminal')
        self.assertEqual(self.attempt['terminal_response']['usage']['output_tokens'], 3)

    def test_changed_id_never_redirects_poll_or_cleanup(self):
        sender = MagicMock(side_effect=[self.response(), self.response(id='resp_other'), self.response('cancelled')])
        with self.assertRaises(ValidationError) as error:
            self.run_response(sender)
        self.assertEqual(error.exception.code, 'response_identity')
        self.assertEqual(sender.call_args.kwargs['response_id'], 'resp_fixture')
        self.assertEqual(self.attempt['response_id'], 'resp_fixture')

    def test_invalid_identity_makes_no_followup_request(self):
        for identity in ('https://evil.invalid/', 'resp_../../secret', 'resp_x?token=key', None, 1):
            sender = MagicMock(return_value=self.response(id=identity))
            with self.subTest(identity=identity), self.assertRaises(ValidationError):
                self.run_response(sender)
            self.assertEqual(sender.call_count, 1)

    def test_unexpected_model_status_or_mode_cancels_acknowledged_active_job(self):
        for change, code in ((dict(model='gpt-6-sol'), 'response_model'),
                             (dict(status='surprise'), 'response_status'),
                             (dict(background=False), 'response_background')):
            sender = MagicMock(side_effect=[self.response(**change), self.response('cancelled')])
            with self.subTest(change=change), self.assertRaises(ValidationError) as error:
                self.run_response(sender)
            self.assertEqual(error.exception.code, code)
            self.assertEqual(self.operations(sender), ['submit', 'cancel'])

    def test_failed_and_incomplete_jobs_return_metadata_for_normal_validation(self):
        for status in ('failed', 'incomplete', 'cancelled'):
            sender = MagicMock(return_value=self.response(status))
            value = self.run_response(sender)
            with self.subTest(status=status), self.assertRaises(ValidationError) as error:
                reviewer.result(value)
            self.assertEqual(error.exception.code, 'response_incomplete')
            self.assertEqual(sender.call_count, 1)

    def test_checkpoint_failure_before_submit_prevents_send(self):
        sender = MagicMock()
        with self.assertRaises(background.CheckpointError):
            self.run_response(sender, checkpoint=MagicMock(side_effect=OSError()))
        sender.assert_not_called()
        self.assertEqual(self.attempt['outcome'], 'not_sent')

    def test_checkpoint_failure_after_ack_does_not_prevent_cancellation(self):
        sender = MagicMock(side_effect=[self.response(), self.response('cancelled')])
        def broken_disk_after_submit():
            if len(self.saved) > 1:
                raise OSError()
        with self.assertRaises(background.CheckpointError):
            self.run_response(sender, checkpoint=broken_disk_after_submit)
        self.assertEqual(self.operations(sender), ['submit', 'cancel'])
        self.assertEqual(self.attempt['response_status'], 'cancelled')

    def test_interrupt_cancels_and_checkpoints_before_propagating(self):
        sender = MagicMock(side_effect=[self.response(), KeyboardInterrupt(), self.response('cancelled')])
        with self.assertRaises(KeyboardInterrupt):
            self.run_response(sender)
        self.assertEqual(self.attempt['outcome'], 'interrupted')
        self.assertEqual(self.saved[-1]['cleanup']['outcome'], 'cancelled')

    def test_late_completed_response_is_not_promoted_or_needlessly_cancelled(self):
        def send(*args, **kwargs):
            self.clock.now = 361
            return self.response('completed', usage={'input_tokens': 1})
        sender = MagicMock(side_effect=send)
        with self.assertRaises(background.ReviewDeadline):
            self.run_response(sender)
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(self.attempt['terminal_response']['usage']['input_tokens'], 1)

    def test_http_methods_identity_guard_and_redirect_refusal(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{}'
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(reviewer, 'build_opener', return_value=opener):
            for cancel, method, suffix in ((False, 'GET', '/resp_fixture'), (True, 'POST', '/resp_fixture/cancel')):
                reviewer.send(None, 'fixture-key', 10, response_id='resp_fixture', cancel=cancel)
                outgoing = opener.open.call_args.args[0]
                self.assertEqual(outgoing.get_method(), method)
                self.assertEqual(outgoing.full_url, 'https://api.openai.com/v1/responses' + suffix)
                self.assertIsNone(outgoing.data)
            for identity in ('resp_../x', 'https://evil.invalid'):
                with self.assertRaises(ValidationError):
                    reviewer.send(None, 'fixture-key', 10, response_id=identity)
        with self.assertRaises(ValueError):
            reviewer.NoRedirect().redirect_request(None, None, None, None, None, None)
