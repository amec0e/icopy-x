"""One generation, bounded status polling, and best-effort cleanup. No retries."""
from datetime import datetime, timezone
import re
import time
from uuid import uuid4

from .errors import ValidationError

PENDING = ('queued', 'in_progress')
TERMINAL = ('completed', 'failed', 'incomplete', 'cancelled')
POLL_SECONDS = 2
MAX_POLLS = 180
CANCEL_TIMEOUT = 10


class ReviewDeadline(TimeoutError):
    pass


class CheckpointError(OSError):
    pass


def response_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'resp_[A-Za-z0-9_-]{1,150}', value):
        raise ValidationError('response_identity')
    return value


def run(request, key, timeout, attempt, deadline, send, capture, checkpoint=None):
    """Return only the final object for the original response ID.

    Checkpoints contain metadata, never raw output. A process kill cannot promise
    cleanup; the last known ID/status remain available for reconciliation.
    """
    known_id = None
    terminal = False
    attempt['http_requests'] = []
    attempt['poll_count'] = 0
    attempt['cleanup'] = {'outcome': 'unknown_response'}

    def save():
        if checkpoint:
            try:
                checkpoint()
            except (ValueError, OSError) as error:
                raise CheckpointError() from error

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise ReviewDeadline()
        return min(timeout, value)

    def exchange(operation, payload=None):
        limit = CANCEL_TIMEOUT if operation == 'cancel' else remaining()
        record = dict(operation=operation,
            client_request_id=attempt['client_request_id'] if operation == 'submit' else str(uuid4()),
            timeout_seconds=limit, started_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=None, outcome='in_flight')
        attempt['http_requests'].append(record)
        # A broken disk must prevent new work, but must not prevent cleanup.
        if operation != 'cancel':
            try:
                save()
            except BaseException:
                record['outcome'] = 'not_sent'
                raise
        else:
            try:
                save()
            except CheckpointError:
                pass
        started = time.monotonic()
        try:
            result = send(payload, key, limit, attempt=record,
                          response_id=known_id, cancel=operation == 'cancel')
            record['outcome'] = 'response_received'
            return result
        except BaseException:
            record['outcome'] = 'transport_error'
            raise
        finally:
            record['elapsed_seconds'] = round(time.monotonic() - started, 3)

    def observe(value):
        nonlocal known_id, terminal
        if not isinstance(value, dict):
            raise ValidationError('response_shape')
        received_id = response_id(value.get('id'))
        if known_id is not None and received_id != known_id:
            raise ValidationError('response_identity')
        known_id = received_id
        attempt['response_id'] = known_id
        attempt['cleanup'] = {'outcome': 'pending'}
        status = value.get('status')
        if status not in PENDING + TERMINAL:
            # Preserve the ID so even an unexpected response can be cancelled.
            save()
            raise ValidationError('response_status')
        terminal = status in TERMINAL
        attempt['response_status'] = status
        attempt['http_requests'][-1].update(response_id=known_id, response_status=status)
        attempt['cleanup'] = {'outcome': 'not_needed' if terminal else 'pending'}
        if terminal:
            attempt['terminal_response'] = capture(value)
        save()
        model = value.get('model')
        if not isinstance(model, str) or (model != request['model'] and not re.fullmatch(
                re.escape(request['model']) + r'-\d{4}-\d{2}-\d{2}', model)):
            raise ValidationError('response_model')
        if value.get('background') is not True:
            raise ValidationError('response_background')
        if status in PENDING and (value.get('error') or value.get('incomplete_details')):
            raise ValidationError('response_incomplete')

    def cleanup():
        if known_id is None or terminal:
            return
        attempt['cleanup'] = {'outcome': 'in_flight'}
        try:
            save()
        except CheckpointError:
            pass
        try:
            value = exchange('cancel')
            observe(value)
            status = attempt['response_status']
            attempt['cleanup'] = {'outcome': 'cancelled' if status == 'cancelled' else
                                  'already_terminal' if terminal else 'unconfirmed',
                                  'response_status': status}
        except (ValueError, OSError) as error:
            attempt['cleanup'] = {'outcome': 'unconfirmed', 'error': type(error).__name__}

    try:
        value = exchange('submit', request)
        observe(value)
        remaining()  # Never accept a response received after the review deadline.
        while not terminal:
            if attempt['poll_count'] >= MAX_POLLS:
                raise ReviewDeadline()
            time.sleep(min(POLL_SECONDS, remaining()))
            remaining()
            attempt['poll_count'] += 1
            value = exchange('poll')
            observe(value)
            remaining()
        return value
    except BaseException as error:
        not_sent = (not attempt['http_requests'] or (len(attempt['http_requests']) == 1 and
                    attempt['http_requests'][0]['outcome'] == 'not_sent'))
        if not_sent:
            attempt['cleanup'] = {'outcome': 'not_needed'}
        attempt['outcome'] = ('not_sent' if not_sent else 'interrupted' if
            isinstance(error, (KeyboardInterrupt, SystemExit)) else 'transport_error')
        try:
            cleanup()
        finally:
            try:
                save()
            except CheckpointError:
                pass
        raise
