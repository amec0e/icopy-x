"""Fixed GitHub-hosted entry point; all inputs are data, never shell text."""
import json
import os
import re
import subprocess
import sys

from .cli import main as cli
from .snapshots import safe_path


def inputs(environ):
    revisions = [environ.get('REVIEW_BASE', ''), environ.get('REVIEW_HEAD', '')]
    if any(not re.fullmatch(r'[0-9a-f]{40}', value) for value in revisions):
        raise ValueError('Full lowercase commit SHAs are required')
    raw = environ.get('REVIEW_CONTEXT', '[]')
    if len(raw) > 16000:
        raise ValueError('Context input exceeds limit')
    context = json.loads(raw)
    if not isinstance(context, list) or len(context) > 100 or any(not isinstance(p, str) for p in context):
        raise ValueError('Context must be a bounded JSON array of paths')
    return revisions, [safe_path(p) for p in context]


def main(operation):
    if os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('Hosted pilot runs only from trusted main')
    revisions, context = inputs(os.environ)
    if operation == 'fetch':
        # Public repository, fixed origin, no auth/header/URL supplied by a PR.
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_') and k != 'OPENAI_API_KEY'}
        env.update(GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1')
        subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'fetch', '--no-tags', '--no-recurse-submodules',
                        'https://github.com/lab-401/icopy-x.git', *revisions],
                       env=env, check=True, timeout=120)
        return 0
    if operation not in ('prepare', 'review'):
        raise ValueError('Unknown hosted operation')
    args = [operation, '--base', revisions[0], '--head', revisions[1], '--output', 'review-evidence']
    args.extend(['--purpose', os.environ.get('REVIEW_PURPOSE', '')])
    for path in context:
        args.extend(['--context', path])
    return cli(args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
