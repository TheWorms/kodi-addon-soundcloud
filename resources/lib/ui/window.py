"""
SoundCloud V2 full-screen home window controller.

This module implements the Python side of the WindowXML script defined in
resources/skins/default/1080i/script-soundcloud-home.xml.

Architecture (kept deliberately simple):

  open_home()                 - public entry point called by script.py
    └── SoundCloudHomeWindow  - subclass of xbmcgui.WindowXMLDialog
          ├── onInit()        - read settings, set up window properties, load home page
          ├── onClick(id)     - dispatch sidebar nav and miniplayer controls
          ├── onAction(act)   - handle Back, also forward to base class
          ├── _load_home()    - populate the 2 horizontal rows on the home page
          ├── _load_page(p)   - populate the generic page list for non-home pages
          └── _play(item)     - resolve a media url and start playback

We use Window.Property to drive the visibility of layout elements so the
XML can be a static file (no python-side rebuild needed when switching
modes). The Properties we set are: layout, miniplayer, page, title,
subtitle, page_empty, row1_title, row2_title.

Control IDs used here MUST match those in the XML file. They are listed
at the top of the XML for reference.
"""
import threading

import xbmc
import xbmcgui


class _ProgressUpdater(threading.Thread):
    """
    Background thread that polls xbmc.Player position 2x per second and
    resizes the orange progress bar images directly via the Python control
    API.

    Why not use the native <progress> control with <info>Player.Progress</info>?
      1. Some skins (e.g. Arctic Zephyr Reloaded) override the native
         progress control's textures with their own (typically blue),
         making colordiffuse and texture overrides ineffective.
      2. For HLS streams Player.Progress can stay frozen at 0% for the
         entire track.

    Why not use $INFO[Window.Property(...)] inside the XML <width>?
      That's a documented Kodi feature but it doesn't actually re-evaluate
      the width on every frame in all Kodi versions — the width gets
      sampled once at window init and stays fixed afterwards.

    So we go fully manual: define the orange image with a placeholder
    width=1 in the XML, then call control.setWidth() from Python every
    500ms with a freshly-computed pixel value.
    """
    # Bar widths in pixels — must match the XML <width> for the bg track.
    CONTROLS_BAR_WIDTH = 700
    COMPACT_BAR_WIDTH = 1000

    # Control IDs of the orange fill images (set in the XML).
    ID_FILL_CONTROLS = 530
    ID_FILL_COMPACT = 531

    def __init__(self, window):
        super().__init__(daemon=True)
        self._player = xbmc.Player()
        self._stop_event = threading.Event()
        self._window = window  # needed for getControl()
        self._tick_count = 0  # for logging cadence

    def stop(self):
        self._stop_event.set()

    def run(self):
        xbmc.log(
            "plugin.audio.soundcloud::ProgressUpdater thread started",
            xbmc.LOGINFO,
        )
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::ProgressUpdater error: %s" % str(e),
                    xbmc.LOGWARNING,
                )
            self._stop_event.wait(0.5)
        xbmc.log(
            "plugin.audio.soundcloud::ProgressUpdater thread stopped",
            xbmc.LOGINFO,
        )

    def _set_width(self, control_id, width):
        """Resize an Image control. Width must be >= 1 for setWidth()
        to be accepted; we clamp to that minimum."""
        try:
            control = self._window.getControl(control_id)
            control.setWidth(max(1, int(width)))
            return True
        except Exception as e:
            # Log only every ~10 seconds to avoid spam
            if self._tick_count % 20 == 0:
                xbmc.log(
                    "plugin.audio.soundcloud::ProgressUpdater setWidth(%d, %d) "
                    "failed: %s" % (control_id, width, str(e)),
                    xbmc.LOGINFO,
                )
            return False

    def _tick(self):
        self._tick_count += 1

        if not self._player.isPlayingAudio():
            self._set_width(self.ID_FILL_CONTROLS, 1)
            self._set_width(self.ID_FILL_COMPACT, 1)
            return

        try:
            elapsed = self._player.getTime()
            duration = self._player.getTotalTime()
        except Exception as e:
            if self._tick_count % 20 == 0:
                xbmc.log(
                    "plugin.audio.soundcloud::ProgressUpdater getTime failed: %s" %
                    str(e), xbmc.LOGINFO,
                )
            return

        if not duration or duration <= 0:
            if self._tick_count % 20 == 0:
                xbmc.log(
                    "plugin.audio.soundcloud::ProgressUpdater duration=%s, "
                    "elapsed=%s — bar can't be computed" % (duration, elapsed),
                    xbmc.LOGINFO,
                )
            return

        ratio = max(0.0, min(1.0, elapsed / duration))
        controls_w = int(self.CONTROLS_BAR_WIDTH * ratio)
        compact_w = int(self.COMPACT_BAR_WIDTH * ratio)

        # Log progress every ~5 seconds (every 10 ticks at 500ms)
        if self._tick_count % 10 == 0:
            xbmc.log(
                "plugin.audio.soundcloud::ProgressUpdater tick: "
                "elapsed=%.1fs, duration=%.1fs, ratio=%.2f, "
                "controls_width=%d, compact_width=%d" %
                (elapsed, duration, ratio, controls_w, compact_w),
                xbmc.LOGINFO,
            )

        self._set_width(self.ID_FILL_CONTROLS, controls_w)
        self._set_width(self.ID_FILL_COMPACT, compact_w)


