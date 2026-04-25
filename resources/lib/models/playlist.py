from resources.lib.models.list_item import ListItem
import urllib.parse
import xbmcaddon
import xbmcgui

addon = xbmcaddon.Addon()
likes = addon.getLocalizedString(30905)
tracks_label = addon.getLocalizedString(30906)


class Playlist(ListItem):
    thumb = ""
    fanart = ""
    info = {}
    is_album = False

    def to_list_item(self, addon_base):
        list_item = xbmcgui.ListItem(label=self.label, label2=self._build_label2())

        art = {"thumb": self.thumb, "icon": self.thumb}
        art["fanart"] = self.fanart or self.thumb
        list_item.setArt(art)

        list_item.setIsFolder(True)
        list_item.setProperty("isPlayable", "false")

        # Use the "music" infotype so skins treat this as an album/playlist.
        # `comment` carries the description — most music-oriented skins render
        # it in the detail panel, which is what the previous "video"/plot
        # hack was trying to achieve. We use the "album" mediatype for both
        # albums and plain playlists because Kodi music skins handle any
        # folder-of-tracks as an album-like container.
        music_info = {
            "artist": self.info.get("artist"),
            "album": self.label,
            "comment": self._build_comment(),
            "mediatype": "album",
        }
        list_item.setInfo("music", music_info)

        url = addon_base + "/?" + urllib.parse.urlencode({
            "action": "call",
            "call": "/playlists/{id}".format(id=self.id)
        })

        return url, list_item, True

    def _build_label2(self):
        """
        Secondary label shown next to the title in list views.
        Priority: explicit label2 (label_name from API) -> "by Artist • N tracks".
        """
        if self.label2:
            return self.label2

        parts = []
        artist = self.info.get("artist")
        if artist:
            parts.append(artist)

        track_count = self.info.get("track_count")
        if track_count:
            parts.append("{} {}".format(track_count, tracks_label))

        return " • ".join(parts)

    def _build_comment(self):
        lines = []
        artist = self.info.get("artist")
        if artist:
            lines.append(artist)

        likes_count = self.info.get("likes")
        if likes_count:
            lines.append("{} {}".format(likes_count, likes))

        description = self.info.get("description")
        if description:
            lines.append("")
            lines.append(description)

        return "\n".join(lines)
