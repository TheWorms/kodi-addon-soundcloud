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


# Kodi action IDs (used by both NowPlayingDialog and SoundCloudHomeWindow,
# defined here at module top so both classes can reference them).
ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92
ACTION_PARENT_DIR = 9


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
        self._close_now_playing()

    def onPlayBackEnded(self):
        # When autoplay queues the next track, onPlayBackEnded fires
        # then onAVStarted fires again — we don't want to close+reopen
        # the fullscreen window between tracks (it would flash). So we
        # leave the dialog open here and rely on Player.* infolabels to
        # update inside the still-open dialog.
        pass

    def _maybe_open_now_playing(self):
        """Open the configured fullscreen overlay, if any, and only if
        not already open."""
        style = (self._window.settings.get("playback.fullscreen_style")
                 or "off").strip()
        xbmc.log(
            "plugin.audio.soundcloud::PlayerObserver _maybe_open_now_"
            "playing setting=%r np_dialog_is_set=%s" %
            (style, self._np_dialog is not None),
            xbmc.LOGINFO,
        )
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
        # Any back/menu/exit action closes the overlay.
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK,
                              ACTION_PARENT_DIR):
            self.close()
            if self._observer is not None:
                self._observer._np_dialog = None
            return

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

            # Stash the about-to-play track's metadata in window props
            # so the fullscreen overlay (NowPlayingDialog) can read them.
            # We update them again on every onAVStarted via the observer
            # (TODO: hook that in for autoplayed next tracks).
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
