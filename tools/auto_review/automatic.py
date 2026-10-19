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
from urllib.request import Request, build_opener

from . import cli, profiles, report, reviewer, snapshots

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
        return json.loads(raw)


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


def marker(comment):
    if comment.get('user', {}).get('id') != BOT_ID:
        return None
    first = comment.get('body', '').split('\n', 1)[0]
    if not first.startswith(PREFIX) or not first.endswith(' -->') or len(first) > 3000:
        return None
    try:
        value = json.loads(first[len(PREFIX):-4])
        if (value['repository_id'] != REPOSITORY_ID or value['state'] not in STATES or
                not SHA.fullmatch(value['base']) or not SHA.fullmatch(value['head'])):
            return None
        integer(value['pr']); integer(value['run_id'])
        if value['reserved_at'] is not None:
            datetime.strptime(value['reserved_at'], '%Y-%m-%dT%H:%M:%SZ')
        return value
    except (ValueError, TypeError, KeyError):
        return None


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


def recipes(changed):
    """Trusted starting contexts, not a claim of complete dependency discovery."""
    selected = {}
    def add(paths, reason):
        selected.update({path: reason for path in paths})
    if any(p in ('src/middleware/ics_decoder.py', 'src/lib/actmain.py') or
           'ics_' in p or 'decoder_menu' in p for p in changed):
        add(profiles.PROFILES['accessory-menu']['paths'], 'Accessory/menu callers and lifecycle.')
        add(['tests/ui/activities/test_ics_decoder.py', 'tools/qemu_env.sh',
             'src/main/rftask.py', 'src/middleware/executor.py', 'src/middleware/pm3_compat.py',
             'src/middleware/pm3_localize.py'], 'Serial ownership, localization and harness boundaries.')
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
    initial = snapshots.collect(repo, current['base'], current['head'])
    context = recipes([row['path'] for row in initial['files'] if row['changed']])
    bundle = snapshots.collect(repo, current['base'], current['head'], context)
    bundle['stated_purpose'] = purpose
    bundle['context_selection'] = dict(profile='automatic-v1', paths=context,
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
    reserved = {comment['id'] for comment in ledger if (marker(comment) or {}).get('reserved_at', '')
                and marker(comment)['reserved_at'] >= cutoff}
    prs = pages(api, route('/pulls'), {'state': 'open', 'base': 'main', 'sort': 'created', 'direction': 'asc'})
    requested = environ.get('ASTRA_TARGET_PR', '').strip()
    if requested:
        requested = integer(int(requested))
        prs = [pr for pr in prs if pr['number'] == requested]
    for entry in prs:
        pr = api('GET', route('/pulls/' + str(integer(entry['number']))))
        if pr.get('draft') or pr.get('state') != 'open':
            continue
        current = identity(pr)
        comments = pages(api, route('/issues/' + str(current['pr']) + '/comments'))
        prior = [(comment, marker(comment)) for comment in comments if marker(comment) and same(marker(comment), current)]
        previous = prior[-1] if prior else None
        if previous and previous[1]['state'] != 'DEFERRED':
            if previous[1]['state'] == 'RESERVED':
                old = api('GET', route('/actions/runs/' + str(previous[1]['run_id'])))
                if old.get('status') == 'completed':
                    record = dict(previous[1], state='INCOMPLETE')
                    put_comment(api, record, '**INCOMPLETE** — the reserved run ended without publishing a result. '
                                'Inspect its evidence; no automatic retry will incur another charge.', previous[0]['id'])
            continue
        record = dict(current, state='DEFERRED', reserved_at=None, run_id=run_id)
        comment_id = previous[0]['id'] if previous else None
        if len(reserved) >= limit:
            if previous is None:
                put_comment(api, record, '**DEFERRED** — the rolling 24-hour automatic review allowance is used. '
                            'The queue will reconsider this commit when capacity is available; CI continues normally.')
            continue
        try:
            bundle = prepare_fn(pr, Path('.'))
            if bundle['gaps']:
                examples = '\n'.join(str(gap.get('path', '')) + ': ' + str(gap.get('reason', ''))
                                     for gap in bundle['gaps'][:8])
                raise ValueError('Source inventory has ' + str(len(bundle['gaps'])) +
                                 ' coverage gaps; first examples:\n' + examples)
        except (ValueError, OSError, TimeoutError, subprocess.CalledProcessError) as error:
            record['state'] = 'INCOMPLETE'
            # Only collector ValueErrors have fixed, non-secret diagnostic text.
            reason = str(error) if type(error) is ValueError else type(error).__name__
            put_comment(api, record, '**INCOMPLETE — no API call made.**\n\n' + report.block(reason[:1000]) +
                '\nUpdate a stale branch or split unrelated/oversized changes; a maintainer can prepare '
                'a focused review with explicit context. This is not a completed source audit.', comment_id)
            continue
        # Recheck after fetching/collecting and immediately before reservation.
        fresh = api('GET', route('/pulls/' + str(current['pr'])))
        if fresh.get('state') != 'open' or fresh.get('draft') or not same(identity(fresh), current):
            continue
        record.update(state='RESERVED', reserved_at=timestamp(reservation_clock()))
        comment_id = put_comment(api, record, '**Review reserved** for head `' + current['head'] +
            '` against base `' + current['base'] + '`. Up to three Astra passes will run. '
            'Findings and coverage gaps will replace this notice; no automatic retry is scheduled.', comment_id)
        policy = Path(__file__).with_name('policy.md').read_text(encoding='utf-8')
        output.mkdir(parents=True, exist_ok=False)
        (output / 'identity.json').write_text(json.dumps(dict(record, comment_id=comment_id,
            tool_revision=environ['GITHUB_SHA'], snapshot_sha256=snapshots.digest(bundle),
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
            record.get('base') != bundle.get('base') or record.get('head') != bundle.get('head')):
        raise ValueError('Review artifact identity mismatch')
    integer(record['comment_id']); integer(record['pr'])
    return record, bundle, policy


def run_review(api, environ, directory, review_fn=reviewer.review):
    record, bundle, policy = checked_input(directory, environ)
    if environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise ValueError('Workflow reruns cannot resubmit paid reviews')
    current = api('GET', route('/pulls/' + str(record['pr'])))
    if current.get('state') != 'open' or current.get('draft') or not same(identity(current), record):
        cli.save_report(directory, dict(status='INCOMPLETE', advisory=True, error='StaleReview'))
        return 2
    started_passes = 0
    def checkpoint(value):
        nonlocal started_passes
        cli.save_report(directory, value)
        count = len(value.get('attempts', []))
        if count > started_passes:
            fresh = api('GET', route('/pulls/' + str(record['pr'])))
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
    current = api('GET', route('/pulls/' + str(record['pr'])))
    if current.get('state') != 'open' or current.get('draft') or not same(identity(current), record):
        final = dict(saved, state='STALE')
        text = '**STALE** — the PR closed, became a draft, or its base/head changed. '
        text += 'This result is historical evidence only; no findings are published against the new revision.'
    else:
        try:
            result = report.read_json(directory / 'report.json')
        except (OSError, ValueError):
            result = dict(status='INCOMPLETE', advisory=True, error='MissingReviewEvidence')
        valid = (result.get('snapshot_sha256') == record['snapshot_sha256'] and
                 result.get('policy_sha256') == record['policy_sha256'] and
                 result.get('base') == record['base'] and result.get('head') == record['head'])
        if not valid:
            result = dict(status='INCOMPLETE', advisory=True, error='MissingOrMismatchedReviewEvidence')
        # The renderer revalidates source quotations and treats model text literally.
        text = report.render(result, bundle)
        complete = '**ADVISORY_COMPLETE**' in text[:200]
        final = dict(saved, state='ADVISORY_COMPLETE' if complete else 'INCOMPLETE')
    put_comment(api, final, text, record['comment_id'])


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
