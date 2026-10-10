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

from resources.lib.soundcloud.api_collection import ApiCollection


# Kodi action IDs (used by both NowPlayingDialog and SoundCloudHomeWindow,
# defined here at module top so both classes can reference them).
ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP = 3
ACTION_MOVE_DOWN = 4
ACTION_SELECT_ITEM = 7
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_NEXT_ITEM = 14
ACTION_PREV_ITEM = 15
ACTION_PLAYER_PLAY = 68
ACTION_STEP_FORWARD = 87
ACTION_STEP_BACK = 88
ACTION_NAV_BACK = 92
# Long-press / menu key on most remotes (opens the context menu).
ACTION_CONTEXT_MENU = 117

# How many seconds the left/right arrow keys seek when an audio
# track is playing. 10s feels right on a TV remote — small enough
# to land precisely, large enough that the user notices movement
# without holding the button down for 10 repeats.
SEEK_STEP_SECONDS = 10
# If the user presses Down within this many seconds of the start
# of a track, we treat it as "previous track". After this threshold,
# Down rewinds to the start of the current track instead. Mimics
# standard music-player behavior.
DOWN_PREV_THRESHOLD_SECONDS = 3


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

    # Control id of the mini-player play/pause button (set in the
    # XML). Its label is synced from Python because Kodi's $INFO has
    # no conditional form to show '>' when paused and 'II' otherwise.
    ID_PLAY_PAUSE = 521

    def __init__(self, window):
        super().__init__(daemon=True)
        self._player = xbmc.Player()
        self._stop_event = threading.Event()
        self._window = window  # needed for getControl()
        self._tick_count = 0  # for logging cadence
        self._last_pp_label = None  # cached play/pause icon

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

    def _sync_play_pause(self):
        """
        Keep the mini-player play/pause button (521) in sync: '>' (play)
        while paused, 'II' (pause) while playing. The XML label can't
        express the two states, so the icon is set from Python every
        tick; the value is cached to avoid spamming setLabel().
        """
        try:
            try:
                paused = self._player.isPaused()
            except Exception:
                paused = False
            label = "[B]>[/B]" if paused else "[B]II[/B]"
            if label != self._last_pp_label:
                self._window.getControl(self.ID_PLAY_PAUSE).setLabel(label)
                self._last_pp_label = label
        except Exception:
            # Control absent (mini-player "off" or window closing) - noop.
            pass

    def _tick(self):
        self._tick_count += 1

        # Sync the play/pause icon first, whatever the player state.
        self._sync_play_pause()

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

        # Remember the playback position for the premature-end resume
        # logic in _PlayerObserver.onPlayBackEnded. SoundCloud's signed
        # CDN URLs can expire mid-track on very long mixes; when that
        # happens the stream EOFs early and Kodi thinks the track is
        # over. These breadcrumbs let the observer detect the early end
        # and restart the track at the interrupted position with a
        # freshly-resolved URL.
        try:
            self._window._last_elapsed = elapsed
            self._window._last_duration = duration
            self._window._last_playlist_pos = xbmc.PlayList(
                xbmc.PLAYLIST_MUSIC
            ).getposition()
        except Exception:
            pass

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


class _AbortWatcher(threading.Thread):
    """
    Closes the home window when Kodi shuts down. Without this, the
    modal doModal() loop keeps the script alive at shutdown; Kodi
    waits 5 seconds then force-kills the interpreter ("script didn't
    stop in 5 seconds - let's kill it" + a threading SystemExit
    traceback in the log). Daemon thread: costs nothing while idle.
    """
    def __init__(self, window):
        super().__init__(daemon=True)
        self._window = window

    def run(self):
        monitor = xbmc.Monitor()
        monitor.waitForAbort()
        try:
            self._window.close()
            xbmc.log(
                "plugin.audio.soundcloud::AbortWatcher closed home "
                "window on Kodi shutdown",
                xbmc.LOGINFO,
            )
        except Exception:
            pass


class _SleepTimer(threading.Thread):
    """
    Sleep timer: counts EFFECTIVE listening time and stops playback
    once the configured number of minutes has elapsed ("effective" =
    the countdown only advances while audio is actually playing;
    pausing suspends it). One instance is (re)armed on every playback
    start; arming a new one cancels the previous. A parallel
    implementation lives in service.py so the timer also works with
    the full-screen UI closed (first timer to elapse wins).
    """
    POLL_SECONDS = 1.0

    def __init__(self, window):
        super().__init__(daemon=True)
        self._window = window
        self._elapsed = 0.0
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _target_seconds(self):
        try:
            minutes = int(
                self._window.settings.get("playback.sleep_timer") or 0
            )
        except Exception:
            return 0
        return max(0, minutes) * 60

    def run(self):
        import time

        while not self._cancelled:
            target = self._target_seconds()
            if target <= 0:
                # Setting off (or turned off mid-playback): exit.
                return
            try:
                if xbmc.Player().isPlayingAudio():
                    self._elapsed += self.POLL_SECONDS
                    if self._elapsed >= target:
                        xbmc.Player().stop()
                        try:
                            xbmcgui.Dialog().notification(
                                self._window.addon.getAddonInfo("name"),
                                self._window.addon.getLocalizedString(30358),
                                xbmcgui.NOTIFICATION_INFO,
                                4000,
                            )
                        except Exception:
                            pass
                        return
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::SleepTimer error: %s" % str(e),
                    xbmc.LOGWARNING,
                )
                return
            time.sleep(self.POLL_SECONDS)


