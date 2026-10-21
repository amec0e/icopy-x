"""Trusted scheduled PR queue: reserve once, review read-only, publish separately.

The queue is the current open-PR inventory. Bot-owned comments are the durable
reservation ledger. Workflow concurrency serializes reservation and generation;
replaced pending schedule events lose no PR. No candidate code is checked out.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, build_opener

from . import checks, cli, dashboard, profiles, report, reviewer, snapshots

REPOSITORY = 'lab-401/icopy-x'
REPOSITORY_ID = 1187322254
BOT_ID = 41898282  # github-actions[bot], not a contributor-supplied login
PREFIX = '<!-- icopy-astra-pr-v1 '
SHA = re.compile(r'[0-9a-f]{40}')
STATES = {'RESERVED', 'DEFERRED', 'INCOMPLETE', 'ADVISORY_COMPLETE', 'STALE'}
MAX_PAGES = 10


def utcnow():
    return datetime.now(timezone.utc)


def timestamp(value):
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def integer(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Invalid positive identity')
    return value


class GitHub:
    def __init__(self, token):
        if not token:
            raise ValueError('Missing GitHub token')
        self.token = token

    def __call__(self, method, path, data=None):
        if not path.startswith('/repos/' + REPOSITORY + '/') and path != '/repos/' + REPOSITORY:
            raise ValueError('Unexpected GitHub repository')
        request = Request('https://api.github.com' + path, method=method,
            data=json.dumps(data).encode('utf-8') if data is not None else None,
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
        with build_opener(reviewer.NoRedirect).open(request, timeout=30) as response:
            raw = response.read(8_000_001)
        if len(raw) > 8_000_000:
            raise ValueError('GitHub response exceeds limit')
        return json.loads(raw) if raw else None


def route(suffix=''):
    return '/repos/' + REPOSITORY + suffix


def pages(api, path, query=None):
    result = []
    for number in range(1, MAX_PAGES + 1):
        params = dict(query or {}, per_page=100, page=number)
        rows = api('GET', path + '?' + urlencode(params))
        if not isinstance(rows, list):
            raise ValueError('Invalid GitHub collection')
        result.extend(rows)
        if len(rows) < 100:
            return result
    raise ValueError('GitHub inventory exceeds limit; no paid review scheduled')


def trusted(environ):
    if (environ.get('GITHUB_REPOSITORY') != REPOSITORY or
            environ.get('GITHUB_REPOSITORY_ID') != str(REPOSITORY_ID) or
            environ.get('GITHUB_REF') != 'refs/heads/main' or
            environ.get('GITHUB_EVENT_NAME') not in ('schedule', 'workflow_dispatch') or
            not SHA.fullmatch(environ.get('GITHUB_SHA', ''))):
        raise ValueError('Automatic review requires trusted repository main')
    return integer(int(environ['GITHUB_RUN_ID']))


def identity(pr):
    if (pr.get('state') != 'open' or pr.get('draft') is not False or
            pr['base']['repo']['id'] != REPOSITORY_ID or pr['base']['ref'] != 'main'):
        raise ValueError('PR is not an eligible open main-branch proposal')
    base, head = pr['base']['sha'], pr['head']['sha']
    if not SHA.fullmatch(base) or not SHA.fullmatch(head):
        raise ValueError('Invalid PR commit')
    return dict(repository_id=REPOSITORY_ID, pr=integer(pr['number']), base=base, head=head)


def current_pr(api, number):
    """PR base.sha can lag main even on an open PR; resolve the live Git ref."""
    pr = api('GET', route('/pulls/' + str(integer(number))))
    reference = api('GET', route('/git/ref/heads/main'))
    commit = reference.get('object', {})
    if (reference.get('ref') != 'refs/heads/main' or commit.get('type') != 'commit' or
            not isinstance(commit.get('sha'), str) or not SHA.fullmatch(commit['sha'])):
        raise ValueError('Invalid current main reference')
    pr['base'] = dict(pr['base'], sha=commit['sha'])
    return pr


def marker(comment):
    if comment.get('user', {}).get('id') != BOT_ID:
        return None
    current = dashboard.load(comment, BOT_ID)
    if current is not None:
        return checked_record(current['current'])
    first = comment.get('body', '').split('\n', 1)[0]
    if not first.startswith(PREFIX) or not first.endswith(' -->') or len(first) > 3000:
        return None
    try:
        return checked_record(json.loads(first[len(PREFIX):-4]))
    except (ValueError, TypeError, KeyError):
        return None


def checked_record(value):
    try:
        if (value['repository_id'] != REPOSITORY_ID or value['state'] not in STATES or
                not SHA.fullmatch(value['base']) or not SHA.fullmatch(value['head'])):
            return None
        integer(value['pr']); integer(value['run_id'])
        if value['reserved_at'] is not None:
            datetime.strptime(value['reserved_at'], '%Y-%m-%dT%H:%M:%SZ')
        return value
    except (ValueError, TypeError, KeyError):
        return None


def records(comment):
    state = dashboard.load(comment, BOT_ID)
    if state is not None:
        values = [checked_record(r) for r in state['records']]
        if any(r is None for r in values):
            raise ValueError('Invalid dashboard reservation ledger')
        return values
    value = marker(comment)
    return [value] if value else []


def state_for(comments, current):
    candidates = [(comment, dashboard.load(comment, BOT_ID)) for comment in comments]
    existing = [(c, s) for c, s in candidates if s is not None and s['current']['pr'] == current['pr']]
    if existing:
        comment, state = existing[-1]
    else:
        legacy = [c for c in comments if marker(c) and marker(c)['pr'] == current['pr']]
        comment, state = (legacy[-1] if legacy else None), dashboard.blank()
    combined = {(r['pr'], r['base'], r['head'], r['run_id']): r
                for c in comments for r in records(c) if r['pr'] == current['pr']}
    # The dashboard is authoritative for migrated records finalized in place.
    combined.update({(r['pr'], r['base'], r['head'], r['run_id']): r for r in state['records']})
    state['records'] = list(combined.values())
    return state, comment


def put_dashboard(api, state, comment=None):
    outgoing = dashboard.body(state)
    if comment and comment['body'] == outgoing:
        checks.publish(api, route, state, comment['id'])
        return comment['id']
    path = ('/issues/comments/' + str(integer(comment['id'])) if comment else
            '/issues/' + str(state['current']['pr']) + '/comments')
    result = api('PATCH' if comment else 'POST', route(path), {'body': outgoing})
    if comment is not None:
        comment['body'] = outgoing
    checks.publish(api, route, state, result['id'])
    return integer(result['id'])


def observe_ci(api, state, pr):
    try:
        state['ci'] = checks.collect(api, route, pr)
    except (ValueError, OSError, KeyError, TypeError):
        state['ci'] = [dict(name='CI evidence', state='unavailable; not a pass')]
    state['integration_pending'] = pr.get('mergeable_state') not in ('clean', 'unstable', 'blocked')


def same(left, right):
    return all(left.get(key) == right.get(key) for key in ('repository_id', 'pr', 'base', 'head'))


def run_url(run_id):
    return 'https://github.com/' + REPOSITORY + '/actions/runs/' + str(integer(run_id))


def body(record, text):
    header = PREFIX + json.dumps(record, sort_keys=True, separators=(',', ':')) + ' -->\n'
    footer = ('\n\n[Full evidence and workflow](' + run_url(record['run_id']) +
              '). Advisory only; existing CI and maintainer approval still govern merging.\n')
    # Keep GitHub's comment limit independent of model verbosity. Full artifact
    # remains available; never claim that this bounded display is exhaustive.
    if len(text.encode('utf-8')) > 50_000:
        text = text.encode('utf-8')[:48_000].decode('utf-8', errors='ignore')
        text += '\n</pre>\n\n**Display shortened. Download review.md for the full returned report.**'
    return header + text + footer


def put_comment(api, record, text, comment_id=None):
    path = '/issues/comments/' + str(integer(comment_id)) if comment_id else '/issues/' + str(record['pr']) + '/comments'
    response = api('PATCH' if comment_id else 'POST', route(path), {'body': body(record, text)})
    # Never retry an unacknowledged write: it may already have reserved work.
    return integer(response['id'])


def reconcile(api, current, comments):
    """Close abandoned/stale reservations without erasing their usage ledger."""
    for comment in comments:
        record = marker(comment)
        if not record or record['pr'] != current['pr'] or record['state'] != 'RESERVED':
            continue
        if not same(record, current):
            final = dict(record, state='STALE')
            text = ('**STALE** — the base/head changed before this reservation was finalized. '
                    'Its usage remains reserved; no automatic retry will review the obsolete commits.')
        else:
            try:
                old = api('GET', route('/actions/runs/' + str(record['run_id'])))
            except HTTPError as error:
                error.close()
                if error.code != 404:
                    raise
                old = {'status': 'completed'}
            if old.get('status') != 'completed':
                continue
            final = dict(record, state='INCOMPLETE')
            text = ('**INCOMPLETE** — the reserved run ended without publishing a result, or its '
                    'run record is no longer available. Inspect prior evidence/usage; '
                    'no automatic retry will incur another charge.')
        state = dashboard.load(comment, BOT_ID)
        if state is not None:
            state = dashboard.remember(state, final)
            state['notice'] = text.replace('**', '')
            put_dashboard(api, state, comment)
        else:
            put_comment(api, final, text, comment['id'])
            comment['body'] = body(final, text)


def recipes(changed):
    """Trusted starting contexts, not a claim of complete dependency discovery."""
    selected = {}
    def add(paths, reason):
        selected.update({path: reason for path in paths})
    if any(p in ('src/middleware/ics_decoder.py', 'src/lib/actmain.py', 'src/lib/activity_main.py') or
           'ics_' in p or 'decoder_' in p for p in changed):
        add(profiles.PROFILES['accessory-menu']['paths'], 'Accessory/menu callers and lifecycle.')
        add(['tests/ui/activities/test_ics_decoder.py', 'tools/qemu_env.sh',
             'src/main/rftask.py', 'src/middleware/executor.py', 'src/middleware/pm3_compat.py',
             'src/middleware/pm3_localize.py'], 'Serial ownership, localization and harness boundaries.')
        add(['tests/ui/activities/test_decoder_workers.py', 'tests/ui/test_pm3_operation_ownership.py',
             'tests/qemu_artifact/strict_transport.py'], 'Worker and persistent transcript assertions.')
    if any(p.startswith('plugins/') or 'plugin_' in p or 'input_' in p for p in changed):
        add(['src/lib/plugin_activity.py', 'src/lib/plugin_loader.py', 'src/lib/plugins_menu.py',
             'src/lib/json_renderer.py', 'src/middleware/executor.py', 'src/middleware/pm3_compat.py',
             'src/middleware/pm3_localize.py', 'src/main/rftask.py', 'tests/ui/test_plugin_activity.py',
             'tests/ui/test_plugin_integration.py', 'tests/ui/test_plugin_loader.py'],
            'Plugin dispatch, rendering, discovery, PM3 ownership and regression contracts.')
    if any(p.startswith('src/middleware/') for p in changed):
        add(['src/middleware/executor.py', 'src/middleware/pm3_compat.py',
             'src/middleware/pm3_localize.py', 'src/main/rftask.py'], 'Shared command/response transport contract.')
    if any(p in ('src/middleware/iclasswrite.py', 'src/middleware/hficlass.py') for p in changed):
        add(['src/middleware/iclassread.py', 'src/middleware/iclasswrite.py', 'src/middleware/hficlass.py',
             'src/middleware/ics_decoder.py', 'tests/ui/test_pm3_response_compat.py'], 'iCLASS consumers and normalization.')
    if any(p.startswith('src/lib/') for p in changed):
        add(['src/lib/actmain.py', 'src/lib/actbase.py', 'src/lib/actstack.py',
             'src/lib/widget.py', 'tests/ui/conftest.py', 'tests/ui/activities/conftest.py'], 'UI lifecycle and test doubles.')
    if any(p.startswith(('build/', 'tools/build', '.github/workflows/build', 'tests/build/')) for p in changed):
        add(['tools/build_ipk.py', '.github/workflows/build-ipk.yml',
             'tests/test_build_ipk_contracts.py'], 'Factory/flash package boundary.')
    if any(p == 'CONTRIBUTING.md' or p.startswith(('tools/auto_review/', 'tests/auto_review/',
                                                 '.github/workflows/astra-')) for p in changed):
        add(['tools/auto_review/' + name for name in ('automatic.py', 'hosted.py', 'cli.py',
             'snapshots.py', 'reviewer.py', 'background.py', 'contract.py', 'report.py',
             'profiles.py', 'policy.md', 'dashboard.py', 'checks.py')], 'Reviewer trust, output and source-coverage contracts.')
        add(['.github/workflows/astra-pr-review.yml', '.github/workflows/astra-review-pilot.yml',
             '.github/workflows/test-host.yml', '.github/workflows/qemu-critical.yml'],
            'Actual automation and contributor CI boundaries.')
    return selected


def prepare(pr, repo):
    current = identity(pr)
    purpose = pr.get('title', '') + '\n\n' + (pr.get('body') or '')
    if not purpose.strip() or len(purpose) > 8000:
        raise ValueError('PR title/body exceeds review context limit; provide a concise purpose')
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('GIT_') and k not in ('OPENAI_API_KEY', 'GH_TOKEN', 'GITHUB_TOKEN')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1')
    subprocess.run(['git', '-C', str(repo), '-c', 'core.hooksPath=/dev/null', 'fetch', '--no-tags',
        '--no-recurse-submodules', 'https://github.com/' + REPOSITORY + '.git', current['base'], current['head']],
        env=env, check=True, timeout=120, stdout=subprocess.DEVNULL)
    # No checkout, imports, hooks, filters or PR-selected executable/configuration.
    comparison_base = snapshots.git(repo, 'merge-base', current['base'], current['head']).decode().strip()
    initial = snapshots.collect(repo, comparison_base, current['head'])
    context = recipes([row['path'] for row in initial['files'] if row['changed']])
    previous = pr.get('_astra_previous_items', [])
    inventory = snapshots.tree(repo, comparison_base).keys() | snapshots.tree(repo, current['head']).keys()
    for item in previous:
        path = item['finding']['path']
        if path in inventory:
            context[path] = 'Recheck an earlier contributor action against this revision.'
    # Reviewing a branch does not require repeatedly merging unrelated main
    # changes into it. Report the real comparison base and prevent GO until
    # current-main integration and CI are established.
    bundle = snapshots.collect(repo, comparison_base, current['head'], context)
    bundle['integration_base'] = current['base']
    bundle['previous_items'] = previous
    bundle['stated_purpose'] = purpose
    bundle['context_selection'] = dict(profile='automatic-v2', paths=context,
        limitation='Maintained starting contexts; model must disclose missing dependencies.')
    if len(snapshots.canonical(bundle)) > bundle['limits']['max_bytes']:
        bundle['gaps'].append(dict(path='', side='', reason='serialized bundle exceeds input budget'))
    return bundle


def select(api, environ, output, prepare_fn=prepare, now=None):
    run_id = trusted(environ)
    if environ.get('ASTRA_AUTOMATIC_REVIEW') != 'true' or environ.get('GITHUB_RUN_ATTEMPT') != '1':
        return False  # Never rerun paid work from a workflow rerun button.
    reservation_clock = utcnow if now is None else lambda: now
    now = now or utcnow()
    limit = int(environ.get('ASTRA_REVIEW_DAILY_LIMIT') or '3')
    if not 1 <= limit <= 20:
        raise ValueError('Daily review limit must be 1..20')
    repo = api('GET', route())
    if repo.get('id') != REPOSITORY_ID or repo.get('default_branch') != 'main':
        raise ValueError('Unexpected repository identity/default branch')
    cutoff = timestamp(now - timedelta(hours=24))
    ledger = pages(api, route('/issues/comments'), {'since': cutoff, 'sort': 'updated', 'direction': 'desc'})
    reserved = {(r['pr'], r['run_id']) for comment in ledger for r in records(comment)
                if r.get('reserved_at') and r['reserved_at'] >= cutoff}
    prs = pages(api, route('/pulls'), {'state': 'open', 'base': 'main', 'sort': 'created', 'direction': 'asc'})
    requested = environ.get('ASTRA_TARGET_PR', '').strip()
    if requested:
        requested = integer(int(requested))
        prs = [pr for pr in prs if pr['number'] == requested]
    for entry in prs:
        pr = current_pr(api, entry['number'])
        if pr.get('draft') or pr.get('state') != 'open':
            continue
        current = identity(pr)
        comments = pages(api, route('/issues/' + str(current['pr']) + '/comments'))
        reconcile(api, current, comments)
        state, comment = state_for(comments, current)
        prior = [r for r in state['records'] if same(r, current)]
        previous = prior[-1] if prior else None
        observe_ci(api, state, pr)
        if previous and previous['state'] != 'DEFERRED':
            state['current'] = previous
            put_dashboard(api, state, comment)
            continue
        record = dict(current, state='DEFERRED', reserved_at=None, run_id=run_id)
        if len(reserved) >= limit or environ.get('ASTRA_REFRESH_ONLY') == 'true':
            state = dashboard.remember(state, previous or record)
            state['notice'] = ('Review queued: the rolling 24-hour allowance is used. The queue will '
                'review the latest commit when capacity returns; no action is needed to obtain a slot.'
                if len(reserved) >= limit else 'Review queued. This run only refreshed the checklist and CI.')
            put_dashboard(api, state, comment)
            continue
        try:
            pr['_astra_previous_items'] = dashboard.pending_items(state)
            bundle = prepare_fn(pr, Path('.'))
            # Test collectors and imported evidence must bind the same prior list.
            bundle['previous_items'] = pr['_astra_previous_items']
            if bundle['gaps']:
                examples = '\n'.join(str(gap.get('path', '')) + ': ' + str(gap.get('reason', ''))
                                     for gap in bundle['gaps'][:8])
                raise ValueError('Source inventory has ' + str(len(bundle['gaps'])) +
                                 ' coverage gaps; first examples:\n' + examples)
        except (ValueError, OSError, TimeoutError, subprocess.CalledProcessError) as error:
            record['state'] = 'INCOMPLETE'
            # Only collector ValueErrors have fixed, non-secret diagnostic text.
            reason = str(error) if type(error) is ValueError else type(error).__name__
            state = dashboard.remember(state, record)
            state['notice'] = ('Review incomplete; no API call made. ' + reason[:1000] +
                ' The reviewer needs this evidence before it can assess the current revision.')
            put_dashboard(api, state, comment)
            continue
        # Recheck after fetching/collecting and immediately before reservation.
        fresh = current_pr(api, current['pr'])
        if fresh.get('state') != 'open' or fresh.get('draft') or not same(identity(fresh), current):
            continue
        record.update(state='RESERVED', reserved_at=timestamp(reservation_clock()))
        state = dashboard.remember(state, record)
        state['notice'] = 'Review in progress. Earlier actions stay visible until they are rechecked.'
        comment_id = put_dashboard(api, state, comment)
        policy = Path(__file__).with_name('policy.md').read_text(encoding='utf-8')
        output.mkdir(parents=True, exist_ok=False)
        (output / 'identity.json').write_text(json.dumps(dict(record, comment_id=comment_id,
            tool_revision=environ['GITHUB_SHA'], comparison_base=bundle['base'], snapshot_sha256=snapshots.digest(bundle),
            policy_sha256=snapshots.digest(policy)), indent=2), encoding='utf-8')
        (output / 'snapshot.json').write_text(json.dumps(bundle, indent=2), encoding='utf-8')
        return True
    return False


def checked_input(directory, environ):
    run_id = trusted(environ)
    record = report.read_json(directory / 'identity.json')
    bundle = report.read_json(directory / 'snapshot.json')
    policy = Path(__file__).with_name('policy.md').read_text(encoding='utf-8')
    if (record.get('repository_id') != REPOSITORY_ID or record.get('run_id') != run_id or
            record.get('tool_revision') != environ['GITHUB_SHA'] or
            record.get('state') != 'RESERVED' or
            record.get('snapshot_sha256') != snapshots.digest(bundle) or
            record.get('policy_sha256') != snapshots.digest(policy) or
            record.get('comparison_base', record.get('base')) != bundle.get('base') or
            record.get('base') != bundle.get('integration_base', bundle.get('base')) or
            record.get('head') != bundle.get('head')):
        raise ValueError('Review artifact identity mismatch')
    integer(record['comment_id']); integer(record['pr'])
    return record, bundle, policy


def run_review(api, environ, directory, review_fn=reviewer.review):
    record, bundle, policy = checked_input(directory, environ)
    if environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise ValueError('Workflow reruns cannot resubmit paid reviews')
    current = current_pr(api, record['pr'])
    if current.get('state') != 'open' or current.get('draft') or not same(identity(current), record):
        cli.save_report(directory, dict(status='INCOMPLETE', advisory=True, error='StaleReview'))
        return 2
    started_passes = 0
    def checkpoint(value):
        nonlocal started_passes
        cli.save_report(directory, value)
        count = len(value.get('attempts', []))
        if count > started_passes:
            fresh = current_pr(api, record['pr'])
            if fresh.get('state') != 'open' or fresh.get('draft') or not same(identity(fresh), record):
                raise ValueError('PR changed before next generation')
            started_passes = count
    result = review_fn(bundle, policy, environ.get('OPENAI_API_KEY'), checkpoint=checkpoint)
    cli.save_report(directory, result)
    return 0 if result['status'] == 'ADVISORY_COMPLETE' else 2


def publish(api, environ, directory):
    record, bundle, _ = checked_input(directory, environ)
    comment = api('GET', route('/issues/comments/' + str(record['comment_id'])))
    saved = marker(comment)
    if not saved or not same(saved, record) or saved['run_id'] != record['run_id'] or saved['state'] != 'RESERVED':
        raise ValueError('Publication reservation mismatch')
    state = dashboard.load(comment, BOT_ID) or dashboard.remember(dashboard.blank(), saved)
    current = current_pr(api, record['pr'])
    if current.get('state') != 'open' or current.get('draft') or not same(identity(current), record):
        final = dict(saved, state='STALE')
        text = '**STALE** — the PR closed, became a draft, or its base/head changed. '
        text += 'This result is historical evidence only; no findings are published against the new revision.'
        state['notice'] = text.replace('**', '')
    else:
        try:
            result = report.read_json(directory / 'report.json')
        except (OSError, ValueError):
            result = dict(status='INCOMPLETE', advisory=True, error='MissingReviewEvidence')
        valid = (result.get('snapshot_sha256') == record['snapshot_sha256'] and
                 result.get('policy_sha256') == record['policy_sha256'] and
                 result.get('base') == bundle['base'] and result.get('head') == record['head'])
        if not valid:
            result = dict(status='INCOMPLETE', advisory=True, error='MissingOrMismatchedReviewEvidence')
        # Validation is structured, never inferred from rendered Markdown.
        status, _, _ = report.validated(result, bundle)
        state = dashboard.accept(state, result, bundle, record['run_id'])
        final = dict(saved, state=status)
        state['integration_pending'] = bundle['base'] != record['base']
    state = dashboard.remember(state, final)
    observe_ci(api, state, current)
    if bundle['base'] != record['base']:
        state['integration_pending'] = True
    put_dashboard(api, state, comment)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['select', 'review', 'publish'])
    parser.add_argument('--directory', type=Path, default=Path('review-evidence'))
    args = parser.parse_args(argv)
    api = GitHub(os.environ.get('GH_TOKEN'))
    if args.operation == 'select':
        ready = select(api, os.environ, args.directory)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
                output.write('ready=' + ('true' if ready else 'false') + '\n')
        return 0
    if args.operation == 'review':
        return run_review(api, os.environ, args.directory)
    publish(api, os.environ, args.directory)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as failure:
        detail = str(failure)[:1000] if type(failure) is ValueError else ''
        if type(getattr(failure, 'code', None)) is int:
            detail = 'HTTP ' + str(failure.code)
        print('Automatic reviewer stopped: ' + type(failure).__name__ + (' — ' + detail if detail else ''))
        raise SystemExit(2)
