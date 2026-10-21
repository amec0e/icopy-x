"""Read exact-revision CI; model statements never turn a check green."""
from urllib.parse import urlencode
import re
from . import dashboard

REQUIRED = ('Host tests (ubuntu-24.04, Python 3.8)',
            'Host tests (ubuntu-24.04, Python 3.12)',
            'Host tests (windows-latest, Python 3.8)', 'QEMU critical flows',
            'Build IPK Packages', 'Verify IPK Contents', 'Package Release Assets',
            'offline (ubuntu-24.04)', 'offline (windows-latest)')
APP_ID = 15368  # GitHub Actions; a contributor status with the same name is insufficient.


def collect(api, route, pr):
    revisions = [pr['head']['sha']]
    merge = pr.get('merge_commit_sha')
    if merge:
        commit = api('GET', route('/git/commits/' + merge))
        parents = {row['sha'] for row in commit.get('parents', [])}
        if parents == {pr['head']['sha'], pr['base']['sha']}:
            revisions.append(merge)
    rows = []
    for revision in revisions:
        for page in range(1, 11):
            result = api('GET', route('/commits/' + revision + '/check-runs?') +
                         urlencode(dict(per_page=100, page=page, filter='latest')))
            batch = result['check_runs']
            rows.extend(row for row in batch if row.get('app', {}).get('id') == APP_ID
                        and row.get('head_sha') == revision)
            if len(batch) < 100:
                break
        else:
            raise ValueError('CI inventory exceeds limit')
    latest = {}
    for row in rows:
        # A running/failed rerun takes precedence over an older green result.
        if row['name'] not in latest or row['id'] > latest[row['name']]['id']:
            latest[row['name']] = row
    # QEMU publishes a commit status, not a Check Run. Bind it to the exact
    # head and trusted bot/controller; never infer it from a worker job name.
    qemu = None
    for page in range(1, 11):
        batch = api('GET', route('/commits/' + pr['head']['sha'] + '/statuses?') +
                    urlencode(dict(per_page=100, page=page)))
        for row in batch:
            if row.get('context') == 'QEMU critical flows':
                if qemu is None or row['id'] > qemu['id']:
                    qemu = row
        if len(batch) < 100:
            break
    else:
        raise ValueError('Status inventory exceeds limit')
    qemu_state = 'not run / awaiting workflow approval'
    if qemu:
        qemu_state = 'unverified status publisher'
        run = re.fullmatch(r'https://github.com/lab-401/icopy-x/actions/runs/([0-9]+)',
                           qemu.get('target_url') or '')
        if qemu.get('creator', {}).get('id') == 41898282 and run:
            qemu_state = qemu['state']
            if qemu_state == 'success':
                evidence = api('GET', route('/actions/runs/' + run[1]))
                qemu_state = ('pass' if evidence.get('conclusion') == 'success' and
                    evidence.get('path') == '.github/workflows/qemu-critical.yml' and
                    evidence.get('event') in ('workflow_run', 'workflow_dispatch') else 'unverified QEMU run')
    names = set(REQUIRED)
    # Surface other actual failures too; skip irrelevant skipped workflow jobs.
    names.update(name for name, row in latest.items() if name != 'Astra readiness' and
                 row.get('conclusion') in ('failure', 'cancelled', 'timed_out', 'action_required'))
    answer = []
    for name in sorted(names):
        row = latest.get(name)
        status = ('not run / awaiting workflow approval' if row is None else
                  'pending' if row.get('status') != 'completed' else
                  'pass' if row.get('conclusion') == 'success' else row.get('conclusion') or 'unknown')
        if name == 'QEMU critical flows':
            status = qemu_state
        answer.append(dict(name=name, state=status, url=(qemu.get('target_url') if qemu else None)
                           if name == 'QEMU critical flows' else row.get('html_url') if row else None))
    return answer


def publish(api, route, state, comment_id):
    """A visible check complements the checklist; it never grants merge rights."""
    current = state['current']
    key = 'astra-dashboard-v2:' + str(current['pr']) + ':' + current['base'] + ':' + current['head']
    decision, reason, _ = dashboard.readiness(state)
    conclusion = 'success' if decision == 'GO' else 'action_required'
    title = decision + ' — ' + reason
    summary = ('[Open the contributor checklist](https://github.com/lab-401/icopy-x/pull/' +
               str(current['pr']) + '#issuecomment-' + str(comment_id) + '). '
               'GO means ready for maintainer review, not automatic merge approval.')
    checks = api('GET', route('/commits/' + current['head'] + '/check-runs?') +
                 urlencode(dict(check_name='Astra readiness', per_page=100, filter='latest')))['check_runs']
    owned = [row for row in checks if row.get('app', {}).get('id') == APP_ID and
             row.get('external_id') == key and row.get('head_sha') == current['head']]
    old = max(owned, key=lambda row: row['id']) if owned else None
    if old and old.get('conclusion') == conclusion and old.get('output', {}).get('title') == title:
        return
    data = dict(name='Astra readiness', status='completed', conclusion=conclusion,
                output=dict(title=title, summary=summary))
    if old:
        api('PATCH', route('/check-runs/' + str(old['id'])), data)
    else:
        data.update(head_sha=current['head'], external_id=key)
        api('POST', route('/check-runs'), data)