class _PlayerObserver(xbmc.Player):
    """
    Subclass of xbmc.Player that gets notified when playback changes.
    We use it to:
      1. highlight the currently-playing track in the visible list
         (so focus follows the song as autoplay moves through the queue)
      2. open the "Now Playing" fullscreen dialog (Cinema/Waveform/etc.)
         on top of the home UI when audio starts, if the user enabled it
         in Settings > Playback > Fullscreen style
    """
    def __init__(self, window):
        super().__init__()
        self._window = window
        # Reference to the currently-open fullscreen dialog so we can
        # close it when playback stops or when the user dismisses it.
        # Stored on the observer (not the home window) so it survives
        # a re-init of the window if that happens.
        self._np_dialog = None
        # Pending screensaver delay timer (threading.Timer): the
        # fullscreen overlay opens only after playback.screensaver_delay
        # seconds, instead of hijacking the screen the moment a track
        # starts.
        self._ss_timer = None

    def onAVStarted(self):
        try:
            self._window._highlight_playing_track()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver onAVStarted: %s" % str(e),
                xbmc.LOGDEBUG,
            )
        # Open fullscreen overlay if user enabled one
        try:
            self._maybe_open_now_playing()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver fullscreen open "
                "failed: %s" % str(e),
                xbmc.LOGWARNING,
            )

    def onAVChange(self):
        try:
            self._window._highlight_playing_track()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver onAVChange: %s" % str(e),
                xbmc.LOGDEBUG,
            )

    def onPlayBackStopped(self):
        self._cancel_screensaver_timer()
        self._close_now_playing()

    def onPlayBackEnded(self):
        # When autoplay queues the next track, onPlayBackEnded fires
        # then onAVStarted fires again — we don't want to close+reopen
        # the fullscreen window between tracks (it would flash). So we
        # leave the dialog open here and rely on Player.* infolabels to
        # update inside the still-open dialog.
        #
        # We DO check whether this "end" was premature: SoundCloud's
        # signed CDN URLs (CloudFront Policy/Signature query params)
        # can expire mid-track on very long mixes. Kodi's file cache
        # then reads 0 bytes, retries with the same expired URL for a
        # while, and finally EOFs — ending the track way before its
        # real duration. When we detect that, we restart the same
        # playlist position (which re-resolves a FRESH stream URL via
        # our /play/ handler) and seek back to where it broke.
        try:
            self._maybe_resume_interrupted()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver resume check "
                "failed: %s" % str(e),
                xbmc.LOGWARNING,
            )

        # Endless playback: if the ended track was the LAST of the
        # queue, fetch related tracks and extend the playlist so the
        # music keeps going.
        try:
            self._maybe_extend_queue()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver endless queue "
                "extension failed: %s" % str(e),
                xbmc.LOGWARNING,
            )

    # How many seconds before the real end an "ended" event must occur
    # to be considered an interruption rather than a normal end.
    RESUME_MARGIN_SECONDS = 60
    # Give up after this many resume attempts for the same track, to
    # avoid an infinite loop if the stream is truly dead.
    MAX_RESUME_ATTEMPTS = 2

    def _maybe_resume_interrupted(self):
        w = self._window
        elapsed = getattr(w, "_last_elapsed", 0.0) or 0.0
        duration = getattr(w, "_last_duration", 0.0) or 0.0
        pos = getattr(w, "_last_playlist_pos", -1)

        if duration <= 0 or elapsed <= 0:
            return
        if elapsed >= duration - self.RESUME_MARGIN_SECONDS:
            return  # normal end of track

        key = (pos, int(duration))
        attempts = w._resume_attempts.get(key, 0)
        if attempts >= self.MAX_RESUME_ATTEMPTS:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver track at "
                "playlist pos %d keeps dying at %.0fs/%.0fs — giving up "
                "after %d resume attempts" %
                (pos, elapsed, duration, attempts),
                xbmc.LOGWARNING,
            )
            return
        w._resume_attempts[key] = attempts + 1

        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        if pos < 0 or pos >= playlist.size():
            return

        xbmc.log(
            "plugin.audio.soundcloud::PlayerObserver stream ended "
            "prematurely at %.0fs of %.0fs (playlist pos %d) — "
            "re-resolving and resuming (attempt %d)" %
            (elapsed, duration, pos, attempts + 1),
            xbmc.LOGINFO,
        )
        try:
            w._notify(w.addon.getLocalizedString(30295))
        except Exception:
            pass

        # Re-play the same playlist position. Kodi calls our /play/
        # handler again, which resolves a fresh stream URL (new
        # track_authorization JWT + fresh CloudFront signature). The
        # rest of the queue stays intact for the tracks after this one.
        target = max(0.0, elapsed - 5.0)
        xbmc.Player().play(playlist, startpos=pos)
        threading.Thread(
            target=self._seek_when_ready, args=(target,), daemon=True
        ).start()

    @staticmethod
    def _seek_when_ready(target_seconds):
        """
        Wait (max 20 s) for the restarted stream to become seekable,
        then jump to the interrupted position.
        """
        player = xbmc.Player()
        monitor = xbmc.Monitor()
        waited = 0.0
        while waited < 20.0 and not monitor.abortRequested():
            try:
                if player.isPlayingAudio() and player.getTotalTime() > 0:
                    player.seekTime(target_seconds)
                    xbmc.log(
                        "plugin.audio.soundcloud::PlayerObserver resumed "
                        "at %.0fs" % target_seconds,
                        xbmc.LOGINFO,
                    )
                    return
            except Exception:
                pass
            if monitor.waitForAbort(0.5):
                return
            waited += 0.5
        xbmc.log(
            "plugin.audio.soundcloud::PlayerObserver resume seek timed "
            "out (stream never became seekable)",
            xbmc.LOGWARNING,
        )

    def _maybe_extend_queue(self):
        """
        Endless playback: when the option is enabled and the track
        that just ended was the LAST of the Kodi queue, fetch
        SoundCloud's related tracks, append them, and continue playback
        at the first appended position (same playlist-restart pattern as
        the interrupted-stream auto-resume). Defensive by design: the
        /tracks/{id}/related endpoint is not part of the stable surface
        we use elsewhere — on any error this is a silent no-op.
        """
        w = self._window
        try:
            enabled = (w.settings.get("playback.endless") or "false") == "true"
        except Exception:
            enabled = False
        if not enabled:
            return

        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        try:
            size = int(playlist.size() or 0)
            position = int(playlist.getposition() or -1)
        except Exception:
            return
        if size <= 0 or position != size - 1:
            # Not the last track of the queue — normal autoplay
            # continues; nothing to do.
            return

        try:
            last_item = playlist[position]
            track_id = (
                last_item.getProperty("soundcloud.track_id") or ""
            ).strip()
        except Exception:
            track_id = ""
        if not track_id:
            return

        # Anti-loop guards: never extend twice from the same track,
        # never append a track that was already appended (or used as
        # an extension source) earlier in the session.
        extended = getattr(w, "_endless_extended", None)
        added = getattr(w, "_endless_added", None)
        if extended is None:
            extended = w._endless_extended = set()
        if added is None:
            added = w._endless_added = set()
        if track_id in extended:
            return
        extended.add(track_id)

        try:
            skip_previews = (
                (w.settings.get("playback.skip_excerpts") or "false")
                == "true"
            )
        except Exception:
            skip_previews = False

        try:
            related = w.api.related_tracks(track_id, limit=10)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver endless queue "
                "fetch failed: %s" % str(e),
                xbmc.LOGWARNING,
            )
            return
        items = getattr(related, "items", None) or []

        addon_base = "plugin://" + w.addon.getAddonInfo("id")
        new_items = []
        for item in items:
            if not getattr(item, "media", ""):
                continue
            # Honour the "Skip Go+ excerpts" option.
            if skip_previews and getattr(item, "preview", False):
                continue
            url, li, _ = item.to_list_item(addon_base)
            if not li.getProperty("mediaUrl"):
                continue
            item_id = (li.getProperty("soundcloud.track_id") or "").strip()
            if item_id and (item_id in added or item_id in extended):
                continue
            if item_id:
                added.add(item_id)
            new_items.append((url, li))

        if not new_items:
            return

        for url, li in new_items:
            playlist.add(url=url, listitem=li)

        xbmc.log(
            "plugin.audio.soundcloud::PlayerObserver endless queue: "
            "appending %d related tracks after track %s" %
            (len(new_items), track_id),
            xbmc.LOGINFO,
        )
        # Continue at the first appended track: the ended position was
        # the last of the old queue, so index 'size' (the old length)
        # lands exactly on the first new item. Older tracks are kept
        # so "previous" navigation still works.
        xbmc.Player().play(playlist, startpos=size)

    def _maybe_open_now_playing(self):
        """Open the configured fullscreen overlay, if any, and only if
        not already open. Honours the playback.screensaver on/off
        toggle and the playback.screensaver_delay setting."""
        enabled = (self._window.settings.get("playback.screensaver")
                   or "true").strip().lower() == "true"
        style = (self._window.settings.get("playback.fullscreen_style")
                 or "off").strip()
        xbmc.log(
            "plugin.audio.soundcloud::PlayerObserver _maybe_open_now_"
            "playing setting=%r enabled=%s np_dialog_is_set=%s" %
            (style, enabled, self._np_dialog is not None),
            xbmc.LOGINFO,
        )
        if not enabled or style in ("", "off"):
            return
        if self._np_dialog is not None:
            # Already open — just leave it; infolabels will refresh.
            return

        delay = 30
        try:
            delay = int(float((self._window.settings.get(
                "playback.screensaver_delay") or "30").strip() or "30"))
        except Exception:
            delay = 30
        if delay <= 0:
            self._open_now_playing()
            return
        self._cancel_screensaver_timer()
        self._ss_timer = threading.Timer(delay, self._open_now_playing_safely)
        self._ss_timer.daemon = True
        self._ss_timer.start()

    def _cancel_screensaver_timer(self):
        """Cancel a pending screensaver delay timer, if any."""
        timer, self._ss_timer = self._ss_timer, None
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass

    def _open_now_playing_safely(self):
        """Timer callback: open the overlay if playback is still up."""
        self._ss_timer = None
        try:
            if xbmc.Player().isPlayingAudio():
                self._open_now_playing()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver screensaver "
                "open failed: %s" % str(e),
                xbmc.LOGWARNING,
            )

    def _open_now_playing(self):
        """Open the configured fullscreen overlay right now (defensive
        re-checks: the settings may have changed while a delay timer
        was pending, and the dialog may already be open)."""
        style = (self._window.settings.get("playback.fullscreen_style")
                 or "off").strip()
        if style in ("", "off"):
            return
        if self._np_dialog is not None:
            # Already open — just leave it; infolabels will refresh.
            return

        xml_for_style = {
            "cinema": "script-soundcloud-now-playing-cinema.xml",
            "waveform": "script-soundcloud-now-playing-waveform.xml",
            "editorial": "script-soundcloud-now-playing-editorial.xml",
            "vinyl": "script-soundcloud-now-playing-vinyl.xml",
        }
        xml_file = xml_for_style.get(style)
        if not xml_file:
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver fullscreen style "
                "'%s' not yet implemented — falling back to no overlay" %
                style, xbmc.LOGINFO,
            )
            return

        # Extract cover URL from Kodi infolabel — that one is reliably
        # available because Kodi sets it from the playing ListItem.
        cover_url = ""
        try:
            cover_url = xbmc.getInfoLabel("Player.Art(thumb)") or ""
        except Exception:
            pass

        # Read the waveform_url and description that were stashed in
        # window properties by _play_with_queue when the user clicked
        # the track. Avoids an extra API call here.
        waveform_url = ""
        description = ""
        if style == "waveform":
            try:
                waveform_url = self._window.getProperty(
                    "soundcloud.last_played_waveform_url"
                ) or ""
            except Exception:
                pass
        if style == "editorial":
            try:
                description = self._window.getProperty(
                    "soundcloud.last_played_description"
                ) or ""
            except Exception:
                pass

        addon_path = self._window.addon.getAddonInfo("path")
        try:
            self._np_dialog = NowPlayingDialog(
                xml_file, addon_path, "default", "1080i",
                observer=self,
                style=style,
                cover_url=cover_url,
                waveform_url=waveform_url,
                description=description,
            )
            self._np_dialog.show()
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver opened fullscreen "
                "'%s' (cover=%s, waveform=%s, descr=%d chars)" %
                (style, bool(cover_url), bool(waveform_url),
                 len(description)),
                xbmc.LOGINFO,
            )
        except Exception as e:
            self._np_dialog = None
            xbmc.log(
                "plugin.audio.soundcloud::PlayerObserver could not open "
                "fullscreen '%s': %s" % (style, str(e)),
                xbmc.LOGWARNING,
            )

    def _close_now_playing(self):
        """Close the fullscreen overlay if open."""
        if self._np_dialog is None:
            return
        try:
            self._np_dialog.close()
        except Exception:
            pass
        self._np_dialog = None


