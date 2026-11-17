"""
Local relay: SoundCloud's AAC HLS playlist served as one continuous
MP4 file, so Kodi's MUSIC player (PAPlayer) can play it.

Why
---
SoundCloud now serves most tracks only as AAC in HLS: an init segment
(init.mp4: ftyp + moov) and ~10-second fragments (data000.m4s...: styp
+ sidx + moof + mdat). PAPlayer reads such playlists badly (no sound,
crashes); VideoPlayer reads them but then Kodi treats the music as a
video (no screensaver) and seeking freezes.

Concatenated, those pieces form a regular fragmented MP4 file - the same
layout as a DASH "on demand" file - which PAPlayer plays like any .m4a:

    ftyp | moov (durations filled in) | sidx (index of every fragment)
    | moof mdat | moof mdat | ...

The per-fragment styp and sidx boxes are left out and the moov gets
the real track duration (fragmented init segments say 0). Every
fragment gets a fixed-size slot computed from its duration (moof +
mdat, then a "free" box that players skip), so a single sidx can list
the size and duration of every slot as soon as the playlist is read:
FFmpeg knows the length of the track and seeks straight to the right
byte, and the relay answers in two requests whatever the length of the
track (6.0.10 first probed every fragment: 14 s for a one-hour mix, a
frozen Kodi meanwhile). Fragments are downloaded when first read, and
the next one in the background.

Served on 127.0.0.1 only, by the add-on service (service.py), and only
for SoundCloud's CDN hosts.
"""

import re
import struct
import sys
import threading
import time
import urllib.parse
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

# No file extension: Kodi's music player runs TagLib on the file to read
# ReplayGain tags, choosing the parser from the extension, and TagLib's
# MP4 parser walks every top-level box - here, every fragment, i.e. the
# whole track downloaded before the first note (36 s for a one-hour mix).
RELAY_PATH = "/stream"
ALLOWED_HOST_SUFFIXES = (".soundcloud.cloud", ".sndcdn.com")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
SLOT_MARGIN = 1.6
SLOT_EXTRA = 16 * 1024
DEFAULT_KBPS = 256
FRAGMENT_CACHE = 6
POOL_SIZE = 8
CHUNK_SIZE = 64 * 1024
HTTP_TIMEOUT = 20
CACHE_TRACKS = 6

_CONTAINERS = (b"moov", b"trak", b"mdia", b"mvex", b"edts", b"minf")


class RelayError(Exception):
    pass


# ---------------------------------------------------------------- boxes

def iter_boxes(data, start=0, end=None):
    """Yields (type, offset, size, header_size) for the boxes found in
    data[start:end]. Stops at a truncated or malformed box."""
    end = len(data) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, typ = struct.unpack(">I4s", data[pos:pos + 8])
        header = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header:
            return
        yield typ, pos, size, header
        pos += size


def _find_all(data, path, start=0, end=None):
    """Offsets of every box matching the path (e.g. [b"moov", b"trak"])."""
    found = []
    for typ, off, size, header in iter_boxes(data, start, end):
        if typ != path[0]:
            continue
        if len(path) == 1:
            found.append((off, size, header))
        elif typ in _CONTAINERS:
            found.extend(_find_all(data, path[1:], off + header, off + size))
    return found


def parse_sidx(payload):
    """Parses a sidx box payload (after the box header)."""
    version = payload[0]
    reference_id, timescale = struct.unpack(">II", payload[4:12])
    if version == 0:
        ept, first_offset = struct.unpack(">II", payload[12:20])
        pos = 20
    else:
        ept, first_offset = struct.unpack(">QQ", payload[12:28])
        pos = 28
    count = struct.unpack(">H", payload[pos + 2:pos + 4])[0]
    pos += 4
    refs = []
    for _ in range(count):
        word, duration, _sap = struct.unpack(">III", payload[pos:pos + 12])
        refs.append((word & 0x7FFFFFFF, duration))
        pos += 12
    return {
        "reference_id": reference_id,
        "timescale": timescale,
        "ept": ept,
        "first_offset": first_offset,
        "refs": refs,
    }


def build_sidx(reference_id, timescale, ept, refs):
    """A version-1 sidx box whose references are (size, duration) pairs,
    each starting with a SAP (every AAC fragment can be decoded on its
    own)."""
    body = struct.pack(">B3xIIQQHH", 1, reference_id, timescale, ept, 0, 0, len(refs))
    for size, duration in refs:
        body += struct.pack(">III", size & 0x7FFFFFFF, duration, 0x90000000)
    return struct.pack(">I4s", 8 + len(body), b"sidx") + body


