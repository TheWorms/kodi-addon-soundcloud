from resources.lib.models.list_item import ListItem
import urllib.parse
import xbmcaddon
import xbmcgui

blocked = xbmcaddon.Addon().getLocalizedString(30902)
preview = xbmcaddon.Addon().getLocalizedString(30903)


class Track(ListItem):
    blocked = False
    preview = False
    thumb = ""
    fanart = ""
    media = ""
    info = {}

    def to_list_item(self, addon_base):
        list_item_label = "[%s] " % blocked + self.label if self.blocked else self.label
        list_item_label = "[%s] " % preview + self.label if self.preview else list_item_label
        list_item = xbmcgui.ListItem(label=list_item_label)

        art = {"thumb": self.thumb, "icon": self.thumb}
        # Fanart is optional; fall back to the thumbnail so skins that
        # show a background image still render something when the user
        # highlights the track.
        art["fanart"] = self.fanart or self.thumb
        list_item.setArt(art)

        # Robust date handling: the API occasionally returns tracks without
        # a display_date (notably through /me/* endpoints), which used to
        # crash the plugin with `TypeError: 'NoneType' is not subscriptable`.
        date = self.info.get("date") or ""
        year = date[:4] if len(date) >= 4 and date[:4].isdigit() else ""

        # Kodi 20+ deprecated ListItem.setInfo('music', ...) in favour
        # of the InfoTagMusic setter API. We migrate to shut up the
        # deprecation warnings that spam kodi.log — the setter API is
        # also stricter about types, so we're explicit about them:
        #   - setDuration wants an int in SECONDS (API gives ms).
        #   - setGenres wants a LIST of strings, not a single string.
        #   - setPlayCount is semantically "times you played it" and
        #     ticks the track as watched. SoundCloud's playback_count
        #     is a global public counter, so it belongs in
        #     setListeners (popularity) instead.
        tag = list_item.getMusicInfoTag()
        tag.setTitle(self.label)
        tag.setMediaType("song")

        artist = self.info.get("artist")
        if artist:
            tag.setArtist(artist)

        album = self.info.get("album")
        if album:
            tag.setAlbum(album)

        duration_value = self.info.get("duration")
        if duration_value is not None:
            # api_v2._build_track already divides ms by 1000, but the
            # result is a float; setDuration wants int.
            try:
                tag.setDuration(int(duration_value))
            except (TypeError, ValueError):
                pass

        genre = self.info.get("genre")
        if genre:
            tag.setGenres([genre])

        description = self.info.get("description")
        if description:
            tag.setComment(description)

        playback_count = self.info.get("playback_count")
        if playback_count:
            try:
                tag.setListeners(int(playback_count))
            except (TypeError, ValueError):
                pass

        if year:
            try:
                tag.setYear(int(year))
            except (TypeError, ValueError):
                pass

        if date and len(date) >= 10:
            # SoundCloud gives ISO datetimes like "2024-01-15T00:00:00Z";
            # setReleaseDate wants "YYYY-MM-DD".
            release_date = date[:10]
            if release_date.count("-") == 2:
                try:
                    tag.setReleaseDate(release_date)
                except Exception:
                    pass

        list_item.setProperty("isPlayable", "true")
        list_item.setProperty("mediaUrl", self.media)
        # Stash the track id and waveform url so the fullscreen overlay
        # can identify the playing track and display its waveform.
        # Kodi keeps these properties on the playing item.
        if self.id is not None:
            list_item.setProperty("soundcloud.track_id", str(self.id))
        if self.info.get("waveform_url"):
            list_item.setProperty(
                "soundcloud.waveform_url", self.info["waveform_url"]
            )
        if self.info.get("description"):
            list_item.setProperty(
                "soundcloud.description", self.info["description"]
            )

        url = addon_base + "/play/?" + urllib.parse.urlencode({"media_url": self.media})
        return url, list_item, False
