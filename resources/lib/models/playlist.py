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

        # Kodi 20+ InfoTagMusic API — see rationale in track.py.
        # Playlists/albums map to mediatype="album" so music-oriented
        # skins render them as folder-of-tracks containers.
        tag = list_item.getMusicInfoTag()
        tag.setMediaType("album")
        tag.setAlbum(self.label)

        artist = self.info.get("artist")
        if artist:
            tag.setArtist(artist)

        comment = self._build_comment()
        if comment:
            tag.setComment(comment)

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