class NowPlayingDialog(xbmcgui.WindowXMLDialog):
    """
    Generic fullscreen "now playing" overlay. The actual look is
    determined by the XML file passed at construction (Cinema, Waveform,
    Vinyl or Editorial).

    Most visual state comes from $INFO[Player.*] infolabels.

    Cinema style: just a progress bar updater.
    Waveform style: ALSO fetches the waveform JSON, generates a blurred
    background, and animates the bars from grey -> orange as the track
    progresses.
    """
    # Control IDs (must match the XML files)
    # Cinema:
    ID_CINEMA_PROGRESS_FILL = 9100
    CINEMA_BAR_WIDTH = 600

    # Waveform style (now visualizer-style: bars heights animated):
    ID_WAVEFORM_BG = 9100
    ID_WAVEFORM_PROGRESS_FG = 9151
    WAVEFORM_PROGRESS_BAR_WIDTH = 1520
    WAVEFORM_NUM_BARS = 90
    WAVEFORM_BAR_BASE = 9200  # single set of orange bars; heights animated
    WAVEFORM_BAR_AREA_HEIGHT = 100
    WAVEFORM_BAR_AREA_TOP = 880

    # Editorial style:
    ID_EDITORIAL_BG = 9100
    ID_EDITORIAL_QUOTE = 9010
    ID_EDITORIAL_PROGRESS_FG = 9151
    EDITORIAL_PROGRESS_BAR_WIDTH = 1080

    # Vinyl style:
    ID_VINYL_BG = 9100
    ID_VINYL_PROGRESS_FG = 9151
    VINYL_PROGRESS_BAR_WIDTH = 820

    def __init__(self, *args, **kwargs):
        self._observer = kwargs.pop("observer", None)
        # Style: "cinema", "waveform", "vinyl", "editorial".
        # Determines which behaviour the dialog applies.
        self._style = kwargs.pop("style", "cinema")
        # Track metadata for waveform/blur generation. Set externally
        # before show() — we don't fetch it ourselves because the
        # observer already has API access.
        self._cover_url = kwargs.pop("cover_url", "")
        self._waveform_url = kwargs.pop("waveform_url", "")
        # Track description (long text) — used for the editorial
        # style's pull quote. May be empty for tracks that don't have
        # one (most user uploads, sadly).
        self._description = kwargs.pop("description", "")
        super().__init__(*args, **kwargs)
        self._progress_updater = None
        self._waveform_samples = None  # 90 floats 0..1, set by prep thread
        self._dominant_colour = "FF5500"  # default orange, may be overridden

    def onInit(self):
        xbmc.log(
            "plugin.audio.soundcloud::NowPlayingDialog onInit style=%s "
            "cover_url=%r waveform_url=%r descr=%d chars" %
            (self._style, self._cover_url[:80], self._waveform_url[:80],
             len(self._description)),
            xbmc.LOGINFO,
        )
        # Kick off the right behaviour depending on style.
        try:
            if self._style == "waveform":
                self._init_waveform()
            elif self._style == "editorial":
                self._init_editorial()
            elif self._style == "vinyl":
                self._init_vinyl()
            else:
                # cinema (default)
                self._progress_updater = _NowPlayingProgressUpdater(self)
                self._progress_updater.start()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::NowPlayingDialog onInit FAILED: "
                "%s" % str(e),
                xbmc.LOGERROR,
            )
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)

    def _init_editorial(self):
        """Set up the editorial display: populate the pull quote label
        (the description text) and start the editorial progress
        updater (thin orange bar at the bottom of the right column)."""
        # 1. Pull quote: clean up the description and set it on the
        # quote label (id 9010). SoundCloud descriptions often contain
        # raw URLs and hashtag spam — we strip those for readability.
        # If there's no description, we leave the quote empty rather
        # than padding with derived metadata (genre/year) — empty
        # whitespace looks intentional, fake filler does not.
        clean = self._clean_description(self._description)
        try:
            self.getControl(self.ID_EDITORIAL_QUOTE).setLabel(clean)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::NowPlayingDialog could not set "
                "editorial pull quote: %s" % str(e),
                xbmc.LOGDEBUG,
            )

        # 2. Optional Pillow blurred bg in a background thread.
        # Reuse the same helper used by waveform.
        prep = threading.Thread(
            target=self._prepare_editorial_assets, daemon=True
        )
        prep.start()

        # 3. Start the editorial progress updater (drives the thin
        # orange progress bar that fills as the track plays).
        self._progress_updater = _EditorialProgressUpdater(self)
        self._progress_updater.start()

    def _prepare_editorial_assets(self):
        """Background: install the blurred cover as the editorial bg
        if Pillow is available. Silently skipped otherwise."""
        try:
            from resources.lib.kodi import imagehelpers
            if not self._cover_url:
                return
            blurred_path = imagehelpers.get_blurred_cover(
                self._cover_url, blur_radius=30
            )
            if blurred_path and blurred_path != self._cover_url:
                # Only swap if we actually got a different (blurred) file
                self.getControl(self.ID_EDITORIAL_BG).setImage(blurred_path)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::NowPlayingDialog editorial bg "
                "blur failed: %s" % str(e),
                xbmc.LOGDEBUG,
            )

    def _init_vinyl(self):
        """Set up the vinyl display. The disc rotation is handled
        natively by Kodi via <animation effect="rotate" loop="true">
        in the XML — Python only needs to install the blurred bg and
        start the progress bar updater. We reuse the editorial
        updater because the only difference is bar width (820 vs
        1080) and that's parameterised via the dialog constants."""
        # 1. Optional Pillow blurred bg in a background thread.
        prep = threading.Thread(
            target=self._prepare_vinyl_assets, daemon=True
        )
        prep.start()

        # 2. Start the progress bar updater. We use the editorial
        # updater class but it reads VINYL_PROGRESS_BAR_WIDTH and
        # ID_VINYL_PROGRESS_FG, so we override at construction.
        self._progress_updater = _VinylProgressUpdater(self)
        self._progress_updater.start()

    def _prepare_vinyl_assets(self):
        """Background: install the blurred cover as the vinyl bg if
        Pillow is available. Silently skipped otherwise."""
        try:
            from resources.lib.kodi import imagehelpers
            if not self._cover_url:
                return
            blurred_path = imagehelpers.get_blurred_cover(
                self._cover_url, blur_radius=30
            )
            if blurred_path and blurred_path != self._cover_url:
                self.getControl(self.ID_VINYL_BG).setImage(blurred_path)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::NowPlayingDialog vinyl bg "
                "blur failed: %s" % str(e),
                xbmc.LOGDEBUG,
            )

    @staticmethod
    def _clean_description(raw):
        """Strip hashtags, URLs, excessive whitespace from a SoundCloud
        track description so it reads as editorial body copy. Truncate
        to ~280 chars (a tweet's worth) so the layout doesn't overflow
        the pull-quote area."""
        if not raw:
            return ""
        import re
        # Strip URLs
        s = re.sub(r"https?://\S+", "", raw)
        # Strip hashtag chains at the end (common SoundCloud pattern)
        s = re.sub(r"(#\S+\s*)+$", "", s)
        # Collapse whitespace runs
        s = re.sub(r"\s+", " ", s).strip()
        # Truncate
        if len(s) > 280:
            # Cut at the last sentence boundary before 280 chars if any
            cut = s[:280].rsplit(".", 1)[0]
            if len(cut) < 80:
                # Sentence boundary too early — just hard-cut with ellipsis
                cut = s[:277].rstrip() + "..."
            else:
                cut = cut.rstrip() + "."
            s = cut
        return s

    def _init_waveform(self):
        """Set up the waveform display: launch a background thread to
        download blur+samples, then start the per-tick foreground bar
        updater. The bar areas stay flat until the prep thread fills
        them in."""
        xbmc.log(
            "plugin.audio.soundcloud::NowPlayingDialog _init_waveform "
            "starting prep thread + progress updater",
            xbmc.LOGINFO,
        )
        # 1. Start a thread that does the heavy lifting (network +
        # PIL operations) without blocking the UI.
        prep = threading.Thread(target=self._prepare_waveform_assets,
                                daemon=True)
        prep.start()

        # 2. Start the foreground bar progress updater (refreshes which
        # bars should be orange based on Player.Time / Duration).
        self._progress_updater = _VisualizerUpdater(self)
        self._progress_updater.start()

    def _prepare_waveform_assets(self):
        """Background thread: download waveform JSON, generate blurred
        background, extract dominant colour. Updates the dialog's
        controls when each piece arrives (no waiting for everything).

        Note: in visualizer mode we no longer fetch the SoundCloud
        waveform JSON — the bar heights are animated in real time by
        the _VisualizerUpdater thread, not derived from a static
        waveform shape. We keep this thread for the (optional) Pillow
        blurred background and dominant colour extraction."""
        xbmc.log(
            "plugin.audio.soundcloud::NowPlayingDialog _prepare_waveform_"
            "assets thread started",
            xbmc.LOGINFO,
        )
        try:
            from resources.lib.kodi import imagehelpers
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::NowPlayingDialog could not import "
                "imagehelpers: %s" % str(e),
                xbmc.LOGERROR,
            )
            return

        # 1. Blurred background (Pillow only — gracefully no-op without it)
        if self._cover_url:
            try:
                blurred_path = imagehelpers.get_blurred_cover(
                    self._cover_url, blur_radius=20
                )
                if blurred_path:
                    self.getControl(self.ID_WAVEFORM_BG)\
                        .setImage(blurred_path)
                    xbmc.log(
                        "plugin.audio.soundcloud::NowPlaying applied "
                        "blurred bg: %s" % blurred_path,
                        xbmc.LOGDEBUG,
                    )
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::NowPlaying blurred bg "
                    "failed: %s" % str(e), xbmc.LOGDEBUG,
                )

        # 2. Dominant colour (currently unused, kept for future styles)
        try:
            self._dominant_colour = imagehelpers.get_dominant_colour(
                self._cover_url
            )
        except Exception:
            pass

    def onAction(self, action):
        action_id = action.getId()

        # Back/menu/exit closes the overlay.
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK,
                         ACTION_PARENT_DIR):
            self.close()
            if self._observer is not None:
                self._observer._np_dialog = None
            return

        # Playback control keys. We resolve the player lazily — if
        # nothing is playing (which shouldn't happen here since the
        # overlay only opens during playback, but defensive code is
        # cheap), all of these become no-ops.
        try:
            player = xbmc.Player()
            if not player.isPlayingAudio():
                return

            # Left/Right: seek backward/forward. The step comes from
            # Settings > Playback > Seek interval (10 s historically).
            # Fall back to the module default if the setting can't be
            # read (defensive: observer/window may be unavailable).
            try:
                seek_step = int(
                    self._observer._window.settings.get(
                        "playback.seek_interval"
                    ) or SEEK_STEP_SECONDS
                )
            except Exception:
                seek_step = SEEK_STEP_SECONDS
            if seek_step < 1:
                seek_step = SEEK_STEP_SECONDS

            # Clamp to [0, totalTime] so we don't crash on edge cases.
            if action_id == ACTION_MOVE_LEFT or action_id == ACTION_STEP_BACK:
                try:
                    current = player.getTime()
                    target = max(0.0, current - seek_step)
                    player.seekTime(target)
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::NowPlayingDialog "
                        "seek backward failed: %s" % str(e),
                        xbmc.LOGWARNING,
                    )
                return

            if action_id == ACTION_MOVE_RIGHT or action_id == ACTION_STEP_FORWARD:
                try:
                    current = player.getTime()
                    total = player.getTotalTime()
                    target = min(total - 0.5, current + seek_step)
                    if target > current:
                        player.seekTime(target)
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::NowPlayingDialog "
                        "seek forward failed: %s" % str(e),
                        xbmc.LOGWARNING,
                    )
                return

            # OK/Enter and the play-pause button both toggle pause.
            if action_id in (ACTION_SELECT_ITEM, ACTION_PLAYER_PLAY):
                try:
                    player.pause()
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::NowPlayingDialog "
                        "pause toggle failed: %s" % str(e),
                        xbmc.LOGWARNING,
                    )
                return

            # Up: next track in the playlist. Equivalent to the
            # "Next" button most music players have.
            if action_id in (ACTION_MOVE_UP, ACTION_NEXT_ITEM):
                try:
                    player.playnext()
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::NowPlayingDialog "
                        "playnext failed: %s" % str(e),
                        xbmc.LOGWARNING,
                    )
                return

            # Down: standard music-player behavior. If we're more
            # than DOWN_PREV_THRESHOLD_SECONDS into the current track,
            # rewind it to 0. Otherwise jump to the previous track.
            # This matches the "Previous" button on most car stereos,
            # phones, and physical CD players.
            if action_id in (ACTION_MOVE_DOWN, ACTION_PREV_ITEM):
                try:
                    current = player.getTime()
                    if current > DOWN_PREV_THRESHOLD_SECONDS:
                        player.seekTime(0.0)
                    else:
                        player.playprevious()
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::NowPlayingDialog "
                        "previous failed: %s" % str(e),
                        xbmc.LOGWARNING,
                    )
                return
        except Exception as e:
            # Catch-all so we never bring down the UI on an action.
            xbmc.log(
                "plugin.audio.soundcloud::NowPlayingDialog onAction "
                "unexpected error: %s" % str(e),
                xbmc.LOGWARNING,
            )

    def close(self):
        try:
            if self._progress_updater is not None:
                self._progress_updater.stop()
        except Exception:
            pass
        super().close()


