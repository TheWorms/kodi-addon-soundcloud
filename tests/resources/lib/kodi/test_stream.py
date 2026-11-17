import sys
from unittest import TestCase
from unittest.mock import MagicMock, patch

sys.modules.setdefault("xbmc", MagicMock())
sys.modules.setdefault("xbmcaddon", MagicMock())
sys.modules.setdefault("xbmcgui", MagicMock())
from resources.lib.kodi import stream  # noqa: E402

HLS = "https://playback.media-streaming.soundcloud.cloud/x/aac_160k/y/playlist.m3u8?expires=1"
MP3 = "https://cf-media.sndcdn.com/abc.128.mp3?Policy=x"
HLS_MEDIA = "https://api-v2.soundcloud.com/media/soundcloud:tracks:1/abc/stream/hls"


class StreamTestCase(TestCase):
    def test_is_hls_url(self):
        self.assertTrue(stream.is_hls_url(HLS))
        self.assertTrue(stream.is_hls_url(HLS_MEDIA))
        self.assertFalse(stream.is_hls_url(MP3))
        self.assertFalse(stream.is_hls_url(None))
        self.assertFalse(stream.is_hls_url(""))

    @patch.object(stream, "relay_port", return_value=40123)
    def test_hls_goes_through_the_relay(self, _port):
        item = MagicMock()
        self.assertEqual(stream.prepare_item(item, HLS, HLS_MEDIA), "relay")
        url = item.setPath.call_args_list[-1].args[0]
        self.assertTrue(url.startswith("http://127.0.0.1:40123/stream?u="))
        self.assertIn("playback.media-streaming.soundcloud.cloud", url)
        self.assertNotIn("&expires", url)  # the playlist URL is quoted whole
        item.setMimeType.assert_called_once_with("audio/mp4")
        item.setContentLookup.assert_called_once_with(False)
        item.setProperty.assert_not_called()

    @patch.object(stream, "relay_port", return_value=0)
    def test_without_relay_falls_back_to_videoplayer(self, _port):
        item = MagicMock()
        self.assertEqual(stream.prepare_item(item, HLS, HLS_MEDIA), "videoplayer")
        item.setPath.assert_called_once_with(HLS)
        item.setMimeType.assert_called_once_with("audio/aacp")
        item.setProperty.assert_not_called()

    @patch.object(stream, "relay_port", return_value=40123)
    def test_progressive_left_to_kodi(self, _port):
        item = MagicMock()
        self.assertEqual(stream.prepare_item(
            item, MP3, "https://api-v2.soundcloud.com/m/stream/progressive"), "")
        item.setPath.assert_called_once_with(MP3)
        item.setMimeType.assert_not_called()