class _PlayerObserver(xbmc.Player):
    """
    Subclass of xbmc.Player that gets notified when playback changes.
    We use it to highlight the currently-playing track in the visible list,
    so the focus follows the song as autoplay moves through the queue.
    """
    def __init__(self, window):
        super().__init__()
        self._window = window

    def onAVStarted(self):
        try:
            self._window._highlight_playing_track()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver onAVStarted: %s" % str(e),
                xbmc.LOGDEBUG,
            )

    def onAVChange(self):
        try:
            self._window._highlight_playing_track()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver onAVChange: %s" % str(e),
                xbmc.LOGDEBUG,
            )


WINDOW_XML = "script-soundcloud-home.xml"

# Sidebar buttons
ID_NAV_HOME = 110
ID_NAV_SEARCH = 111
ID_NAV_LIKES = 112
ID_NAV_PLAYLISTS = 113
ID_NAV_FOLLOWING = 114
ID_NAV_SETTINGS = 115
# (ID 116 was the legacy interface button — removed in 5.2.4, the option
# to switch to the classic UI now lives in the addon settings)

# Page lists / row lists
ID_ROW1_LIST = 350
ID_ROW2_LIST = 351
ID_ROW3_LIST = 352
ID_ROW4_LIST = 353
ID_ROW_LISTS = (ID_ROW1_LIST, ID_ROW2_LIST, ID_ROW3_LIST, ID_ROW4_LIST)
ID_PAGE_LIST = 400

# Available row types — used to map a setting value to a content loader.
# Localized titles use the corresponding string ID.
ROW_TYPES = {
    "likes":     {"title_strid": 30152, "loader": "_load_likes"},
    "trending":  {"title_strid": 30155, "loader": "_load_trending"},
    "playlists": {"title_strid": 30153, "loader": "_load_playlists"},
    "following": {"title_strid": 30154, "loader": "_load_following"},
}

# Mini-player buttons
ID_MP_PREV = 520
ID_MP_PLAY = 521
ID_MP_NEXT = 522

# Kodi action IDs
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ACTION_PARENT_DIR = 9


