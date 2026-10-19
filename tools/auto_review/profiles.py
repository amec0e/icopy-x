"""Opt-in context recipes from trusted code, never candidate configuration.

These are maintained starting points, not complete dependency graphs. Update
the version and evaluation record when a recipe changes. Missing paths fail
collection; do not silently weaken a recipe to fit an older source tree.
"""
from .snapshots import safe_path, search_terms

PROFILES = {
    'manual': {'paths': {}, 'searches': []},
    'ics-ui': {
        'paths': {
            'src/lib/activity_main.py': 'Accessory screens and general device About comparison.',
            'src/lib/actmain.py': 'Root-menu entry and activity lifecycle caller.',
            'src/lib/actbase.py': 'Activity lifecycle and UI dispatch contract.',
            'src/lib/widget.py': 'Menu and console rendering contracts.',
            'src/lib/ics_info_view.py': 'Actual accessory information-view implementation.',
            'src/middleware/ics_decoder.py': 'Accessory connection and operation contract.',
            'tests/ui/activities/test_ics_decoder.py': 'Screen and navigation regression expectations.',
            'tests/ui/activities/conftest.py': 'Activity test doubles and their limits.',
            'CONTRIBUTING.md': 'Existing unified-device contribution requirements.',
        },
        'searches': ['ICSInfoView', 'STATE_ABOUT', '_show_about'],
    },
    'ics-transport': {
        'paths': {
            'src/middleware/ics_decoder.py': 'Discovery, identity handshake and serial ownership.',
            'src/lib/activity_main.py': 'Foreground accessory operations and serial callers.',
            'src/lib/actmain.py': 'Background discovery lifecycle caller.',
            'src/main/main.py': 'Internal PM3 reservation and startup.',
            'src/middleware/pm3_flash.py': 'PM3 port and flash interaction contract.',
            'tests/ui/test_ics_transport.py': 'Deterministic transport and alias regressions.',
            'tests/ui/test_ics_presence.py': 'Discovery ownership and polling regressions.',
        },
        'searches': ['_is_pm3_port', 'detect_decoder(', 'DecoderPresence'],
    },
    'accessory-menu': {
        'paths': {
            'src/lib/actmain.py': 'Root-menu visibility, polling and lifecycle integration.',
            'src/middleware/ics_decoder.py': 'Identity handshake and presence monitor.',
            'src/lib/activity_main.py': 'Foreground activity interactions with discovery.',
            'src/lib/actbase.py': 'Activity scheduling and destruction contract.',
            'src/lib/widget.py': 'Menu selection and rendering contract.',
            'src/lib/actstack.py': 'Pause, resume and activity stack behavior.',
            'src/main/main.py': 'Device startup and serial reservation.',
            'tests/ui/conftest.py': 'Shared UI test doubles and their limits.',
            'tests/ui/activities/conftest.py': 'Activity test setup and doubles.',
            'tests/ui/test_ics_presence.py': 'Polling and ownership regression expectations.',
        },
        'searches': ['DecoderPresence', '_poll_decoder', '_set_decoder_visible', 'detect_decoder('],
    },
}


def select(name, context, searches):
    if name not in PROFILES:
        raise ValueError('Unknown trusted context profile')
    manual_context = sorted(set(safe_path(path) for path in context))
    manual_searches = search_terms(searches)
    recipe = PROFILES[name]
    paths = sorted(set(manual_context) | set(recipe['paths']))
    terms = search_terms(sorted(set(manual_searches) | set(recipe['searches'])))
    selection = None if name == 'manual' else dict(profile=name, version=1,
        paths=dict(recipe['paths']), searches=list(recipe['searches']),
        manual_context=manual_context, manual_searches=manual_searches)
    return paths, terms, selection
