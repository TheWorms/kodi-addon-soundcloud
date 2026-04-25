from resources.lib.kodi.utils import format_bold
from resources.routes import *

import urllib.parse
import xbmcgui


class Items:
    def __init__(self, addon, addon_base, search_history, api=None):
        self.addon = addon
        self.addon_base = addon_base
        self.search_history = search_history
        self.api = api

    def root(self):
        items = []

        # Search
        list_item = xbmcgui.ListItem(label=self.addon.getLocalizedString(30101))
        url = self.addon_base + PATH_SEARCH
        items.append((url, list_item, True))

        # Charts
        list_item = xbmcgui.ListItem(label=self.addon.getLocalizedString(30102))
        url = self.addon_base + PATH_CHARTS
        items.append((url, list_item, True))

        # Discover
        list_item = xbmcgui.ListItem(label=self.addon.getLocalizedString(30103))
        url = self.addon_base + PATH_DISCOVER
        items.append((url, list_item, True))

        # My profile (requires OAuth token; when missing the handler
        # shows a helpful dialog pointing to the settings screen)
        list_item = xbmcgui.ListItem(label=self.addon.getLocalizedString(30110))
        url = self.addon_base + PATH_ME
        items.append((url, list_item, True))

        # New full-screen UI (beta) — opens a custom WindowXML script.
        list_item = xbmcgui.ListItem(label=self.addon.getLocalizedString(30120))
        list_item.setArt({"icon": "DefaultAddonSkin.png"})
        url = self.addon_base + PATH_LAUNCH_UI
        items.append((url, list_item, False))

        # Settings
        list_item = xbmcgui.ListItem(label=self.addon.getLocalizedString(30108))
        url = self.addon_base + "/?action=settings"
        items.append((url, list_item, False))

        # Sign in TODO
        # list_item = xbmcgui.ListItem(label=addon.getLocalizedString(30109))
        # url = addon_base + "/action=signin"
        # items.append((url, list_item, False))

        return items

    def me(self):
        """
        Returns the sub-menu for the authenticated user (likes, playlists, etc.).

        SoundCloud's api-v2 doesn't expose stable /me/* sub-resources for these
        — those paths return 404. Instead, we resolve the authenticated user's
        ID via GET /me and then call /users/{id}/* for each sub-resource.
        """
        items = []

        user_id = self.api.get_my_user_id() if self.api else None
        if not user_id:
            # Token is missing, expired, or /me failed. Returning an empty
            # menu would be confusing — surface a clear hint instead.
            list_item = xbmcgui.ListItem(
                label=format_bold(self.addon.getLocalizedString(30024))  # "OAuth invalid"
            )
            url = self.addon_base + PATH_SETTINGS_AUTH_HELP
            items.append((url, list_item, False))
            return items

        # Likes (tracks the user has liked)
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30401)))
        url = self.addon_base + "/?" + urllib.parse.urlencode({
            "action": "call",
            "call": "/users/{id}/track_likes".format(id=user_id)
        })
        items.append((url, list_item, True))

        # My playlists (playlists owned by the user)
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30402)))
        url = self.addon_base + "/?" + urllib.parse.urlencode({
            "action": "call",
            "call": "/users/{id}/playlists_without_albums".format(id=user_id)
        })
        items.append((url, list_item, True))

        # Following (artists the user follows)
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30403)))
        url = self.addon_base + "/?" + urllib.parse.urlencode({
            "action": "call",
            "call": "/users/{id}/followings".format(id=user_id)
        })
        items.append((url, list_item, True))

        # Reposts (tracks/playlists reposted by the user)
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30404)))
        url = self.addon_base + "/?" + urllib.parse.urlencode({
            "action": "call",
            "call": "/stream/users/{id}/reposts".format(id=user_id)
        })
        items.append((url, list_item, True))

        return items

    def search(self):
        items = []

        # New search
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30201)))
        url = self.addon_base + PATH_SEARCH + "?action=new"
        items.append((url, list_item, True))

        # Search history
        history = self.search_history.get()
        for k in sorted(list(history), reverse=True):
            query = history[k].get("query")
            list_item = xbmcgui.ListItem(label=query)
            list_item.addContextMenuItems(self._search_context_menu(query))
            url = self.addon_base + PATH_SEARCH + "?" + urllib.parse.urlencode({
                "query": history[k].get("query")
            })
            items.append((url, list_item, True))

        return items

    def search_sub(self, query):
        items = []

        # People
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30211)))
        url = self.addon_base + PATH_SEARCH + "?" + urllib.parse.urlencode({
            "action": "people",
            "query": query
        })
        items.append((url, list_item, True))

        # Albums
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30212)))
        url = self.addon_base + PATH_SEARCH + "?" + urllib.parse.urlencode({
            "action": "albums",
            "query": query
        })
        items.append((url, list_item, True))

        # Playlists
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30213)))
        url = self.addon_base + PATH_SEARCH + "?" + urllib.parse.urlencode({
            "action": "playlists",
            "query": query
        })
        items.append((url, list_item, True))

        return items

    def user(self, id):
        items = []

        # Albums
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30212)))
        url = self.addon_base + "/?" + urllib.parse.urlencode({
            "action": "call",
            "call": "/users/{id}/albums".format(id=id)
        })
        items.append((url, list_item, True))

        # Playlists
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30213)))
        url = self.addon_base + "/?" + urllib.parse.urlencode({
            "action": "call",
            "call": "/users/{id}/playlists_without_albums".format(id=id)
        })
        items.append((url, list_item, True))

        # Spotlight
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30214)))
        url = self.addon_base + "/?" + urllib.parse.urlencode({
            "action": "call",
            "call": "/users/{id}/spotlight".format(id=id)
        })
        items.append((url, list_item, True))

        return items

    def charts(self):
        items = []

        # Top 50
        # TOOD Not working anymore, replace with new GraphQL API
        # list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30301)))
        # url = self.addon_base + PATH_CHARTS + "?" + urllib.parse.urlencode({
        #     "action": "top"
        # })
        # items.append((url, list_item, True))

        # Trending
        list_item = xbmcgui.ListItem(label=format_bold(self.addon.getLocalizedString(30302)))
        url = self.addon_base + PATH_CHARTS + "?" + urllib.parse.urlencode({
            "action": "trending"
        })
        items.append((url, list_item, True))

        return items

    def from_collection(self, collection):
        items = []

        for item in collection.items:
            items.append(item.to_list_item(self.addon_base))

        if collection.next_href:
            next_item = xbmcgui.ListItem(label=self.addon.getLocalizedString(30901))
            url = self.addon_base + "/?" + urllib.parse.urlencode({
                "action": "call",
                "call": collection.next_href
            })
            items.append((url, next_item, True))

        return items

    def _search_context_menu(self, query):
        return [
            (
                self.addon.getLocalizedString(30601),
                "RunPlugin({}/{}?{})".format(
                    self.addon_base, PATH_SEARCH, urllib.parse.urlencode({
                        "action": "remove",
                        "query": query
                    })
                )
            ),
            (
                self.addon.getLocalizedString(30602),
                "RunPlugin({}/{}?{})".format(
                    self.addon_base, PATH_SEARCH, urllib.parse.urlencode({"action": "clear"})
                )
             ),
        ]
