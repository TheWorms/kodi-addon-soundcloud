import hashlib
import json
import re
import requests
import urllib.parse
import xbmc

from resources.lib.models.playlist import Playlist
from resources.lib.models.track import Track
from resources.lib.models.selection import Selection
from resources.lib.models.user import User
from resources.lib.soundcloud.api_collection import ApiCollection
from resources.lib.soundcloud.api_interface import ApiInterface


class ApiV2(ApiInterface):
    """This class uses the unofficial API used by the SoundCloud website."""

    api_host = "https://api-v2.soundcloud.com"
    api_client_id_cache_duration = 1440  # 24 hours
    api_client_id_cache_key = "api-client-id"
    api_limit = 20
    api_limit_tracks = 50
    api_lang = "en"
    api_user_agent = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"
    api_cache = {
        "discover": 120  # 2 hours
    }
    thumbnail_size = 500

    def __init__(self, settings, lang, cache):
        self.cache = cache
        self.settings = settings
        self.api_limit = int(self.settings.get("search.items.size"))

        if self.settings.get("apiv2.locale") == self.settings.APIV2_LOCALE["auto"]:
            self.api_lang = lang

    @property
    def api_client_id(self):
        # It is possible to set a custom client ID in the settings
        client_id_settings = self.settings.get("apiv2.client_id")
        if client_id_settings:
            xbmc.log("plugin.audio.soundcloud::ApiV2() Using custom client ID", xbmc.LOGDEBUG)
            return client_id_settings

        # Check if there is a cached client ID
        client_id_cached = self.cache.get(
            self.api_client_id_cache_key,
            self.api_client_id_cache_duration
        )
        if client_id_cached:
            xbmc.log("plugin.audio.soundcloud::ApiV2() Using cached client ID", xbmc.LOGDEBUG)
            return client_id_cached

        # Extract client ID from website and cache it
        client_id = self.fetch_client_id()
        self.cache.add(self.api_client_id_cache_key, client_id)
        xbmc.log("plugin.audio.soundcloud::ApiV2() Using new client ID", xbmc.LOGDEBUG)

        return client_id

    def search(self, query, kind="tracks"):
        res = self._do_request("/search/" + kind, {"q": query, "limit": self.api_limit})
        return self._map_json_to_collection(res)

    def discover(self, selection_id=None):
        res = self._do_request("/mixed-selections", {}, self.api_cache["discover"])

        if selection_id and "collection" in res:
            res = self._find_id_in_selection(res["collection"], selection_id)

        return self._map_json_to_collection(res)

    def charts(self, filters):
        res = self._do_request("/charts", filters)
        res = {"collection": [item["track"] for item in res["collection"]]}
        return self._map_json_to_collection(res)

    def call(self, url):
        url = urllib.parse.urlparse(url)
        res = self._do_request(url.path, urllib.parse.parse_qs(url.query))
        return self._map_json_to_collection(res)

    def get_me(self):
        """
        Returns the authenticated user's profile object (or None if the
        request fails — e.g. no token, expired token, network error).

        Cached for 24h so we don't hit /me on every menu navigation.
        """
        # If we've already detected an invalid token earlier this session,
        # short-circuit to avoid the double round-trip (auth fail + retry
        # which also fails because /me requires a user). The user must
        # update the token in settings to recover.
        if getattr(self, "_token_invalid", False):
            return None

        if not self.settings.get_oauth_token():
            return None

        cache_key = "api-me-profile"
        cached = self.cache.get(cache_key, 1440)  # 24h
        if cached:
            try:
                return json.loads(cached)
            except ValueError:
                pass

        res = self._do_request("/me", {})
        # _do_request returns {"collection": []} on errors, so a real /me
        # response is recognisable by the presence of an "id" key.
        if isinstance(res, dict) and "id" in res:
            try:
                self.cache.add(cache_key, json.dumps(res))
            except Exception:
                pass
            return res
        return None

    def get_my_user_id(self):
        """Convenience wrapper — returns just the user id, or None."""
        me = self.get_me()
        if me:
            return me.get("id")
        return None

    def resolve_id(self, id):
        res = self._do_request("/tracks", {"ids": id})
        return self._map_json_to_collection({"collection": res})

    def resolve_url(self, url):
        url = self._sanitize_url(url)
        res = self._do_request("/resolve", {"url": url})
        return self._map_json_to_collection(res)

    def resolve_media_url(self, url):
        """
        Resolves a transcoding URL (e.g. /media/.../stream/hls) to the actual
        playable stream URL.

        Note: SoundCloud HLS/progressive transcoding URLs are short-lived
        (typically 30 minutes after the parent track was fetched). If the
        URL has expired, the API responds 404 and we return None — the
        caller (plugin.py play handler) is responsible for telling Kodi
        the resolution failed via setResolvedUrl(succeeded=False).
        """
        url = urllib.parse.urlparse(url)
        res = self._do_request(url.path, urllib.parse.parse_qs(url.query))
        resolved = res.get("url") if isinstance(res, dict) else None
        if not resolved:
            xbmc.log(
                "plugin.audio.soundcloud::ApiV2() Could not resolve stream URL %s "
                "(probably expired transcoding token)" % url.path,
                xbmc.LOGWARNING,
            )
        return resolved

    def _do_request(self, path, payload, cache=0, _retry_after_401=False):
        # Read the current token from settings. We always re-read because
        # the user might have just edited it (Settings now creates a fresh
        # Addon() per call to bypass Kodi's in-memory caching).
        current_token = self.settings.get_oauth_token()

        # If the token has changed since we last marked it invalid, reset
        # the flag so the new token gets a fresh chance. This way the user
        # doesn't have to restart Kodi after pasting a new token.
        if (
            getattr(self, "_token_invalid", False)
            and current_token
            and current_token != getattr(self, "_last_invalid_token", None)
        ):
            xbmc.log(
                "plugin.audio.soundcloud::ApiV2() OAuth token changed since "
                "last 401 — re-enabling auth for this session",
                xbmc.LOGINFO,
            )
            self._token_invalid = False
            self._last_invalid_token = None

        # Inject OAuth token when the user has configured one in the settings.
        # However, if we've previously seen the token rejected with 401, we
        # disable it for the rest of this session — otherwise we keep getting
        # 401s on EVERY endpoint (even public ones like /charts) because
        # SoundCloud refuses any request bearing an invalid token.
        oauth_token = (
            current_token
            if not getattr(self, "_token_invalid", False)
            else None
        )
        authenticated = bool(oauth_token)

        # The client_id is required for unauthenticated calls. When we have
        # an OAuth token we leave it out — sending both can cause some /me/*
        # endpoints to return empty collections (the API arbitrates between
        # the two and the client_id "wins" the user context, giving back the
        # client_id app's empty profile instead of the user's data).
        if not authenticated:
            payload["client_id"] = self.api_client_id
        payload["app_locale"] = self.api_lang

        headers = {"Accept-Encoding": "gzip", "User-Agent": self.api_user_agent}
        if authenticated:
            headers["Authorization"] = "OAuth " + oauth_token

        path = self.api_host + path
        cache_key = hashlib.sha1((path + str(payload)).encode()).hexdigest()

        # Redact the token before logging the headers.
        log_headers = dict(headers)
        if "Authorization" in log_headers:
            log_headers["Authorization"] = "OAuth <redacted>"

        xbmc.log(
            "plugin.audio.soundcloud::ApiV2() Calling %s with header %s and payload %s" %
            (path, str(log_headers), str(payload)),
            xbmc.LOGDEBUG
        )

        # If caching is active, check for an existing cached file.
        if cache:
            cached_response = self.cache.get(cache_key, cache)
            if cached_response:
                xbmc.log("plugin.audio.soundcloud::ApiV2() Cache hit", xbmc.LOGDEBUG)
                return json.loads(cached_response)

        # Send the request.
        raw = requests.get(path, headers=headers, params=payload)

        # Status-code-aware handling. We log the body on errors (truncated)
        # so debug logs reveal the real cause without crashing the addon.
        body_preview = (raw.text or "")[:200]

        if authenticated and raw.status_code in (401, 403) and not _retry_after_401:
            xbmc.log(
                "plugin.audio.soundcloud::ApiV2() Authentication failed (HTTP %d) on %s. "
                "Body: %r. The OAuth token is missing, invalid or expired. "
                "Disabling token for the rest of this session — "
                "update it in Settings > Account > OAuth token to fix." %
                (raw.status_code, path, body_preview),
                xbmc.LOGWARNING
            )
            self._notify_auth_error()
            # Mark the token as invalid for the rest of this Python session
            # so subsequent calls don't keep failing with 401 on every
            # endpoint (including public ones like /charts).
            # We also remember WHICH token was rejected, so when the user
            # pastes a new one we can detect the change and try again.
            self._token_invalid = True
            self._last_invalid_token = current_token
            # Retry the same request immediately, this time anonymously.
            # The _retry_after_401 flag prevents infinite recursion if the
            # endpoint somehow returns 401 even unauthenticated.
            retry_path = path.replace(self.api_host, "", 1)
            # Drop any auth-side payload key we may have added (defensive,
            # currently none). The recursive call adds client_id itself.
            payload.pop("oauth_token", None)
            return self._do_request(
                retry_path, payload, cache, _retry_after_401=True
            )

        if raw.status_code >= 400:
            xbmc.log(
                "plugin.audio.soundcloud::ApiV2() HTTP %d on %s. Body: %r" %
                (raw.status_code, path, body_preview),
                xbmc.LOGWARNING
            )
            return {"collection": []}

        # Some endpoints can return an empty body (204 No Content, or even
        # a successful 200 with no body for empty user lists). Don't crash.
        if not raw.text or not raw.text.strip():
            xbmc.log(
                "plugin.audio.soundcloud::ApiV2() Empty body on %s (status %d)" %
                (path, raw.status_code),
                xbmc.LOGDEBUG
            )
            return {"collection": []}

        try:
            response = raw.json()
        except ValueError as e:
            xbmc.log(
                "plugin.audio.soundcloud::ApiV2() Non-JSON response on %s (status %d): %s. "
                "Body: %r" %
                (path, raw.status_code, str(e), body_preview),
                xbmc.LOGWARNING
            )
            return {"collection": []}

        # If caching is active, cache the response.
        if cache:
            self.cache.add(cache_key, json.dumps(response))

        return response

    _auth_error_notified = False

    def _notify_auth_error(self):
        """
        Shows a non-blocking notification about an invalid OAuth token.
        Guarded so we only bother the user once per plugin invocation.
        """
        if ApiV2._auth_error_notified:
            return
        ApiV2._auth_error_notified = True
        try:
            import xbmcaddon
            import xbmcgui
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getAddonInfo("name"),
                addon.getLocalizedString(30024),
                xbmcgui.NOTIFICATION_WARNING,
                5000
            )
        except Exception:
            # Never let a notification failure break playback.
            pass

    def _extract_media_url(self, transcodings):
        setting = self.settings.get("audio.format")
        for codec in transcodings:
            if self._is_preferred_codec(codec["format"], self.settings.AUDIO_FORMATS[setting]):
                return codec["url"]

        # Fallback
        return transcodings[0]["url"] if len(transcodings) else None

    def _find_id_in_selection(self, selection, selection_id):
        for category in selection:
            if category["id"] == selection_id:
                if "items" in category:
                    return category["items"]
                elif "tracks" in category:
                    return {"collection": category["tracks"]}
            elif "items" in category:
                res = self._find_id_in_selection(category["items"]["collection"], selection_id)
                if res:
                    return res

    def _map_json_to_collection(self, json_obj):
        collection = ApiCollection()
        collection.items = []  # Reset list in order to resolve problems in unit tests.
        collection.load = []
        collection.next_href = json_obj.get("next_href", None)

        if "kind" in json_obj and json_obj["kind"] == "track":
            # If we are dealing with a single track, pack it into a dict
            json_obj = {"collection": [json_obj]}

        if "collection" in json_obj:

            for item in json_obj["collection"]:
                kind = item.get("kind", None)

                # /me/* endpoints wrap the actual content in a "like" / "repost" /
                # "playlist-like" envelope with the real object nested inside.
                # Unwrap so the rest of the code sees the underlying track / playlist.
                if kind in ("like", "track-like"):
                    if isinstance(item.get("track"), dict):
                        item = item["track"]
                        kind = item.get("kind", "track")
                    elif isinstance(item.get("playlist"), dict):
                        item = item["playlist"]
                        kind = item.get("kind", "playlist")
                    else:
                        continue
                elif kind in ("track-repost", "repost"):
                    if isinstance(item.get("track"), dict):
                        item = item["track"]
                        kind = item.get("kind", "track")
                    else:
                        continue
                elif kind == "playlist-like":
                    if isinstance(item.get("playlist"), dict):
                        item = item["playlist"]
                        kind = item.get("kind", "playlist")
                    else:
                        continue
                elif kind == "playlist-repost":
                    if isinstance(item.get("playlist"), dict):
                        item = item["playlist"]
                        kind = item.get("kind", "playlist")
                    else:
                        continue

                if kind == "track":
                    if "title" not in item:
                        # Track not fully returned by API
                        collection.load.append(item["id"])
                        continue

                    track = self._build_track(item)
                    collection.items.append(track)

                elif kind == "user":
                    user = User(id=item["id"], label=item["username"])
                    user.label2 = item.get("full_name", "")
                    user.thumb = self._get_thumbnail(item, self.thumbnail_size)
                    user.fanart = self._get_user_banner(item)
                    user.info = {
                        "description": item.get("description", ""),
                        "followers": item.get("followers_count", 0)
                    }
                    collection.items.append(user)

                elif kind == "playlist":
                    playlist = Playlist(id=item["id"], label=item.get("title"))
                    playlist.is_album = item.get("is_album", False)
                    playlist.label2 = item.get("label_name", "")
                    playlist.thumb = self._get_thumbnail(item, self.thumbnail_size)
                    playlist.fanart = playlist.thumb
                    playlist.info = {
                        "artist": item["user"]["username"],
                        "description": item.get("description", ""),
                        "likes": item.get("likes_count", 0),
                        "track_count": item.get("track_count", 0),
                    }
                    collection.items.append(playlist)

                elif kind == "system-playlist":
                    # System playlists only appear inside selections
                    playlist = Selection(id=item["id"], label=item.get("title"))
                    playlist.thumb = self._get_thumbnail(item, self.thumbnail_size)
                    collection.items.append(playlist)

                elif kind == "selection":
                    selection = Selection(id=item["id"], label=item.get("title"))
                    selection.label2 = item.get("description", "")
                    collection.items.append(selection)

                else:
                    xbmc.log("plugin.audio.soundcloud::ApiV2() "
                             "Could not convert JSON kind to model...",
                             xbmc.LOGWARNING)

        elif "tracks" in json_obj:

            for item in json_obj["tracks"]:
                if "title" not in item:
                    # Track not fully returned by API
                    collection.load.append(item["id"])
                    continue

                track = self._build_track(item)
                track.label2 = json_obj["title"]
                collection.items.append(track)

        else:
            raise RuntimeError("ApiV2 JSON seems to be invalid")

        # Load unresolved tracks
        if collection.load:
            # The API only supports a max of 50 track IDs per request:
            for chunk in self._chunks(collection.load, self.api_limit_tracks):
                track_ids = ",".join(str(x) for x in chunk)
                loaded_tracks = self._do_request("/tracks", {"ids": track_ids})
                # Because returned tracks are not sorted, we have to manually match them
                for track_id in chunk:
                    loaded_track = [lt for lt in loaded_tracks if lt["id"] == track_id]
                    if len(loaded_track):  # Sometimes a track cannot be resolved
                        track = self._build_track(loaded_track[0])
                        collection.items.append(track)

        return collection

    def _build_track(self, item):
        album = None
        if type(item.get("publisher_metadata")) is dict:
            artist = item["publisher_metadata"].get("artist", item["user"]["username"])
            album = item["publisher_metadata"].get("album_title")
        else:
            artist = item["user"]["username"]

        track = Track(id=item["id"], label=item["title"])
        track.blocked = True if item.get("policy") == "BLOCK" else False
        track.preview = True if item.get("policy") == "SNIP" else False
        track.thumb = self._get_thumbnail(item, self.thumbnail_size)
        track.fanart = track.thumb  # Artwork doubles as fanart for detail views.
        track.media = self._extract_media_url(item["media"]["transcodings"])
        track.info = {
            "artist": artist,
            "album": album,
            "genre": item.get("genre", None),
            "date": item.get("display_date", None),
            "description": item.get("description", None),
            "duration": int(item["duration"]) / 1000,
            "playback_count": item.get("playback_count", 0)
        }

        return track

    @staticmethod
    def fetch_client_id():
        headers = {"Accept-Encoding": "gzip", "User-Agent": ApiV2.api_user_agent}

        # Get the HTML (includes a reference to the JS file we need)
        html = requests.get("https://soundcloud.com/", headers=headers).text

        # Extract the HREF to the JS file (which contains the API key)
        matches = re.findall(r"=\"(https://a-v2\.sndcdn\.com/assets/.*.js)\"", html)

        if matches:
            for match in matches:
                # Get the JS
                response = requests.get(match, headers=headers)
                response.encoding = "utf-8"  # This speeds up `response.text` by 3 seconds

                # Extract the API key
                key = re.search(r"client_application_id:[1-9]+,client_id:\"(\w*)\"", response.text)

                if key:
                    return str(key.group(1))

            raise Exception("Failed to extract client key from js")
        else:
            raise Exception("Failed to extract js href from html")

    @staticmethod
    def _is_preferred_codec(codec, setting):
        return codec["mime_type"] == setting["mime_type"] and \
               codec["protocol"] == setting["protocol"]

    @staticmethod
    def _sanitize_url(url):
        return url.replace("m.soundcloud.com/", "soundcloud.com/")

    @staticmethod
    def _get_thumbnail(item, size):
        """
        availableSizes: [
          [ 20, 't20x20'],
          [ 50, 't50x50'],
          [120, 't120x120'],
          [200, 't200x200'],
          [500, 't500x500']
        ]
        """
        url = item.get(
            "artwork_url", item.get("avatar_url", item.get("calculated_artwork_url", False))
        )

        return re.sub(
            r"^(.*/)(\w+)-([-a-zA-Z0-9]+)-([a-z0-9]+)\.(jpg|png|gif).*$",
            r"\1\2-\3-t{x}x{y}.\5".format(x=size, y=size),
            url
        ) if url else None

    @staticmethod
    def _get_user_banner(item):
        """
        SoundCloud user objects can include a `visuals` section with the
        profile-page banner (usually 2480x520 px). We use it as fanart so
        the detail view of an artist looks rich instead of showing the
        addon's default fanart.

        Structure:
          "visuals": {"visuals": [{"visual_url": "https://..."}]}
        """
        visuals = item.get("visuals") or {}
        inner = visuals.get("visuals") or []
        if inner and isinstance(inner, list):
            url = inner[0].get("visual_url")
            if url:
                return url
        return None

    @staticmethod
    def _chunks(lst, size):
        for i in range(0, len(lst), size):
            yield lst[i:i + size]
