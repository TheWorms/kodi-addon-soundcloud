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

        music_info = {
            "artist": self.info.get("artist"),
            "album": self.info.get("album"),
            "duration": self.info.get("duration"),
            "genre": self.info.get("genre"),
            "title": self.label,
            "playcount": self.info.get("playback_count"),
            "comment": self.info.get("description"),
            "mediatype": "song",
        }
        if year:
            music_info["year"] = year
        if date:
            music_info["date"] = date
        list_item.setInfo("music", music_info)

        list_item.setProperty("isPlayable", "true")
        list_item.setProperty("mediaUrl", self.media)

        url = addon_base + "/play/?" + urllib.parse.urlencode({"media_url": self.media})
        return url, list_item, False
