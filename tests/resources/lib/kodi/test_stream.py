import sys
from unittest import TestCase
from unittest.mock import MagicMock

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

    def test_hls_goes_to_videoplayer_without_inputstream(self):
        item = MagicMock()
        self.assertTrue(stream.prepare_item(item, HLS, HLS_MEDIA))
        item.setPath.assert_called_once_with(HLS)
        # audio/aacp: Kodi's player rules send it to VideoPlayer, whose
        # FFmpeg HLS reader handles SoundCloud's fMP4 segments.
        item.setMimeType.assert_called_once_with("audio/aacp")
        item.setContentLookup.assert_called_once_with(False)
        # No inputstream add-on: inputstream.adaptive takes a bare media
        # playlist for video and fails.
        item.setProperty.assert_not_called()

    def test_progressive_left_to_kodi(self):
        item = MagicMock()
        self.assertFalse(stream.prepare_item(
            item, MP3, "https://api-v2.soundcloud.com/m/stream/progressive"))
        item.setPath.assert_called_once_with(MP3)
        item.setMimeType.assert_not_called()
        item.setProperty.assert_not_called()
