"""Literal screen guards with explicitly enrolled numeric progress fields."""
import re


def screen_matches(expected, observed):
    if not isinstance(expected, list) or not 1 <= len(expected) <= 32:
        raise ValueError('Screen guard needs 1-32 expectations')
    patterns = []
    for item in expected:
        if isinstance(item, str) and item:
            patterns.append(re.escape(item))
        elif isinstance(item, dict) and set(item) == {'template'}:
            template = item['template']
            if (not isinstance(template, str) or '{n}' not in template or
                    len(template.replace('{n}', '').strip()) < 4):
                raise ValueError('Numeric screen template needs a literal context')
            # No user-supplied regex: only bounded ASCII decimal counters vary.
            patterns.append(re.escape(template).replace(re.escape('{n}'), '[0-9]{1,10}'))
        else:
            raise ValueError('Invalid screen expectation')
    return all(any(isinstance(text, str) and re.fullmatch(pattern, text) is not None
                   for text in observed) for pattern in patterns)


def require_screen(expected, observed):
    if not screen_matches(expected, observed):
        raise ValueError('Unexpected screen; no key sent')