class SoundCloudHomeWindow(xbmcgui.WindowXMLDialog):
    """Full-screen home window."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = kwargs.get("api")
        self.addon = kwargs.get("addon")
        self.settings = kwargs.get("settings")

        # Track which collections we have loaded for which control id, so
        # onClick can resolve the index back to the actual track to play.
        # Key: control_id, Value: list of (play_url, ListItem) tuples.
        self._lists = {}

        # Cached next-page link for the page list (set by _fill_page_list).
        self._next_href = None

        # Player observer to follow the currently-playing track in the UI.
        # We keep a reference so it doesn't get garbage-collected.
        self._player_observer = _PlayerObserver(self)

        # Progress bar updater — created here, started in onInit() once
        # the controls actually exist in the GUI tree. Starting it from
        # __init__ would be too early: getControl() would fail because
        # Kodi hasn't built the window yet.
        self._progress_updater = _ProgressUpdater(self)

    # =====================================================================
    # Lifecycle
    # =====================================================================

    def onInit(self):
        # Apply layout from settings.
        layout_setting = self.settings.get("ui.layout") or "1"
        layout = "sidebar" if layout_setting == "1" else "rows"
        self.setProperty("layout", layout)

        # Apply miniplayer mode from settings.
        # 0 = off, 1 = compact (no controls), 2 = controls (full)
        mp_setting = self.settings.get("ui.miniplayer") or "2"
        mp_mode = {"0": "off", "1": "compact", "2": "controls"}.get(mp_setting, "controls")
        self.setProperty("miniplayer", mp_mode)

        # Default page = home.
        self._show_home()

        # Focus the home button in sidebar mode, or the first row in
        # rows-only mode. Wrapped in try/except because setFocusId on a
        # non-existent or invisible control logs a "can't focus" error
        # and (in some Kodi versions) can trigger a window reload loop.
        try:
            if layout == "sidebar":
                target = ID_NAV_HOME
            else:
                target = ID_ROW1_LIST
            # Small delay to let the controls fully initialize before
            # we try to focus them. Without this, focus can race against
            # the layout pass and silently fail.
            xbmc.sleep(50)
            self.setFocusId(target)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow setFocusId failed: %s" % str(e),
                xbmc.LOGDEBUG,
            )

        # Now that the GUI tree is fully built, start the progress
        # bar updater thread. It needs getControl() to work, which
        # requires onInit() to have run.
        try:
            self._progress_updater.start()
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow progress updater started",
                xbmc.LOGINFO,
            )
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow progress updater failed to start: %s" %
                str(e),
                xbmc.LOGWARNING,
            )

    # =====================================================================
    # Input handling
    # =====================================================================

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK, ACTION_PARENT_DIR):
            # Stop the background progress updater before closing the
            # window so it doesn't keep polling the player after we're gone.
            try:
                self._progress_updater.stop()
            except Exception:
                pass
            self.close()
            # After closing the WindowXMLDialog, Kodi would normally return
            # to whichever window the user came from (often "Music files /
            # add-ons"). For a cleaner UX we send them straight back to
            # Kodi's home screen — the SoundCloud "app" experience ends
            # cleanly instead of dropping them into the music browser.
            xbmc.executebuiltin("ActivateWindow(Home)")
            return
        try:
            super().onAction(action)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow onAction error: %s" % str(e),
                xbmc.LOGWARNING,
            )

    def onClick(self, control_id):
        # ----- Sidebar navigation -----
        if control_id == ID_NAV_HOME:
            self._show_home()
            return
        if control_id == ID_NAV_SEARCH:
            self._show_search()
            return
        if control_id == ID_NAV_LIKES:
            self._show_likes()
            return
        if control_id == ID_NAV_PLAYLISTS:
            self._show_playlists()
            return
        if control_id == ID_NAV_FOLLOWING:
            self._show_following()
            return
        if control_id == ID_NAV_SETTINGS:
            self.addon.openSettings()
            return

        # ----- Mini-player controls -----
        if control_id == ID_MP_PREV:
            xbmc.executebuiltin("PlayerControl(Previous)")
            return
        if control_id == ID_MP_PLAY:
            xbmc.executebuiltin("PlayerControl(Play)")
            return
        if control_id == ID_MP_NEXT:
            xbmc.executebuiltin("PlayerControl(Next)")
            return

        # ----- A track was clicked in one of the rows or the page list -----
        if control_id in ID_ROW_LISTS or control_id == ID_PAGE_LIST:
            self._play_from_list(control_id)
            return

    # =====================================================================
    # Page rendering
    # =====================================================================

    def _show_home(self):
        self.setProperty("page", "home")
        self.setProperty("title", self.addon.getLocalizedString(30150))
        self.setProperty("subtitle", "")
        self.setProperty("page_empty", "false")

        # Read row config from settings. Each of the 4 rows has:
        #   - row1.type, row2.type, row3.type, row4.type
        # Defaults: likes / trending / playlists / following.
        # A row set to "off" is hidden.
        defaults = ["likes", "trending", "playlists", "following"]
        row_configs = []
        for i in range(1, 5):
            t = self.settings.get("row%d.type" % i) or defaults[i - 1]
            if t not in ROW_TYPES and t != "off":
                t = defaults[i - 1]
            row_configs.append(t)

        list_ids = ID_ROW_LISTS
        for idx, row_type in enumerate(row_configs, start=1):
            list_id = list_ids[idx - 1]
            visible = row_type != "off"
            self.setProperty("row%d_visible" % idx, "true" if visible else "false")

            if not visible:
                continue

            cfg = ROW_TYPES[row_type]
            title_strid = cfg["title_strid"]
            self.setProperty(
                "row%d_title" % idx,
                self.addon.getLocalizedString(title_strid)
            )

            # Limit comes from the items-per-page setting.
            limit = self._page_size()
            loader_name = cfg["loader"]
            try:
                loader = getattr(self, loader_name)
                loader(list_id, limit=limit)
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow %s failed: %s" %
                    (loader_name, str(e)),
                    xbmc.LOGERROR,
                )

    def _page_size(self):
        """Read items-per-page from settings, with a sensible default."""
        try:
            return int(self.settings.get("search.items.size") or 20)
        except (TypeError, ValueError):
            return 20

    # ---------- Row content loaders (each fills one fixedlist) ----------

    def _load_likes(self, list_id, limit=20):
        if not self.api.settings.get_oauth_token():
            self._load_trending(list_id, limit=limit)
            return
        try:
            user_id = self.api.get_my_user_id()
            if not user_id:
                self._load_trending(list_id, limit=limit)
                return
            collection = self.api.call(
                "/users/%d/track_likes?limit=%d" % (user_id, limit)
            )
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_likes failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _load_trending(self, list_id, limit=20):
        try:
            collection = self.api.charts({
                "kind": "trending",
                "genre": "soundcloud:genres:all-music",
                "limit": limit,
            })
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_trending failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _load_playlists(self, list_id, limit=20):
        if not self.api.settings.get_oauth_token():
            self._load_trending(list_id, limit=limit)
            return
        try:
            user_id = self.api.get_my_user_id()
            if not user_id:
                self._load_trending(list_id, limit=limit)
                return
            collection = self.api.call(
                "/users/%d/playlists_without_albums?limit=%d" % (user_id, limit)
            )
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_playlists failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _load_following(self, list_id, limit=20):
        if not self.api.settings.get_oauth_token():
            self._load_trending(list_id, limit=limit)
            return
        try:
            user_id = self.api.get_my_user_id()
            if not user_id:
                self._load_trending(list_id, limit=limit)
                return
            collection = self.api.call(
                "/users/%d/followings?limit=%d" % (user_id, limit)
            )
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_following failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _show_search(self):
        # For V2 step 1 we keep search simple: prompt for input, then show
        # the results in the generic page list.
        self.setProperty("page", "search")
        self.setProperty("title", self.addon.getLocalizedString(30101))
        self.setProperty("subtitle", "")

        query = xbmcgui.Dialog().input(self.addon.getLocalizedString(30160))
        if not query:
            self._show_home()
            return
        self.setProperty("subtitle", query)
        try:
            collection = self.api.search(query)
            self._fill_page_list(collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow search failed: %s" % str(e),
                xbmc.LOGERROR,
            )
            self._fill_page_list(None)

    def _show_likes(self):
        self.setProperty("page", "likes")
        self.setProperty("title", self.addon.getLocalizedString(30152))
        self.setProperty("subtitle", "")
        if not self._require_auth():
            return
        try:
            user_id = self.api.get_my_user_id()
            collection = self.api.call(
                "/users/%d/track_likes?limit=50" % user_id
            )
            self._fill_page_list(collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow likes failed: %s" % str(e),
                xbmc.LOGERROR,
            )
            self._fill_page_list(None)

    def _show_playlists(self):
        self.setProperty("page", "playlists")
        self.setProperty("title", self.addon.getLocalizedString(30153))
        self.setProperty("subtitle", "")
        if not self._require_auth():
            return
        try:
            user_id = self.api.get_my_user_id()
            collection = self.api.call(
                "/users/%d/playlists_without_albums?limit=50" % user_id
            )
            self._fill_page_list(collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow playlists failed: %s" % str(e),
                xbmc.LOGERROR,
            )
            self._fill_page_list(None)

    def _show_following(self):
        self.setProperty("page", "following")
        self.setProperty("title", self.addon.getLocalizedString(30154))
        self.setProperty("subtitle", "")
        if not self._require_auth():
            return
        try:
            user_id = self.api.get_my_user_id()
            collection = self.api.call("/users/%d/followings?limit=50" % user_id)
            self._fill_page_list(collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow following failed: %s" % str(e),
                xbmc.LOGERROR,
            )
            self._fill_page_list(None)

    # =====================================================================
    # Data loading helpers
    # =====================================================================

    def _load_likes_into(self, list_id, title_property, title_strid, limit=20):
        # Deprecated wrapper, kept temporarily for safety. Use _load_likes.
        self._load_likes(list_id, limit=limit)

    def _load_trending_into(self, list_id, title_property, title_strid, limit=20):
        # Deprecated wrapper, kept temporarily for safety. Use _load_trending.
        self._load_trending(list_id, limit=limit)

    def _fill_list(self, control_id, collection):
        """Push tracks/playlists/users into a fixedlist control."""
        try:
            control = self.getControl(control_id)
        except Exception:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow can't get control %d" % control_id,
                xbmc.LOGWARNING,
            )
            return

        # Reset any previous content and our internal cache.
        try:
            control.reset()
        except Exception:
            pass
        self._lists[control_id] = []

        if collection is None or not collection.items:
            return

        addon_base = "plugin://" + self.addon.getAddonInfo("id")
        for item in collection.items:
            try:
                play_url, list_item, _ = item.to_list_item(addon_base)
                control.addItem(list_item)
                self._lists[control_id].append((play_url, list_item))
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow skip item: %s" % str(e),
                    xbmc.LOGWARNING,
                )

    def _fill_page_list(self, collection):
        """
        Fills the generic page list with collection items, plus a
        synthetic "Next page" item at the end if the collection has
        more results (next_href).
        """
        # Remember the next-page link so we can load it when the user
        # selects the "Next page" item.
        self._next_href = (collection.next_href if collection else None)

        self._fill_list(ID_PAGE_LIST, collection)

        # Append "Next page" pseudo-item if there's more.
        if self._next_href:
            try:
                control = self.getControl(ID_PAGE_LIST)
                next_item = xbmcgui.ListItem(
                    label=self.addon.getLocalizedString(30901)  # "Next page"
                )
                next_item.setArt({
                    "thumb": "DefaultFolderForward.png",
                    "icon": "DefaultFolderForward.png",
                })
                next_item.setProperty("isNextPage", "true")
                control.addItem(next_item)
                self._lists[ID_PAGE_LIST].append((None, next_item))
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow add_next_page failed: %s" % str(e),
                    xbmc.LOGWARNING,
                )

        is_empty = collection is None or not collection.items
        self.setProperty("page_empty", "true" if is_empty else "false")
        try:
            self.setFocusId(ID_PAGE_LIST)
        except Exception:
            pass

    # =====================================================================
    # Playback
    # =====================================================================

    def _play_from_list(self, control_id):
        try:
            position = self.getControl(control_id).getSelectedPosition()
        except Exception:
            return

        items = self._lists.get(control_id, [])
        if position < 0 or position >= len(items):
            return

        play_url, list_item = items[position]

        # Handle the synthetic "Next page" item: load the next batch
        # from the cached next_href and replace the current page contents.
        if list_item.getProperty("isNextPage") == "true":
            if self._next_href:
                try:
                    collection = self.api.call(self._next_href)
                    self._fill_page_list(collection)
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::HomeWindow next_page failed: %s" % str(e),
                        xbmc.LOGERROR,
                    )
            return

        # If it's a folder (playlist/user), navigate into it via the page list.
        # If it's a track, queue the surrounding tracks and start playback.
        media_url = list_item.getProperty("mediaUrl")
        if media_url:
            self._play_with_queue(control_id, position)
        else:
            # Open the folder content in the page list.
            try:
                from urllib.parse import urlparse, parse_qs, unquote
                parsed = urlparse(play_url)
                qs = parse_qs(parsed.query)
                call_path = unquote(qs.get("call", [""])[0])
                if call_path:
                    self.setProperty("page", "browse")
                    self.setProperty("title", list_item.getLabel())
                    self.setProperty("subtitle", "")
                    collection = self.api.call(call_path)
                    self._fill_page_list(collection)
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow folder open failed: %s" % str(e),
                    xbmc.LOGERROR,
                )

    def _play_with_queue(self, control_id, start_position):
        """
        Build a Kodi music playlist from all the tracks visible in the
        given list, then start playback at the requested position. This
        gives the user automatic next-track playback without having to
        click each one manually.

        We intentionally hand Kodi the plugin:// resolver URLs (NOT the
        pre-resolved media URLs). Kodi will call our /play/ handler when
        it actually needs to start each track, so we resolve transcoding
        URLs just-in-time and avoid the 30-minute expiry window.

        When the autoplay setting is disabled, fall back to single-track
        play so the user gets the legacy "one track at a time" behaviour.
        """
        items = self._lists.get(control_id, [])
        if not items or start_position >= len(items):
            return

        # Setting "0" = autoplay off, anything else = on (default).
        autoplay = (self.settings.get("ui.autoplay") or "1") != "0"

        if not autoplay:
            # Legacy: just play the one clicked track.
            _, list_item = items[start_position]
            media_url = list_item.getProperty("mediaUrl")
            if media_url:
                self._play_track(media_url, list_item)
            return

        # Filter to tracks only (skip non-playable items in case the
        # list mixes types — shouldn't happen on the home rows but
        # belts and suspenders).
        track_items = [
            (url, li) for (url, li) in items
            if li.getProperty("mediaUrl")
        ]
        if not track_items:
            return

        # Find where the originally-clicked item lands in the filtered list.
        clicked_url = items[start_position][0]
        new_start = 0
        for i, (url, _) in enumerate(track_items):
            if url == clicked_url:
                new_start = i
                break

        try:
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            playlist.clear()
            for url, li in track_items:
                playlist.add(url=url, listitem=li)

            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow queued %d tracks, "
                "starting at position %d" % (len(track_items), new_start),
                xbmc.LOGINFO,
            )
            xbmc.Player().play(playlist, startpos=new_start)

            # Shuffle if the user enabled it. We call shuffle AFTER play()
            # so the clicked track plays first, then random thereafter.
            shuffle = (self.settings.get("ui.shuffle") or "false") == "true"
            if shuffle:
                xbmc.executebuiltin("PlayerControl(RandomOn)")
            else:
                xbmc.executebuiltin("PlayerControl(RandomOff)")
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow playlist queue failed: %s" % str(e),
                xbmc.LOGERROR,
            )
            # Fallback to single-track play so the user at least hears
            # the track they clicked.
            _, list_item = items[start_position]
            media_url = list_item.getProperty("mediaUrl")
            if media_url:
                self._play_track(media_url, list_item)

    def _play_track(self, media_url, list_item):
        """Single-track playback (used when autoplay is disabled)."""
        try:
            resolved = self.api.resolve_media_url(media_url)
            if not resolved:
                self._notify(self.addon.getLocalizedString(30126))
                return
            list_item.setPath(resolved)
            xbmc.Player().play(resolved, list_item)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow play failed: %s" % str(e),
                xbmc.LOGERROR,
            )
            self._notify(self.addon.getLocalizedString(30126))

    # =====================================================================
    # Helpers
    # =====================================================================

    def _require_auth(self):
        if self.api.settings.get_oauth_token():
            return True
        self._notify(self.addon.getLocalizedString(30024))
        self._fill_page_list(None)
        return False

    def _notify(self, message):
        try:
            xbmcgui.Dialog().notification(
                self.addon.getAddonInfo("name"),
                message,
                xbmcgui.NOTIFICATION_INFO,
                4000,
            )
        except Exception:
            pass

    def _highlight_playing_track(self):
        """
        Move the focus to the currently-playing track in whichever list
        contains it. Called by _PlayerObserver when playback changes.

        We compare against the plugin:// URL we passed to the playlist;
        when Kodi plays a track from our queue, getPlayingFile() returns
        the same URL (after Kodi has resolved it back through us).
        """
        try:
            playing = self._player_observer.getPlayingFile()
        except Exception:
            return
        if not playing:
            return

        # The playing file may be the resolved URL (api-v2.soundcloud.com/.../stream/hls)
        # rather than our plugin:// URL — Kodi caches resolved URLs internally.
        # Best signal we have: match by media_url substring.
        for control_id, items in self._lists.items():
            for idx, (play_url, list_item) in enumerate(items):
                if play_url and play_url in playing:
                    try:
                        # Move focus to that position. setSelectedPosition
                        # is the right call for xbmcgui.ControlList.
                        self.getControl(control_id).selectItem(idx)
                    except Exception as e:
                        xbmc.log(
                            "plugin.audio.soundcloud::HomeWindow highlight failed: %s" %
                            str(e),
                            xbmc.LOGDEBUG,
                        )
                    return


def open_home(api, addon, settings):
    """Public entry point — build and show the window modally."""
    addon_path = addon.getAddonInfo("path")
    window = SoundCloudHomeWindow(
        WINDOW_XML,
        addon_path,
        "default",
        "1080i",
        api=api,
        addon=addon,
        settings=settings,
    )
    window.doModal()
    del window
