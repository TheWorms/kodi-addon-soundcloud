"""
Entry point for the SoundCloud V2 full-screen UI.

Launched via `RunScript(plugin.audio.soundcloud)` — either by the user
clicking "SoundCloud" in Kodi, or via the auto-launch path in plugin.py.

Boot strategy
-------------
The expensive part of our boot is importing resources.lib.ui.window
(1700+ lines plus transitive imports). On ARM (ODROID-N2Plus etc.)
this takes ~870ms cold.

If the background service is enabled (default), it has already shown
a splash window for us BEFORE we even started — plugin.py set the
"soundcloud.splash" = "show" property on Kodi's home window, and the
service picked it up within ~50ms. In that case, all we do is the
heavy imports, then signal "hide splash" right before opening home.

If the service is disabled (user setting), we fall back to the old
behaviour: create and show our own splash in this process. Slower
because we can't show the splash until our process has been Python-
cold-started (~150ms after the click), but still better than nothing.
"""
import os
import sys
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

GUARD_PROPERTY = "soundcloud.ui.open"
SPLASH_PROPERTY = "soundcloud.splash"


def _t(t0, label):
    """Log elapsed milliseconds since t0 with a phase label."""
    elapsed = int((time.time() - t0) * 1000)
    xbmc.log(
        "plugin.audio.soundcloud::script.py timing T+%dms %s" %
        (elapsed, label),
        xbmc.LOGINFO,
    )


class _SplashWindow(xbmcgui.WindowXMLDialog):
    """
    Fallback splash used when the background service is disabled.
    Same XML, same look — just opened from this process instead of
    the service's process.
    """
    pass


if __name__ == "__main__":
    t0 = time.time()
    _t(t0, "script.py entry")

    # Optional argument from RunScript(plugin.audio.soundcloud,play_track=<id>)
    # — used by widget track clicks to open the UI with a track playing.
    startup_track_id = None
    for _arg in sys.argv[1:]:
        if isinstance(_arg, str) and _arg.startswith("play_track="):
            startup_track_id = _arg.split("=", 1)[1].strip() or None
    if startup_track_id:
        _t(t0, "startup track requested: %s" % startup_track_id)

    home_window = xbmcgui.Window(10000)

    # Re-entrancy guard: if the UI is already open, don't open another.
    if home_window.getProperty(GUARD_PROPERTY) == "1":
        xbmc.log(
            "plugin.audio.soundcloud::script.py UI already open, skipping",
            xbmc.LOGINFO,
        )
        sys.exit(0)

    home_window.setProperty(GUARD_PROPERTY, "1")

    addon = xbmcaddon.Addon()
    addon_path = addon.getAddonInfo("path")

    # Check whether the background service is enabled. Defaults to
    # DISABLED — users must opt in via Settings > Account >
    # "Background service (faster open)" and then restart Kodi. If
    # disabled, we use our in-process splash like before (slower but
    # zero background memory).
    service_enabled = addon.getSetting("service.preload") == "true"
    fallback_splash = None

    if not service_enabled:
        # Service-less fallback: create and show splash from this
        # process (old 5.9.6010+ behaviour).
        try:
            fallback_splash = _SplashWindow(
                "script-soundcloud-splash.xml", addon_path, "default", "1080i"
            )
            fallback_splash.show()
            _t(t0, "fallback splash shown (service disabled)")
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::script.py fallback splash failed: %s"
                % str(e),
                xbmc.LOGWARNING,
            )
            fallback_splash = None
    else:
        _t(t0, "service mode: splash should already be visible from service")

    try:
        addon_profile_path = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        _t(t0, "addon profile resolved")

        # The heavy imports — these are what take ~870ms on cold start.
        # The splash (either the service's or our fallback) is already
        # on screen so the user doesn't see this delay.
        from resources.lib.kodi.settings import Settings
        from resources.lib.kodi.vfs import VFS
        from resources.lib.kodi.cache import Cache
        from resources.lib.soundcloud.api_v2 import ApiV2
        from resources.lib.ui.window import open_home
        _t(t0, "all modules imported")

        vfs_cache = VFS(os.path.join(addon_profile_path, "cache"))
        settings = Settings(addon)
        cache = Cache(settings, vfs_cache)
        api = ApiV2(settings, xbmc.getLanguage(xbmc.ISO_639_1), cache)
        _t(t0, "API/settings/cache constructed")

        # Close whichever splash is up, just before opening home.
        if service_enabled:
            # Signal the service to close its splash. It polls every
            # 50ms so the splash disappears within ~50ms after this.
            home_window.setProperty(SPLASH_PROPERTY, "hide")
            _t(t0, "signaled service to hide splash")
        elif fallback_splash is not None:
            try:
                fallback_splash.close()
                _t(t0, "fallback splash closed")
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::script.py fallback splash close failed: %s"
                    % str(e),
                    xbmc.LOGWARNING,
                )

        _t(t0, "calling open_home()")
        open_home(
            api=api,
            addon=addon,
            settings=settings,
            startup_track_id=startup_track_id,
        )
        _t(t0, "open_home() returned (UI closed)")
    finally:
        # Cleanup. The service should already have closed its splash
        # at this point, but defensively signal "hide" again in case
        # something went wrong on the exception path.
        if service_enabled:
            home_window.setProperty(SPLASH_PROPERTY, "hide")
        if fallback_splash is not None:
            try:
                fallback_splash.close()
            except Exception:
                pass
        home_window.clearProperty(GUARD_PROPERTY)
