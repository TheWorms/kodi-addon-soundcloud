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

            # We need to distinguish two callers of this URL:
            #
            # 1. The user clicked SoundCloud from Kodi's add-on browser
            #    or the music browser. Here they expect the full-screen
            #    UI to open immediately.
            #
            # 2. A skin home widget (Arctic Zephyr Reloaded etc.) is
            #    fetching content to populate its carousel. Here we
            #    MUST return a flat directory — launching the UI would
            #    rip the user out of their home screen.
            #
            # Heuristic: if the active window is the Kodi Home screen
            # (or a skin's customised home), it's almost certainly a
            # widget data fetch. Otherwise it's the user clicking from
            # an add-on browser / music section. This isn't 100% bullet
            # proof but works for every common skin we tested.
            is_widget_call = (
                xbmc.getCondVisibility("Window.IsActive(home)")
                or xbmc.getCondVisibility("Window.IsVisible(home)")
            )

            if not is_widget_call:
                # User-initiated open: launch the full-screen UI.
                # We use ReplaceWindow(home) to replace the music browser
                # (which Kodi opened to host the plugin) with the home
                # screen — this minimises the visible flash of the music
                # window and means hitting Back from our UI returns
                # straight to home rather than to the music browser.
                xbmc.executebuiltin("ReplaceWindow(home)")
                xbmcplugin.endOfDirectory(
                    handle, succeeded=False, cacheToDisc=False
                )
                xbmc.executebuiltin("RunScript(" + addon_id + ")")
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
        dialog = xbmcgui.Dialog()
        dialog.textviewer(
            addon.getLocalizedString(30022),
            addon.getLocalizedString(30026)
        )

    elif path == PATH_SETTINGS_AUTH_TEST:
        # Direct token test bypassing our normal API flow so the test result
        # reflects the *real* current state of the token, not a cached
        # decision from earlier in the session.
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
            try:
                # Log the exact request we're about to make so we can compare
                # with what works in the browser.
                xbmc.log(
                    "plugin.audio.soundcloud::AuthTest sending GET to "
                    "https://api-v2.soundcloud.com/me with header "
                    "Authorization='OAuth %s' (%d chars)" %
                    (token[:6] + "..." + token[-4:], len(token)),
                    xbmc.LOGINFO,
                )
                resp = requests.get(
                    "https://api-v2.soundcloud.com/me",
                    headers={"Authorization": "OAuth " + token},
                    timeout=10,
                )
                # Log what we got back.
                body_preview = (resp.text or "")[:300]
                xbmc.log(
                    "plugin.audio.soundcloud::AuthTest got HTTP %d, "
                    "body[:300]=%r, "
                    "response_headers=%r" % (
                        resp.status_code,
                        body_preview,
                        dict(resp.headers),
                    ),
                    xbmc.LOGINFO,
                )

                if resp.status_code == 200:
                    try:
                        username = resp.json().get("username", "?")
                    except Exception:
                        username = "?"
                    dialog.ok(
                        "SoundCloud",
                        addon.getLocalizedString(30242).format(username) +
                        "\n\n" + preview
                    )
                    if hasattr(api, "_token_invalid"):
                        api._token_invalid = False
                else:
                    # Show the body of the error response so the user can
                    # see the exact reason from SoundCloud (sometimes it
                    # says "expired", "invalid scope", "rate-limited", etc).
                    err_msg = (
                        addon.getLocalizedString(30243).format(resp.status_code) +
                        "\n\n" + preview +
                        "\n\nResponse body:\n" + body_preview
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
