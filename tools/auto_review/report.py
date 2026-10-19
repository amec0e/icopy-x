"""Render bounded advisory evidence; never call the model or publish a PR review."""
import argparse
import html
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

from .contract import validate
from .snapshots import digest

MAX_JSON_BYTES = 16_000_000
MAX_SUMMARY_FINDINGS = 30


def literal(value):
    # Model/source text stays literal, including HTML, Markdown and mentions.
    return html.escape(str(value)).replace('@', '&#64;')


def block(value):
    return '<pre>' + literal(value) + '</pre>\n'


def accounting(report):
    """Count each generation once, including terminal cleanup accounting.

    Missing accounting is unknown, never silently treated as zero usage.
    Prefer terminal records where a deadline prevented accepting a response.
    """
    records = {}
    for call in report.get('calls', []):
        identity = call.get('id') or call.get('client_request_id')
        if identity:
            records[identity] = call
    unknown = 0
    for attempt in report.get('attempts', []):
        terminal = attempt.get('terminal_response')
        identity = attempt.get('response_id') or attempt.get('client_request_id')
        if terminal and identity:
            records[identity] = terminal
        if attempt.get('outcome') != 'not_sent' and identity not in records:
            unknown += 1
    totals = dict(input_tokens=0, output_tokens=0, reasoning_tokens=0,
                  cached_tokens=0, cache_write_tokens=0)
    for record in records.values():
        usage = record.get('usage', {})
        if any(type(usage.get(k)) is not int for k in ('input_tokens', 'output_tokens')):
            unknown += 1
        for key in ('input_tokens', 'output_tokens'):
            if type(usage.get(key)) is int:
                totals[key] += usage[key]
        for group, keys in [('input_tokens_details', ('cached_tokens', 'cache_write_tokens')),
                            ('output_tokens_details', ('reasoning_tokens',))]:
            for key in keys:
                value = usage.get(group, {}).get(key)
                if type(value) is int:
                    totals[key] += value
    return dict(generations_with_metadata=len(records), unknown_usage_generations=unknown,
                reported_tokens=totals)


def render(report, bundle=None):
    status = report.get('status', 'INCOMPLETE')
    if status not in ('ADVISORY_COMPLETE', 'PREPARED', 'INCOMPLETE'):
        status = 'INCOMPLETE'
    proposal = report.get('review')
    if status == 'ADVISORY_COMPLETE' and (report.get('error') or not isinstance(proposal, dict)
                                         or proposal.get('completion') != 'complete'):
        status = 'INCOMPLETE'
    lines = ['# Astra advisory result\n', '**' + status + '** — advisory only; not merge approval.\n']
    if proposal is not None:
        try:
            if bundle is None or report.get('snapshot_sha256') != digest(bundle):
                raise ValueError('Snapshot mismatch')
            if report.get('base') != bundle['base'] or report.get('head') != bundle['head']:
                raise ValueError('Commit mismatch')
            validate(proposal, bundle)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError):
            proposal = None
            lines[1] = '**INCOMPLETE** — saved review failed source validation; no findings displayed.\n'
    for field in ('base', 'head', 'snapshot_sha256', 'policy_sha256'):
        value = report.get(field)
        if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value):
            lines.append('- ' + field + ': `' + value + '`')
    lines.append('\n## Execution and accounting\n')
    stats = accounting(report)
    lines.append(block(json.dumps(stats, indent=2)))
    lines.append('Token totals include only returned accounting; detail fields may be absent. '
                 'Polling is not a new generation. This is not a billing invoice.\n')
    attempts = report.get('attempts', [])
    for index, attempt in enumerate(attempts, 1):
        details = {name: attempt[name] for name in ('outcome', 'response_status', 'elapsed_seconds',
                   'poll_count', 'cleanup') if name in attempt}
        lines.append('Pass ' + str(index) + ':\n' + block(json.dumps(details, sort_keys=True)))
    failure = {key: report[key] for key in ('error', 'failure_stage', 'validation_code', 'http_status')
               if key in report}
    if failure:
        lines.append('Execution/validation failure:\n' + block(json.dumps(failure, sort_keys=True)))
    if proposal is None:
        lines.append('No source-validated advisory is available. Inspect report.json and snapshot.json '
                     'in the run artifact; do not infer that the change is safe.\n')
    else:
        if status != 'ADVISORY_COMPLETE':
            lines.append('**Partial result.** Findings below are from the last source-validated '
                         'proposal. Coverage gaps or a later failed pass remain unresolved.\n')
        lines.extend(['## Review\n', block(proposal['summary'])])
        lines.append('Model coverage declaration: **' + proposal['completion'] + '**.\n')
        lines.append('## Findings\n')
        if not proposal['findings']:
            lines.append('No findings were returned; this is not a correctness guarantee.\n')
        for finding in proposal['findings'][:MAX_SUMMARY_FINDINGS]:
            revision = report[finding['side']]
            if not re.fullmatch(r'[0-9a-f]{40}', revision):
                raise ValueError('Invalid source revision')
            url = ('https://github.com/lab-401/icopy-x/blob/' + revision + '/' +
                   quote(finding['path'], safe='/') + '#L' + str(finding['line']))
            lines.append('### ' + finding['severity'] + ' — <a href="' + html.escape(url, quote=True) +
                         '">' + literal(finding['path']) + ':' + str(finding['line']) + '</a>\n')
            for label, key in [('Trigger', 'trigger'), ('Impact', 'impact'),
                               ('Requested change', 'requested_change'), ('Source', 'quote')]:
                lines.append('**' + label + '**\n' + block(finding[key]))
            lines.append('Evidence classification: ' + finding['validation'] + '\n')
        if len(proposal['findings']) > MAX_SUMMARY_FINDINGS:
            lines.append('Additional findings are in report.json; this display is capped at 30.\n')
        lines.append('## Scope\n')
        for row in proposal['files']:
            lines.append(block(row['path'] + ' — ' + row['scope'] +
                               ('; reviewed' if row['reviewed'] else '; NOT reviewed') + '\n' + row['reason']))
        for title, key in [('Required device checks', 'required_device_checks'), ('Limitations', 'limitations')]:
            lines.append('## ' + title + '\n')
            lines.extend(block(value) for value in proposal[key])
            if not proposal[key]:
                lines.append('None listed by the model.\n')
    if report.get('gaps'):
        lines.append('## Collector gaps\n' + block(json.dumps(report['gaps'], indent=2)))
    return '\n'.join(lines)


def read_json(path):
    with path.open('rb') as source:
        raw = source.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('Evidence file exceeds rendering limit')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Expected evidence object')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path('review-evidence'))
    args = parser.parse_args(argv)
    try:
        report = read_json(args.directory / 'report.json')
        snapshot = args.directory / 'snapshot.json'
        result = render(report, read_json(snapshot) if snapshot.exists() else None)
    except (ValueError, OSError, KeyError, TypeError, AttributeError, IndexError):
        result = ('# Astra advisory result\n\n**INCOMPLETE** — readable evidence was unavailable. '
                  'Inspect the job logs. No review or merge approval is implied.\n')
    args.directory.mkdir(parents=True, exist_ok=True)
    (args.directory / 'review.md').write_text(result, encoding='utf-8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        # GitHub limits each step summary to 1 MiB; the full file stays in artifacts.
        summary = result if len(result.encode('utf-8')) <= 900_000 else (
            '# Astra advisory result\n\nReport exceeds the summary display limit. '
            'Download review.md and report.json from the run artifact.\n')
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as target:
            target.write(summary)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
