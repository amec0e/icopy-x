"""Public diagnostics are fixed codes, never API bodies or exception text."""

MESSAGES = {
    'field_type': 'Invalid review field type',
    'field_enum': 'Invalid review enum',
    'field_set': 'Missing or extra review fields',
    'array_limit': 'Review array exceeds limit',
    'text_limit': 'Empty or oversized review text',
    'file_coverage': 'Review coverage does not match changed-file inventory',
    'incomplete_coverage': 'Incomplete coverage cannot be reported complete',
    'source_unavailable': 'Finding references unavailable source',
    'source_citation': 'Finding line/quote does not match immutable source',
    'response_shape': 'Invalid API response',
    'response_incomplete': 'API response is incomplete or failed',
    'response_model': 'Unexpected returned model; no model substitution permitted',
    'response_output': 'Invalid API output',
    'response_item': 'Unexpected response item',
    'response_content': 'Invalid API message content',
    'response_refusal': 'Refusal or unsupported response content',
    'response_count': 'Expected one structured review',
    'review_json': 'Structured review is not valid JSON',
    'request_budget': 'Serialized model request exceeds input budget',
}


class ValidationError(ValueError):
    def __init__(self, code):
        super().__init__(MESSAGES[code])
        self.code = code
