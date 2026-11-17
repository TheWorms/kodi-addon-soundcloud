"""
Playback of the resolved SoundCloud stream URL.

Since late 2026 SoundCloud only serves most tracks as AAC in HLS
(fragmented MP4 segments: presets aac_160k / aac_96k, plus the abr_*
master playlist); the MP3 and Opus transcodings are gone.

Kodi's music player (PAPlayer) reads these playlists badly: no sound,
each track skipped after a few seconds, Kodi crashing in the audio
decoder (CoreELEC 21.3). inputstream.adaptive takes a bare media
playlist for video and fails. VideoPlayer plays them, but Kodi then
treats the music as a video (no screensaver) and seeking freezes.

6.0.10: the add-on service runs a local relay (hls_relay.py) that
serves the playlist as ONE continuous MP4 file (duration and seek
index included) on 127.0.0.1, which PAPlayer plays like any .m4a:
seeking, screensaver, gapless queueing and the music OSD all behave as
with the old MP3 streams. When the relay is not running (service not
started yet), HLS items fall back to VideoPlayer (audio/aacp MIME type,
Kodi's player rules send it there), as in 6.0.9.
"""

import urllib.parse

import xbmc
import xbmcgui

# Home window property where service.py publishes the relay's port.
RELAY_PORT_PROPERTY = "soundcloud.relay_port"
RELAY_PATH = "/stream"  # no extension: see hls_relay.RELAY_PATH
RELAY_MIME = "audio/mp4"
# MIME type that makes Kodi pick VideoPlayer instead of PAPlayer.
VIDEOPLAYER_MIME = "audio/aacp"
_LOG_PREFIX = "plugin.audio.soundcloud::stream "


def is_hls_url(url):
    """True for an HLS playlist URL (resolved .m3u8) or an HLS
    transcoding URL of the SoundCloud API (/stream/hls)."""
    if not url:
        return False
    try:
        path = urllib.parse.urlparse(url).path.lower()
    except (TypeError, ValueError):
        return False
    return path.endswith(".m3u8") or path.endswith("/stream/hls")


def relay_port():
    """Port of the service's relay, or 0 when it is not running."""
    try:
        return int(xbmcgui.Window(10000).getProperty(RELAY_PORT_PROPERTY) or 0)
    except (TypeError, ValueError):
        return 0


def relay_url(port, playlist_url):
    return "http://127.0.0.1:%d%s?u=%s" % (
        port, RELAY_PATH, urllib.parse.quote(playlist_url, safe=""))


def prepare_item(list_item, resolved_url, media_url=None):
    """
    Points list_item at the URL Kodi should play. HLS goes through the
    local relay (music player) or, without it, to VideoPlayer. Returns
    "relay", "videoplayer" or "" (plain stream, left to Kodi).
    """
    list_item.setPath(resolved_url)
    hls = is_hls_url(resolved_url) or is_hls_url(media_url)
    if not (hls and resolved_url.startswith("http")):
        return ""

    port = relay_port()
    if port:
        list_item.setPath(relay_url(port, resolved_url))
        list_item.setMimeType(RELAY_MIME)
        list_item.setContentLookup(False)
        xbmc.log(_LOG_PREFIX + "HLS stream relayed to the music player", xbmc.LOGINFO)
        return "relay"

    list_item.setMimeType(VIDEOPLAYER_MIME)
    list_item.setContentLookup(False)
    xbmc.log(
        _LOG_PREFIX + "relay not running: HLS stream handed to VideoPlayer",
        xbmc.LOGWARNING,
    )
    return "videoplayer"
