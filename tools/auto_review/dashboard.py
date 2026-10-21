"""One human-facing checklist; no model calls, merges, or candidate execution."""
from copy import deepcopy
import html
import json
import re
from urllib.parse import quote

from . import report

PREFIX = '<!-- icopy-astra-dashboard-v2 '
END = ' -->'
MAX_ITEMS = 50


def text(value):
    """Literal prose, without allowing model HTML, links, mentions or checkboxes."""
    value = ''.join('&#' + str(ord(char)) + ';' if char in '\\`*_{}[]()#+-!|~@' else
                    html.escape(char) for char in str(value))
    return ' '.join(value.split())


def source(finding, base, head):
    revision = head if finding['side'] == 'head' else base
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Invalid source revision')
    path = finding['path']
    url = ('https://github.com/lab-401/icopy-x/blob/' + revision + '/' +
           quote(path, safe='/') + '#L' + str(finding['line']))
    return '<a href="' + html.escape(url, quote=True) + '">' + text(path) + ':' + str(finding['line']) + '</a>'


def ci_label(row):
    url = row.get('url') or ''
    if re.fullmatch(r'https://github.com/lab-401/icopy-x/actions/runs/[0-9]+(?:/job/[0-9]+)?', url):
        return '<a href="' + url + '">' + text(row['name']) + '</a>'
    return text(row['name'])


def load(comment, bot_id):
    if comment.get('user', {}).get('id') != bot_id:
        return None
    line = comment.get('body', '').split('\n', 1)[0]
    if not line.startswith(PREFIX) or not line.endswith(END):
        return None
    value = json.loads(line[len(PREFIX):-len(END)])
    if not isinstance(value, dict) or value.get('version') != 2:
        raise ValueError('Invalid dashboard state')
    if not isinstance(value.get('records'), list) or len(value['records']) > 120:
        raise ValueError('Dashboard ledger limit; archive before reviewing again')
    return value


def blank():
    return dict(version=2, records=[], review=None, items=[], next_id=1, ci=[])


def remember(state, record):
    """Retain reservations when the same visible comment moves to another head."""
    state = deepcopy(state)
    records = state['records']
    key = (record['base'], record['head'], record['run_id'])
    records[:] = [r for r in records if (r['base'], r['head'], r['run_id']) != key]
    # Superseded unpaid notices have no cost/dedup value. Paid records are never
    # discarded, including old/failed runs and reservations with unknown usage.
    records[:] = [r for r in records if r.get('reserved_at') or
                 (r['base'], r['head']) != (record['base'], record['head'])]
    records.append(record)
    if len(records) > 120:
        raise ValueError('Dashboard ledger limit; no reservation made')
    state['current'] = record
    return state


def accept(state, saved, bundle, run_id):
    """Persist only source-validated findings and explicit, cited resolutions."""
    state = deepcopy(state)
    status, proposal, error = report.validated(saved, bundle)
    if proposal is None:
        state['notice'] = error or 'No source-validated advisory is available.'
        return state
    old = {item['id']: item for item in state['items']}
    linked = {}
    for follow in proposal.get('follow_up', []):
        if follow['id'] not in old:
            continue
        item = old[follow['id']]
        if follow['status'] == 'open':
            linked[follow['finding_index']] = follow['id']
        elif follow['status'] == 'resolved' and not saved.get('error'):
            # An explicitly cited correction can be established even when the
            # final source audit names an unrelated coverage gap. A later failed
            # pass cannot promote an earlier proposal into a resolved action.
            item.update(state='resolved', resolution=follow['reason'],
                        resolved_head=saved['head'], evidence=follow['evidence'])
        else:
            item['state'] = 'unassessed'
    # Missing actions and interrupted reviews cannot silently close old tasks.
    for item in old.values():
        if item['state'] != 'resolved':
            item['state'] = 'unassessed'
    for index, finding in enumerate(proposal['findings'][:MAX_ITEMS]):
        item_id = linked.get(index)
        if item_id is None:
            # Exact source identity allows safe migration of a legacy result.
            item_id = next((key for key, item in old.items() if
                item['finding'] == finding and item['head'] == saved['head']), None)
        if item_id is None:
            item_id = 'A' + str(state['next_id']).zfill(3)
            state['next_id'] += 1
        old[item_id] = dict(id=item_id, state='open', finding=finding,
                            base=saved['base'], head=saved['head'])
    state['items'] = list(old.values())
    state['review'] = dict(status=status, base=saved['base'], head=saved['head'],
        integration_base=bundle.get('integration_base', saved['base']), run_id=run_id,
        summary=proposal['summary'], completion=proposal['completion'],
        assessments=proposal.get('assessments', []), files=proposal['files'],
        required_device_checks=proposal['required_device_checks'], limitations=proposal['limitations'],
        snapshot_sha256=saved['snapshot_sha256'], policy_sha256=saved.get('policy_sha256'),
        accounting=report.accounting(saved), overflow=len(proposal['findings']) > MAX_ITEMS)
    state.pop('notice', None)
    return state