class _NowPlayingProgressUpdater(threading.Thread):
    """
    Cinema-style progress: poll the player every 500ms and resize the
    orange fill control via Python's setWidth().
    """
    def __init__(self, dialog):
        super().__init__(daemon=True)
        self._dialog = dialog
        self._player = xbmc.Player()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop_event.wait(0.5)

    def _tick(self):
        if not self._player.isPlayingAudio():
            return
        try:
            elapsed = self._player.getTime()
            duration = self._player.getTotalTime()
        except Exception:
            return
        if not duration or duration <= 0:
            return
        ratio = max(0.0, min(1.0, elapsed / duration))
        width = max(1, int(NowPlayingDialog.CINEMA_BAR_WIDTH * ratio))
        try:
            self._dialog.getControl(NowPlayingDialog.ID_CINEMA_PROGRESS_FILL)\
                .setWidth(width)
        except Exception:
            pass


class _VisualizerUpdater(threading.Thread):
    """
    Animates the 90 orange bars with pseudo-audio-reactive heights to
    SIMULATE a real-time audio visualizer. Kodi's Python API doesn't
    expose audio samples to addons, so we can't make a true visualizer
    — but a well-tuned animation pattern is indistinguishable from one
    for a casual user.

    Pattern logic (per tick, ~80ms cadence):
      - Bars 0..30 (left, "bass"): slow undulation, medium amplitude
      - Bars 30..60 (middle, "mids"): faster variation, high amplitude
      - Bars 60..90 (right, "highs"): rapid flicker, lower amplitude

    Each bar's target height is recomputed every tick from a smooth
    sinusoid + a small random perturbation, then setHeight is applied.

    The thread also updates the thin progress bar above the
    visualizer based on real Player.Time / Duration so the user has
    an accurate playback indicator.
    """
    # Animation cadence in seconds. 80ms = 12.5 FPS — fast enough to
    # feel alive, slow enough to not hammer Kodi's UI thread.
    TICK_INTERVAL = 0.08

    def __init__(self, dialog):
        super().__init__(daemon=True)
        self._dialog = dialog
        self._player = xbmc.Player()
        self._stop_event = threading.Event()
        # Per-bar phase offsets so they don't all peak together.
        # Pre-computed once at thread creation.
        import random
        rng = random.Random(42)  # deterministic so behaviour is reproducible
        self._phases = [rng.uniform(0, 6.28) for _ in
                        range(NowPlayingDialog.WAVEFORM_NUM_BARS)]
        # Counter that drives the sinusoids. Incremented each tick.
        self._t = 0.0

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::VisualizerUpdater "
                    "tick error: %s" % str(e),
                    xbmc.LOGDEBUG,
                )
            self._stop_event.wait(self.TICK_INTERVAL)

    def _tick(self):
        if not self._player.isPlayingAudio():
            return

        # 1. Update the progress bar based on real Player.Time
        try:
            elapsed = self._player.getTime()
            duration = self._player.getTotalTime()
            if duration and duration > 0:
                ratio = max(0.0, min(1.0, elapsed / duration))
                width = max(
                    1, int(NowPlayingDialog.WAVEFORM_PROGRESS_BAR_WIDTH * ratio)
                )
                self._dialog.getControl(
                    NowPlayingDialog.ID_WAVEFORM_PROGRESS_FG
                ).setWidth(width)
        except Exception:
            pass

        # 2. Animate bar heights to simulate audio reactivity
        import math
        import random
        self._t += self.TICK_INTERVAL

        n = NowPlayingDialog.WAVEFORM_NUM_BARS
        max_h = NowPlayingDialog.WAVEFORM_BAR_AREA_HEIGHT
        top_base = NowPlayingDialog.WAVEFORM_BAR_AREA_TOP
        for i in range(n):
            # Frequency band: 0=bass (slow), 1=mid, 2=highs (fast).
            band = i / n  # 0..1 left to right
            if band < 0.33:
                # Bass: slow rolling motion, ~0.6 cycles/sec
                freq = 1.5
                amp_base = 0.55
                noise = random.uniform(-0.1, 0.1)
            elif band < 0.66:
                # Mids: faster, more variable
                freq = 4.0
                amp_base = 0.65
                noise = random.uniform(-0.2, 0.2)
            else:
                # Highs: rapid flicker, smaller
                freq = 8.0
                amp_base = 0.4
                noise = random.uniform(-0.3, 0.3)

            # Sinusoidal motion + per-bar phase offset + random noise
            sine = (math.sin(self._t * freq + self._phases[i]) + 1.0) / 2.0
            target = amp_base * sine + noise
            target = max(0.05, min(1.0, target))
            h = max(4, int(target * max_h))
            new_top = top_base + max_h - h

            try:
                bar = self._dialog.getControl(
                    NowPlayingDialog.WAVEFORM_BAR_BASE + i
                )
                bar.setHeight(h)
                bar.setPosition(bar.getPosition()[0], new_top)
            except Exception:
                # Dialog might be closing — bail out for this tick
                return


class _EditorialProgressUpdater(threading.Thread):
    """
    Drives the thin orange progress bar at the bottom of the editorial
    layout. Same pattern as the cinema updater (poll Player.Time every
    500ms, resize the orange fill control via setWidth) but targets a
    different control id and a wider bar (1080px instead of 600px).
    """
    def __init__(self, dialog):
        super().__init__(daemon=True)
        self._dialog = dialog
        self._player = xbmc.Player()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop_event.wait(0.5)

    def _tick(self):
        if not self._player.isPlayingAudio():
            return
        try:
            elapsed = self._player.getTime()
            duration = self._player.getTotalTime()
        except Exception:
            return
        if not duration or duration <= 0:
            return
        ratio = max(0.0, min(1.0, elapsed / duration))
        width = max(
            1, int(NowPlayingDialog.EDITORIAL_PROGRESS_BAR_WIDTH * ratio)
        )
        try:
            self._dialog.getControl(
                NowPlayingDialog.ID_EDITORIAL_PROGRESS_FG
            ).setWidth(width)
        except Exception:
            pass


class _VinylProgressUpdater(threading.Thread):
    """
    Drives the thin orange progress bar in the vinyl style. Same
    pattern as the cinema/editorial updaters, just targeting different
    constants (VINYL_PROGRESS_BAR_WIDTH=820, ID_VINYL_PROGRESS_FG=9151).

    NOTE: the disc rotation itself is NOT driven by Python — it's a
    native Kodi <animation effect="rotate" loop="true"> in the XML.
    That's why the rotation stays smooth even when Python is busy
    doing other work.
    """
    def __init__(self, dialog):
        super().__init__(daemon=True)
        self._dialog = dialog
        self._player = xbmc.Player()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop_event.wait(0.5)

    def _tick(self):
        if not self._player.isPlayingAudio():
            return
        try:
            elapsed = self._player.getTime()
            duration = self._player.getTotalTime()
        except Exception:
            return
        if not duration or duration <= 0:
            return
        ratio = max(0.0, min(1.0, elapsed / duration))
        width = max(
            1, int(NowPlayingDialog.VINYL_PROGRESS_BAR_WIDTH * ratio)
        )
        try:
            self._dialog.getControl(
                NowPlayingDialog.ID_VINYL_PROGRESS_FG
            ).setWidth(width)
        except Exception:
            pass


WINDOW_XML = "script-soundcloud-home.xml"

# Sidebar buttons
ID_NAV_HOME = 110
ID_NAV_SEARCH = 111
ID_NAV_LIKES = 112
ID_NAV_PLAYLISTS = 113
ID_NAV_FOLLOWING = 114
ID_NAV_SETTINGS = 115
ID_NAV_STATIONS = 116
# (ID 116 was the legacy interface button — removed in 5.2.4; it is now
# the "Stations" entry of the side menu.)

