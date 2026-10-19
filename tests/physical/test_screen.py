import pytest

from tools.physical.screen import screen_matches


@pytest.mark.parametrize('observed,expected', [
    ('ChkDIC...0/32keys', True), ('ChkDIC...12/32keys', True),
    ('ChkDIC...12/64keys', False), ('ChkDIC...-1/32keys', False),
    ('ChkDIC...1.2/32keys', False), ('ChkDIC...１２/32keys', False),
    ('ChkDIC...12345678901/32keys', False), ('ChkDIC...1/32keys\n', False),
    ('Read successful', False), ('ChkDICxxx1/32keys', False),
])
def test_progress_template_changes_only_enrolled_numeric_field(observed, expected):
    assert screen_matches([{'template': 'ChkDIC...{n}/32keys'}], [observed]) is expected


@pytest.mark.parametrize('guard', [[], '', [''], [{}], [{'template': '{n}'}],
    [{'template': 'Read'}], [{'template': 123}], [{'regex': '.*'}], [None]])
def test_invalid_guard_is_not_an_unconditional_match(guard):
    with pytest.raises(ValueError):
        screen_matches(guard, ['Read'])


def test_literal_guard_is_still_exact_and_all_clauses_are_required():
    assert not screen_matches(['ChkDIC...0/32keys'], ['ChkDIC...1/32keys'])
    guard = ['Read', {'template': 'ChkDIC...{n}/32keys'}]
    assert not screen_matches(guard, ['ChkDIC...1/32keys'])
    assert screen_matches(guard, ['Read', 'ChkDIC...1/32keys'])
