from resources.lib.soundcloud.api_v2 import ApiV2
from resources.lib.kodi.cache import Cache
from resources.lib.kodi.items import Items
from resources.lib.kodi.search_history import SearchHistory
from resources.lib.kodi.settings import Settings
from resources.lib.kodi.vfs import VFS
from resources.routes import *
import os
import sys
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

addon = xbmcaddon.Addon()
addon_id = addon.getAddonInfo("id")
addon_base = "plugin://" + addon_id
addon_profile_path = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
vfs = VFS(addon_profile_path)
vfs_cache = VFS(os.path.join(addon_profile_path, "cache"))
settings = Settings(addon)
cache = Cache(settings, vfs_cache)
api = ApiV2(settings, xbmc.getLanguage(xbmc.ISO_639_1), cache)
search_history = SearchHistory(settings, vfs)
listItems = Items(addon, addon_base, search_history, api=api)


def run():
    import time as _t
    _t0 = _t.time()
    xbmc.log(
        "plugin.audio.soundcloud::plugin.py timing T+0ms run() entry",
        xbmc.LOGINFO,
    )

    url = urllib.parse.urlparse(sys.argv[0])
    path = url.path
    handle = int(sys.argv[1])
    args = urllib.parse.parse_qs(sys.argv[2][1:])

    # Widget mode redirection (must happen BEFORE the main dispatch).
    # When the user has set widget.mode to something other than "off",
    # any call to the plugin root returns directly the items for that
    # source instead of launching the UI. This lets skins like
    # Arctic Zephyr Reloaded — which only let widgets point at the
    # addon root — show a flat list of tracks as a home widget.
    if path == PATH_ROOT:
        widget_mode = (settings.get("widget.mode") or "off").strip()
        action_param = args.get("action", None)
        if (
            action_param is None
            and widget_mode not in ("", "off")
        ):
            redirect_to = {
                "likes": PATH_WIDGET_LIKES,
                "playlists": PATH_WIDGET_PLAYLISTS,
                "following": PATH_WIDGET_FOLLOWING,
                "trending": PATH_WIDGET_TRENDING,
                "discover": PATH_WIDGET_DISCOVER,
            }.get(widget_mode)
            if redirect_to:
                xbmc.log(
                    addon_id + ": widget.mode='%s' — redirecting / to %s" %
                    (widget_mode, redirect_to),
                    xbmc.LOGINFO,
                )
                path = redirect_to
            else:
                xbmc.log(
                    addon_id + ": unknown widget.mode '%s', falling through" %
                    widget_mode, xbmc.LOGWARNING,
                )

    if path == PATH_ROOT:
        action = args.get("action", None)

        if action is None:
            # Diagnostic: log every condition we could test, so we can
            # actually see what Kodi reports for this call.
            diag_conditions = [
                "Window.IsActive(home)",
                "Window.IsVisible(home)",
                "Window.IsActive(addonbrowser)",
                "Window.IsVisible(addonbrowser)",
                "Window.IsActive(MyMusicNav.xml)",
                "Window.IsActive(musicfiles)",
                "Window.IsActive(filemanager)",
                "Container.Content(addons)",
                "System.HasAddon(skin.arcticzephyr2)",
            ]
            diag_active_window = xbmc.getInfoLabel("System.CurrentWindow")
            diag_active_id = xbmc.getInfoLabel("System.CurrentWindow.ID")
            diag_caller = xbmc.getInfoLabel("Container.PluginName")
            diag_results = {
                c: xbmc.getCondVisibility(c) for c in diag_conditions
            }
            xbmc.log(
                "plugin.audio.soundcloud::ROOT context diag — "
                "CurrentWindow=%r ID=%r PluginName=%r conditions=%r" %
                (diag_active_window, diag_active_id, diag_caller, diag_results),
                xbmc.LOGINFO,
            )

            # Heuristic to distinguish "user clicked the addon" from
            # "skin home widget is fetching content":
            #
            # - User clicks: Kodi opened MyMusicNav.xml (Music > Add-ons)
            #   or addonbrowser to host the plugin call. These windows
            #   are visible during the call.
            # - Widget fetch: the active window stays "home" (the user is
            #   on the Kodi/skin home screen and the widget panel is
            #   loading content in the background).
            #
            # We log everything so it's easy to debug skin-specific cases.
            diag_active_window = xbmc.getInfoLabel("System.CurrentWindow")
            is_user_browsing = (
                xbmc.getCondVisibility("Window.IsActive(MyMusicNav.xml)")
                or xbmc.getCondVisibility("Window.IsActive(musicfiles)")
                or xbmc.getCondVisibility("Window.IsActive(addonbrowser)")
                or xbmc.getCondVisibility("Window.IsActive(filemanager)")
            )
            is_widget_call = not is_user_browsing

            if not is_widget_call:
                # User-initiated open: launch the full-screen UI.
                #
                # Step 1: signal the background service to show the
                # splash window. If the service is running, it picks
                # up this signal within ~50ms and shows the splash.
                # If the service is disabled (or hasn't been started
                # because the user just enabled it without restarting
                # Kodi), the signal is harmless and script.py will
                # fall back to creating its own splash later.
                home_signal = xbmcgui.Window(10000)

                # Detect "enabled but not running" — set a sentinel
                # property that the service clears on its first poll.
                # If the property is still there when plugin.py runs,
                # it means the service hasn't seen a single poll yet,
                # which on a running service shouldn't happen. We use
                # this to nudge the user about the required restart.
                service_setting = settings.get("service.preload")
                service_alive = home_signal.getProperty(
                    "soundcloud.service.alive"
                ) == "1"
                if service_setting == "true" and not service_alive:
                    # User enabled the service but it's not running.
                    # Show a one-shot notification (gated by another
                    # property so we don't spam on every click).
                    if home_signal.getProperty(
                        "soundcloud.restart.notified"
                    ) != "1":
                        xbmcgui.Dialog().notification(
                            "SoundCloud",
                            addon.getLocalizedString(30292),
                            xbmcgui.NOTIFICATION_INFO,
                            5000,
                        )
                        home_signal.setProperty(
                            "soundcloud.restart.notified", "1"
                        )

                home_signal.setProperty("soundcloud.splash", "show")

                # Step 2: launch script.py via RunScript. Python's
                # process scheduler will let it start in parallel with
                # the music-browser cleanup below.
                xbmc.executebuiltin("RunScript(" + addon_id + ")")
                xbmc.log(
                    "plugin.audio.soundcloud::plugin.py timing T+%dms "
                    "after RunScript() call" %
                    int((_t.time() - _t0) * 1000),
                    xbmc.LOGINFO,
                )

                # Step 3: tell Kodi this plugin call returns no items
                # (so the music browser doesn't try to populate itself
                # with a non-existent listing).
                xbmcplugin.endOfDirectory(
                    handle, succeeded=False, cacheToDisc=False
                )

                # Step 4: replace the music browser with home. The
                # service's splash, if it succeeded in showing, will
                # be on top of home and stays visible.
                xbmc.executebuiltin("ReplaceWindow(home)")
                xbmc.log(
                    "plugin.audio.soundcloud::plugin.py timing T+%dms "
                    "plugin.py exiting (service should be showing splash)" %
                    int((_t.time() - _t0) * 1000),
                    xbmc.LOGINFO,
                )
                return

            # Widget call: return the flat directory of widget shortcuts
            # so the skin has something playable to render.
            items = listItems.widgets(include_ui_launcher=True)
            xbmcplugin.addDirectoryItems(handle, items, len(items))
            xbmcplugin.endOfDirectory(handle)
        elif "call" in action:
            # Generic "call" action — used by the full-screen UI to
            # navigate inside the plugin's data tree. We don't know what
            # the call returns, so we inspect the resulting collection
            # and set content accordingly.
            collection = api.call(args.get("call")[0])
            _set_content_for_collection(handle, collection)
            list_items = listItems.from_collection(collection)
            _add_sort_methods_for_collection(handle, collection)
            xbmcplugin.addDirectoryItems(handle, list_items, len(list_items))
            xbmcplugin.endOfDirectory(handle)
        elif "settings" in action:
            # Used by the sidebar Settings button in the full-screen UI.
            addon.openSettings()
        elif "launch_ui" in action:
            # Explicit launcher: clicked from the root directory listing.
            # Launches the full-screen UI as a separate Kodi script so
            # the directory handler returns cleanly.
            xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
            xbmc.executebuiltin("RunScript(" + addon_id + ")")
            return
        else:
            xbmc.log(addon_id + ": Invalid root action", xbmc.LOGERROR)

    elif path == PATH_CHARTS:
        xbmcplugin.setContent(handle, "songs")
        action = args.get("action", [None])[0]
        genre = args.get("genre", ["soundcloud:genres:all-music"])[0]
        if action is None:
            items = listItems.charts()
            xbmcplugin.addDirectoryItems(handle, items, len(items))
            xbmcplugin.endOfDirectory(handle)
        else:
            api_result = api.charts({"kind": action, "genre": genre, "limit": 50})
            collection = listItems.from_collection(api_result)
            _add_song_sort_methods(handle)
            xbmcplugin.addDirectoryItems(handle, collection, len(collection))
            xbmcplugin.endOfDirectory(handle)

    elif path == PATH_DISCOVER:
        xbmcplugin.setContent(handle, "songs")
        selection = args.get("selection", [None])[0]
        collection = listItems.from_collection(api.discover(selection))
        xbmcplugin.addDirectoryItems(handle, collection, len(collection))
        xbmcplugin.endOfDirectory(handle)

    elif path == PATH_PLAY:
        xbmcplugin.setContent(handle, "songs")
        # Public params
        track_id = args.get("track_id", [None])[0]
        playlist_id = args.get("playlist_id", [None])[0]
        url = args.get("url", [None])[0]

        # Public legacy params (@deprecated)
        audio_id_legacy = args.get("audio_id", [None])[0]
        track_id = audio_id_legacy if audio_id_legacy else track_id

        # Private params
        media_url = args.get("media_url", [None])[0]

        if media_url:
            resolved_url = api.resolve_media_url(media_url)
            if resolved_url:
                item = xbmcgui.ListItem(path=resolved_url)
                xbmcplugin.setResolvedUrl(handle, succeeded=True, listitem=item)
            else:
                # Media URL has expired (HLS URLs are short-lived) or the
                # API rejected the request. Tell Kodi the resolution failed
                # so it skips to the next track instead of crashing the
                # decoder on a None path.
                xbmc.log(
                    addon_id + ": failed to resolve media URL %s" % media_url,
                    xbmc.LOGWARNING,
                )
                xbmcplugin.setResolvedUrl(
                    handle, succeeded=False, listitem=xbmcgui.ListItem()
                )
        elif track_id:
            collection = listItems.from_collection(api.resolve_id(track_id))
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            resolve_list_item(handle, collection[0][1])
            playlist.add(url=collection[0][0], listitem=collection[0][1])
        elif playlist_id:
            call = "/playlists/{id}".format(id=playlist_id)
            collection = listItems.from_collection(api.call(call))
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            for item in collection:
                resolve_list_item(handle, item[1])
                playlist.add(url=item[0], listitem=item[1])
        elif url:
            collection = listItems.from_collection(api.resolve_url(url))
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            for item in collection:
                resolve_list_item(handle, item[1])
                playlist.add(url=item[0], listitem=item[1])
        else:
            xbmc.log(addon_id + ": Invalid play param", xbmc.LOGERROR)

    elif path == PATH_SEARCH:
        xbmcplugin.setContent(handle, "songs")
        action = args.get("action", None)
        query = args.get("query", [""])[0]

        if action and "remove" in action:
            search_history.remove(query)
            xbmc.executebuiltin("Container.Refresh")
        elif action and "clear" in action:
            search_history.clear()
            xbmc.executebuiltin("Container.Refresh")

        if query:
            if action is None:
                search(handle, query)
            elif "people" in action:
                xbmcplugin.setContent(handle, "artists")
                collection = listItems.from_collection(api.search(query, "users"))
                xbmcplugin.addDirectoryItems(handle, collection, len(collection))
                xbmcplugin.endOfDirectory(handle)
            elif "albums" in action:
                xbmcplugin.setContent(handle, "albums")
                collection = listItems.from_collection(api.search(query, "albums"))
                xbmcplugin.addDirectoryItems(handle, collection, len(collection))
                xbmcplugin.endOfDirectory(handle)
            elif "playlists" in action:
                xbmcplugin.setContent(handle, "albums")
                collection = listItems.from_collection(
                    api.search(query, "playlists_without_albums")
                )
                xbmcplugin.addDirectoryItems(handle, collection, len(collection))
                xbmcplugin.endOfDirectory(handle)
            else:
                xbmc.log(addon_id + ": Invalid search action", xbmc.LOGERROR)
        else:
            if action is None:
                items = listItems.search()
                xbmcplugin.addDirectoryItems(handle, items, len(items))
                xbmcplugin.endOfDirectory(handle)
            elif "new" in action:
                query = xbmcgui.Dialog().input(addon.getLocalizedString(30101))
                search_history.add(query)
                search(handle, query)
            else:
                xbmc.log(addon_id + ": Invalid search action", xbmc.LOGERROR)

    # Legacy search query used by Chorus2 (@deprecated)
    elif path == PATH_SEARCH_LEGACY:
        xbmcplugin.setContent(handle, "songs")
        query = args.get("q", [""])[0]
        collection = listItems.from_collection(api.search(query))
        xbmcplugin.addDirectoryItems(handle, collection, len(collection))
        xbmcplugin.endOfDirectory(handle)

    elif path == PATH_USER:
        xbmcplugin.setContent(handle, "songs")
        user_id = args.get("id")[0]
        default_action = args.get("call")[0]
        if user_id:
            items = listItems.user(user_id)
            collection = listItems.from_collection(api.call(default_action))
            _add_song_sort_methods(handle)
            xbmcplugin.addDirectoryItems(handle, items, len(items))
            xbmcplugin.addDirectoryItems(handle, collection, len(collection))
            xbmcplugin.endOfDirectory(handle)
        else:
            xbmc.log(addon_id + ": Invalid user action", xbmc.LOGERROR)

    elif path == PATH_ME:
        # "My profile" — requires an OAuth token configured in settings.
        if not settings.get_oauth_token():
            dialog = xbmcgui.Dialog()
            dialog.ok(
                addon.getLocalizedString(30110),
                addon.getLocalizedString(30025)
            )
            addon.openSettings()
        else:
            items = listItems.me()
            xbmcplugin.addDirectoryItems(handle, items, len(items))
            xbmcplugin.endOfDirectory(handle)

    elif path == PATH_SETTINGS_AUTH_HELP:
        # We used to render the help text in a textviewer dialog, but
        # some Kodi skins render it blank on TV resolutions. dialog.ok()
        # is plainer-looking but renders reliably everywhere.
        dialog = xbmcgui.Dialog()
        help_text = addon.getLocalizedString(30026)
        if not help_text or not help_text.strip():
            # Translation didn't load (shouldn't happen) — fall back to
            # the hardcoded URL so the user at least gets something.
            help_text = (
                "Get your token on the helper page:\n\n"
                "[COLOR=FFFF5500]https://theworms.github.io/"
                "kodi-addon-soundcloud/[/COLOR]\n\n"
                "The page has a copy-paste console snippet that grabs your "
                "token automatically. The snippet runs entirely in your "
                "browser - your token is never sent anywhere."
            )
        dialog.ok(
            addon.getLocalizedString(30022) or "Get your OAuth token",
            help_text
        )

    elif path == PATH_SETTINGS_AUTH_TEST:
        # Direct token test bypassing our normal API flow so the test result
        # reflects the *real* current state of the token, not a cached
        # decision from earlier in the session.
        #
        # IMPORTANT: SoundCloud's edge tightened up since 2025. /me returns
        # 403 unless we send Origin + Referer headers identifying us as
        # coming from soundcloud.com. We now always send those, matching
        # what api_v2.py does for its normal requests.
        #
        # Cascade strategy:
        #   1) /me — gives us username + subscription tier
        #   2) /users/{my_id}/track_likes — proven to work in the user's
        #      log even when /me misbehaves
        # If any responds 200, auth is confirmed.
        import requests
        dialog = xbmcgui.Dialog()
        token = settings.get_oauth_token()
        if not token:
            dialog.ok("SoundCloud", addon.getLocalizedString(30244))
        else:
            preview = "len=%d, starts=%s..., ends=...%s" % (
                len(token),
                token[:6],
                token[-4:],
            )

            common_headers = {
                "Authorization": "OAuth " + token,
                "User-Agent": (
                    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:142.0) "
                    "Gecko/20100101 Firefox/142.0"
                ),
                "Origin": "https://soundcloud.com",
                "Referer": "https://soundcloud.com/",
            }

            def try_endpoint(test_url):
                """Returns (status, body_preview, parsed_json_or_None)."""
                try:
                    xbmc.log(
                        "plugin.audio.soundcloud::AuthTest GET %s "
                        "with token len=%d" % (test_url, len(token)),
                        xbmc.LOGINFO,
                    )
                    r = requests.get(test_url, headers=common_headers,
                                     timeout=10)
                    bp = (r.text or "")[:300]
                    xbmc.log(
                        "plugin.audio.soundcloud::AuthTest %s -> HTTP %d, "
                        "body[:300]=%r" % (test_url, r.status_code, bp),
                        xbmc.LOGINFO,
                    )
                    parsed = None
                    if r.status_code == 200:
                        try:
                            parsed = r.json()
                        except Exception:
                            parsed = None
                    return (r.status_code, bp, parsed)
                except Exception as ex:
                    xbmc.log(
                        "plugin.audio.soundcloud::AuthTest %s failed: %s" %
                        (test_url, str(ex)),
                        xbmc.LOGWARNING,
                    )
                    return (None, str(ex), None)

            try:
                username = None
                tier = None
                last_status = None
                last_body = ""

                # Step 1: /me with browser-like headers
                status, body, parsed = try_endpoint(
                    "https://api-v2.soundcloud.com/me"
                )
                last_status, last_body = status, body
                if status == 200 and parsed:
                    username = parsed.get("username")
                    # Extract subscription tier so we can show it to the
                    # user. Free accounts have certain SoundCloud-imposed
                    # limitations (preview-only tracks marked SNIP, etc).
                    sub = parsed.get("consumer_subscription") or {}
                    product = sub.get("product") or {}
                    tier = product.get("id")  # "free", "go_plus", "pro", ...
                    # Persist tier so other code paths (settings menu,
                    # row filters) can react without re-querying.
                    try:
                        settings.set("account.tier", tier or "")
                    except Exception:
                        pass

                # Step 2: /users/{my_id}/track_likes - proven to work
                # when /me is blocked. We try this even when /me succeeded,
                # but only as a fallback if /me failed.
                if status is None or status != 200:
                    user_id = None
                    try:
                        user_id = api.get_my_user_id()
                    except Exception:
                        pass
                    if user_id:
                        status, body, _ = try_endpoint(
                            "https://api-v2.soundcloud.com/users/%d/track_likes?limit=1"
                            % user_id
                        )
                        last_status, last_body = status, body

                if status == 200:
                    # Auth confirmed.
                    if username and tier:
                        msg = addon.getLocalizedString(30242).format(username)
                        msg += "\n\n" + addon.getLocalizedString(30247).format(
                            tier.replace("_", " ").title() if tier != "free"
                            else "Free"
                        )
                    elif username:
                        msg = addon.getLocalizedString(30242).format(username)
                    else:
                        msg = addon.getLocalizedString(30246)
                    dialog.ok("SoundCloud", msg + "\n\n" + preview)
                    if hasattr(api, "_token_invalid"):
                        api._token_invalid = False
                else:
                    err_msg = (
                        addon.getLocalizedString(30243).format(
                            last_status if last_status else "?") +
                        "\n\n" + preview +
                        "\n\nLast response body:\n" + last_body
                    )
                    dialog.ok("SoundCloud", err_msg)
            except Exception as e:
                dialog.ok(
                    "SoundCloud",
                    addon.getLocalizedString(30245).format(str(e)) +
                    "\n\n" + preview
                )

    elif path == PATH_WIDGETS:
        # Browseable list of all widget shortcuts. Use this in skin widget
        # pickers (Arctic Zephyr Reloaded > Customise Home > Add Widget):
        # navigate into "SoundCloud > Widgets > <choice>" and the skin
        # remembers the path.
        items = listItems.widgets()
        xbmcplugin.addDirectoryItems(handle, items, len(items))
        xbmcplugin.endOfDirectory(handle)

    elif path == PATH_WIDGET_LIKES:
        # Tracks the user has liked. Requires OAuth.
        xbmcplugin.setContent(handle, "songs")
        try:
            user_id = api.get_my_user_id()
            if user_id:
                limit = int(settings.get("search.items.size") or 20)
                api_result = api.call(
                    "/users/%d/track_likes?limit=%d" % (user_id, limit)
                )
                collection = listItems.from_collection(api_result)
                _add_song_sort_methods(handle)
                xbmcplugin.addDirectoryItems(handle, collection, len(collection))
        except Exception as e:
            xbmc.log(addon_id + ": widget/likes failed: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle)

    elif path == PATH_WIDGET_PLAYLISTS:
        # User's own playlists. Requires OAuth.
        xbmcplugin.setContent(handle, "albums")
        try:
            user_id = api.get_my_user_id()
            if user_id:
                limit = int(settings.get("search.items.size") or 20)
                api_result = api.call(
                    "/users/%d/playlists_without_albums?limit=%d" % (user_id, limit)
                )
                collection = listItems.from_collection(api_result)
                xbmcplugin.addDirectoryItems(handle, collection, len(collection))
        except Exception as e:
            xbmc.log(addon_id + ": widget/playlists failed: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle)

    elif path == PATH_WIDGET_FOLLOWING:
        # Artists the user follows. Requires OAuth.
        xbmcplugin.setContent(handle, "artists")
        try:
            user_id = api.get_my_user_id()
            if user_id:
                limit = int(settings.get("search.items.size") or 20)
                api_result = api.call(
                    "/users/%d/followings?limit=%d" % (user_id, limit)
                )
                collection = listItems.from_collection(api_result)
                xbmcplugin.addDirectoryItems(handle, collection, len(collection))
        except Exception as e:
            xbmc.log(addon_id + ": widget/following failed: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle)

    elif path == PATH_WIDGET_TRENDING:
        # Worldwide trending tracks (no OAuth required).
        xbmcplugin.setContent(handle, "songs")
        try:
            limit = int(settings.get("search.items.size") or 20)
            api_result = api.charts({
                "kind": "trending",
                "genre": "soundcloud:genres:all-music",
                "limit": limit,
            })
            collection = listItems.from_collection(api_result)
            _add_song_sort_methods(handle)
            xbmcplugin.addDirectoryItems(handle, collection, len(collection))
        except Exception as e:
            xbmc.log(addon_id + ": widget/trending failed: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle)

    elif path == PATH_WIDGET_DISCOVER:
        # SoundCloud's "Discover" / mixed-selections endpoint.
        # No OAuth required but quality of results is better when authenticated
        # (personalisation by SoundCloud).
        xbmcplugin.setContent(handle, "songs")
        try:
            collection = listItems.from_collection(api.discover(None))
            xbmcplugin.addDirectoryItems(handle, collection, len(collection))
        except Exception as e:
            xbmc.log(addon_id + ": widget/discover failed: %s" % str(e), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle)

    elif path == PATH_SETTINGS_CACHE_CLEAR:
        vfs_cache.destroy()
        dialog = xbmcgui.Dialog()
        dialog.ok("SoundCloud", addon.getLocalizedString(30501))

    elif path == PATH_SETTINGS_CREATE_FAVOURITE:
        # Create a Kodi favourite that points at RunScript(plugin.audio.soundcloud).
        # The favourite can then be picked from skin menu editors that don't
        # let the user type a RunScript command directly (Arctic Zephyr
        # Reloaded, Estuary, etc.). Launching the addon via the favourite
        # bypasses the music browser entirely — the splash appears within
        # ~200ms instead of ~600ms after click.
        #
        # We edit favourites.xml directly because there's no public Kodi
        # API to add a favourite from a script. The file lives at
        # special://userdata/favourites.xml (a single XML doc with
        # <favourites><favourite>...</favourite></favourites>).
        import xml.etree.ElementTree as ET

        dialog = xbmcgui.Dialog()
        fav_path = xbmcvfs.translatePath("special://userdata/favourites.xml")
        # NOTE: we deliberately don't name this local variable `addon_id` —
        # there's already an `addon_id` at module scope (line 18). Assigning
        # to `addon_id` here would make Python treat the whole `run()` body
        # as having a local `addon_id`, including the `xbmc.executebuiltin
        # ("RunScript(" + addon_id + ")")` call ~500 lines earlier, which
        # then raises UnboundLocalError at runtime. The module-level value
        # is identical, so we just use it.
        thumb_path = "special://home/addons/%s/resources/icon.png" % addon_id
        runscript = "RunScript(%s)" % addon_id
        fav_name = "SoundCloud"

        try:
            # Load existing favourites.xml or start a new tree.
            if os.path.exists(fav_path):
                try:
                    tree = ET.parse(fav_path)
                    root = tree.getroot()
                except ET.ParseError:
                    # Existing file is corrupt — back it up and start fresh
                    # rather than blow it away silently.
                    import time as _bt
                    backup = fav_path + ".bak." + str(int(_bt.time()))
                    os.rename(fav_path, backup)
                    xbmc.log(
                        "plugin.audio.soundcloud::create_favourite "
                        "favourites.xml was corrupt, backed up to %s" % backup,
                        xbmc.LOGWARNING,
                    )
                    root = ET.Element("favourites")
                    tree = ET.ElementTree(root)
            else:
                root = ET.Element("favourites")
                tree = ET.ElementTree(root)

            # Look for an existing entry pointing at our RunScript so we
            # don't add a duplicate every time the user clicks the button.
            already_present = False
            for fav in root.findall("favourite"):
                if (fav.text or "").strip() == runscript:
                    already_present = True
                    # Refresh thumb + name in case they were stale.
                    fav.set("name", fav_name)
                    fav.set("thumb", thumb_path)
                    break

            if not already_present:
                new_fav = ET.SubElement(root, "favourite")
                new_fav.set("name", fav_name)
                new_fav.set("thumb", thumb_path)
                new_fav.text = runscript

            tree.write(fav_path, encoding="utf-8", xml_declaration=True)

            # Tell Kodi to reload favourites so the new entry shows up
            # immediately without a restart.
            xbmc.executebuiltin("ReloadSkin()")

            if already_present:
                msg = addon.getLocalizedString(30280)  # already exists
            else:
                msg = addon.getLocalizedString(30281)  # created
            dialog.ok("SoundCloud", msg)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::create_favourite failed: %s" % str(e),
                xbmc.LOGERROR,
            )
            dialog.ok(
                "SoundCloud",
                addon.getLocalizedString(30282).format(str(e))
            )

    else:
        xbmc.log(addon_id + ": Path not found", xbmc.LOGERROR)


def _set_content_for_collection(handle, collection):
    """
    Sets the Kodi content type based on what the collection actually
    contains. Kodi skins use this hint to pick the right view mode
    (grid of album covers vs list of songs vs artist tiles).
    """
    kinds = {type(item).__name__ for item in collection.items}
    if kinds == {"User"}:
        xbmcplugin.setContent(handle, "artists")
    elif kinds == {"Playlist"}:
        xbmcplugin.setContent(handle, "albums")
    else:
        # Mixed content or only tracks.
        xbmcplugin.setContent(handle, "songs")


def _add_sort_methods_for_collection(handle, collection):
    """Adds appropriate sort methods based on the collection's content type."""
    kinds = {type(item).__name__ for item in collection.items}
    if "Track" in kinds:
        _add_song_sort_methods(handle)


def _add_song_sort_methods(handle):
    """Standard sort methods for a list of songs/tracks."""
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE)
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_DURATION)
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_PLAYCOUNT)


def resolve_list_item(handle, list_item):
    resolved_url = api.resolve_media_url(list_item.getProperty("mediaUrl"))
    if resolved_url:
        list_item.setPath(resolved_url)
        xbmcplugin.setResolvedUrl(handle, succeeded=True, listitem=list_item)
    else:
        # Same defensive handling as the play handler — let Kodi skip the
        # track instead of crashing the audio decoder on a None path.
        xbmc.log(addon_id + ": resolve_list_item got no URL", xbmc.LOGWARNING)
        xbmcplugin.setResolvedUrl(
            handle, succeeded=False, listitem=xbmcgui.ListItem()
        )


def search(handle, query):
    search_options = listItems.search_sub(query)
    collection = listItems.from_collection(api.search(query))
    xbmcplugin.addDirectoryItems(handle, search_options, len(collection))
    xbmcplugin.addDirectoryItems(handle, collection, len(collection))
    xbmcplugin.endOfDirectory(handle)
