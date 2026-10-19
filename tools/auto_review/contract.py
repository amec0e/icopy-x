"""Strict output shape and source-bound evidence validation."""
from .errors import ValidationError


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


TEXT = dict(type='string')
TEXTS = dict(type='array', items=TEXT)
SCHEMA = obj({
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
    shape(review, SCHEMA)
    inventory = {row['path']: row for row in bundle['files']}
    required = {path for path, row in inventory.items() if row['changed']}
    actual = [row['path'] for row in review['files']]
    if len(actual) != len(set(actual)) or set(actual) != required:
        raise ValidationError('file_coverage')
    if review['completion'] == 'complete' and (
            bundle['gaps'] or not all(row['reviewed'] for row in review['files'])):
        raise ValidationError('incomplete_coverage')
    for finding in review['findings']:
        source = inventory.get(finding['path'], {}).get(finding['side'])
        if not source or 'text' not in source:
            raise ValidationError('source_unavailable')
        lines = source['text'].splitlines()
        line = finding['line']
        if not 1 <= line <= len(lines) or finding['quote'].strip() != lines[line - 1].strip():
            raise ValidationError('source_citation')
    return review
