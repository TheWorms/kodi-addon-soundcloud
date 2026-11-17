import struct
import sys
import urllib.parse
import urllib.request
from unittest import TestCase
from unittest.mock import MagicMock

sys.modules.setdefault("xbmc", MagicMock())
sys.modules.setdefault("xbmcaddon", MagicMock())
sys.modules.setdefault("xbmcgui", MagicMock())
from resources.lib.kodi import hls_relay  # noqa: E402

TS = 44100


def box(typ, payload):
    return struct.pack(">I4s", 8 + len(payload), typ) + payload


def full_box(typ, version, payload):
    return box(typ, bytes([version, 0, 0, 0]) + payload)


def make_init():
    mvhd = full_box(b"mvhd", 0, struct.pack(">IIII", 0, 0, 1000, 0) + b"\0" * 80)
    tkhd = full_box(b"tkhd", 0, struct.pack(">IIIII", 0, 0, 7, 0, 0) + b"\0" * 60)
    mdhd = full_box(b"mdhd", 0, struct.pack(">IIII", 0, 0, TS, 0) + b"\0" * 4)
    hdlr = full_box(b"hdlr", 0, b"\0" * 4 + b"soun" + b"\0" * 13)
    trak = box(b"trak", tkhd + box(b"mdia", mdhd + hdlr))
    mvex = box(b"mvex", full_box(b"trex", 0, b"\0" * 20))
    return box(b"ftyp", b"iso5\0\0\0\1iso6mp41") + box(b"moov", mvhd + trak + mvex)


def make_segment(index, units, payload_size):
    moof = box(b"moof", b"\x11" * 40)
    mdat = box(b"mdat", bytes([index % 251]) * payload_size)
    sidx = hls_relay.build_sidx(7, TS, index * units, [(len(moof) + len(mdat), units)])
    return box(b"styp", b"msdh\0\0\0\0msdhmsix") + sidx + moof + mdat


class FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self.content = body
        self.text = body.decode("latin1")
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise IOError(self.status_code)

    def iter_content(self, size):
        for i in range(0, len(self.content), 7):  # small odd chunks
            yield self.content[i:i + 7]

    def close(self):
        pass


class FakeSession:
    def __init__(self, files):
        self.files = files
        self.calls = []

    def get(self, url, headers=None, stream=False, timeout=None):
        self.calls.append((url, (headers or {}).get("Range")))
        body = self.files[url.split("?")[0]]
        rng = (headers or {}).get("Range")
        if not rng:
            return FakeResponse(body)
        first, last = rng[6:].split("-")
        first, last = int(first), min(int(last), len(body) - 1)
        return FakeResponse(body[first:last + 1], 206, {
            "Content-Range": "bytes %d-%d/%d" % (first, last, len(body))})


BASE = "https://cdn.example.test/t/aac_160k/u/"
PLAYLIST = """#EXTM3U
#EXT-X-VERSION:7
#EXT-X-PLAYLIST-TYPE:VOD
#EXT-X-MAP:URI="%sinit.mp4?sig=1"
#EXTINF:10.0,
data000.m4s?sig=2
#EXTINF:10.0,
%sdata001.m4s?sig=3
#EXTINF:4.5,
data002.m4s?sig=4
#EXT-X-ENDLIST
""" % (BASE, BASE)


def fake_cdn():
    units = [441000, 441000, 198450]
    segments = [make_segment(i, u, 3000 + 1000 * i) for i, u in enumerate(units)]
    files = {BASE + "playlist.m3u8": PLAYLIST.encode(), BASE + "init.mp4": make_init()}
    for i, seg in enumerate(segments):
        files[BASE + "data%03d.m4s" % i] = seg
    return files, segments


class ParsingTestCase(TestCase):
    def test_playlist(self):
        init, segments, encrypted = hls_relay.parse_playlist(
            PLAYLIST, BASE + "playlist.m3u8?x=1")
        self.assertEqual(init, BASE + "init.mp4?sig=1")
        self.assertEqual(segments[0], (BASE + "data000.m4s?sig=2", 10.0))
        self.assertEqual(segments[2], (BASE + "data002.m4s?sig=4", 4.5))
        self.assertFalse(encrypted)

    def test_encrypted_playlist(self):
        text = PLAYLIST.replace(
            "#EXT-X-MAP", '#EXT-X-KEY:METHOD=SAMPLE-AES,URI="k"\n#EXT-X-MAP')
        self.assertTrue(hls_relay.parse_playlist(text, BASE)[2])

    def test_sidx_round_trip(self):
        sidx = hls_relay.build_sidx(7, TS, 1234, [(100, 441000), (200, 5)])
        parsed = hls_relay.parse_sidx(sidx[8:])
        self.assertEqual(parsed["timescale"], TS)
        self.assertEqual(parsed["ept"], 1234)
        self.assertEqual(parsed["refs"], [(100, 441000), (200, 5)])

    def test_patch_init_durations(self):
        patched, track_id, media_ts = hls_relay.patch_init(make_init(), 24.5)
        self.assertEqual((track_id, media_ts), (7, TS))
        mvhd = hls_relay._find_all(patched, [b"moov", b"mvhd"])[0]
        p = mvhd[0] + mvhd[2]
        self.assertEqual(struct.unpack(">I", patched[p + 16:p + 20])[0], 24500)
        mdhd = hls_relay._find_all(patched, [b"moov", b"trak", b"mdia", b"mdhd"])[0]
        p = mdhd[0] + mdhd[2]
        self.assertEqual(struct.unpack(">I", patched[p + 16:p + 20])[0], int(24.5 * TS))
        self.assertEqual(len(patched), len(make_init()))


