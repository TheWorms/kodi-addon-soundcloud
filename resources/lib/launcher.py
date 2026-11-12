"""
Opening the full-screen UI without ever showing Kodi's file browser.

Deliberately light (xbmc and xbmcgui only): addon.py imports it before
anything else so the hand-off happens as early as possible.

Why the home screen goes UNDER the UI
-------------------------------------
Opened as a plugin (Add-ons, Music > Add-ons, a plugin:// menu
shortcut), the add-on is hosted by Kodi's file browser, which Kodi
shows BEFORE a single line of the add-on runs. If the UI opened on top
of it, closing the UI would land on the file browser for a moment. The
plugin entry point therefore replaces the browser with the home screen
first, then hands the UI over to the script entry point (RunScript).
Launched directly with RunScript(plugin.audio.soundcloud) (home menu
shortcut, favourite), the browser is never opened at all.

Order matters
-------------
Kodi refuses to change windows while a dialog is up, and the splash is
a dialog: the home screen must be in place BEFORE the splash shows.

The UI is a dialog too, so it opens ON TOP of the splash (dialogs stack
in opening order). The splash is closed only once the UI covers the
screen: nothing (home screen, file browser) is ever visible between
the two. Closing the splash first used to leave the home screen on
screen for about half a second while the UI was being built.
"""
import threading
import time

import xbmc
import xbmcgui

ADDON_ID = "plugin.audio.soundcloud"
SPLASH_XML = "script-soundcloud-splash.xml"
MAIN_XML = "script-soundcloud-home.xml"
SKIN = "default"
RES = "1080i"
# Shared with service.py, which hosts the splash when it runs (it is
# already in memory, so the splash shows faster).
PROP_SPLASH = "soundcloud.splash"
PROP_ALIVE = "soundcloud.service.alive"
HANDOFF_ARG = "handoff"

_HOME = "Window.IsActive(home)"
# File-browser windows that host a plugin opened by the user. A plugin
# call made from anywhere else (home screen or skin hub widget, skin
# shortcut picker...) is a widget fetch, not a click.
_EXPLORER = ("Window.IsActive(music) | Window.IsActive(videos)"
             " | Window.IsActive(programs) | Window.IsActive(addonbrowser)"
             " | Window.IsActive(filemanager)")
_SPLASH_VISIBLE = "Window.IsVisible(%s)" % SPLASH_XML
_MAIN_VISIBLE = "Window.IsVisible(%s)" % MAIN_XML

_local = None
_lock = threading.Lock()


class _Splash(xbmcgui.WindowXMLDialog):
    """Splash opened by this process when the service does not run."""

    def onAction(self, action):
        pass  # Back does not close the splash: the UI is on its way


def _log(msg, level=xbmc.LOGINFO):
    xbmc.log("%s::launcher %s" % (ADDON_ID, msg), level)


def _service_alive():
    return xbmcgui.Window(10000).getProperty(PROP_ALIVE) == "1"


def _wait(condition, expected, timeout):
    """Wait until the Kodi condition takes the expected value."""
    monitor = xbmc.Monitor()
    deadline = time.time() + timeout
    while bool(xbmc.getCondVisibility(condition)) != expected:
        if time.time() >= deadline or monitor.waitForAbort(0.05):
            return False
    return True


def user_open():
    """The user opened the add-on from the file browser, and the UI is
    not already on screen."""
    if xbmc.getCondVisibility(_MAIN_VISIBLE):
        return False
    return bool(xbmc.getCondVisibility(_EXPLORER))


def hand_off(handle, args=""):
    """Plugin entry point: replace the file browser with the home screen,
    then hand the UI over to the script entry point. The caller has
    nothing left to do. args: extra RunScript arguments
    (play_track=<id>,source=<cat>)."""
    import xbmcplugin
    xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
    at_home = bool(xbmc.getCondVisibility(_HOME))
    if not at_home:
        xbmc.executebuiltin("ReplaceWindow(home)")
        at_home = _wait(_HOME, True, 2.0)
    # Home screen first, splash second (see the module docstring).
    if at_home and _service_alive():
        xbmcgui.Window(10000).setProperty(PROP_SPLASH, "show")
    params = ",".join(p for p in (args, HANDOFF_ARG) if p)
    xbmc.executebuiltin("RunScript(%s,%s)" % (ADDON_ID, params))


def go_home(handed_off, timeout=3.0):
    """Call BEFORE splash_show. Makes the home screen the active window so
    that the UI opens on top of it.

    handed_off: the plugin entry point already asked for it. Otherwise
    (favourite, Programs, skin menu) it is asked for here when a file
    browser is on screen."""
    if xbmc.getCondVisibility(_HOME):
        return True
    if handed_off:
        return _wait(_HOME, True, 1.0)
    if not xbmc.getCondVisibility(_EXPLORER):
        return False  # launched from elsewhere (player, other add-on): leave it
    xbmc.executebuiltin("ReplaceWindow(home)")
    if not _wait(_HOME, True, timeout):
        _log("home screen not reached in %.0f s, opening anyway" % timeout,
             xbmc.LOGWARNING)
        return False
    return True


def splash_show(addon_path):
    """Script entry point, AFTER go_home: splash while the heavy modules
    load."""
    global _local
    if xbmc.getCondVisibility(_SPLASH_VISIBLE):
        return  # already shown by the service
    if _service_alive():
        xbmcgui.Window(10000).setProperty(PROP_SPLASH, "show")
        return
    try:
        win = _Splash(SPLASH_XML, addon_path, SKIN, RES)
        win.show()
        with _lock:
            _local = win
    except Exception as e:  # the splash must never block the UI
        _log("splash failed: %s" % e, xbmc.LOGWARNING)


def splash_hide():
    """Close the splash, whoever shows it. Safe to call several times, or
    with no splash on screen."""
    global _local
    try:
        if _service_alive():
            xbmcgui.Window(10000).setProperty(PROP_SPLASH, "hide")
    except Exception:
        pass
    with _lock:
        win, _local = _local, None
    if win is not None:
        try:
            win.close()
        except Exception:
            pass
        del win


def _hide_when_covered():
    if _wait(_MAIN_VISIBLE, True, 60.0):
        xbmc.Monitor().waitForAbort(0.2)  # let Kodi draw the UI first
    splash_hide()


def splash_hide_when_covered():
    """Call right before opening the UI (whose doModal blocks): the splash
    closes as soon as the UI covers it."""
    threading.Thread(target=_hide_when_covered, name="soundcloud-splash",
                     daemon=True).start()
