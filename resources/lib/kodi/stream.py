"""
Playback of the resolved SoundCloud stream URL.

Since late 2026 SoundCloud only serves most tracks as AAC in HLS
(fragmented MP4 segments: presets aac_160k / aac_96k, plus the abr_*
master playlist); the MP3 and Opus transcodings are gone.

Kodi gives an item queued in the music playlist to its audio player,
PAPlayer, which reads these playlists badly: no sound, each track
skipped after a few seconds ("Error reading samples"), the decoder
sometimes reporting dozens of channels, and Kodi crashing (segfault in
the audio decoder thread, seen on CoreELEC 21.3).

inputstream.adaptive is no way out either: given a bare media playlist
(no master playlist naming the codec) it assumes a video track and
fails ("No suitable Track atom found in stream").

VideoPlayer, Kodi's main player, reads the same playlists with its
built-in HLS reader (FFmpeg) like any .m3u8 link. Kodi's player rules
send internet streams with the audio/aacp MIME type to VideoPlayer, so
HLS items carry that MIME type. Progressive (plain HTTP) streams keep
going to PAPlayer as before.
"""

import urllib.parse

import xbmc

# MIME type that makes Kodi pick VideoPlayer instead of PAPlayer.
PLAYER_MIME = "audio/aacp"
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


def prepare_item(list_item, resolved_url, media_url=None):
    """
    Points list_item at resolved_url and, for HLS, makes Kodi play it
    with VideoPlayer. Returns True when the item was marked as HLS.
    """
    list_item.setPath(resolved_url)
    if not (is_hls_url(resolved_url) or is_hls_url(media_url)):
        return False
    list_item.setMimeType(PLAYER_MIME)
    list_item.setContentLookup(False)
    xbmc.log(_LOG_PREFIX + "HLS stream handed to VideoPlayer", xbmc.LOGINFO)
    return True
