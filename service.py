"""
SoundCloud V2 background service.

Runs continuously from Kodi login until Kodi shutdown. Its only purpose
is to make the addon's full-screen UI appear faster when the user
clicks "SoundCloud" — by having a splash window ready to display the
moment plugin.py asks for it.

Without this service, the cold-start sequence is:
  - User clicks → plugin.py runs (Python cold-start ~150ms)
  - plugin.py launches script.py (another Python cold-start ~150ms)
  - script.py imports ~870ms of heavy modules
  - script.py creates and shows the splash window
  - Total: ~1.2s of "frozen music browser" before any visible feedback

With this service running:
  - At Kodi login, this service pre-warms the OS file cache for our
    Python modules so future imports are faster
  - When the user clicks → plugin.py signals "show splash" via a Window
    property → the service (already running, modules warm) shows the
    splash in <50ms
  - script.py loads its modules (faster now, cache warm) and signals
    "hide splash" when its home window is ready
  - Total perceived delay: ~50ms before visible feedback

Memory cost: a few MB for the running Python interpreter plus whatever
the splash window needs (it's only instantiated on demand, not held in
memory permanently).

The service can be disabled via the "service.preload" setting for
users on low-memory devices (which would prefer the slower cold-start
over the constant background memory use).

Architecture
------------
plugin.py and script.py communicate with the service via Window
properties on Kodi's home window (id 10000), which all addons can
read and write:
  - "soundcloud.splash" = "show": service shows the splash window
  - "soundcloud.splash" = "hide": service closes the splash window
  - The service clears the property after each action.

The service polls the property every 50ms — fast enough that the user
doesn't perceive any delay, slow enough that the CPU cost is
negligible (an idle ARM Cortex-A73 spends <0.1% on this loop).
"""
import os
import sys

import xbmc
import xbmcaddon
import xbmcgui


PROPERTY_SPLASH = "soundcloud.splash"
POLL_INTERVAL_SECONDS = 0.05


class _SplashWindow(xbmcgui.WindowXMLDialog):
    """
    No-op splash window subclass. Renders the XML, nothing more.
    Lives in this module (not in resources.lib.ui.window) so the
    service can instantiate it without importing the full UI tree.
    """
    pass


def _service_enabled():
    """
    Read the user's preference. Defaults to DISABLED (return False)
    if the setting hasn't been touched yet — we want users to opt in
    explicitly, since the service uses memory continuously.
    """
    try:
        addon = xbmcaddon.Addon()
        return addon.getSetting("service.preload") == "true"
    except Exception:
        return False


def _warm_module_files(addon_path):
    """
    Read our heavy Python module files once so they land in the OS
    file cache. The next time Python imports them (from script.py),
    the read from disk is satisfied from cache — typically 5-10x
    faster on slow eMMC storage.

    Note: we don't actually IMPORT the modules here. Importing would
    create module objects in the service's Python interpreter, which
    can't be shared with the script.py interpreter (different
    process, different namespace). Cache warming is all we can do
    cross-process.
    """
    module_files = [
        "resources/lib/kodi/settings.py",
        "resources/lib/kodi/vfs.py",
        "resources/lib/kodi/cache.py",
        "resources/lib/soundcloud/api_v2.py",
        "resources/lib/ui/window.py",
        "resources/lib/ui/listItems.py",
        "resources/lib/soundcloud/objects.py",
        "resources/skins/default/1080i/script-soundcloud-home.xml",
        "resources/skins/default/1080i/script-soundcloud-splash.xml",
    ]
    warmed = 0
    for rel_path in module_files:
        full_path = os.path.join(addon_path, rel_path)
        try:
            if os.path.exists(full_path):
                with open(full_path, "rb") as f:
                    f.read()
                warmed += 1
        except Exception:
            pass  # missing file isn't fatal, just skip
    xbmc.log(
        "plugin.audio.soundcloud::service.py warmed %d files into OS cache" % warmed,
        xbmc.LOGINFO,
    )


def _run_service():
    addon = xbmcaddon.Addon()
    addon_path = addon.getAddonInfo("path")
    home = xbmcgui.Window(10000)
    monitor = xbmc.Monitor()

    # Clear any stale signal from a previous Kodi session (in case the
    # last shutdown happened while a signal was in flight).
    home.clearProperty(PROPERTY_SPLASH)

    # Wait briefly for Kodi to finish booting — we don't want to
    # compete with all the other startup work for CPU during the
    # first few seconds.
    if monitor.waitForAbort(3.0):
        return

    _warm_module_files(addon_path)

    # Announce that we're alive — plugin.py reads this to detect when
    # the user enabled the service but hasn't restarted Kodi yet.
    home.setProperty("soundcloud.service.alive", "1")

    splash = None
    xbmc.log(
        "plugin.audio.soundcloud::service.py started, polling for splash signal "
        "every %dms" % int(POLL_INTERVAL_SECONDS * 1000),
        xbmc.LOGINFO,
    )

    while not monitor.abortRequested():
        try:
            cmd = home.getProperty(PROPERTY_SPLASH)

            if cmd == "show" and splash is None:
                try:
                    splash = _SplashWindow(
                        "script-soundcloud-splash.xml",
                        addon_path,
                        "default",
                        "1080i",
                    )
                    splash.show()
                    xbmc.log(
                        "plugin.audio.soundcloud::service.py splash shown",
                        xbmc.LOGINFO,
                    )
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::service.py splash show failed: %s"
                        % str(e),
                        xbmc.LOGWARNING,
                    )
                    splash = None
                home.clearProperty(PROPERTY_SPLASH)

            elif cmd == "hide":
                if splash is not None:
                    try:
                        splash.close()
                        xbmc.log(
                            "plugin.audio.soundcloud::service.py splash closed",
                            xbmc.LOGINFO,
                        )
                    except Exception as e:
                        xbmc.log(
                            "plugin.audio.soundcloud::service.py splash close failed: %s"
                            % str(e),
                            xbmc.LOGWARNING,
                        )
                    splash = None
                home.clearProperty(PROPERTY_SPLASH)

            elif cmd == "show" and splash is not None:
                # Already showing — just clear the (redundant) signal
                home.clearProperty(PROPERTY_SPLASH)

            # waitForAbort returns True if Kodi is shutting down, so
            # we exit the loop cleanly. The 50ms poll interval is fast
            # enough to feel instant but slow enough to cost almost
            # nothing on idle.
            if monitor.waitForAbort(POLL_INTERVAL_SECONDS):
                break
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::service.py loop exception: %s" % str(e),
                xbmc.LOGERROR,
            )
            # Back off briefly on errors so we don't spam the log
            if monitor.waitForAbort(1.0):
                break

    # Kodi is shutting down — clean up our resources.
    if splash is not None:
        try:
            splash.close()
        except Exception:
            pass
    home.clearProperty(PROPERTY_SPLASH)
    home.clearProperty("soundcloud.service.alive")
    home.clearProperty("soundcloud.restart.notified")
    xbmc.log(
        "plugin.audio.soundcloud::service.py shutting down cleanly",
        xbmc.LOGINFO,
    )


if __name__ == "__main__":
    if not _service_enabled():
        xbmc.log(
            "plugin.audio.soundcloud::service.py disabled by user setting, exiting",
            xbmc.LOGINFO,
        )
        sys.exit(0)
    _run_service()
