from resources.lib.models.list_item import ListItem
from resources.routes import *
import urllib.parse
import xbmcaddon
import xbmcgui

followers = xbmcaddon.Addon().getLocalizedString(30904)


class User(ListItem):
    thumb = ""
    fanart = ""
    info = {}

    def to_list_item(self, addon_base):
        list_item = xbmcgui.ListItem(label=self.label, label2=self._build_label2())

        art = {"thumb": self.thumb, "icon": self.thumb}
        # Banner from SoundCloud's `visuals` field if available, otherwise
        # use the avatar as a fallback so the detail view never looks empty.
        art["fanart"] = self.fanart or self.thumb
        list_item.setArt(art)

        list_item.setIsFolder(True)
        list_item.setProperty("isPlayable", "false")

        # Use the `music` infotype with the artist mediatype so music-oriented
        # skins (Estuary's music view, Arctic Zephyr's artist panels, etc.)
        # display the entry correctly. `comment` carries the bio — most skins
        # render it in the detail pane.
        list_item.setInfo("music", {
            "artist": self.label,
            "comment": self._build_comment(),
            "mediatype": "artist",
        })

        url = addon_base + PATH_USER + "?" + urllib.parse.urlencode({
            "id": self.id,
            "call": "/users/{id}/tracks".format(id=self.id)
        })

        return url, list_item, True

    def _build_label2(self):
        """
        Prefer the user's full name (when set). Otherwise fall back to the
        follower count so the list view has a useful secondary line.
        """
        if self.label2:
            return self.label2

        follower_count = self.info.get("followers")
        if follower_count:
            return "{} {}".format(self._format_count(follower_count), followers)

        return ""

    def _build_comment(self):
        lines = []
        if self.label2 and self.label2 != self.label:
            lines.append(self.label2)
        follower_count = self.info.get("followers")
        if follower_count:
            lines.append("{} {}".format(self._format_count(follower_count), followers))
        description = self.info.get("description")
        if description:
            lines.append("")
            lines.append(description)
        return "\n".join(lines)

    @staticmethod
    def _format_count(n):
        """Human-friendly count: 1234 -> "1.2K", 1200000 -> "1.2M"."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return str(n)
        if n >= 1_000_000:
            return "{:.1f}M".format(n / 1_000_000).replace(".0M", "M")
        if n >= 1_000:
            return "{:.1f}K".format(n / 1_000).replace(".0K", "K")
        return str(n)
