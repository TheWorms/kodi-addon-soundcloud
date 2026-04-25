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

    def widgets(self, include_ui_launcher=False):
        """
        Returns a menu of widget shortcuts. Each entry points to a flat
        directory route (PATH_WIDGET_*) that returns playable items
        directly — perfect for skin widget panes that expect a flat list.

        This menu is what the addon root URL returns: skin widget pickers
        will see these entries when browsing the addon, and so will users
        clicking on the addon from Kodi's add-on browser.

        :param include_ui_launcher: when True, prepend a "▶ Open
            SoundCloud" entry that launches the full-screen UI. We use
            this on the root listing so users coming from the add-on
            browser still have a way into the full UI; we omit it from
            the deep /widgets/ listing where the launcher item would be
            confusing inside a widget pane.
        """
        items = []

        if include_ui_launcher:
            # Entry point to the full-screen UI. Lives at the top of
            # the root listing so it's the first thing users see when
            # they click the addon from Kodi's add-on browser.
            list_item = xbmcgui.ListItem(
                label=format_bold(self.addon.getLocalizedString(30270))
            )
            list_item.setArt({
                "icon": "DefaultAddonSkin.png",
                "thumb": "DefaultAddonSkin.png",
            })
            url = self.addon_base + "/?action=launch_ui"
            # isFolder=False because clicking it triggers an action
            # (launch the script), not a directory navigation.
            items.append((url, list_item, False))

        # Likes (tracks the user has liked)
        list_item = xbmcgui.ListItem(
            label=format_bold(self.addon.getLocalizedString(30251))
        )
        list_item.setArt({
            "icon": "DefaultMusicSongs.png",
            "thumb": "DefaultMusicSongs.png",
        })
        items.append((self.addon_base + PATH_WIDGET_LIKES, list_item, True))

        # My playlists
        list_item = xbmcgui.ListItem(
            label=format_bold(self.addon.getLocalizedString(30252))
        )
        list_item.setArt({
            "icon": "DefaultMusicPlaylists.png",
            "thumb": "DefaultMusicPlaylists.png",
        })
        items.append((self.addon_base + PATH_WIDGET_PLAYLISTS, list_item, True))

        # Following
        list_item = xbmcgui.ListItem(
            label=format_bold(self.addon.getLocalizedString(30253))
        )
        list_item.setArt({
            "icon": "DefaultArtist.png",
            "thumb": "DefaultArtist.png",
        })
        items.append((self.addon_base + PATH_WIDGET_FOLLOWING, list_item, True))

        # Trending
        list_item = xbmcgui.ListItem(
            label=format_bold(self.addon.getLocalizedString(30254))
        )
        list_item.setArt({
            "icon": "DefaultMusicTop100.png",
            "thumb": "DefaultMusicTop100.png",
        })
        items.append((self.addon_base + PATH_WIDGET_TRENDING, list_item, True))

        # Discover
        list_item = xbmcgui.ListItem(
            label=format_bold(self.addon.getLocalizedString(30255))
        )
        list_item.setArt({
            "icon": "DefaultMusicCompilations.png",
            "thumb": "DefaultMusicCompilations.png",
        })
        items.append((self.addon_base + PATH_WIDGET_DISCOVER, list_item, True))

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
