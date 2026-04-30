"""
Image processing helpers (Pillow-based) with graceful fallback.

This module is used by the "Now Playing" fullscreen overlays to:
  - generate a blurred version of the cover art for use as background
  - extract the dominant colour from the cover art for accent colours

We use Pillow (PIL fork) which is available on most Kodi installs as
the script.module.pil addon. If Pillow is NOT installed (some Android
builds, custom Kodi setups), we fall back gracefully:
  - blur: returns the original cover URL, no blur applied
  - dominant colour: returns SoundCloud orange (#FF5500)

Functions in this module are safe to call from background threads.
Output files are stored in special://temp so Kodi cleans them up
between sessions.
"""
import hashlib
import os

import xbmc
import xbmcvfs


# Probe Pillow availability ONCE at import time so subsequent calls
# don't pay the import cost / log the warning repeatedly.
try:
    from PIL import Image, ImageFilter  # noqa: F401
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    xbmc.log(
        "plugin.audio.soundcloud::imagehelpers Pillow (script.module.pil) "
        "is not installed — image effects (blur, dominant colour) will "
        "be skipped gracefully. Install it via Kodi's addon repository "
        "for the full visual experience.",
        xbmc.LOGINFO,
    )


def _temp_dir():
    """Return the directory we use for cached PNGs, creating it if missing."""
    base = xbmcvfs.translatePath("special://temp/plugin.audio.soundcloud/")
    if not xbmcvfs.exists(base):
        xbmcvfs.mkdirs(base)
    return base


def _hash_url(url):
    """Stable short hash for an image URL — used as cache key."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def get_blurred_cover(cover_url, blur_radius=20):
    """
    Generate a blurred version of the cover image. Returns a path to
    a JPG file in Kodi's temp dir (suitable for use as <texture>).

    Falls back to the original URL if Pillow is missing.

    Cached on disk by URL hash, so repeated calls for the same track
    return immediately.
    """
    if not cover_url:
        return ""
    if not PIL_AVAILABLE:
        return cover_url

    cache_key = _hash_url(cover_url) + "_blur" + str(blur_radius) + ".jpg"
    output_path = os.path.join(_temp_dir(), cache_key)
    if os.path.exists(output_path):
        return output_path

    try:
        import requests
        from io import BytesIO
        from PIL import Image, ImageFilter

        # Replace SoundCloud's "large" size suffix with t500x500 so we
        # have enough resolution for upscaling to fullscreen without
        # pixellation.
        url = cover_url.replace("-large.", "-t500x500.")
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()

        img = Image.open(BytesIO(resp.content)).convert("RGB")
        # Upscale a bit before blurring so the result fills 1920x1080
        # without visible pixels.
        img = img.resize((1280, 1280), Image.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        img.save(output_path, "JPEG", quality=82, optimize=True)

        xbmc.log(
            "plugin.audio.soundcloud::imagehelpers blurred cover -> %s" %
            output_path, xbmc.LOGDEBUG,
        )
        return output_path
    except Exception as e:
        xbmc.log(
            "plugin.audio.soundcloud::imagehelpers blur failed for %s: %s" %
            (cover_url, str(e)), xbmc.LOGWARNING,
        )
        return cover_url


def get_dominant_colour(cover_url):
    """
    Returns the dominant RGB colour of the cover as a hex string
    'RRGGBB' (no alpha). Falls back to SoundCloud orange.

    Uses Pillow's quantize() to bucket colours into 8 representative
    ones, then picks the most frequent that's neither too dark nor too
    bright (avoids picking pure-black backgrounds or pure-white logos).
    """
    fallback = "FF5500"  # SoundCloud orange
    if not cover_url or not PIL_AVAILABLE:
        return fallback

    try:
        import requests
        from io import BytesIO
        from PIL import Image

        url = cover_url.replace("-large.", "-t300x300.")
        resp = requests.get(url, timeout=6)
        resp.raise_for_status()

        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img = img.resize((100, 100))  # speed-up
        # Reduce to 8 colours
        quantized = img.quantize(colors=8)
        palette = quantized.getpalette()  # list of R,G,B,R,G,B,...
        counts = sorted(quantized.getcolors(), reverse=True)  # [(count, idx),...]

        # Filter palette: pick most frequent colour that's not too dark
        # (sum < 120) and not too bright (sum > 720)
        for _, idx in counts:
            r, g, b = palette[idx*3:idx*3+3]
            brightness = r + g + b
            if 120 < brightness < 720:
                return "%02X%02X%02X" % (r, g, b)

        # Fallback: most frequent colour, even if dark/bright
        if counts:
            _, idx = counts[0]
            r, g, b = palette[idx*3:idx*3+3]
            return "%02X%02X%02X" % (r, g, b)
    except Exception as e:
        xbmc.log(
            "plugin.audio.soundcloud::imagehelpers dominant colour failed: %s" %
            str(e), xbmc.LOGWARNING,
        )
    return fallback


def fetch_waveform_samples(waveform_url, target_bars=90):
    """
    Fetch SoundCloud's waveform JSON and downsample to `target_bars`
    height values, normalised to 0.0..1.0.

    Returns a list of floats. Returns None on error.
    """
    if not waveform_url:
        return None
    try:
        import requests
        # waveform_url often ends in .png — replace with .json
        if waveform_url.endswith(".png"):
            waveform_url = waveform_url[:-4] + ".json"
        resp = requests.get(waveform_url, timeout=6)
        resp.raise_for_status()
        data = resp.json()

        samples = data.get("samples", [])
        height = data.get("height", 1) or 1
        if not samples:
            return None

        # Downsample to `target_bars` by averaging bins
        n = len(samples)
        downsampled = []
        for i in range(target_bars):
            start = (i * n) // target_bars
            end = ((i + 1) * n) // target_bars
            chunk = samples[start:end] or [samples[start]]
            avg = sum(chunk) / len(chunk)
            downsampled.append(avg / height)  # normalise 0..1

        return downsampled
    except Exception as e:
        xbmc.log(
            "plugin.audio.soundcloud::imagehelpers waveform fetch failed: %s" %
            str(e), xbmc.LOGWARNING,
        )
        return None
