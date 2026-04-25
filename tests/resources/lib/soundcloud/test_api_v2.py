import json
import sys
from unittest import mock, TestCase
from unittest.mock import MagicMock, Mock, DEFAULT, ANY
sys.modules["xbmc"] = MagicMock()
sys.modules["xbmcaddon"] = MagicMock()
sys.modules["xbmcgui"] = MagicMock()
from resources.lib.kodi.settings import Settings
from resources.lib.soundcloud.api_v2 import ApiV2


class ApiV2TestCase(TestCase):
    def setUp(self):
        self.api = ApiV2(settings=Settings(MagicMock()), lang="en", cache=MagicMock())
        self.api.settings.get = self._side_effect_settings_get

    @staticmethod
    def _side_effect_do_request(*args):
        if args[0] == "/tracks":
            if args[1].get("ids") == "53787294":
                with open("./tests/mocks/api_v2_playlist_tracks.json") as f:
                    mock_data = f.read()
            else:
                with open("./tests/mocks/api_v2_discover_tracks.json") as f:
                    mock_data = f.read()
            return json.loads(mock_data)
        else:
            return DEFAULT

    @staticmethod
    def _side_effect_settings_get(*args):
        if args[0] == "audio.format":
            return "2"  # Default in settings (mp3 progressive)
        else:
            return DEFAULT

    @staticmethod
    def _side_effect_request_get(*args, **keywargs):
        if args[0] == "https://soundcloud.com/":
            with open("./tests/mocks/html/soundcloud.com.html") as f:
                mock_data = f.read()
            obj = mock.Mock()
            obj.text = mock_data
            return obj
        elif args[0] == "https://a-v2.sndcdn.com/assets/0-744ba03a-3.js":
            with open("./tests/mocks/html/assets.0-744ba03a-3.js") as f:
                mock_data = f.read()
            obj = mock.Mock()
            obj.text = mock_data
            return obj
        elif args[0] == "https://a-v2.sndcdn.com/assets/49-4786eb1d-3.js":
            with open("./tests/mocks/html/assets.49-4786eb1d-3.js") as f:
                mock_data = f.read()
            obj = mock.Mock()
            obj.text = mock_data
            return obj
        else:
            return DEFAULT

    def test_search(self):
        with open("./tests/mocks/api_v2_search_tracks.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))

        res = self.api.search("foo")

        self.assertEqual(res.items[0].label, "Deadmau5 - Raise Your Weapon (Noisia Remix)")
        self.assertEqual(res.items[0].info["artist"], "NOISIA")
        self.assertEqual(res.items[0].info["description"], "The description (1)")
        self.assertEqual(res.items[0].info["duration"], 194.763)
        self.assertEqual(res.items[0].info["genre"], "Dubstep")
        self.assertEqual(res.items[0].info["date"], "2011-05-23T16:22:06Z")
        self.assertEqual(res.items[0].media, "https://api-v2.soundcloud.com/media/soundcloud:tracks:15784497/580ad806-b3ab-440f-adbe-c12a83258a37/stream/progressive")
        self.assertEqual(res.items[0].thumb, "https://i1.sndcdn.com/artworks-000007527658-smjpzh-t500x500.jpg")

        self.assertEqual(res.items[1].label, "Labrinth ft. Tinie Tempah - Earthquake (Noisia Remix)")
        self.assertEqual(res.items[1].info["artist"], "NOISIA")
        self.assertEqual(res.items[1].info["description"], "The description (2)")
        self.assertEqual(res.items[1].info["duration"], 389.371)
        self.assertEqual(res.items[1].info["genre"], "Dubstep")
        self.assertEqual(res.items[1].info["date"], "2011-09-17T15:39:49Z")
        self.assertEqual(res.items[1].media, "https://api-v2.soundcloud.com/media/soundcloud:tracks:23547065/e7846551-5c8e-4b93-b4f0-f94bfa7b1275/stream/progressive")
        self.assertEqual(res.items[1].thumb, "https://i1.sndcdn.com/artworks-000011681052-n1a6w6-t500x500.jpg")

    def test_search_playlists(self):
        with open("./tests/mocks/api_v2_search_playlists_without_albums.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))

        res = self.api.search("foo")

        self.assertEqual(res.items[0].label, "Noisia")
        self.assertEqual(res.items[0].info["artist"], "Sebastian Morad")
        self.assertEqual(res.items[0].thumb, "https://i1.sndcdn.com/artworks-000498621510-fk1ovg-t500x500.jpg")

        self.assertEqual(res.items[1].label, "NOISIA")
        self.assertEqual(res.items[1].info["artist"], "Samuel Harris")
        self.assertEqual(res.items[1].thumb, None)

    def test_search_users(self):
        with open("./tests/mocks/api_v2_search_users.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))

        res = self.api.search("foo")

        self.assertEqual(res.items[0].label, "NOISIA")
        self.assertEqual(res.items[0].label2, "Outer Edges")
        self.assertEqual(res.items[0].thumb, "https://i1.sndcdn.com/avatars-000451809714-n5njwk-t500x500.jpg")

        self.assertEqual(res.items[1].label, "Noisia Radio")
        self.assertEqual(res.items[1].label2, "Noisia  Radio")
        self.assertEqual(res.items[1].thumb, "https://i1.sndcdn.com/avatars-000559848966-7tof1c-t500x500.jpg")

    def test_playlist(self):
        with open("./tests/mocks/api_v2_playlists.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))
        self.api._do_request.side_effect = self._side_effect_do_request

        res = self.api.search("foo")

        self.assertEqual(res.items[0].label, "Rock Your Body - Justin Timberlake (Alex Dogmatic Remix)")
        self.assertEqual(res.items[1].label, "Philip's Push")
        self.assertEqual(res.items[2].label, "The Man I Want To Be")
        self.assertEqual(res.items[3].label, "2004 Car Commercial")

    def test_resolve_id(self):
        with open("./tests/mocks/api_v2_tracks.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))

        res = self.api.resolve_id(273627408)

        self.assertEqual(res.items[0].label, "Voodoo (Outer Edges)")
        self.assertEqual(res.items[0].media, "https://api-v2.soundcloud.com/media/soundcloud:tracks:273627408/d35bd07a-3adb-4620-a876-7770f80ff48d/stream/progressive")

    def test_resolve_url(self):
        with open("./tests/mocks/api_v2_resolve_track.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))

        res = self.api.resolve_url("https://m.soundcloud.com/user/foo")
        # The SoundCloud APIv2 can't resolve mobile links (m.soundcloud.com), so they have to
        # be fixed manually. The following assertion is testing this.
        self.api._do_request.assert_called_with(ANY, {"url": "https://soundcloud.com/user/foo"})
        self.assertEqual(res.items[0].label, "Thomas Hayden - Universe")
        self.assertEqual(res.items[0].media, "https://api-v2.soundcloud.com/media/soundcloud:tracks:584959245/631cc995-e8f2-4a62-a212-5a5768046bc2/stream/progressive")

    def test_discover(self):
        with open("./tests/mocks/api_v2_discover.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))
        self.api._do_request.side_effect = self._side_effect_do_request

        # Level 1
        res = self.api.discover()
        self.assertEqual(res.items[0].label, "Chill")
        self.assertEqual(res.items[1].label, "Party")
        self.assertEqual(res.items[2].label, "Charts: New & hot")
        self.assertEqual(res.items[3].label, "Charts: Top 50")

        # Level 2
        res = self.api.discover("soundcloud:selections:charts-top")
        self.assertEqual(res.items[0].label, "Top 50: All music genres")
        self.assertEqual(res.items[1].label, "Top 50: Alternative Rock")
        self.assertEqual(res.items[2].label, "Top 50: Ambient")

        # Level 3
        res = self.api.discover("soundcloud:system-playlists:charts-top:all-music:at")
        self.assertEqual(res.load[0], 683327426)
        self.assertEqual(res.load[1], 591031647)
        self.assertEqual(res.items[0].label, "110")
        self.assertEqual(res.items[1].label, "THis iS thE LiFe - TEKK Remix")

    def test_charts(self):
        with open("./tests/mocks/api_v2_charts.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))

        res = self.api.charts({})
        self.assertEqual(res.items[0].label, "Stop Snitchin")
        self.assertEqual(res.items[0].preview, True)
        self.assertEqual(res.items[1].label, "Young Nudy X Playboi Carti - Pissy Pamper Aka KID CUDI (Slimerre Shit)")
        self.assertEqual(res.items[1].preview, False)

    def test_blocked(self):
        with open("./tests/mocks/api_v2_tracks_blocked.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))

        res = self.api.resolve_id("country blocks suck")
        self.assertEqual(res.items[0].blocked, True)

    def test_audio_format(self):
        with open("./tests/mocks/api_v2_tracks.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))
        self.api.settings.get = Mock(return_value="0")

        res = self.api.resolve_id(1)

        self.assertEqual(res.items[0].media, "https://api-v2.soundcloud.com/media/soundcloud:tracks:273627408/23d4e278-f8c0-4438-ace8-201dbd242a1c/stream/hls")

    def test_call(self):
        with open("./tests/mocks/api_v2_search_playlists_without_albums.json") as f:
            mock_data = f.read()

        self.api._do_request = Mock(return_value=json.loads(mock_data))

        res = self.api.call("/playlists/1")

        self.assertEqual(res.items[0].label, "Noisia")
        self.assertEqual(res.items[1].label, "NOISIA")

    @mock.patch("requests.get")
    def test_fetch_client_id(self, mock_method):
        mock_method.side_effect = self._side_effect_request_get

        client_id = self.api.fetch_client_id()
        self.assertEqual(client_id, "1XduoqV99lROqCMpijtDo5WnJmpaLuYm")

    @mock.patch("requests.get")
    def test_do_request_without_oauth_token_sends_no_auth_header(self, mock_get):
        """When no OAuth token is configured, no Authorization header is sent."""
        self.api.api_client_id_cache_key = "unused"
        self.api.cache.get = Mock(return_value="fake_client_id")
        self.api.settings.get_oauth_token = Mock(return_value=None)

        response = Mock()
        response.status_code = 200
        response.text = '{"collection": []}'
        response.json.return_value = {"collection": []}
        mock_get.return_value = response

        self.api._do_request("/search/tracks", {"q": "foo"})

        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        self.assertNotIn("Authorization", headers)

    @mock.patch("requests.get")
    def test_do_request_with_oauth_token_sends_auth_header(self, mock_get):
        """When an OAuth token is configured, an Authorization: OAuth <token>
        header is sent and the client_id is OMITTED (sending both can cause
        /me/* endpoints to return empty collections)."""
        self.api.cache.get = Mock(return_value="fake_client_id")
        self.api.settings.get_oauth_token = Mock(return_value="1-12345-67890-abcdef")

        response = Mock()
        response.status_code = 200
        response.text = '{"collection": []}'
        response.json.return_value = {"collection": []}
        mock_get.return_value = response

        self.api._do_request("/me/likes/tracks", {})

        _, kwargs = mock_get.call_args
        headers = kwargs.get("headers", {})
        params = kwargs.get("params", {})
        self.assertEqual(headers.get("Authorization"), "OAuth 1-12345-67890-abcdef")
        self.assertNotIn("client_id", params)

    @mock.patch("requests.get")
    def test_map_unwraps_like_envelope(self, mock_get):
        """Items returned by /me/likes/tracks are wrapped in a {kind: 'like',
        track: {...}} envelope. The mapper should unwrap them so they appear
        as regular tracks."""
        self.api.cache.get = Mock(return_value="fake_client_id")
        self.api.settings.get_oauth_token = Mock(return_value="any-token")

        # Realistic shape (trimmed) of a /me/likes/tracks response.
        with open("./tests/mocks/api_v2_search_tracks.json") as f:
            inner_tracks = json.load(f)["collection"]
        wrapped = {
            "collection": [
                {"kind": "like", "created_at": "2024-01-01", "track": t}
                for t in inner_tracks
            ]
        }
        response = Mock()
        response.status_code = 200
        response.text = json.dumps(wrapped)
        response.json.return_value = wrapped
        mock_get.return_value = response

        res = self.api.call("/me/likes/tracks")
        self.assertEqual(len(res.items), len(inner_tracks))
        self.assertEqual(type(res.items[0]).__name__, "Track")

    @mock.patch("requests.get")
    def test_do_request_handles_empty_body_without_crashing(self, mock_get):
        """Some endpoints return an empty body (204, or 200 with no body).
        Don't crash with JSONDecodeError — return an empty collection."""
        self.api.cache.get = Mock(return_value="fake_client_id")
        self.api.settings.get_oauth_token = Mock(return_value=None)

        response = Mock()
        response.status_code = 200
        response.text = ""
        # Configure .json() to raise like requests would on empty body.
        response.json = Mock(side_effect=ValueError("Expecting value"))
        mock_get.return_value = response

        result = self.api._do_request("/charts", {})
        self.assertEqual(result, {"collection": []})

    @mock.patch("requests.get")
    def test_do_request_handles_401_without_crashing(self, mock_get):
        """A 401 from an authenticated request returns an empty collection
        instead of crashing on JSON parse — this is the regression we
        were fixing for /me/* endpoints."""
        self.api.cache.get = Mock(return_value="fake_client_id")
        self.api.settings.get_oauth_token = Mock(return_value="bad-token")

        response = Mock()
        response.status_code = 401
        response.text = ""
        response.json = Mock(side_effect=ValueError("Expecting value"))
        mock_get.return_value = response

        result = self.api._do_request("/me/likes/tracks", {})
        self.assertEqual(result, {"collection": []})

    @mock.patch("requests.get")
    def test_do_request_handles_non_json_response(self, mock_get):
        """If the server returns HTML or plain text, don't crash."""
        self.api.cache.get = Mock(return_value="fake_client_id")
        self.api.settings.get_oauth_token = Mock(return_value=None)

        response = Mock()
        response.status_code = 200
        response.text = "<html>Maintenance</html>"
        response.json = Mock(side_effect=ValueError("Expecting value"))
        mock_get.return_value = response

        result = self.api._do_request("/charts", {})
        self.assertEqual(result, {"collection": []})

    @mock.patch("requests.get")
    def test_get_me_returns_profile_when_authenticated(self, mock_get):
        """GET /me with a valid token returns the user profile dict."""
        self.api.cache.get = Mock(return_value=None)  # no cache hit
        self.api.cache.add = Mock()
        self.api.settings.get_oauth_token = Mock(return_value="valid-token")

        profile = {"id": 123456, "username": "testuser", "kind": "user"}
        response = Mock()
        response.status_code = 200
        response.text = json.dumps(profile)
        response.json.return_value = profile
        mock_get.return_value = response

        me = self.api.get_me()
        self.assertEqual(me["id"], 123456)
        self.assertEqual(self.api.get_my_user_id(), 123456)

    @mock.patch("requests.get")
    def test_get_me_returns_none_without_token(self, mock_get):
        """Without a token we don't even attempt the request."""
        self.api.settings.get_oauth_token = Mock(return_value=None)
        self.assertIsNone(self.api.get_me())
        self.assertIsNone(self.api.get_my_user_id())
        mock_get.assert_not_called()

    @mock.patch("requests.get")
    def test_get_me_returns_none_on_failure(self, mock_get):
        """A 401 returning {"collection": []} should be treated as failure."""
        self.api.cache.get = Mock(return_value=None)
        self.api.settings.get_oauth_token = Mock(return_value="bad-token")

        response = Mock()
        response.status_code = 401
        response.text = ""
        response.json = Mock(side_effect=ValueError())
        mock_get.return_value = response

        self.assertIsNone(self.api.get_me())

    @mock.patch("requests.get")
    def test_resolve_media_url_returns_none_on_404(self, mock_get):
        """Expired transcoding URLs return 404 — resolve_media_url should
        return None instead of crashing, so the play handler can tell Kodi
        to skip the track via setResolvedUrl(succeeded=False)."""
        self.api.cache.get = Mock(return_value="fake_client_id")
        self.api.settings.get_oauth_token = Mock(return_value=None)

        response = Mock()
        response.status_code = 404
        response.text = "{}"
        response.json.return_value = {}
        mock_get.return_value = response

        resolved = self.api.resolve_media_url(
            "https://api-v2.soundcloud.com/media/soundcloud:tracks:1/abc/stream/hls"
        )
        self.assertIsNone(resolved)

    @mock.patch("requests.get")
    def test_do_request_strips_whitespace_in_oauth_token(self, mock_get):
        """Leading/trailing whitespace in the token is stripped (common copy-paste artifact)."""
        self.api.cache.get = Mock(return_value="fake_client_id")

        # Settings now creates a fresh xbmcaddon.Addon() instance for every
        # read, so we patch xbmcaddon.Addon at module level rather than
        # passing a mock to Settings().
        mock_addon = MagicMock()
        mock_addon.getAddonInfo = Mock(return_value="plugin.audio.soundcloud")
        with mock.patch(
            "resources.lib.kodi.settings.xbmcaddon.Addon",
            return_value=mock_addon,
        ):
            mock_addon.getSetting = Mock(return_value="   1-12345-67890-abcdef   ")
            settings = Settings(mock_addon)
            self.assertEqual(settings.get_oauth_token(), "1-12345-67890-abcdef")

            mock_addon.getSetting = Mock(return_value="   ")
            self.assertIsNone(settings.get_oauth_token())

            mock_addon.getSetting = Mock(return_value="")
            self.assertIsNone(settings.get_oauth_token())

    def test_oauth_token_strips_oauth_prefix(self):
        """If user pastes the full Authorization header value
        ('OAuth 1-12345-...' or 'Bearer ...'), strip the prefix
        automatically to avoid silent 401s."""
        from resources.lib.kodi.settings import Settings
        mock_addon = MagicMock()
        mock_addon.getAddonInfo = Mock(return_value="plugin.audio.soundcloud")

        with mock.patch(
            "resources.lib.kodi.settings.xbmcaddon.Addon",
            return_value=mock_addon,
        ):
            for raw, expected in [
                ("OAuth 2-12345-67890-abc", "2-12345-67890-abc"),
                ("oauth 2-12345-67890-abc", "2-12345-67890-abc"),  # lowercase
                ("Bearer abc123", "abc123"),
                ("  OAuth   spaces-token  ", "spaces-token"),
                ('"2-12345-67890-abc"', "2-12345-67890-abc"),  # with quotes
                ("2-12345-67890-abc", "2-12345-67890-abc"),  # already clean
            ]:
                mock_addon.getSetting = Mock(return_value=raw)
                self.assertEqual(
                    Settings(mock_addon).get_oauth_token(),
                    expected,
                    f"Failed for input: {raw!r}",
                )

    @mock.patch("requests.get")
    def test_do_request_falls_back_to_anonymous_on_401(self, mock_get):
        """When a stale OAuth token causes a 401, the API should:
          1. Mark the token as invalid for the rest of the session
          2. Retry the request anonymously (with client_id) and return that
          3. Never include the bad token in subsequent requests
        Without this, every endpoint (even public ones like /charts) would
        fail with 401 until the user manually clears the token."""
        self.api.cache.get = Mock(return_value="fake_client_id")
        self.api.settings.get_oauth_token = Mock(return_value="stale-token")

        # First call: 401. Second call (retry without token): 200 with data.
        bad = Mock()
        bad.status_code = 401
        bad.text = ""
        bad.json = Mock(side_effect=ValueError())

        good = Mock()
        good.status_code = 200
        good.text = '{"collection": [{"id": 1, "kind": "track"}]}'
        good.json.return_value = {"collection": [{"id": 1, "kind": "track"}]}

        mock_get.side_effect = [bad, good]

        result = self.api._do_request("/charts", {})
        self.assertEqual(result, {"collection": [{"id": 1, "kind": "track"}]})
        self.assertTrue(self.api._token_invalid)

        # Subsequent call should NOT use the token (since _token_invalid is set)
        good2 = Mock()
        good2.status_code = 200
        good2.text = '{"collection": []}'
        good2.json.return_value = {"collection": []}
        mock_get.side_effect = [good2]
        self.api._do_request("/some/other/endpoint", {})
        # Verify the second call's headers don't include Authorization
        call_args = mock_get.call_args_list[-1]
        sent_headers = call_args.kwargs.get("headers", {})
        self.assertNotIn("Authorization", sent_headers)


    def test_track_handles_missing_date(self):
        """
        Regression test: tracks without a display_date used to crash the plugin
        with `TypeError: 'NoneType' object is not subscriptable` when trying
        to extract the year. This happens on some tracks returned by /me/*
        endpoints. The fix should result in a track without year/date info
        but no crash.
        """
        from resources.lib.models.track import Track
        track = Track(id=1, label="No date track")
        track.thumb = "https://example.com/t.jpg"
        track.media = "https://example.com/m.mp3"
        track.info = {
            "artist": "Anon",
            "album": None,
            "genre": "Electronic",
            "date": None,                     # <-- the trigger
            "description": None,
            "duration": 100,
            "playback_count": 0,
        }

        # Must not raise.
        url, list_item, is_folder = track.to_list_item("plugin://plugin.audio.soundcloud")
        self.assertIsNotNone(list_item)
        self.assertFalse(is_folder)