def pending_items(state):
    return [dict(id=item['id'], finding=item['finding'], previous_head=item['head'])
            for item in state['items'] if item['state'] != 'resolved']


def readiness(state):
    current, review = state['current'], state.get('review')
    fresh = bool(review and review['head'] == current['head'] and
                 review.get('integration_base', review['base']) == current['base'])
    active = [i for i in state['items'] if i['state'] != 'resolved']
    blockers = [i for i in active if i['finding']['severity'] != 'P3']
    ci_ok = bool(state.get('ci')) and all(row['state'] == 'pass' for row in state['ci'])
    complete = fresh and review['status'] == 'ADVISORY_COMPLETE' and not review.get('overflow')
    attention = (not complete or not review.get('assessments') or
                 any(a['status'] == 'needs_attention' for a in review.get('assessments', [])) or
                 bool(review.get('required_device_checks')) or
                 any(i['state'] == 'unassessed' for i in active))
    go = (complete and not blockers and not attention and ci_ok and
          current['state'] == 'ADVISORY_COMPLETE' and review['base'] == current['base'] and
          not state.get('integration_pending'))
    if go:
        return 'GO', 'Ready for maintainer review', fresh
    if current['state'] in ('DEFERRED', 'RESERVED', 'STALE') or not fresh:
        return 'NO-GO', 'Current revision awaits review', fresh
    if blockers:
        return 'NO-GO', 'Contributor changes required', fresh
    return 'NO-GO', 'Assessment or validation required', fresh


