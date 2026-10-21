"""Strict output shape and source-bound evidence validation."""
from copy import deepcopy
from .errors import ValidationError


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


TEXT = dict(type='string')
TEXTS = dict(type='array', items=TEXT)
LEGACY_SCHEMA = obj({
    'summary': TEXT,
    'completion': dict(type='string', enum=['complete', 'incomplete']),
    'files': dict(type='array', items=obj({
        'path': TEXT, 'scope': dict(type='string', enum=[
            'purpose', 'supporting', 'core_dependency', 'independent', 'artifact']),
        'reviewed': dict(type='boolean'), 'reason': TEXT})),
    'findings': dict(type='array', items=obj({
        'severity': dict(type='string', enum=['P0', 'P1', 'P2', 'P3']),
        'path': TEXT, 'side': dict(type='string', enum=['base', 'head']),
        'line': dict(type='integer'), 'quote': TEXT,
        'trigger': TEXT, 'impact': TEXT, 'requested_change': TEXT,
        'validation': dict(type='string', enum=['source_confirmed', 'hardware_pending'])})),
    'required_device_checks': TEXTS, 'limitations': TEXTS,
})

CITATION = obj({'path': TEXT, 'side': dict(type='string', enum=['base', 'head']),
                'line': dict(type='integer'), 'quote': TEXT})
SCHEMA = deepcopy(LEGACY_SCHEMA)
SCHEMA['properties'].update({
    'assessments': dict(type='array', items=obj({
        'area': dict(type='string', enum=['scope', 'compatibility', 'core_stability', 'testing']),
        'status': dict(type='string', enum=['pass', 'needs_attention', 'not_applicable']),
        'reason': TEXT, 'evidence': dict(type='array', items=CITATION)})),
    'follow_up': dict(type='array', items=obj({
        'id': TEXT, 'status': dict(type='string', enum=['open', 'resolved', 'not_assessed']),
        'finding_index': dict(type='integer'), 'reason': TEXT,
        'evidence': dict(type='array', items=CITATION)})),
})
SCHEMA['required'] = list(SCHEMA['properties'])


def shape(value, schema):
    kind = schema['type']
    expected = {'object': dict, 'array': list, 'string': str, 'integer': int, 'boolean': bool}[kind]
    if type(value) is not expected:
        raise ValidationError('field_type')
    if 'enum' in schema and value not in schema['enum']:
        raise ValidationError('field_enum')
    if kind == 'object':
        if set(value) != set(schema['properties']):
            raise ValidationError('field_set')
        for key, child in value.items():
            shape(child, schema['properties'][key])
    elif kind == 'array':
        if len(value) > 500:
            raise ValidationError('array_limit')
        for child in value:
            shape(child, schema['items'])
    elif kind == 'string' and (not value.strip() or len(value) > 8000):
        raise ValidationError('text_limit')


def validate(review, bundle):
    # Old saved artifacts remain readable; new API requests use only SCHEMA.
    modern = 'assessments' in review or 'follow_up' in review
    shape(review, SCHEMA if modern else LEGACY_SCHEMA)
    inventory = {row['path']: row for row in bundle['files']}
    required = {path for path, row in inventory.items() if row['changed']}
    actual = [row['path'] for row in review['files']]
    if len(actual) != len(set(actual)) or set(actual) != required:
        raise ValidationError('file_coverage')
    if review['completion'] == 'complete' and (
            bundle['gaps'] or not all(row['reviewed'] for row in review['files'])):
        raise ValidationError('incomplete_coverage')
    citations = list(review['findings'])
    if modern:
        areas = [row['area'] for row in review['assessments']]
        if sorted(areas) != ['compatibility', 'core_stability', 'scope', 'testing']:
            raise ValidationError('assessment_coverage')
        prior = {row['id']: row for row in bundle.get('previous_items', [])}
        follow = review['follow_up']
        if len(follow) != len(prior) or {row['id'] for row in follow} != set(prior):
            raise ValidationError('follow_up_coverage')
        mapped = set()
        for row in follow:
            index = row['finding_index']
            if row['status'] == 'open':
                if not 0 <= index < len(review['findings']) or index in mapped:
                    raise ValidationError('follow_up_finding')
                mapped.add(index)
            elif index != -1:
                raise ValidationError('follow_up_finding')
            if row['status'] == 'resolved' and not row['evidence']:
                raise ValidationError('resolution_evidence')
            if row['status'] == 'not_assessed' and review['completion'] == 'complete':
                raise ValidationError('incomplete_follow_up')
        for row in review['assessments'] + follow:
            if row.get('status') == 'pass' and not row['evidence']:
                raise ValidationError('assessment_evidence')
            citations.extend(row['evidence'])
        for row in follow:
            if row['status'] == 'resolved':
                # A deleted file can be supported by its old quote. Otherwise
                # resolution needs current source, not a quote of the old bug.
                if not any(c['side'] == 'head' or
                           inventory.get(c['path'], {}).get('head') is None
                           for c in row['evidence']):
                    raise ValidationError('resolution_evidence')
    elif bundle.get('previous_items'):
        raise ValidationError('follow_up_coverage')
    for finding in citations:
        source = inventory.get(finding['path'], {}).get(finding['side'])
        if not source or 'text' not in source:
            raise ValidationError('source_unavailable')
        lines = source['text'].splitlines()
        line = finding['line']
        if not 1 <= line <= len(lines) or finding['quote'].strip() != lines[line - 1].strip():
            raise ValidationError('source_citation')
    return review
