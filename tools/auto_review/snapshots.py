"""Collect immutable Git blobs without checking out or executing a candidate."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def git(repo, *args, allow_no_match=False, max_output=32 * 1024 * 1024):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('GIT_') and key != 'OPENAI_API_KEY'}
    env.update(GIT_NO_REPLACE_OBJECTS='1', GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    limit = max_output
    with tempfile.TemporaryFile() as output:
        child = subprocess.Popen(['git', '-C', str(repo), '--no-pager', *args],
                                 stdout=output, stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL, env=env)
        deadline = time.monotonic() + 30
        try:
            while child.poll() is None:
                if time.monotonic() > deadline or os.fstat(output.fileno()).st_size > limit:
                    raise ValueError('Git snapshot time/output limit exceeded')
                time.sleep(.01)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
        if child.returncode and not (allow_no_match and child.returncode == 1
                                    and os.fstat(output.fileno()).st_size == 0):
            raise ValueError('Git snapshot operation failed: ' + args[0])
        if os.fstat(output.fileno()).st_size > limit:
            raise ValueError('Git result exceeds collector limit')
        output.seek(0)
        return output.read(limit)


def commit(repo, revision):
    result = git(repo, 'rev-parse', '--verify', '--end-of-options', revision + '^{commit}').decode().strip()
    if not re.fullmatch('[0-9a-f]{40,64}', result):
        raise ValueError('Invalid commit identity')
    return result


def safe_path(path):
    parts = path.split('/')
    if (not path or any(p in ('', '.', '..', '.git') for p in parts)
            or '\\' in path or ':' in path or any(ord(c) < 32 for c in path)):
        raise ValueError('Unsupported repository path')
    return path


def tree(repo, revision):
    result = {}
    for entry in git(repo, 'ls-tree', '-rz', '--full-tree', revision).split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        result[safe_path(name.decode('utf-8'))] = dict(mode=mode, kind=kind, oid=oid)
    return result


def search_terms(terms):
    """Bound literal UTF-8 terms; they never become regexes, paths or options."""
    if (not isinstance(terms, (list, tuple)) or len(terms) > 16
            or any(not isinstance(term, str) or not term.strip() or len(term) > 128
                   or any(ord(c) < 32 or ord(c) == 127 for c in term) for term in terms)):
        raise ValueError('Search requires at most 16 nonempty single-line terms of 128 characters')
    return sorted(set(terms))


def references(repo, revision, inventory, terms):
    """Search raw Git blobs, not the worktree, attributes, filters or submodules.

    -a avoids attribute/binary heuristics hiding literal matches. Binary match
    metadata is retained without passing raw bytes to the model. Even a readable
    hit is only a reference hint. Results use Git's LF-based line numbering.
    """
    args = ['grep', '-a', '-n', '-z', '-F', '--full-name', '--no-textconv',
            '--no-recurse-submodules', '--no-color', '--no-column', '--no-heading', '--no-break']
    for term in terms:
        args.extend(['-e', term])
    raw = git(repo, *args, revision, '--', allow_no_match=True, max_output=512_000)
    lines = raw.split(b'\n')
    if lines[-1] != b'' or len(lines) - 1 > 250:
        raise ValueError('Reference search result limit/format')
    matches = []
    for record in lines[:-1]:
        location, number, content = record.split(b'\0', 2)
        if not location.startswith((revision + ':').encode('ascii')) or not number.isdigit():
            raise ValueError('Invalid reference search location')
        path = safe_path(location[len(revision) + 1:].decode('utf-8'))
        item = inventory.get(path)
        if not item or item['kind'] != 'blob' or item['mode'] not in ('100644', '100755'):
            raise ValueError('Unsupported reference search object')
        found = [term for term in terms if term.encode('utf-8') in content]
        if not found or int(number) < 1:
            raise ValueError('Invalid reference search match')
        match = dict(path=path, oid=item['oid'], line=int(number), terms=found)
        try:
            text = content.decode('utf-8')
            if '\0' in text:
                raise UnicodeError()
            match['text'] = text
        except UnicodeError:
            match['text_unavailable'] = 'binary/non-UTF-8 match line; inspect separately if relevant'
        matches.append(match)
    return dict(revision=revision, status='complete', matches=matches)


def collect(repo, base, head, context=(), max_bytes=2_000_000, max_file_bytes=1_000_000, searches=()):
    if not 1024 <= max_bytes <= 8_000_000 or not 1024 <= max_file_bytes <= 2_000_000:
        raise ValueError('Snapshot limits outside allowed range')
    terms = search_terms(searches)
    base, head = commit(repo, base), commit(repo, head)
    merge_base = git(repo, 'merge-base', base, head).decode().strip()
    if merge_base != base:
        raise ValueError('Update the candidate to include base before review')
    before, after = tree(repo, base), tree(repo, head)
    changed = sorted(path for path in before.keys() | after.keys()
                     if before.get(path) != after.get(path))
    if not changed:
        raise ValueError('No changed files')
    if len(changed) > 500:
        raise ValueError('Changed-file inventory exceeds pilot limit; split the review')
    context = sorted(set(safe_path(path) for path in context) - set(changed))
    if len(context) > 100 or any(path not in before and path not in after for path in context):
        raise ValueError('Invalid context-file inventory')
    bundle = dict(base=base, head=head, merge_base=merge_base, files=[], gaps=[],
                  limits=dict(max_bytes=max_bytes, max_file_bytes=max_file_bytes))
    used = 0
    for path in changed + context:
        row = dict(path=path, changed=path in changed, base=None, head=None)
        for side, inventory in (('base', before), ('head', after)):
            item = inventory.get(path)
            if item is None:
                continue
            blob = dict(item)
            row[side] = blob
            if item['mode'] not in ('100644', '100755') or item['kind'] != 'blob':
                bundle['gaps'].append(dict(path=path, side=side, reason='symlink/submodule/unsupported mode'))
                continue
            size = int(git(repo, 'cat-file', '-s', item['oid']))
            blob['bytes'] = size
            if size > max_file_bytes or used + size > max_bytes:
                bundle['gaps'].append(dict(path=path, side=side, reason='content budget exceeded'))
                continue
            raw = git(repo, 'cat-file', 'blob', item['oid'])
            used += len(raw)
            try:
                text = raw.decode('utf-8')
                if '\0' in text:
                    raise UnicodeError()
            except UnicodeError:
                bundle['gaps'].append(dict(path=path, side=side, reason='binary/non-UTF-8 blob'))
                continue
            if text.startswith(('version https://git-lfs.github.com/spec/v1\n',
                                'version https://hawser.github.com/spec/v1\n')):
                bundle['gaps'].append(dict(path=path, side=side, reason='Git LFS payload unavailable'))
                continue
            blob.update(text=text, sha256=hashlib.sha256(raw).hexdigest())
        bundle['files'].append(row)
    if terms:
        bundle['reference_search'] = dict(terms=terms, scope='all tracked regular blobs; literal UTF-8 bytes; '
            'no submodules, symlinks, filters or worktree; LF-based line numbers',
            limits=dict(max_lines_per_revision=250, max_output_bytes_per_revision=512_000))
        for side, revision, inventory in (('base', base, before), ('head', head, after)):
            try:
                bundle['reference_search'][side] = references(repo, revision, inventory, terms)
            except (ValueError, OSError, TimeoutError):
                bundle['reference_search'][side] = dict(revision=revision, status='incomplete')
                bundle['gaps'].append(dict(path='', side=side, reason='reference search failed or exceeded limits'))
    # JSON escaping and metadata also count. Never silently truncate content.
    if len(canonical(bundle)) > max_bytes:
        bundle['gaps'].append(dict(path='', side='', reason='serialized bundle exceeds input budget'))
    return bundle