# Page lists / row lists
ID_ROW1_LIST = 350
ID_ROW2_LIST = 351
ID_ROW3_LIST = 352
ID_ROW4_LIST = 353
ID_ROW_LISTS = (ID_ROW1_LIST, ID_ROW2_LIST, ID_ROW3_LIST, ID_ROW4_LIST)
ID_PAGE_LIST = 400
# Vertical mirror of the page list shown in the "list" layout on
# non-home pages (the card panel 400 covers the "sidebar" layout).
# Both containers are always filled with the same content, so
# switching layouts live never needs a re-fetch.
ID_PAGE_LIST_L = 401
# Vertical list shown on the home page in the "list" layout.
ID_HOME_LIST = 354
# Max items per section of the sectioned home list ("list" layout).
HOME_SECTION_LIMIT = 10
# Genre chips shown on the home page above the list in the "list"
# layout. Ids 360..367, one per GENRE_URNS entry, in the same order.
ID_GENRE_CHIPS = (360, 361, 362, 363, 364, 365, 366, 367)

# Available row types — used to map a setting value to a content loader.
# Localized titles use the corresponding string ID.
ROW_TYPES = {
    "likes":     {"title_strid": 30152, "loader": "_load_likes"},
    "trending":  {"title_strid": 30155, "loader": "_load_trending"},
    "playlists": {"title_strid": 30153, "loader": "_load_playlists"},
    "following": {"title_strid": 30154, "loader": "_load_following"},
    "history":   {"title_strid": 30382, "loader": "_load_history"},
    "foryou":    {"title_strid": 30383, "loader": "_load_foryou"},
    "based":     {"title_strid": 30384, "loader": "_load_based"},
    "curated":   {"title_strid": 30385, "loader": "_load_curated"},
    "buzzing":   {"title_strid": 30386, "loader": "_load_buzzing"},
}

# Localized labels of the trending genres live in the .po files
# (string ids 30365..30376) and are shown by the genre chips of the
# home page in BOTH layouts.

# Order of the genre chips shown on the home page. MUST match the
GENRE_URNS = (
    "soundcloud:genres:all-music",
    "soundcloud:genres:techno",
    "soundcloud:genres:house",
    "soundcloud:genres:deephouse",
    "soundcloud:genres:electronic",
    "soundcloud:genres:hiphop",
    "soundcloud:genres:ambient",
    "soundcloud:genres:jazz",
)

# Mini-player buttons
ID_MP_PREV = 520
ID_MP_PLAY = 521
ID_MP_NEXT = 522


