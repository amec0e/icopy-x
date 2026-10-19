"""Prepare immutable review evidence or run an advisory Astra review."""
import argparse
import json
import os
from pathlib import Path
import sys

from .reviewer import DEFAULT_OUTPUT_TOKENS, DEFAULT_REVIEW_BUDGET_SECONDS, review
from .profiles import PROFILES, select
from .snapshots import canonical, collect, digest


def save_report(output, report):
    """Replace our own report atomically so interruption leaves a readable checkpoint."""
    temporary = output / 'report.json.tmp'
    temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
    temporary.replace(output / 'report.json')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'review'))
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--context', action='append', default=[])
    parser.add_argument('--profile', choices=tuple(PROFILES), default='manual')
    parser.add_argument('--search', action='append', default=[], help='Literal reference term, not a regex')
    parser.add_argument('--purpose', default='', help='Stated PR outcome; treated as untrusted context')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-bytes', type=int, default=2_000_000)
    parser.add_argument('--max-file-bytes', type=int, default=1_000_000)
    parser.add_argument('--max-output-tokens', type=int, default=DEFAULT_OUTPUT_TOKENS)
    parser.add_argument('--timeout', type=int, default=120, help='Inactivity timeout for each HTTP operation')
    parser.add_argument('--review-budget-seconds', type=int, default=DEFAULT_REVIEW_BUDGET_SECONDS,
                        help='Scheduling budget across all three background generations')
    args = parser.parse_args(argv)
    # Refuse overwriting evidence; never write to paths selected by the model.
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(status='INCOMPLETE', advisory=True)
    code = 2
    try:
        if len(args.purpose) > 8000 or (args.operation == 'review' and not args.purpose.strip()):
            raise ValueError('Review requires a bounded statement of the intended PR outcome')
        context, searches, selection = select(args.profile, args.context, args.search)
        bundle = collect(args.repo, args.base, args.head, context, args.max_bytes, args.max_file_bytes,
                         searches=searches)
        if selection is not None:
            bundle['context_selection'] = selection
        bundle['stated_purpose'] = args.purpose
        budget_gap = 'serialized bundle exceeds input budget'
        if len(canonical(bundle)) > args.max_bytes and not any(g['reason'] == budget_gap for g in bundle['gaps']):
            bundle['gaps'].append(dict(path='', side='', reason=budget_gap))
        (args.output / 'snapshot.json').write_text(json.dumps(bundle, indent=2), encoding='utf-8')
        report.update(base=bundle['base'], head=bundle['head'], snapshot_sha256=digest(bundle), gaps=bundle['gaps'])
        if args.operation == 'prepare':
            report['status'] = 'PREPARED' if not bundle['gaps'] else 'INCOMPLETE'
            code = 0 if not bundle['gaps'] else 2
        else:
            policy = Path(__file__).with_name('policy.md').read_text(encoding='utf-8')
            report = review(bundle, policy, os.environ.get('OPENAI_API_KEY'),
                            max_output_tokens=args.max_output_tokens, timeout=args.timeout,
                            review_budget_seconds=args.review_budget_seconds,
                            checkpoint=lambda value: save_report(args.output, value))
            code = 0 if report['status'] == 'ADVISORY_COMPLETE' else 2
    except (ValueError, OSError, TimeoutError) as error:
        # Never persist API bodies, credentials or arbitrary exception reprs.
        report['error'] = type(error).__name__
    save_report(args.output, report)
    print(json.dumps(dict(status=report['status'], report=str(args.output / 'report.json'))))
    return code


if __name__ == '__main__':
    sys.exit(main())
