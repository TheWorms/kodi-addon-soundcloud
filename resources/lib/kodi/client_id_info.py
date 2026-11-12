"""
Keep the read-only "apiv2.client_id_info" display setting in sync with
the API client ID actually in use (Settings > Account, above the OAuth
token). The resolution order matches ApiV2.api_client_id: custom
override > 24h cache > live extraction, so the ID is shown whether the
user browses anonymously or with an OAuth token (a token is sent
INSTEAD of the client ID, but the ID is still resolved and used for
anonymous fallback calls).

Audit N3: this used to run BEFORE the routing on EVERY plugin call -
every /play/ of the queue, every widget refresh - which forced a full
client-ID extraction (soundcloud.com plus every JS asset, each with
network timeouts) whenever the 24h cache was cold, and again on every
call while the extraction kept failing (no negative cache). It runs
once per UI open, in the background, and a failed or empty resolution
is remembered for one hour so repeated calls don't re-download the
whole site before each failure.

Since 6.0.7 it runs in the UI process (script.py) rather than in the
plugin call that launched the UI: that call now returns at once, and a
daemon thread there could be cut short when its interpreter ended.
"""
import threading
import time

import xbmc

_FAIL_MARKER = "client-id-extract-failed"
_FAIL_TTL = 3600  # seconds


def _failed_recently(vfs_cache):
    """
    True when a failed client-ID extraction is less than an hour old.
    get_mtime raises on a missing marker file - that means "no recent
    failure".
    """
    try:
        mtime = vfs_cache.get_mtime(_FAIL_MARKER)
        return (time.time() - mtime) < _FAIL_TTL
    except Exception:
        return False


def sync(addon, settings, api, vfs_cache):
    addon_id = addon.getAddonInfo("id")
    try:
        if _failed_recently(vfs_cache):
            return
        current = settings.get("apiv2.client_id_info") or ""
        resolved = api.api_client_id
        if not resolved:
            raise RuntimeError("client id resolution returned nothing")
        if resolved != current:
            addon.setSetting("apiv2.client_id_info", resolved)
            xbmc.log("%s: client id info refreshed" % addon_id, xbmc.LOGDEBUG)
        try:
            vfs_cache.delete(_FAIL_MARKER)
        except Exception:
            pass
    except Exception as e:
        try:
            vfs_cache.write(_FAIL_MARKER, "1")
        except Exception:
            pass
        xbmc.log("%s: client id info sync failed: %s" % (addon_id, str(e)),
                 xbmc.LOGWARNING)


def sync_bg(addon, settings, api, vfs_cache):
    """sync() on a daemon thread, so the (potentially slow) client-ID
    resolution never delays the UI."""
    threading.Thread(target=sync, args=(addon, settings, api, vfs_cache),
                     name="soundcloud-client-id", daemon=True).start()
