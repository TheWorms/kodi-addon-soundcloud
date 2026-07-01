from resources.lib.models.list_item import ListItem
from resources.routes import *
import urllib.parse
import xbmcgui


class Selection(ListItem):
    info = {}

    def to_list_item(self, addon_base):
        list_item = xbmcgui.ListItem(label=self.label, label2=self.label2)
        # Kodi 20+ InfoTagMusic API — see rationale in track.py.
        description = self.info.get("description")
        if description:
            list_item.getMusicInfoTag().setTitle(description)
        url = addon_base + PATH_DISCOVER + "?" + urllib.parse.urlencode({
            "selection": self.id
        })

        return url, list_item, True