class SoundCloudHomeWindow(xbmcgui.WindowXMLDialog):
    """Full-screen home window."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = kwargs.get("api")
        self.addon = kwargs.get("addon")
        self.settings = kwargs.get("settings")

        # Optional track id to play immediately after the window opens
        # (widget track click → full UI with the track playing), plus
        # the widget category it came from (for continuous playback).
        self._startup_track_id = kwargs.get("startup_track_id")
        self._startup_track_source = kwargs.get("startup_track_source")

        # Track which collections we have loaded for which control id, so
        # onClick can resolve the index back to the actual track to play.
        # Key: control_id, Value: list of (play_url, ListItem) tuples.
        self._lists = {}

        # Cached next-page link for the page list (set by _fill_page_list).
        self._next_href = None

        # Navigation history stack — pushed every time we change "page"
        # (home, browse, likes, playlists, etc.) so that Back can pop the
        # previous state instead of closing the whole window.
        # Each entry is a callable that re-renders the previous state.
        self._nav_stack = []

        # Player observer to follow the currently-playing track in the UI.
        # We keep a reference so it doesn't get garbage-collected.
        self._player_observer = _PlayerObserver(self)

        # Breadcrumbs written by _ProgressUpdater and read by the
        # observer's premature-end resume logic.
        self._last_elapsed = 0.0
        self._last_duration = 0.0
        self._last_playlist_pos = -1
        self._resume_attempts = {}
        # Endless-playback bookkeeping: track ids used as extension
        # source, and ids appended by endless mode (anti-loop /
        # anti-duplicate guards).
        self._endless_extended = set()
        self._endless_added = set()
        # Sleep-timer thread — (re)armed on every playback start.
        self._sleep_timer_thread = None

        # Closes this window on Kodi shutdown so the script exits
        # cleanly instead of being force-killed after 5 seconds.
        self._abort_watcher = _AbortWatcher(self)

        # Progress bar updater — created here, started in onInit() once
        # the controls actually exist in the GUI tree. Starting it from
        # __init__ would be too early: getControl() would fail because
        # Kodi hasn't built the window yet.
        self._progress_updater = _ProgressUpdater(self)

    # =====================================================================
    # Lifecycle
    # =====================================================================

    def onInit(self):
        xbmc.log(
            "plugin.audio.soundcloud::SoundCloudHomeWindow onInit "
            "(skin XML loaded, ready to populate)",
            xbmc.LOGINFO,
        )

        # Apply layout from settings.
        # 1 = side menu + rows ("cards"), 2 = side menu + trending
        # list. The old "rows only" layout (which hid the side menu
        # and left no way back to the addon settings from the
        # interface) was removed - the side menu is now ALWAYS visible.
        # A stale persisted value of 0 (or the empty string a freshly
        # installed setting can return) falls back to the cards layout.
        layout_setting = (self.settings.get("ui.layout") or "1").strip()
        layout = {"1": "sidebar", "2": "list"}.get(
            layout_setting, "sidebar"
        )
        self.setProperty("layout", layout)
        # Genre of the trending list (highlights the matching chip).
        self.setProperty("trending_genre", self._trending_genre())

        # Apply miniplayer mode from settings.
        # 0 = off (hidden - the content takes the full screen height),
        # 1 = compact (cover + title + progress bar). A stale stored
        # "2" (the old removed "display + controls" mode) falls back
        # to compact.
        mp_setting = self.settings.get("ui.miniplayer") or "1"
        mp_mode = {"0": "off", "1": "compact"}.get(mp_setting, "compact")
        self.setProperty("miniplayer", mp_mode)
        self._apply_content_geometry(mp_mode == "off")

        # Default page = home.
        self._show_home()

        # Always focus the Home button of the side menu on open (in
        # both layouts): moving into the content is the user's
        # choice (right / down), never automatic. Wrapped in
        # try/except because setFocusId on a non-existent or
        # invisible control logs a "can't focus" error and (in some
        # Kodi versions) can trigger a window reload loop.
        try:
            target = ID_NAV_HOME
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

        # Watch for Kodi shutdown so the modal window closes itself
        # instead of getting force-killed after 5 seconds.
        try:
            if not self._abort_watcher.is_alive():
                self._abort_watcher.start()
        except Exception:
            pass

        # Widget track click: start playback of the requested track now
        # that the UI is fully up. Done last so a playback failure can't
        # break the window construction.
        if self._startup_track_id:
            track_id, self._startup_track_id = self._startup_track_id, None
            source, self._startup_track_source = self._startup_track_source, None
            self._play_startup_track(track_id, source)

    # Content heights: (control id, height when the mini-player bar
    # is visible, full height when the bar is hidden). These
    # containers (list / panel / group) are all reachable from Python.
    # The home rows grouplist (290) is NOT reachable (Kodi exposes no
    # Python control for grouplists) - its full height is baked into
    # the skin XML instead, and the bar simply covers the bottom of
    # the rows when it is shown.
    _CONTENT_GEOMETRY = (
        (354, 750, 870),  # home list (list layout on home)
        (295, 720, 880),  # generic page group (cards + list)
        (401, 720, 880),  # page vertical list (list layout)
        (400, 720, 880),  # page card panel (tiles layout)
    )

    def _apply_content_geometry(self, miniplayer_off):
        """Stretch the content containers down to the bottom of the
        screen when the mini-player bar is hidden, and restore their
        original heights when the bar is shown again. Called from
        onInit and whenever the setting changes live. Any failure is
        logged at LOGWARNING (not LOGDEBUG) so a Kodi limitation
        shows up in kodi.log without debug mode."""
        for control_id, height_bar, height_full in self._CONTENT_GEOMETRY:
            height = height_full if miniplayer_off else height_bar
            try:
                self.getControl(control_id).setHeight(height)
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow could not "
                    "resize control %d: %s" % (control_id, str(e)),
                    xbmc.LOGWARNING,
                )

    def _check_live_settings(self):
        """
        Live reload of the interface settings, called from onAction
        (so it fires on the first key press after the settings screen
        opened from the sidebar closes, and also covers settings
        changed any other way while the window is up). Layout and
        mini-player changes are applied immediately; anything else
        still needs a window reopen.
        """
        layout_setting = (self.settings.get("ui.layout") or "1").strip()
        layout = {"1": "sidebar", "2": "list"}.get(
            layout_setting, "sidebar"
        )
        if layout != (self.getProperty("layout") or "sidebar"):
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow layout changed to "
                "'%s', applying live" % layout,
                xbmc.LOGINFO,
            )
            self.setProperty("layout", layout)
            page = (self.getProperty("page") or "home")
            if page == "home":
                self._show_home()
            try:
                # Only move the focus when it currently sits on a
                # content container that the layout switch just hid
                # (card panel becoming the vertical list, or the
                # reverse). If the user is on the side menu — visible
                # in both layouts — the focus stays exactly where it
                # is.
                focused = self.getFocusId()
            except Exception:
                focused = None
            if (focused in ID_ROW_LISTS
                    or focused in (ID_PAGE_LIST, ID_PAGE_LIST_L, ID_HOME_LIST)):
                try:
                    if layout == "list":
                        self.setFocusId(
                            ID_HOME_LIST if page == "home" else ID_PAGE_LIST_L)
                    else:
                        self.setFocusId(
                            ID_ROW1_LIST if page == "home" else ID_PAGE_LIST)
                except Exception:
                    pass

        # Trending genre changed in the settings (the chips and the
        # list subtitle follow it live, like the layout).
        genre = self._trending_genre()
        if genre != (self.getProperty("trending_genre") or ""):
            self.setProperty("trending_genre", genre)
            # Reload the home page in BOTH layouts: the genre chips
            # and the trending row exist in tiles mode too now.
            if (self.getProperty("page") or "home") == "home":
                self._show_home()

        # Home rows (order / types) changed in the settings - applied
        # immediately, like the layout and the genre. The chips bar
        # follows too: it is only shown when a Trending row exists.
        row_fingerprint = ",".join(self._row_configs())
        if row_fingerprint != (self.getProperty("row_configs") or ""):
            self.setProperty("row_configs", row_fingerprint)
            self.setProperty("show_genre_chips",
                             "true" if "trending" in row_fingerprint else "false")
            if (self.getProperty("page") or "home") == "home":
                self._show_home()

        mp_setting = self.settings.get("ui.miniplayer") or "1"
        mp_mode = {"0": "off", "1": "compact"}.get(
            mp_setting, "compact"
        )
        if mp_mode != (self.getProperty("miniplayer") or "compact"):
            self.setProperty("miniplayer", mp_mode)
            self._apply_content_geometry(mp_mode == "off")

    def _play_startup_track(self, track_id, source=None):
        """
        Start playback for a widget track click (plugin root
        ?play_track=<id>&source=<cat> → RunScript → open_home).

        When the "widget.autoplay" setting is enabled (default) and we
        know which widget category the click came from, we queue the
        WHOLE category (likes / trending / discover) with the clicked
        track first — so when it ends, playback continues with the
        rest of the category instead of stopping on a silent screen.

        When the setting is off, or the category can't be fetched, we
        fall back to playing just the requested track.
        """
        try:
            continue_category = (
                (self.settings.get("widget.autoplay") or "true") == "true"
            )
            if continue_category and source:
                track_items, start = self._build_source_queue(source, track_id)
                if track_items:
                    _, li = track_items[start]
                    self._stash_now_playing_props(li)
                    xbmc.log(
                        "plugin.audio.soundcloud::HomeWindow widget "
                        "startup: queueing %d tracks from '%s', start=%d" %
                        (len(track_items), source, start),
                        xbmc.LOGINFO,
                    )
                    self._queue_and_play(track_items, start)
                    return

            # Single-track fallback (setting off, no source, or the
            # category fetch failed).
            collection = self.api.resolve_id(track_id)
            items = getattr(collection, "items", None) or []
            if not items:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow startup track %s "
                    "not found via resolve_id" % track_id,
                    xbmc.LOGWARNING,
                )
                self._notify(self.addon.getLocalizedString(30126))
                return
            track = items[0]
            _, list_item, _ = track.to_list_item(
                "plugin://" + self.addon.getAddonInfo("id")
            )
            self._stash_now_playing_props(list_item)
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow playing startup "
                "track %s (%s)" % (track_id, track.label),
                xbmc.LOGINFO,
            )
            self._play_track(track.media, list_item)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow startup track failed: %s"
                % str(e),
                xbmc.LOGERROR,
            )
            self._notify(self.addon.getLocalizedString(30126))

    def _stash_now_playing_props(self, list_item):
        """
        Copy the track-identifying properties from a ListItem into
        window properties, so the fullscreen now-playing overlay can
        identify the playing track. Same props the home-row click path
        sets.
        """
        try:
            self.setProperty(
                "soundcloud.last_played_track_id",
                list_item.getProperty("soundcloud.track_id") or "",
            )
            self.setProperty(
                "soundcloud.last_played_waveform_url",
                list_item.getProperty("soundcloud.waveform_url") or "",
            )
            self.setProperty(
                "soundcloud.last_played_description",
                list_item.getProperty("soundcloud.description") or "",
            )
        except Exception:
            pass

    def _build_source_queue(self, source, track_id):
        """
        Fetch the widget category's track list and return it as a list
        of (plugin_play_url, ListItem) pairs plus the index of the
        clicked track. Returns ([], 0) when the category can't be
        fetched (auth missing, network error, unknown source).

        If the clicked track isn't in the fetched page (e.g. it fell
        off the first page since the widget was rendered), it is
        prepended so the user still hears what they clicked, followed
        by the category.
        """
        try:
            limit = int(self.settings.get("search.items.size") or 20)
        except (TypeError, ValueError):
            limit = 20

        collection = None
        try:
            if source == "likes":
                user_id = self.api.get_my_user_id()
                if user_id:
                    collection = self.api.call(
                        "/users/%d/track_likes?limit=%d" % (user_id, limit)
                    )
            elif source == "trending":
                collection = self.api.charts({
                    "kind": "trending",
                    "genre": self._trending_genre(),
                    "limit": limit,
                })
            elif source == "discover":
                collection = self.api.discover(None)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow source queue fetch "
                "failed for '%s': %s" % (source, str(e)),
                xbmc.LOGWARNING,
            )
            return [], 0

        if collection is None:
            return [], 0

        addon_base = "plugin://" + self.addon.getAddonInfo("id")
        # Skip Go+ excerpts (30-second snippets) when the user
        # enabled the option.
        skip_previews = (
            (self.settings.get("playback.skip_excerpts") or "false") == "true"
        )
        track_items = []
        start = None
        for item in getattr(collection, "items", None) or []:
            # Tracks have a media URL; selections/playlists/users don't.
            if not getattr(item, "media", ""):
                continue
            # Skip Go+ excerpts when the user enabled the option.
            if skip_previews and getattr(item, "preview", False):
                continue
            url, li, _ = item.to_list_item(addon_base)
            if not li.getProperty("mediaUrl"):
                continue
            if start is None and str(getattr(item, "id", "")) == str(track_id):
                start = len(track_items)
            track_items.append((url, li))

        if not track_items:
            return [], 0

        if start is None:
            # Clicked track not in the page anymore — fetch it alone
            # and put it first.
            try:
                col = self.api.resolve_id(track_id)
                its = getattr(col, "items", None) or []
                if its:
                    url, li, _ = its[0].to_list_item(addon_base)
                    track_items.insert(0, (url, li))
                    start = 0
                else:
                    return [], 0
            except Exception:
                return [], 0

        return track_items, start

    # =====================================================================
    # Input handling
    # =====================================================================

    def onAction(self, action):
        action_id = action.getId()

        # The settings screen is opened FROM this window (sidebar
        # button); when it closes, the home window resumes without a
        # new onInit - and the layout used to be read only at window
        # open, so changing it had no visible effect until the addon
        # was fully closed and reopened. Re-read the interface
        # settings on every action (a cheap settings read) and apply
        # any change live.
        try:
            self._check_live_settings()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow live settings "
                "reload failed: %s" % str(e),
                xbmc.LOGDEBUG,
            )

        if action_id == ACTION_CONTEXT_MENU:
            # Long-press menu: add/remove the focused track from the
            # user's SoundCloud likes.
            try:
                self._handle_context_menu()
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow context menu "
                    "failed: %s" % str(e),
                    xbmc.LOGWARNING,
                )
            return
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK, ACTION_PARENT_DIR):
            # Back behaviour:
            # - If we have navigation history (user is deep in a folder),
            #   pop the previous state and re-render it.
            # - If the stack is empty (we're at the home page or top-level),
            #   close the window and return to Kodi's home screen.
            if self._nav_stack:
                try:
                    restore = self._nav_stack.pop()
                    xbmc.log(
                        "plugin.audio.soundcloud::HomeWindow Back pops nav "
                        "stack (depth now %d)" % len(self._nav_stack),
                        xbmc.LOGINFO,
                    )
                    restore()
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::HomeWindow nav restore "
                        "failed: %s" % str(e),
                        xbmc.LOGWARNING,
                    )
                return

            # Stack empty -> exit addon
            try:
                self._progress_updater.stop()
            except Exception:
                pass
            self.close()
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
        if control_id == ID_NAV_STATIONS:
            self._show_stations()
            return
        if control_id == ID_NAV_SETTINGS:
            self.addon.openSettings()
            return

        # ----- Genre chip clicked (home page of the "list" layout) -----
        if control_id in ID_GENRE_CHIPS:
            urn = GENRE_URNS[control_id - ID_GENRE_CHIPS[0]]
            if urn != self._trending_genre():
                try:
                    self.addon.setSetting("trending.genre", urn)
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::HomeWindow genre chip "
                        "persist failed: %s" % str(e),
                        xbmc.LOGWARNING,
                    )
                self.setProperty("trending_genre", urn)
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow trending genre "
                    "switched to '%s'" % urn,
                    xbmc.LOGINFO,
                )
                # Reload the trending list with the new genre. The
                # chips are only reachable on the home page, and
                # _show_home re-reads the (already persisted) genre.
                if (self.getProperty("page") or "home") == "home":
                    self._show_home()
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

        # ----- A track was clicked in one of the rows, the home list
        # or the page list -----
        if (control_id in ID_ROW_LISTS
                or control_id == ID_PAGE_LIST
                or control_id == ID_PAGE_LIST_L
                or control_id == ID_HOME_LIST):
            self._play_from_list(control_id)
            return

    # =====================================================================
    # Page rendering
    # =====================================================================

    def _push_nav_state(self):
        """
        Capture the current page state (page id, title, subtitle, page
        list contents) and push a restoration callable on the nav stack.
        Called before navigating deeper (e.g. opening a playlist) so
        that Back can return to where the user was.
        """
        current_page = self.getProperty("page") or "home"
        current_title = self.getProperty("title") or ""
        current_subtitle = self.getProperty("subtitle") or ""
        # We don't capture the page-list collection itself — for the most
        # common case (Playlists -> playlist tracks -> Back), the previous
        # state was "show_playlists" which we re-trigger via the helper.
        if current_page == "playlists":
            self._nav_stack.append(self._show_playlists)
        elif current_page == "likes":
            self._nav_stack.append(self._show_likes)
        elif current_page == "following":
            self._nav_stack.append(self._show_following)
        elif current_page == "stations":
            self._nav_stack.append(self._show_stations)
        elif current_page == "search":
            self._nav_stack.append(self._show_search)
        elif current_page == "home":
            self._nav_stack.append(self._show_home)
        elif current_page == "browse":
            # Nested browse (e.g. user -> tracks). Restoring this is
            # tricky because we'd need to re-call the original API path.
            # For now we just go back to home rather than re-fetching;
            # users can re-navigate if needed. Better than dropping out
            # of the addon entirely.
            self._nav_stack.append(self._show_home)
        else:
            self._nav_stack.append(self._show_home)

        xbmc.log(
            "plugin.audio.soundcloud::HomeWindow pushed nav state '%s' "
            "(stack depth %d)" % (current_page, len(self._nav_stack)),
            xbmc.LOGINFO,
        )

    def _show_home(self):
        # Home is the root of the navigation tree — clear the nav stack
        # so Back from here cleanly exits the addon instead of trying
        # to pop something.
        self._nav_stack = []
        self.setProperty("page", "home")
        self.setProperty("title", self.addon.getLocalizedString(30150))
        self.setProperty("subtitle", "")
        self.setProperty("page_empty", "false")

        # In "list" layout the home page is a vertical list with one
        # section per configured home row (the same row1..4.type
        # settings as the tiles layout): a non-clickable localized
        # header, then the row's items. Rows set to "off" are skipped;
        # when every row is off the list falls back to a single
        # Trending section.
        if self.getProperty("layout") == "list":
            for idx in range(1, 5):
                self.setProperty("row%d_visible" % idx, "false")
            row_configs = self._row_configs()
            if all(t == "off" for t in row_configs):
                row_configs = ["trending"]
            self._apply_home_properties(row_configs)
            if not self._fill_home_sections(row_configs):
                self.setProperty("page_empty", "true")
            return

        # Read row config from settings (see _row_configs). Each of
        # the 4 rows has a type setting; a row set to "off" is hidden.
        row_configs = self._row_configs()
        self._apply_home_properties(row_configs)

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

    def _row_configs(self):
        """
        Row types from settings (row1.type .. row4.type), each falling
        back to its default (likes / trending / playlists / following)
        when unset or unknown, or "off" when the user disabled it.
        """
        defaults = ["likes", "trending", "playlists", "following"]
        configs = []
        for i in range(1, 5):
            t = self.settings.get("row%d.type" % i) or defaults[i - 1]
            if t not in ROW_TYPES and t != "off":
                t = defaults[i - 1]
            configs.append(t)
        return configs

    def _apply_home_properties(self, row_configs):
        """
        Window properties shared by both home layouts:
        - show_genre_chips: the genre chips bar is only useful (and
          only shown) when a Trending row is configured - the genre
          setting only affects trending content;
        - row_configs: the row-config fingerprint, compared by
          _check_live_settings so order/type changes in the settings
          are applied immediately.
        """
        self.setProperty("show_genre_chips",
                         "true" if "trending" in row_configs else "false")
        self.setProperty("row_configs", ",".join(row_configs))

    def _page_size(self):
        """Read items-per-page from settings, with a sensible default."""
        try:
            return int(self.settings.get("search.items.size") or 20)
        except (TypeError, ValueError):
            return 20

    def _trending_genre(self):
        """
        Trending genre from settings (URN form expected by the /charts
        endpoint), defaulting to all-music.
        """
        genre = (self.settings.get("trending.genre") or "").strip()
        return genre or "soundcloud:genres:all-music"

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
                "genre": self._trending_genre(),
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

    def _load_history(self, list_id, limit=20):
        # Recently played (/me/play-history) - requires an OAuth
        # token; falls back to trending like the other personal rows.
        if not self.api.settings.get_oauth_token():
            self._load_trending(list_id, limit=limit)
            return
        try:
            collection = self.api.play_history(limit)
            if collection is None or not collection.items:
                self._load_trending(list_id, limit=limit)
                return
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_history "
                "failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _load_foryou(self, list_id, limit=20):
        # "Mixed for you" - personalized section matched at runtime
        # from /mixed-selections; trending fallback when not served.
        try:
            collection = self.api.discover_section(
                ("mixed for you", "mixed-for-you")
            )
            if collection is None or not collection.items:
                self._load_trending(list_id, limit=limit)
                return
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_foryou "
                "failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _load_based(self, list_id, limit=20):
        # "More of what you like" / "Based on what you like" -
        # personalized section matched at runtime from
        # /mixed-selections; trending fallback when not served.
        try:
            collection = self.api.discover_section(
                ("more of what you like", "more-of-what-you-like",
                 "based on what you like", "based-on-what-you-like")
            )
            if collection is None or not collection.items:
                self._load_trending(list_id, limit=limit)
                return
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_based "
                "failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _load_curated(self, list_id, limit=20):
        # "Curated by SoundCloud" selection - available anonymously.
        try:
            collection = self.api.discover(
                "soundcloud:selections:personalised-curated-global"
            )
            if collection is None or not collection.items:
                self._load_trending(list_id, limit=limit)
                return
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_curated "
                "failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _load_buzzing(self, list_id, limit=20):
        # "Artists to watch out for" (Buzzing) selection - available
        # anonymously.
        try:
            collection = self.api.discover(
                "soundcloud:selections:buzzing"
            )
            if collection is None or not collection.items:
                self._load_trending(list_id, limit=limit)
                return
            self._fill_list(list_id, collection)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow load_buzzing "
                "failed: %s" % str(e),
                xbmc.LOGERROR,
            )

    def _fetch_home_section(self, row_type, limit):
        """
        Fetch the content of one configured home row for the sectioned
        list layout of the home page. Mirrors the row loaders' fallback
        behaviour (trending when logged out or without a user id).
        Returns None when the fetch failed.
        """
        try:
            if row_type == "history":
                # Recently played requires an OAuth token; falls
                # through to the trending fallback when logged out.
                if self.api.settings.get_oauth_token():
                    history = self.api.play_history(limit)
                    if history is not None and history.items:
                        return history
            elif row_type == "foryou":
                # "Mixed for you" - personalized section matched at
                # runtime from /mixed-selections (user-specific ids).
                collection = self.api.discover_section(
                    ("mixed for you", "mixed-for-you")
                )
                if collection is not None and collection.items:
                    return collection
            elif row_type == "based":
                # "More of what you like" / "Based on what you like".
                collection = self.api.discover_section(
                    ("more of what you like", "more-of-what-you-like",
                     "based on what you like", "based-on-what-you-like")
                )
                if collection is not None and collection.items:
                    return collection
            elif row_type == "curated":
                # "Curated by SoundCloud" selection - anonymous OK.
                collection = self.api.discover(
                    "soundcloud:selections:personalised-curated-global"
                )
                if collection is not None and collection.items:
                    return collection
            elif row_type == "buzzing":
                # "Artists to watch out for" (Buzzing) - anonymous OK.
                collection = self.api.discover(
                    "soundcloud:selections:buzzing"
                )
                if collection is not None and collection.items:
                    return collection
            if (row_type in ("likes", "playlists", "following")
                    and self.api.settings.get_oauth_token()):
                user_id = self.api.get_my_user_id()
                if user_id:
                    if row_type == "likes":
                        return self.api.call(
                            "/users/%d/track_likes?limit=%d" % (user_id, limit)
                        )
                    if row_type == "playlists":
                        return self.api.call(
                            "/users/%d/playlists_without_albums?limit=%d"
                            % (user_id, limit)
                        )
                    return self.api.call(
                        "/users/%d/followings?limit=%d" % (user_id, limit)
                    )
            # Trending, or the fallback for the other rows when the
            # user is not logged in.
            return self.api.charts({
                "kind": "trending",
                "genre": self._trending_genre(),
                "limit": limit,
            })
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow fetch_home_section "
                "(%s) failed: %s" % (row_type, str(e)),
                xbmc.LOGERROR,
            )
            return None

    def _fill_home_sections(self, row_configs):
        """
        Fill the home list (354) with one section per configured home
        row: a non-clickable localized header item (property
        isSectionHeader=true) followed by the row's items. Returns True
        when at least one track item was added.
        """
        try:
            control = self.getControl(ID_HOME_LIST)
        except Exception:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow can't get control %d"
                % ID_HOME_LIST,
                xbmc.LOGWARNING,
            )
            return False

        try:
            control.reset()
        except Exception:
            pass
        self._lists[ID_HOME_LIST] = []
        self._next_href = None

        addon_base = "plugin://" + self.addon.getAddonInfo("id")
        limit = min(self._page_size(), HOME_SECTION_LIMIT)
        added = 0
        for row_type in row_configs:
            if row_type == "off":
                continue
            collection = self._fetch_home_section(row_type, limit)
            if collection is None or not collection.items:
                continue
            header = xbmcgui.ListItem(
                label=self.addon.getLocalizedString(ROW_TYPES[row_type]["title_strid"])
            )
            header.setProperty("isSectionHeader", "true")
            try:
                control.addItem(header)
                self._lists[ID_HOME_LIST].append((None, header))
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow add_section_header "
                    "failed: %s" % str(e),
                    xbmc.LOGWARNING,
                )
            for item in collection.items:
                try:
                    play_url, list_item, _ = item.to_list_item(addon_base)
                    control.addItem(list_item)
                    self._lists[ID_HOME_LIST].append((play_url, list_item))
                    added += 1
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::HomeWindow skip item: %s" % str(e),
                        xbmc.LOGWARNING,
                    )
        return added > 0

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

    def _show_stations(self):
        """
        Stations page: the user's liked stations (when logged in) are
        listed first, followed by SoundCloud's genre stations - the
        "trending by genre" system playlists served by /mixed-selections
        (Trap, Hip Hop, Pop, Electronic, House, ...). Clicking a
        station opens its tracks (see the "selection" parameter
        handling in _play_from_list).
        """
        self.setProperty("page", "stations")
        self.setProperty("title", self.addon.getLocalizedString(30381))
        self.setProperty("subtitle", "")

        merged = ApiCollection()
        merged.items = []
        merged.load = []
        merged.next_href = None

        if self.api.settings.get_oauth_token():
            try:
                liked = self.api.call("/me/likes/system-playlists?limit=50")
                if liked is not None:
                    merged.items.extend(liked.items)
            except Exception as e:
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow liked stations "
                    "failed: %s" % str(e),
                    xbmc.LOGWARNING,
                )
        try:
            genres = self.api.discover(
                "soundcloud:selections:trending-by-genre-playlists"
            )
            if genres is not None:
                merged.items.extend(genres.items)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow genre stations "
                "failed: %s" % str(e),
                xbmc.LOGERROR,
            )

        self._fill_page_list(merged)

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

        Both containers are filled with the same content: the card
        panel (400, "sidebar" layout) and the vertical list (401,
        "list" layout), so switching layouts live from the settings
        just moves the focus, without re-fetching anything.
        """
        # Remember the next-page link so we can load it when the user
        # selects the "Next page" item.
        self._next_href = (collection.next_href if collection else None)

        self._fill_list(ID_PAGE_LIST, collection)
        self._fill_list(ID_PAGE_LIST_L, collection)

        # Append "Next page" pseudo-item if there's more.
        if self._next_href:
            for list_id in (ID_PAGE_LIST, ID_PAGE_LIST_L):
                try:
                    control = self.getControl(list_id)
                    next_item = xbmcgui.ListItem(
                        label=self.addon.getLocalizedString(30901)  # "Next page"
                    )
                    next_item.setArt({
                        "thumb": "DefaultFolderForward.png",
                        "icon": "DefaultFolderForward.png",
                    })
                    next_item.setProperty("isNextPage", "true")
                    control.addItem(next_item)
                    self._lists[list_id].append((None, next_item))
                except Exception as e:
                    xbmc.log(
                        "plugin.audio.soundcloud::HomeWindow add_next_page "
                        "failed: %s" % str(e),
                        xbmc.LOGWARNING,
                    )

        is_empty = collection is None or not collection.items
        self.setProperty("page_empty", "true" if is_empty else "false")
        # NOTE: the focus is deliberately NOT moved here. Selecting a
        # menu entry keeps the focus on the side menu — the user
        # navigates into the content with right/down when they want
        # to (both page-list containers are always filled, so no
        # re-fetch is ever needed).

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

        # Section headers in the home list are not clickable.
        if list_item.getProperty("isSectionHeader") == "true":
            return

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
                selection_id = unquote(qs.get("selection", [""])[0])
                if call_path:
                    # Push the current page onto the nav stack so Back
                    # can return here instead of closing the window.
                    self._push_nav_state()
                    self.setProperty("page", "browse")
                    self.setProperty("title", list_item.getLabel())
                    self.setProperty("subtitle", "")
                    collection = self.api.call(call_path)
                    self._fill_page_list(collection)
                elif selection_id:
                    # Selection / station items (Discover selections and
                    # system playlists - genre stations, artist stations,
                    # "Mixed for you", ...) carry a "selection" parameter
                    # instead of "call": they previously did nothing when
                    # clicked. System playlists have their own endpoint;
                    # other selections are resolved from /mixed-selections.
                    self._push_nav_state()
                    self.setProperty("page", "browse")
                    self.setProperty("title", list_item.getLabel())
                    self.setProperty("subtitle", "")
                    try:
                        if selection_id.startswith(
                                "soundcloud:system-playlists:"):
                            collection = self.api.system_playlist(selection_id)
                        else:
                            collection = self.api.discover(selection_id)
                    except Exception:
                        collection = None
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
        # Skip Go+ excerpts (30-second snippets) when the user
        # enabled the option.
        skip_previews = (
            (self.settings.get("playback.skip_excerpts") or "false") == "true"
        )
        track_items = [
            (url, li) for (url, li) in items
            if li.getProperty("mediaUrl")
            and not (skip_previews and li.getProperty("soundcloud.preview") == "true")
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

        self._queue_and_play(track_items, new_start)

    def _queue_and_play(self, track_items, new_start):
        """
        Queue a list of (plugin_play_url, ListItem) pairs into Kodi's
        music playlist and start playback at new_start. Shared by the
        home-row click path (_play_with_queue) and the widget startup
        path (_play_startup_track). Honours the shuffle setting: the
        selected track stays first, the rest is randomised.
        """
        try:
            # If the user enabled shuffle, randomise the order of
            # track_items BEFORE building the Kodi playlist. We pin the
            # clicked track at position 0 so it plays first, then the
            # rest in shuffled order. This is more reliable than calling
            # PlayerControl(RandomOn) after play() — the builtin doesn't
            # always apply in time on some Kodi versions, especially when
            # the player is still resolving the stream URL.
            shuffle = (self.settings.get("ui.shuffle") or "false") == "true"
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow shuffle setting=%s "
                "tracks=%d clicked_pos=%d" %
                (shuffle, len(track_items), new_start),
                xbmc.LOGINFO,
            )
            if shuffle and len(track_items) > 1:
                import random
                clicked = track_items[new_start]
                remaining = track_items[:new_start] + track_items[new_start + 1:]
                random.shuffle(remaining)
                track_items = [clicked] + remaining
                new_start = 0
                xbmc.log(
                    "plugin.audio.soundcloud::HomeWindow shuffled playlist; "
                    "clicked track now at position 0, %d others randomised" %
                    len(remaining),
                    xbmc.LOGINFO,
                )

            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            playlist.clear()
            for url, li in track_items:
                playlist.add(url=url, listitem=li)

            # Stash the about-to-play track's metadata in window props
            # so the fullscreen overlay (NowPlayingDialog) can read them.
            try:
                _, first_li = track_items[new_start]
                self.setProperty(
                    "soundcloud.last_played_track_id",
                    first_li.getProperty("soundcloud.track_id") or "",
                )
                self.setProperty(
                    "soundcloud.last_played_waveform_url",
                    first_li.getProperty("soundcloud.waveform_url") or "",
                )
                self.setProperty(
                    "soundcloud.last_played_description",
                    first_li.getProperty("soundcloud.description") or "",
                )
            except Exception:
                pass

            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow queued %d tracks, "
                "starting at position %d" % (len(track_items), new_start),
                xbmc.LOGINFO,
            )
            xbmc.Player().play(playlist, startpos=new_start)

            # Arm the sleep timer for this fresh playback.
            self._arm_sleep_timer()

            # Also flip Kodi's own random toggle for visual consistency
            # in the player controls. If we shuffled the list above, the
            # actual order is already random; this builtin just makes
            # the "shuffle" icon light up in the player UI.
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
            _, list_item = track_items[new_start]
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
            # Arm the sleep timer for this fresh playback.
            self._arm_sleep_timer()
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow play failed: %s" % str(e),
                xbmc.LOGERROR,
            )
            self._notify(self.addon.getLocalizedString(30126))

    def _arm_sleep_timer(self):
        """
        (Re)start the sleep timer for a fresh playback. The previous
        timer (if any) is cancelled; no new thread is started when
        the setting is 0/disabled.
        """
        try:
            old = getattr(self, "_sleep_timer_thread", None)
            if old is not None:
                old.cancel()
        except Exception:
            pass
        try:
            try:
                minutes = int(
                    self.settings.get("playback.sleep_timer") or 0
                )
            except (TypeError, ValueError):
                minutes = 0
            if minutes > 0:
                timer = _SleepTimer(self)
                self._sleep_timer_thread = timer
                timer.start()
            else:
                self._sleep_timer_thread = None
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow sleep timer arm "
                "failed: %s" % str(e),
                xbmc.LOGWARNING,
            )

    def _handle_context_menu(self):
        """
        Long-press context menu on the focused list: add or remove
        the selected track from the user's SoundCloud likes
        (PUT/DELETE /me/favorites/{id}). Requires an OAuth token.
        """
        try:
            control_id = self.getFocusId()
        except Exception:
            control_id = None
        items = self._lists.get(control_id, [])
        if not items:
            return

        try:
            position = self.getControl(control_id).getSelectedPosition()
        except Exception:
            position = -1
        if position < 0 or position >= len(items):
            return

        _, list_item = items[position]
        track_id = (
            list_item.getProperty("soundcloud.track_id") or ""
        ).strip()
        if not track_id:
            return

        if not self.api.settings.get_oauth_token():
            self._notify(self.addon.getLocalizedString(30024))
            return

        choice = xbmcgui.Dialog().select(
            self.addon.getLocalizedString(30364),
            [
                self.addon.getLocalizedString(30359),
                self.addon.getLocalizedString(30360),
            ],
        )
        if choice < 0:
            return

        try:
            if choice == 0:
                ok = self.api.like_track(track_id)
            else:
                ok = self.api.unlike_track(track_id)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::HomeWindow like/unlike "
                "failed: %s" % str(e),
                xbmc.LOGWARNING,
            )
            ok = False

        if ok:
            self._notify(self.addon.getLocalizedString(
                30361 if choice == 0 else 30362))
        else:
            self._notify(self.addon.getLocalizedString(30363))

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


