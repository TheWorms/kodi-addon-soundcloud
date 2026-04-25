"""
Entry point for the SoundCloud V2 full-screen UI.

Launched via `RunScript(plugin.audio.soundcloud)` — either by the user
clicking "SoundCloud" in Kodi (auto-launch) or via the "New interface"
menu entry in the classic plugin.

We use a simple Window.Property guard to prevent double-launching: if
another instance is already up, we just bail. Without this, rapid clicks
or background re-renders of the plugin directory would stack multiple
WindowXMLDialog instances, which interrupts playback.
"""
import os
import sys

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

GUARD_PROPERTY = "soundcloud.ui.open"


if __name__ == "__main__":
    home_window = xbmcgui.Window(10000)  # Kodi's home window — global property store

    # Re-entrancy guard: if the UI is already open, don't open another.
    if home_window.getProperty(GUARD_PROPERTY) == "1":
        xbmc.log(
            "plugin.audio.soundcloud::script.py UI already open, skipping",
            xbmc.LOGINFO,
        )
        sys.exit(0)

    home_window.setProperty(GUARD_PROPERTY, "1")
    try:
        addon = xbmcaddon.Addon()
        addon_profile_path = xbmcvfs.translatePath(addon.getAddonInfo("profile"))

        from resources.lib.kodi.settings import Settings
        from resources.lib.kodi.vfs import VFS
        from resources.lib.kodi.cache import Cache
        from resources.lib.soundcloud.api_v2 import ApiV2
        from resources.lib.ui.window import open_home

        vfs_cache = VFS(os.path.join(addon_profile_path, "cache"))
        settings = Settings(addon)
        cache = Cache(settings, vfs_cache)
        api = ApiV2(settings, xbmc.getLanguage(xbmc.ISO_639_1), cache)

        open_home(api=api, addon=addon, settings=settings)
    finally:
        # Always clear the guard so the user can re-open the UI later.
        home_window.clearProperty(GUARD_PROPERTY)
