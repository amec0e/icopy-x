##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Main activity module — replaces actmain.so.

Contains MainActivity (root menu), plus stubs for OTAActivity,
SleepModeActivity, and WarningDiskFullActivity which are also defined
in the original actmain.so (252KB, 129 functions, 43 methods across
4 Activity classes).

"""

import logging
import importlib
import queue
import threading

from lib.actbase import BaseActivity
from lib import actstack
from lib import resources
from lib.widget import ListView
from lib._constants import (
    LIST_ITEM_H,
    KEY_UP,
    KEY_DOWN,
    KEY_OK,
    KEY_M1,
    KEY_M2,
    KEY_PWR,
    KEY_ALL,
)

logger = logging.getLogger(__name__)

# =====================================================================
# Activity registry — maps action keys to (module_path, class_name)
# =====================================================================
# The original actmain.so uses check_all_activity() with importlib and
# inspect to discover activities dynamically.  We use a static registry
# because all activity modules are known at build time and dynamic
# discovery adds fragility without benefit.

_ACTIVITY_REGISTRY = {
    'autocopy':     ('activity_main',   'AutoCopyActivity'),
    'dump_files':   ('activity_main',   'CardWalletActivity'),
    'scan':         ('activity_main',   'ScanActivity'),
    'read_list':    ('activity_main',   'ReadListActivity'),
    'sniff':        ('activity_main',   'SniffActivity'),
    'simulation':   ('activity_main',   'SimulationActivity'),
    'pcmode':       ('activity_main',   'PCModeActivity'),
    'backlight':    ('activity_main',   'BacklightActivity'),
    'diagnosis':    ('activity_tools',  'DiagnosisActivity'),
    'volume':       ('activity_main',   'VolumeActivity'),
    'about':        ('activity_main',   'AboutActivity'),
    'erase':        ('activity_main',   'WipeTagActivity'),
    'time_settings': ('activity_main',  'TimeSyncActivity'),
    'lua_script':   ('activity_main',   'LUAScriptCMDActivity'),
    'plugins_menu': ('lib.plugins_menu', 'PluginsMenuActivity'),
    'settings_menu': ('activity_main',  'SettingsMenuActivity'),
    'iclass_se':    ('activity_main',   'ICSDecoderActivity'),
}

# =====================================================================
# Plugin integration
# =====================================================================
# Populated once at boot time by init_plugins(). Contains all
# discovered PluginInfo objects (both promoted and non-promoted).
_discovered_plugins = []

def init_plugins():
    """Discover and register plugins from the plugins/ directory.

    Called once at boot time (from the boot sequence in application.py
    or main.py).  Stores discovered PluginInfo objects in
    ``_discovered_plugins`` for use by MainActivity and
    PluginsMenuActivity.

    Safe to call multiple times — subsequent calls re-discover.
    """
    global _discovered_plugins
    try:
        from lib.plugin_loader import discover_plugins
        _discovered_plugins = discover_plugins()
        if _discovered_plugins:
            logger.info(
                "Plugin system: %d plugin(s) loaded", len(_discovered_plugins))
        else:
            logger.debug("Plugin system: no plugins found")
    except Exception as exc:
        logger.error("Plugin discovery failed: %s", exc)
        _discovered_plugins = []

class MainActivity(BaseActivity):
    """Root activity -- main menu.

    Uses ListView with icons for menu items.
    Handles activity launch via actstack.start_activity.
    Battery bar shown via BaseActivity.onResume.

    This activity is the ROOT -- it is never popped from the stack.
    PWR on main menu triggers the shutdown/sleep flow rather than
    calling finish().

    Instance variables (beyond BaseActivity):
        lv_main_page    -- ListView widget for the menu
        _menu_items     -- list of (label, icon_or_None, action_key) tuples
    """

    ACT_NAME = 'main'

    # Menu items: (label, icon_name_or_None, activity_action_key)
    # Verified order from v1.0.90 QEMU walker + UI_Mapping/00_main_menu
    MENU_ITEMS = [
        ("Auto Copy",     "1",    "autocopy"),
        ("Dump Files",    "2",    "dump_files"),
        ("Scan Tag",      "3",    "scan"),
        ("Read Tag",      "4",    "read_list"),
        ("Sniff TRF",     "5",    "sniff"),
        ("Simulation",    "6",    "simulation"),
        ("PC-Mode",       "7",    "pcmode"),
        ("Diagnosis",     "diagnosis", "diagnosis"),  # pos 7 — wrench icon (diagnosis.png)
        ("Backlight",     "8",    "backlight"),      # pos 8 — lightbulb icon
        ("Volume",        "9",    "volume"),          # pos 9 — speaker icon
        ("About",         "list",   "about"),
        ("Erase Tag",     "erase",  "erase"),
        ("Time Settings", "time",   "time_settings"),
        ("LUA Script",    "script", "lua_script"),
        ("ICS Decoder",   "47",     "iclass_se"),
    ]

    def __init__(self, bundle=None):
        super().__init__(bundle)
        self.lv_main_page = None
        # Language the cached menu labels were built for; used by onResume to
        # re-localise the root menu when the language changed while away.
        self._labels_lang = None
        self._menu_items = list(self.MENU_ITEMS)

        # --- Plugin integration ---
        # Append "Plugins" submenu entry if there are non-promoted plugins,
        # then append each promoted plugin as a direct main menu entry.
        non_promoted = [p for p in _discovered_plugins if not p.promoted]
        promoted = [p for p in _discovered_plugins if p.promoted]

        if non_promoted:
            self._menu_items.append(("Plugins", "plugins", "plugins_menu"))

        for plugin in promoted:
            icon = plugin.icon_path or "plugin"
            action_key = "plugin:" + plugin.key
            self._menu_items.append((plugin.name, icon, action_key))

        # Settings is always the last menu item
        self._menu_items.append(("Settings", "3", "settings_menu"))
        self._menu_catalog = list(self._menu_items)
        self._menu_items = [item for item in self._menu_catalog if item[2] != 'iclass_se']
        self._decoder_presence = None
        self._decoder_worker = None
        self._decoder_cancel = threading.Event()
        self._decoder_results = queue.Queue()
        self._decoder_timer = None

    def onCreate(self, bundle=None):
        """Set up the main menu.

        Startup sequence:
            1. setTitle("Main Page")
            2. setLeftButton("") -- M1 empty on root (no back)
            3. setRightButton("") -- no button labels on real device
            4. Create ListView at (0, 40) with menu items + icons
        """
        # Buttons: M1 empty, M2 empty (HANDOVER.md, main_page_1_3_1.png)
        self.setLeftButton("")
        self.setRightButton("")

        # Build ListView
        canvas = self.getCanvas()
        if canvas is not None:
            xy = resources.get_xy('lv_main_page')
            text_size = resources.get_text_size('lv_main_page')
            self.lv_main_page = ListView(
                canvas, xy=xy, text_size=text_size, item_height=LIST_ITEM_H,
            )
            labels = [self._menu_label(item) for item in self._menu_items]
            self.lv_main_page.setItems(labels)
            self._labels_lang = resources.getLanguage()
            icons = [item[1] for item in self._menu_items]
            self.lv_main_page.setIcons(icons)
            self.lv_main_page.setOnPageChangeCall(self._onPageChange)
            self.lv_main_page.show()

        # Title with page indicator: "Main Page N/M"
        # [Source: main_page_1_3_1.png, UI_MAP_COMPLETE.md row 1]
        self._updateTitle()

    def onResume(self):
        """Refresh battery, restore list display and title.

        The main menu is the root activity: it is only ever resumed, never
        recreated. Its item labels are built once in onCreate and cached in
        the ListView, so a language change made elsewhere (Settings > Language)
        would leave them stale. Re-localise them here when the active language
        differs from the one they were built for, preserving the highlight.
        """
        super().onResume()
        if self.lv_main_page is not None:
            if resources.getLanguage() != self._labels_lang:
                selected = self.lv_main_page.selection()
                labels = [self._menu_label(item) for item in self._menu_items]
                self.lv_main_page.setItems(labels)
                self.lv_main_page.setSelection(selected)
                self._labels_lang = resources.getLanguage()
            if not self.lv_main_page.isShowing():
                self.lv_main_page.show()
        self._updateTitle()

        # Schedule from Tk only. Workers put results in a queue; they never
        # touch a paused/destroyed activity's canvas or call Tk.after().
        self._set_decoder_visible(False)
        if self._decoder_timer is None and self.getCanvas() is not None:
            self._decoder_timer = self.getCanvas().after(250, self._poll_decoder)

    def onPause(self):
        self._stop_decoder_poll()
        super().onPause()

    def onDestroy(self):
        self._stop_decoder_poll()
        super().onDestroy()

    def _stop_decoder_poll(self):
        self._decoder_cancel.set()
        if self._decoder_timer is not None:
            self.getCanvas().after_cancel(self._decoder_timer)
            self._decoder_timer = None

    def _poll_decoder(self):
        self._decoder_timer = None
        if not self.resumed or self.life.destroyed:
            return
        while not self._decoder_results.empty():
            token, present = self._decoder_results.get_nowait()
            if token is self._decoder_cancel and not token.is_set():
                self._set_decoder_visible(present)
        if self._decoder_worker is None or not self._decoder_worker.is_alive():
            self._decoder_cancel = threading.Event()
            token = self._decoder_cancel

            def check():
                try:
                    if self._decoder_presence is None:
                        import ics_decoder
                        self._decoder_presence = ics_decoder.DecoderPresence()
                    present = self._decoder_presence.check(token.is_set)
                except Exception:
                    logger.exception('Could not check ICS Decoder presence')
                    present = False
                self._decoder_results.put((token, present))

            self._decoder_worker = threading.Thread(target=check, daemon=True)
            self._decoder_worker.start()
        self._decoder_timer = self.getCanvas().after(1000, self._poll_decoder)

    def _set_decoder_visible(self, present):
        items = [item for item in self._menu_catalog
                 if item[2] != 'iclass_se' or present]
        if items == self._menu_items:
            return
        selected = self.lv_main_page.selection() if self.lv_main_page else 0
        action = self._menu_items[selected][2]
        self._menu_items = items
        if self.lv_main_page is not None:
            self.lv_main_page.setItems([self._menu_label(item) for item in items])
            self.lv_main_page.setIcons([item[1] for item in items])
            selected = next((i for i, item in enumerate(items) if item[2] == action),
                            min(selected, len(items) - 1))
            self.lv_main_page.setSelection(selected)
        self._updateTitle()

    def onKeyEvent(self, key):
        """Handle key input on the main menu."""
        if self.isbusy():
            return

        if key == KEY_UP:
            if self.lv_main_page is not None:
                old_page = self.lv_main_page.getPagePosition()
                self.lv_main_page.prev()
                if self.lv_main_page.getPagePosition() != old_page:
                    self._updateTitle()

        elif key == KEY_DOWN:
            if self.lv_main_page is not None:
                old_page = self.lv_main_page.getPagePosition()
                self.lv_main_page.next()
                if self.lv_main_page.getPagePosition() != old_page:
                    self._updateTitle()

        elif key in (KEY_OK, KEY_M2):
            if self.lv_main_page is not None:
                pos = self.lv_main_page.selection()
                self._launchActivity(pos)

        elif key == KEY_M1:
            # M1 is empty on main menu -- no action
            pass

        elif key == KEY_ALL:
            # S/R/W button — launch AutoCopy (Scan -> Read -> Write)
            from lib.activity_main import AutoCopyActivity
            actstack.start_activity(AutoCopyActivity)

        elif key == KEY_PWR:
            # PWR triggers shutdown/sleep flow
            # For now, no-op (SleepModeActivity not yet wired)
            pass

    def _launchActivity(self, index):
        """Launch the activity at menu position *index*.

        For plugin action keys (``"plugin:<key>"``), a bundle is built
        from the corresponding PluginInfo and passed to the activity.
        Standard activities are launched without a bundle.
        """
        if index < 0 or index >= len(self._menu_items):
            logger.warning("Menu index %d out of range", index)
            return

        _label, _icon, action_key = self._menu_items[index]
        act_cls = self._getActivityClass(action_key)

        if act_cls is None:
            logger.warning(
                "Activity '%s' not available (module not implemented)",
                action_key,
            )
            return

        # Build plugin bundle if this is a plugin action key
        bundle = None
        if action_key.startswith('plugin:'):
            plugin_key = action_key[7:]
            info = self._find_plugin_info(plugin_key)
            if info is not None:
                if info.canvas_mode:
                    bundle = {
                        'plugin_dir': info.plugin_dir,
                        'manifest': info.manifest,
                        'binary': info.binary,
                        'args': info.args,
                        'key_map': info.key_map,
                    }
                else:
                    bundle = {
                        'plugin_dir': info.plugin_dir,
                        'manifest': info.manifest,
                        'ui_definition': info.ui_definition,
                        'entry_class': info.activity_class,
                        'plugin_key': info.key,
                        'translations': getattr(info, 'translations', None),
                    }

        actstack.start_activity(act_cls, bundle)

    def _getActivityClass(self, key):
        """Resolve an action key to an activity class.

        Uses the static _ACTIVITY_REGISTRY to find the module path and
        class name.  Keys starting with ``"plugin:"`` resolve to
        PluginActivity or CanvasModeActivity depending on the plugin's
        canvas_mode flag.  Returns None if the module cannot be imported
        (activity not yet implemented).

        Args:
            key: Action key string (e.g. 'backlight', 'volume',
                 'plugins_menu', 'plugin:my_plugin').

        Returns:
            The activity class, or None if not available.
        """
        # --- Plugin action keys ---
        if key.startswith('plugin:'):
            plugin_key = key[7:]  # strip "plugin:" prefix
            info = self._find_plugin_info(plugin_key)
            if info is None:
                logger.warning("Plugin '%s' not found", plugin_key)
                return None
            if info.canvas_mode:
                from lib.plugin_activity import CanvasModeActivity
                return CanvasModeActivity
            else:
                from lib.plugin_activity import PluginActivity
                return PluginActivity

        # --- Standard registry lookup ---
        if key not in _ACTIVITY_REGISTRY:
            logger.debug("No registry entry for action key '%s'", key)
            return None

        module_path, class_name = _ACTIVITY_REGISTRY[key]
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name, None)
            if cls is None:
                logger.debug(
                    "Class '%s' not found in module '%s'",
                    class_name, module_path,
                )
            return cls
        except (ImportError, ModuleNotFoundError):
            logger.debug("Module '%s' not importable", module_path)
            return None
        except Exception as exc:
            logger.error("Error loading '%s': %s", module_path, exc)
            return None

    def gotoActByPos(self, pos):
        """Navigate to activity at list position (alias for _launchActivity).

        Matches the original method signature.
        """
        self._launchActivity(pos)

    def getMenuItemCount(self):
        """Return the number of menu items."""
        return len(self._menu_items)

    def _onPageChange(self, page):
        """Callback from ListView when page changes."""
        self._updateTitle()

    def _updateTitle(self):
        """Update title: "Main Page N/M".

        [Source: main_page_1_3_1.png, SCREEN_LAYOUT.md "Page indicator"]
        """
        base_title = resources.get_str('main_page')
        if self.lv_main_page is not None:
            total = self.lv_main_page.getPageCount()
            current = self.lv_main_page.getPagePosition() + 1
            self.setTitle('%s %d/%d' % (base_title, current, total))
        else:
            self.setTitle(base_title)

    def _menu_label(self, item):
        """Localized label for a menu item.

        Built-in entries translate through the core pack; a promoted
        plugin's entry translates through that plugin's own pack first.
        """
        label, _icon, action_key = item
        if action_key.startswith('plugin:'):
            info = self._find_plugin_info(action_key[7:])
            return resources.tr_plugin(
                label, getattr(info, 'translations', None))
        return resources.tr(label)

    def _find_plugin_info(self, plugin_key):
        """Look up a PluginInfo by its key from the discovered plugins.

        Args:
            plugin_key: Plugin key string (directory basename).

        Returns:
            PluginInfo if found, else None.
        """
        for info in _discovered_plugins:
            if info.key == plugin_key:
                return info
        return None
