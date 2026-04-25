import xbmcaddon


class Settings:

    AUDIO_FORMATS = {
        "0": {
            "mime_type": "audio/ogg; codecs=\"opus\"",
            "protocol": "hls",
        },
        "1": {
            "mime_type": "audio/mpeg",
            "protocol": "hls",
        },
        "2": {
            "mime_type": "audio/mpeg",
            "protocol": "progressive",
        }
    }

    APIV2_LOCALE = {
        "auto": "0",
        "disabled": "1"
    }

    def __init__(self, addon):
        # Cache the addon id once. We DO NOT keep the addon instance itself
        # because Kodi's xbmcaddon.Addon caches the in-memory copy of
        # settings.xml — which means edits made during the same session
        # (e.g. user pastes a new OAuth token) are not visible until Kodi
        # is restarted. By creating a fresh Addon() instance for every
        # getSetting/setSetting call, we always read the latest values
        # from disk.
        try:
            self._addon_id = addon.getAddonInfo("id")
        except Exception:
            # Fallback: hard-coded addon id (matches addon.xml)
            self._addon_id = "plugin.audio.soundcloud"

    def _fresh_addon(self):
        """
        Returns a fresh xbmcaddon.Addon() instance bound to our addon id.
        This forces Kodi to re-read settings.xml from disk, working around
        the in-memory caching that would otherwise hide settings edits
        made in the current session.
        """
        return xbmcaddon.Addon(self._addon_id)

    def get(self, id):
        return self._fresh_addon().getSetting(id)

    def set(self, id, value):
        return self._fresh_addon().setSetting(id, value)

    def get_oauth_token(self):
        """
        Returns the user's OAuth token or None if empty.

        Defensively cleans common copy-paste artifacts:
          - leading/trailing whitespace (incl. invisible unicode chars)
          - "OAuth " or "Bearer " prefix (users often paste the full
            Authorization header value rather than just the token)
          - leading/trailing quotes
          - any whitespace anywhere inside (newlines, tabs, multiple
            spaces — all get squashed because real tokens never have
            internal whitespace)

        Reads from a fresh Addon() instance so token edits in the same
        Kodi session are picked up immediately (without needing a restart).
        """
        token = self._fresh_addon().getSetting("auth.oauth_token")
        if not token:
            return None
        # Step 1: strip surrounding whitespace and quotes
        token = token.strip().strip('"').strip("'").strip()
        # Step 2: strip "OAuth " or "Bearer " prefix (case-insensitive)
        for prefix in ("OAuth ", "Bearer "):
            if token.lower().startswith(prefix.lower()):
                token = token[len(prefix):].strip()
                break
        # Step 3: drop ALL whitespace anywhere (real tokens are
        # contiguous alphanumeric+dash, no spaces, tabs, or newlines)
        # This catches \r\n smuggled in by paste from Windows clipboards,
        # zero-width spaces, etc.
        import re
        token = re.sub(r"\s+", "", token)
        # Step 4: strip any non-printable characters (control chars,
        # zero-width spaces \u200b, BOM \ufeff, etc.)
        token = "".join(c for c in token if c.isprintable() and not c.isspace())
        return token if token else None