def render(state):
    current, review = state['current'], state.get('review')
    decision, reason, fresh = readiness(state)
    icon = '✅' if decision == 'GO' else '🛑'
    lines = ['## ' + icon + ' Astra: ' + decision + ' — ' + reason, '',
        'Latest commit: `' + current['head'][:7] + '`. This checklist updates in place after each review.', '',
        '**Contributor:** address the unchecked changes below and push your fixes. '
        '**Maintainer:** GO means the PR is ready for your final review; Astra does not merge it.', '']
    if state.get('notice'):
        lines += [text(state['notice']), '']
    if review:
        if not fresh:
            lines += ['**Previous findings need rechecking:** the last source review covered `' +
                      review['head'][:7] + '`. They are not confirmed defects in the latest commit.', '']
        lines += [text(review['summary']), '']
    lines += ['### Blocking issues — changes required', '']
    blocking = [i for i in state['items'] if i['state'] != 'resolved' and i['finding']['severity'] != 'P3']
    for item in blocking:
        f = item['finding']
        pending = ' · needs recheck' if not fresh or item['state'] == 'unassessed' else ''
        lines += ['- [ ] **' + item['id'] + ' · ' + f['severity'] + pending + '** — ' +
                  text(f['requested_change']) + ' (' + source(f, item['base'], item['head']) + ')',
                  '  - Why: ' + text(f['impact']), '  - Reproduce: ' + text(f['trigger'])]
    if not blocking:
        lines.append('No confirmed code blockers returned.' if fresh and review else
                     'No current source review yet; this is not a pass.')
    lines += ['', '### Passing checks and resolved issues', '']
    passed = [row for row in state.get('ci', []) if row['state'] == 'pass']
    lines += ['- [x] CI: ' + ci_label(row) for row in passed]
    resolved = [i for i in state['items'] if i['state'] == 'resolved']
    for item in resolved:
        lines.append('- [x] **' + item['id'] + '** — ' + text(item['resolution']) +
                     ' (reviewed at `' + item['resolved_head'][:7] + '`).')
    if fresh and review:
        lines += ['- [x] Source assessment: **' + text(row['area'].replace('_', ' ')) +
                  '** — ' + text(row['reason']) for row in review.get('assessments', [])
                  if row['status'] == 'pass']
    if not passed and not resolved and not (fresh and review and any(
            a['status'] == 'pass' for a in review.get('assessments', []))):
        lines.append('No verified passes available for the current revision.')
    lines += ['', '### Assessments — evidence or maintainer decision needed', '']
    if not fresh or not review or review['status'] != 'ADVISORY_COMPLETE':
        lines.append('- [ ] Finish the source review for the current commit; missing context is not approval.')
    if state.get('integration_pending') or (review and review['base'] != current['base']):
        lines.append('- [ ] Update the branch with current main and rerun CI before merging.')
    for row in state.get('ci', []):
        if row['state'] != 'pass':
            lines.append('- [ ] **CI: ' + ci_label(row) + '** — ' + text(row['state']) + '.')
    if review:
        for row in review.get('assessments', []):
            if row['status'] != 'pass':
                lines.append(('- ' if row['status'] == 'not_applicable' else '- [ ] ') +
                    '**' + text(row['area'].replace('_', ' ')) + '** — ' + text(row['reason']))
        for check in review['required_device_checks']:
            lines.append('- [ ] **Device evidence:** ' + text(check))
        if review['status'] != 'ADVISORY_COMPLETE':
            lines += ['- [ ] **Review limitation:** ' + text(gap) for gap in review['limitations']]
        if review.get('overflow'):
            lines.append('- [ ] More findings exist than fit here; inspect the full review artifact before proceeding.')
    lines += ['', '### Suggestions — optional improvements', '']
    suggestions = [i for i in state['items'] if i['state'] != 'resolved' and i['finding']['severity'] == 'P3']
    for item in suggestions:
        f = item['finding']
        lines.append('- [ ] **' + item['id'] + '** — ' + text(f['requested_change']) +
                     ' (' + source(f, item['base'], item['head']) + ')')
    if not suggestions:
        lines.append('None listed.')
    lines += ['', '<details>', '<summary>Review coverage, evidence and run details</summary>', '']
    if review:
        lines += ['Source review: **' + review['status'] + '**; model coverage: **' + review['completion'] + '**.', '',
                  'Base `' + review['base'] + '` · head `' + review['head'] + '`.', '']
        lines += ['- ' + text(row['path']) + ': ' + text(row['scope']) + ' — ' + text(row['reason'])
                  for row in review['files']]
        lines += ['', 'Limitations:', ''] + ['- ' + text(value) for value in review['limitations']]
        lines += ['', 'Accounting (reported usage, not an invoice):',
                  report.block(json.dumps(review['accounting'], indent=2))]
        lines += ['[Full source review and evidence](https://github.com/lab-401/icopy-x/actions/runs/' +
                  str(review['run_id']) + ').', '']
    lines += ['[Latest queue run](https://github.com/lab-401/icopy-x/actions/runs/' + str(current['run_id']) +
              '). Checkboxes are generated from review evidence, not manual completion marks.', '', '</details>']
    return '\n'.join(lines) + '\n'


def body(state):
    # JSON is hidden but durable. Escape '<' so even malicious source cannot
    # close the HTML comment. Never truncate reservations or silently lose work.
    def encode(value):
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).replace('<', '\\u003c')
        return PREFIX + encoded + END + '\n' + render(value)
    result = encode(state)
    if len(result.encode('utf-8')) > 60_000:
        state = deepcopy(state)
        def short(value):
            return value if len(value) <= 200 else value[:200] + '… [full detail in the review artifact]'
        for item in state['items']:
            for key in ('trigger', 'impact', 'requested_change', 'quote'):
                item['finding'][key] = short(item['finding'][key])
            if 'resolution' in item:
                item['resolution'] = short(item['resolution'])
            for citation in item.get('evidence', []):
                citation['quote'] = short(citation['quote'])
        review = state.get('review')
        if review:
            review['overflow'] = True
            review['summary'] = short(review['summary'])
            for row in review['files'] + review['assessments']:
                row['reason'] = short(row['reason'])
                for citation in row.get('evidence', []):
                    citation['quote'] = short(citation['quote'])
            for field in ('limitations', 'required_device_checks'):
                review[field] = [short(value) for value in review[field]]
        state['notice'] = 'Display shortened to fit GitHub. All action IDs and reservations remain; full details are in the review artifact.'
        result = encode(state)
    if len(result.encode('utf-8')) > 60_000:
        raise ValueError('Dashboard exceeds comment limit; retain prior ledger and inspect artifacts')
    return result