class TrackTestCase(TestCase):
    def setUp(self):
        self.files, self.segments = fake_cdn()
        self.session = FakeSession(self.files)
        self.track = hls_relay.Track(BASE + "playlist.m3u8?sig=0", self.session)
        # Fragment bodies: styp and per-fragment sidx left out.
        self.bodies = [seg[24 + 52:] for seg in self.segments]
        self.full = b"".join(self.track.read(0, self.track.size - 1))

    def test_start_needs_two_requests(self):
        session = FakeSession(self.files)
        hls_relay.Track(BASE + "playlist.m3u8", session)
        self.assertEqual([c[0].split("?")[0] for c in session.calls],
                         [BASE + "playlist.m3u8", BASE + "init.mp4"])

    def test_layout(self):
        self.assertAlmostEqual(self.track.duration, 24.5, places=3)
        self.assertEqual(self.track.size, len(self.full))
        boxes = [t for t, _o, _s, _h in hls_relay.iter_boxes(self.full)]
        self.assertEqual(
            boxes, [b"ftyp", b"moov", b"sidx"] + [b"moof", b"mdat", b"free"] * 3)
        off, size, header = hls_relay._find_all(self.full, [b"sidx"])[0]
        sidx = hls_relay.parse_sidx(self.full[off + header:off + size])
        slots = [hls_relay.slot_size(d, 160) for d in (10.0, 10.0, 4.5)]
        self.assertEqual([r[0] for r in sidx["refs"]], slots)
        self.assertEqual(sum(r[1] for r in sidx["refs"]), int(24.5 * TS))
        # The index covers the file up to its last byte (FFmpeg then
        # trusts it for seeking) and every slot starts with its moof.
        self.assertEqual(off + size + sum(slots), self.track.size)
        for body, offset in zip(self.bodies, self.track.offsets):
            self.assertEqual(self.full[offset:offset + len(body)], body)

    def test_ranges(self):
        size = self.track.size
        header = len(self.track.header)
        offsets = self.track.offsets
        body0 = len(self.bodies[0])
        for start, end in ((0, 10), (5, size - 1), (header - 3, header + 3),
                           (offsets[0] + body0 - 4, offsets[0] + body0 + 12),
                           (offsets[1] - 1, offsets[2] + 5), (size - 1, size - 1)):
            got = b"".join(self.track.read(start, end))
            self.assertEqual(got, self.full[start:end + 1], (start, end))

    def test_seek_fetches_only_the_needed_fragments(self):
        session = FakeSession(self.files)
        track = hls_relay.Track(BASE + "playlist.m3u8", session)
        session.calls.clear()
        start = track.offsets[2] + 10
        b"".join(track.read(start, start + 99))
        fetched = {c[0].split("?")[0] for c in session.calls}
        self.assertEqual(fetched, {BASE + "data002.m4s"})

    def test_bitrate_from_preset(self):
        self.assertEqual(hls_relay.bitrate_kbps(BASE + "playlist.m3u8"), 160)
        self.assertEqual(hls_relay.bitrate_kbps("https://x/aac_96k/y/p.m3u8"), 96)
        self.assertEqual(hls_relay.bitrate_kbps("https://x/p.m3u8"), 256)

    def test_encrypted_refused(self):
        self.files[BASE + "playlist.m3u8"] = PLAYLIST.replace(
            "#EXT-X-MAP", '#EXT-X-KEY:METHOD=SAMPLE-AES,URI="k"\n#EXT-X-MAP').encode()
        with self.assertRaises(hls_relay.RelayError):
            hls_relay.Track(BASE + "playlist.m3u8", FakeSession(self.files))


class RelayServerTestCase(TestCase):
    def setUp(self):
        files, _segments = fake_cdn()
        self.track = hls_relay.Track(BASE + "playlist.m3u8", FakeSession(files))
        self.full = b"".join(self.track.read(0, self.track.size - 1))
        self.relay = hls_relay.Relay(allowed_suffixes=(".example.test",))
        self.relay.track = lambda url: self.track
        self.port = self.relay.start()

    def tearDown(self):
        self.relay.stop()

    def url(self, playlist):
        return "http://127.0.0.1:%d%s?u=%s" % (
            self.port, hls_relay.RELAY_PATH, urllib.parse.quote(playlist, safe=""))

    def test_full_and_range(self):
        with urllib.request.urlopen(self.url(BASE + "playlist.m3u8")) as r:
            self.assertEqual(r.status, 200)
            self.assertEqual(r.headers["Accept-Ranges"], "bytes")
            self.assertEqual(r.read(), self.full)
        req = urllib.request.Request(self.url(BASE + "playlist.m3u8"),
                                     headers={"Range": "bytes=100-"})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status, 206)
            self.assertEqual(r.headers["Content-Range"],
                             "bytes 100-%d/%d" % (self.track.size - 1, self.track.size))
            self.assertEqual(r.read(), self.full[100:])

    def test_foreign_host_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url("https://evil.example.com/playlist.m3u8"))
        self.assertEqual(ctx.exception.code, 404)