def open_home(api, addon, settings, startup_track_id=None,
              startup_track_source=None):
    """
    Public entry point — build and show the window modally.

    startup_track_id: optional SoundCloud track id. When provided
    (widget track click), the window starts playback of that track
    right after its initial population, so the user lands in the full
    UI with their chosen track playing (now-playing overlay included).

    startup_track_source: optional widget category name the click came
    from (likes / trending / discover). When present and the
    widget.autoplay setting is on, the rest of the category is queued
    after the clicked track for continuous playback.
    """
    addon_path = addon.getAddonInfo("path")
    window = SoundCloudHomeWindow(
        WINDOW_XML,
        addon_path,
        "default",
        "1080i",
        api=api,
        addon=addon,
        settings=settings,
        startup_track_id=startup_track_id,
        startup_track_source=startup_track_source,
    )

    # Abort watchdog: doModal() blocks until the window is closed, and
    # Kodi does NOT close Python windows on shutdown — it waits 5
    # seconds then force-kills the interpreter ("script didn't stop in
    # 5 seconds - let's kill it" in the log), delaying every Kodi
    # shutdown/restart by 5s while our UI is open. This daemon thread
    # waits for the abort signal and closes the window so doModal()
    # returns immediately and the script exits cleanly.
    import threading

    def _close_on_abort(win):
        monitor = xbmc.Monitor()
        monitor.waitForAbort()
        try:
            win.close()
        except Exception:
            pass

    watchdog = threading.Thread(
        target=_close_on_abort, args=(window,), daemon=True
    )
    watchdog.start()

    window.doModal()
    del window