def _put(buf, offset, version, v0_size, value):
    if version == 0 and v0_size == 4:
        struct.pack_into(">I", buf, offset, min(value, 0xFFFFFFFF))
    else:
        struct.pack_into(">Q", buf, offset, value)


def patch_init(init, duration_seconds):
    """
    Writes the real duration into the init segment (mvhd, tkhd, mdhd,
    mehd), which a fragmented init leaves at 0. Returns
    (patched bytes, track_id, media timescale).
    """
    buf = bytearray(init)
    mvhd = _find_all(buf, [b"moov", b"mvhd"])
    if not mvhd:
        raise RelayError("init segment without moov/mvhd")
    off, _size, header = mvhd[0]
    p = off + header
    version = buf[p]
    if version == 0:
        movie_ts = struct.unpack(">I", buf[p + 12:p + 16])[0]
        _put(buf, p + 16, 0, 4, int(round(duration_seconds * movie_ts)))
    else:
        movie_ts = struct.unpack(">I", buf[p + 20:p + 24])[0]
        _put(buf, p + 24, 1, 8, int(round(duration_seconds * movie_ts)))

    track_id = 1
    for off, _size, header in _find_all(buf, [b"moov", b"trak", b"tkhd"]):
        p = off + header
        version = buf[p]
        if version == 0:
            track_id = struct.unpack(">I", buf[p + 12:p + 16])[0]
            _put(buf, p + 20, 0, 4, int(round(duration_seconds * movie_ts)))
        else:
            track_id = struct.unpack(">I", buf[p + 20:p + 24])[0]
            _put(buf, p + 28, 1, 8, int(round(duration_seconds * movie_ts)))
        break

    media_ts = movie_ts
    for off, _size, header in _find_all(buf, [b"moov", b"trak", b"mdia", b"mdhd"]):
        p = off + header
        version = buf[p]
        if version == 0:
            media_ts = struct.unpack(">I", buf[p + 12:p + 16])[0]
            _put(buf, p + 16, 0, 4, int(round(duration_seconds * media_ts)))
        else:
            media_ts = struct.unpack(">I", buf[p + 20:p + 24])[0]
            _put(buf, p + 24, 1, 8, int(round(duration_seconds * media_ts)))
        break

    for off, _size, header in _find_all(buf, [b"moov", b"mvex", b"mehd"]):
        p = off + header
        version = buf[p]
        _put(buf, p + 4, version, 4, int(round(duration_seconds * movie_ts)))

    return bytes(buf), track_id, media_ts


# ------------------------------------------------------------- playlist

def parse_playlist(text, base_url):
    """Returns (init_url, [(segment_url, duration_seconds)], encrypted)."""
    init_url = None
    segments = []
    encrypted = False
    duration = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-MAP:"):
            attrs = line[len("#EXT-X-MAP:"):]
            start = attrs.find('URI="')
            if start >= 0:
                stop = attrs.find('"', start + 5)
                init_url = urllib.parse.urljoin(base_url, attrs[start + 5:stop])
        elif line.startswith("#EXT-X-KEY:"):
            if "METHOD=NONE" not in line:
                encrypted = True
        elif line.startswith("#EXTINF:"):
            try:
                duration = float(line[len("#EXTINF:"):].split(",", 1)[0])
            except ValueError:
                duration = 0.0
        elif not line.startswith("#"):
            segments.append((urllib.parse.urljoin(base_url, line), duration or 0.0))
            duration = None
    return init_url, segments, encrypted


# ---------------------------------------------------------------- track

def bitrate_kbps(url):
    """Nominal bitrate from the preset in the URL (aac_160k -> 160)."""
    match = re.search(r"/(?:aac|mp3|opus)_(\d+)k/", url or "")
    return int(match.group(1)) if match else DEFAULT_KBPS


def slot_size(duration, kbps):
    """Bytes reserved for a fragment of this duration: the nominal size
    plus a wide margin (AAC is near-constant bitrate; SoundCloud's
    aac_160k fragments measure ~20.2 KB per second)."""
    return int(duration * kbps * 1000 / 8 * SLOT_MARGIN) + SLOT_EXTRA


def strip_to_moof(data):
    """Drops the boxes before the moof (styp, sidx...) of a fragment."""
    for typ, off, _size, _header in iter_boxes(data):
        if typ == b"moof":
            return data[off:]
    raise RelayError("fragment without moof")


