import sys
import urllib.parse


def _early_hand_off():
    """
    The user opened the add-on from Kodi's file browser (Add-ons,
    Music > Add-ons, a plugin:// shortcut): hand the full-screen UI over
    to the script entry point BEFORE importing the plugin (API, cache,
    listing modules), so the browser is replaced by the home screen at
    once. See resources/lib/launcher.py. Returns True when handed over.
    """
    if len(sys.argv) < 3 or sys.argv[2] not in ("", "?"):
        return False
    if urllib.parse.urlparse(sys.argv[0]).path not in ("", "/"):
        return False
    import xbmc
    try:
        from resources.lib import launcher
        if not launcher.user_open():
            return False  # widget fetch: the plugin serves the listing
        launcher.hand_off(int(sys.argv[1]))
        xbmc.log("plugin.audio.soundcloud::addon.py UI handed over to the "
                 "script entry point, home screen under the UI", xbmc.LOGINFO)
        return True
    except Exception as e:  # fall back to the plugin's own launch path
        xbmc.log("plugin.audio.soundcloud::addon.py early hand-off failed: %s" % e,
                 xbmc.LOGWARNING)
        return False


if not _early_hand_off():
    from resources import plugin

    plugin.run()
