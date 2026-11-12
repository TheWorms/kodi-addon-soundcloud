"""
Entry point for the SoundCloud V2 full-screen UI.

Launched via `RunScript(plugin.audio.soundcloud)` — either by the user
clicking "SoundCloud" in Kodi, or via the auto-launch path in plugin.py.

Boot strategy
-------------
The expensive part of our boot is importing resources.lib.ui.window
(1700+ lines plus transitive imports). On ARM (ODROID-N2Plus etc.)
this takes ~870ms cold, hidden behind a splash.

Order (see resources/lib/launcher.py): the home screen goes under the
UI first (Kodi refuses to change windows while a dialog such as the
splash is up), then the splash shows - hosted by the background
service when it runs, by this process otherwise - and the UI opens ON
TOP of the splash, which closes only once the UI covers the screen.
Nothing is ever visible between the splash and the UI, and closing the
UI lands straight on the home screen.
"""
import os
import sys
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

GUARD_PROPERTY = "soundcloud.ui.open"


def _t(t0, label):
    """Log elapsed milliseconds since t0 with a phase label."""
    elapsed = int((time.time() - t0) * 1000)
    xbmc.log(
        "plugin.audio.soundcloud::script.py timing T+%dms %s" %
        (elapsed, label),
        xbmc.LOGINFO,
    )


if __name__ == "__main__":
    t0 = time.time()
    _t(t0, "script.py entry")

    # Optional arguments from RunScript(plugin.audio.soundcloud,
    # play_track=<id>,source=<likes|trending|discover>) — used by
    # widget track clicks to open the UI with a track playing, and to
    # queue the rest of the widget category after it.
    startup_track_id = None
    startup_track_source = None
    token_mode = False
    from_settings = False
    handed_off = False
    for _arg in sys.argv[1:]:
        if not isinstance(_arg, str):
            continue
        if _arg.startswith("play_track="):
            startup_track_id = _arg.split("=", 1)[1].strip() or None
        elif _arg.startswith("source="):
            startup_track_source = _arg.split("=", 1)[1].strip() or None
        elif _arg.strip() == "token":
            token_mode = True
        elif _arg.strip() == "from_settings":
            from_settings = True
        elif _arg.strip() == "handoff":
            handed_off = True

    if token_mode:
        # RunScript(plugin.audio.soundcloud,token[,from_settings]):
        # the "OAuth token" window alone - no splash, no full-screen UI.
        # Settings > Account runs it with <close>true</close>, so Kodi
        # has already saved and closed the settings dialog (it would
        # otherwise write its stale copy of the token back on close);
        # it is reopened afterwards so the user lands where they were.
        if from_settings:
            # Settings opened via Add-ons > SoundCloud > Configure: the
            # add-on information dialog underneath keeps its own copy
            # of the settings (with the old token) and would write it
            # back the next time Configure is used. Close it; the
            # settings are reopened from a fresh copy below.
            xbmc.executebuiltin("Dialog.Close(addoninformation,true)")
        _addon = xbmcaddon.Addon()
        _profile = xbmcvfs.translatePath(_addon.getAddonInfo("profile"))
        from resources.lib.kodi.cache import Cache
        from resources.lib.kodi.settings import Settings
        from resources.lib.kodi.vfs import VFS
        from resources.lib.soundcloud.api_v2 import ApiV2
        from resources.lib.ui.token_dialog import open_token_dialog
        _settings = Settings(_addon)
        _api = ApiV2(_settings, xbmc.getLanguage(xbmc.ISO_639_1),
                     Cache(_settings, VFS(os.path.join(_profile, "cache"))))
        try:
            open_token_dialog(_addon, _settings, _api)
        finally:
            if from_settings:
                xbmc.executebuiltin("Addon.OpenSettings(%s)" % _addon.getAddonInfo("id"))
        sys.exit(0)
    if startup_track_id:
        _t(t0, "startup track requested: %s (source=%s)" % (
            startup_track_id, startup_track_source or "-"))

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

    from resources.lib import launcher

    launcher.go_home(handed_off)
    launcher.splash_show(addon_path)
    _t(t0, "splash requested")

    # Background service enabled in the settings but not running: it
    # only starts with Kodi. One notification per Kodi session.
    if (addon.getSetting("service.preload") == "true"
            and home_window.getProperty(launcher.PROP_ALIVE) != "1"
            and home_window.getProperty("soundcloud.restart.notified") != "1"):
        xbmcgui.Dialog().notification(
            "SoundCloud", addon.getLocalizedString(30292),
            xbmcgui.NOTIFICATION_INFO, 5000)
        home_window.setProperty("soundcloud.restart.notified", "1")

    try:
        addon_profile_path = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        _t(t0, "addon profile resolved")

        # The heavy imports — these are what take ~870ms on cold start,
        # behind the splash.
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

        # Client ID display setting, refreshed in the background
        # (audit N3).
        from resources.lib.kodi import client_id_info
        client_id_info.sync_bg(addon, settings, api, vfs_cache)

        # The UI opens on top of the splash; the splash closes once
        # covered (closing it first showed the home screen meanwhile).
        launcher.splash_hide_when_covered()
        _t(t0, "calling open_home()")
        open_home(
            api=api,
            addon=addon,
            settings=settings,
            startup_track_id=startup_track_id,
            startup_track_source=startup_track_source,
        )
        _t(t0, "open_home() returned (UI closed)")
    finally:
        # Splash still up if the UI never opened (error, guard).
        launcher.splash_hide()
        home_window.clearProperty(GUARD_PROPERTY)