class Track:
    """
    One SoundCloud HLS playlist laid out as a continuous MP4 file.

    Every fragment gets a fixed slot computed from its duration alone
    (no request needed): the fragment's moof + mdat, then a "free" box
    filling the rest of the slot, which players skip. The index (sidx)
    and the file size are therefore known as soon as the playlist and
    the init segment are read - a two-request start whatever the length
    of the track - and a seek lands on a slot boundary. Fragments are
    downloaded when first read, kept in a small cache, and the next
    one is fetched in the background while the current one plays.
    """

    def __init__(self, playlist_url, session=None, log=None):
        self.session = session or _new_session()
        self.log = log or (lambda msg: None)
        started = time.time()

        response = self.session.get(playlist_url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        init_url, segments, encrypted = parse_playlist(response.text, playlist_url)
        if encrypted:
            raise RelayError("encrypted stream (DRM), cannot be relayed")
        if not init_url or not segments:
            raise RelayError("not a fragmented-MP4 HLS playlist")

        response = self.session.get(init_url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        init = response.content

        media_ts = None
        for off, _size, header in _find_all(init, [b"moov", b"trak", b"mdia", b"mdhd"]):
            p = off + header
            media_ts = struct.unpack(
                ">I", init[p + 12:p + 16] if init[p] == 0 else init[p + 20:p + 24])[0]
            break
        if not media_ts:
            raise RelayError("init segment without mdhd")

        kbps = bitrate_kbps(playlist_url)
        self.parts = []  # (url, duration_units, slot_size)
        for url, extinf in segments:
            self.parts.append((
                url, int(round(extinf * media_ts)), slot_size(extinf, kbps)))
        self.duration = sum(p[1] for p in self.parts) / float(media_ts)

        patched, track_id, _ts = patch_init(init, self.duration)
        index = build_sidx(track_id, media_ts, 0, [(p[2], p[1]) for p in self.parts])
        self.header = patched + index
        self.size = len(self.header) + sum(p[2] for p in self.parts)
        self.offsets = []
        pos = len(self.header)
        for part in self.parts:
            self.offsets.append(pos)
            pos += part[2]

        self._cache = OrderedDict()
        self._pending = {}
        self._lock = threading.Lock()
        self.log("relay ready: %d fragments, %.0f s, %d kb/s, built in %.1f s" % (
            len(self.parts), self.duration, kbps, time.time() - started))

    # Fragment bodies (moof + mdat), downloaded once, shared by readers.
    def _body(self, index):
        with self._lock:
            if index in self._cache:
                self._cache.move_to_end(index)
                return self._cache[index]
            event = self._pending.get(index)
            fetcher = event is None
            if fetcher:
                event = self._pending[index] = threading.Event()
        if not fetcher:
            event.wait(HTTP_TIMEOUT * 2)
            with self._lock:
                body = self._cache.get(index)
            if body is None:
                raise RelayError("fragment %d unavailable" % index)
            return body
        try:
            url, _units, slot = self.parts[index]
            response = self.session.get(url, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            body = strip_to_moof(response.content)
            if len(body) > slot - 8:
                # Never seen (the margin is wide): keep the file layout
                # valid, at the cost of a glitch in this fragment.
                self.log("relay: fragment %d larger than its slot (%d > %d)" % (
                    index, len(body), slot - 8))
                body = body[:slot - 8]
            with self._lock:
                self._cache[index] = body
                while len(self._cache) > FRAGMENT_CACHE:
                    self._cache.popitem(last=False)
            return body
        finally:
            with self._lock:
                self._pending.pop(index, None)
            event.set()

    def _prefetch(self, index):
        if index >= len(self.parts):
            return
        with self._lock:
            if index in self._cache or index in self._pending:
                return

        def run():
            try:
                self._body(index)
            except Exception:
                pass  # the reader will retry and report

        threading.Thread(target=run, daemon=True).start()

    def _slot_bytes(self, index, first, last):
        """Bytes first..last (inclusive) of the slot: body, then a free
        box padding the slot to its fixed size."""
        body = self._body(index)
        slot = self.parts[index][2]
        out = b""
        if first < len(body):
            out += body[first:min(last + 1, len(body))]
        if last >= len(body):
            pad = slot - len(body)
            free_header = struct.pack(">I4s", pad, b"free")
            lo = max(first, len(body)) - len(body)
            hi = last - len(body)
            if lo < 8:
                out += free_header[lo:min(hi + 1, 8)]
            if hi >= 8:
                out += bytes(hi + 1 - max(lo, 8))
        return out

    def read(self, start, end):
        """Yields the bytes start..end (inclusive) of the served file."""
        pos = start
        if pos < len(self.header):
            stop = min(end + 1, len(self.header))
            yield self.header[pos:stop]
            pos = stop
        for index, offset in enumerate(self.offsets):
            if pos > end:
                return
            slot = self.parts[index][2]
            if offset + slot <= pos:
                continue
            first = pos - offset
            last = min(end, offset + slot - 1) - offset
            self._prefetch(index + 1)
            data = self._slot_bytes(index, first, last)
            for i in range(0, len(data), CHUNK_SIZE):
                yield data[i:i + CHUNK_SIZE]
            pos = offset + last + 1


def _new_session():
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=4, pool_maxsize=POOL_SIZE)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = USER_AGENT
    return session


# --------------------------------------------------------------- server

class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Kodi drops connections all the time (seek, stop, next track):
        # not worth a traceback in the log.
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def host_allowed(url, suffixes=ALLOWED_HOST_SUFFIXES):
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("https", "http"):
        return False
    return any(host == s.lstrip(".") or host.endswith(s) for s in suffixes)


class Relay:
    """The local HTTP server and its small cache of tracks."""

    def __init__(self, log=None, allowed_suffixes=ALLOWED_HOST_SUFFIXES):
        self.log = log or (lambda msg: None)
        self.allowed_suffixes = allowed_suffixes
        self._tracks = OrderedDict()
        self._building = {}
        self._lock = threading.Lock()
        self._server = None
        self._session = _new_session()

    def start(self, port=0):
        relay = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_HEAD(self):
                relay._handle(self, send_body=False)

            def do_GET(self):
                relay._handle(self, send_body=True)

        self._server = _Server(("127.0.0.1", port), Handler)
        threading.Thread(
            target=self._server.serve_forever, daemon=True,
            name="soundcloud-relay").start()
        return self._server.server_address[1]

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def track(self, playlist_url):
        """Cached Track for this playlist, built once even when Kodi
        opens the URL several times at once."""
        with self._lock:
            if playlist_url in self._tracks:
                self._tracks.move_to_end(playlist_url)
                return self._tracks[playlist_url]
            event = self._building.get(playlist_url)
            builder = event is None
            if builder:
                event = self._building[playlist_url] = threading.Event()
        if not builder:
            event.wait(120)
            with self._lock:
                track = self._tracks.get(playlist_url)
            if track is None:
                raise RelayError("track build failed")
            return track
        try:
            track = Track(playlist_url, self._session, self.log)
            with self._lock:
                self._tracks[playlist_url] = track
                while len(self._tracks) > CACHE_TRACKS:
                    self._tracks.popitem(last=False)
            return track
        finally:
            with self._lock:
                self._building.pop(playlist_url, None)
            event.set()

    def _handle(self, req, send_body):
        parsed = urllib.parse.urlparse(req.path)
        playlist_url = urllib.parse.parse_qs(parsed.query).get("u", [""])[0]
        if parsed.path != RELAY_PATH or not host_allowed(
                playlist_url, self.allowed_suffixes):
            req.send_error(404)
            return
        try:
            track = self.track(playlist_url)
        except Exception as e:
            self.log("relay: cannot prepare track: %s" % e)
            req.send_error(502)
            return

        start, end = 0, track.size - 1
        status = 200
        range_header = req.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            first, _sep, last = range_header[6:].split(",")[0].partition("-")
            try:
                if first:
                    start = int(first)
                    if last:
                        end = min(int(last), track.size - 1)
                elif last:
                    start = max(0, track.size - int(last))
            except ValueError:
                start, end = 0, track.size - 1
            if start >= track.size or start > end:
                req.send_response(416)
                req.send_header("Content-Range", "bytes */%d" % track.size)
                req.send_header("Content-Length", "0")
                req.end_headers()
                return
            status = 206

        req.send_response(status)
        req.send_header("Content-Type", "audio/mp4")
        req.send_header("Accept-Ranges", "bytes")
        req.send_header("Content-Length", str(end - start + 1))
        if status == 206:
            req.send_header(
                "Content-Range", "bytes %d-%d/%d" % (start, end, track.size))
        req.end_headers()
        if not send_body:
            return
        try:
            for chunk in track.read(start, end):
                req.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Kodi closed the connection (seek, stop, next track)
        except Exception as e:
            self.log("relay: transfer error: %s" % e)
            req.close_connection = True
