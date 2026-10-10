"""
"OAuth token" window.

One place to enter, check and save the SoundCloud OAuth token:
  - shows the saved token (masked) and whether SoundCloud accepts it;
  - "Enter token" opens Kodi's keyboard, titled with the addon's
    "OAuth token" string, so the token can be typed by hand, pasted from
    a remote app, or sent by the "SoundCloud token for Kodi" browser
    extension (which only types into a keyboard with that title);
  - "Save" asks SoundCloud (GET /me) first and keeps the token only if it
    is valid; the result is shown at once;
  - "Delete" forgets the saved token.

Opened from Settings > Account (RunScript(plugin.audio.soundcloud,token,
from_settings)); the settings are reopened when it closes.
While it is open, the home window property "soundcloud.tokenwindow" is
"1" so the browser extension can find it.
"""
import re
import time

import xbmc
import xbmcgui

WINDOW_XML = "script-soundcloud-token.xml"
HOME_PROPERTY = "soundcloud.tokenwindow"

ID_ENTER = 9101
ID_SAVE = 9102
ID_DELETE = 9103
ID_CLOSE = 9104
ID_SAVED = 9201
ID_CANDIDATE = 9202
ID_RESULT = 9203
ID_HELP = 9204

ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92

TOKEN_SHAPE = re.compile(r"^[12]-\d+-\d+-[A-Za-z0-9_-]+$")

GREEN = "FF4CAF50"
RED = "FFEF5350"
ORANGE = "FFFF9800"
GREY = "FFA8A8A8"


def mask(token):
    if not token:
        return ""
    return token[:6] + "…" + token[-4:] if len(token) > 12 else "…"


def tier_name(tier):
    names = {"free": "Free", "go": "Go", "go_plus": "Go+", "pro": "Pro",
             "pro_unlimited": "Pro Unlimited"}
    if not tier:
        return ""
    return names.get(tier, tier.replace("_", " ").title())


def colour(text, argb):
    return "[COLOR %s]%s[/COLOR]" % (argb, text)


class TokenDialog(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        self.api = kwargs.pop("api")
        self.addon = kwargs.pop("addon")
        self.settings = kwargs.pop("settings")
        super().__init__(*args, **kwargs)
        self.candidate = None
        self.changed = False

    # ------------------------------------------------------------ helpers

    def _s(self, string_id):
        return self.addon.getLocalizedString(string_id)

    def _label(self, control_id, text):
        try:
            control = self.getControl(control_id)
            # textbox controls (multi-line) only have setText().
            if isinstance(control, xbmcgui.ControlTextBox):
                control.setText(text)
            else:
                control.setLabel(text)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::TokenDialog label %d: %s"
                % (control_id, str(e)),
                xbmc.LOGWARNING,
            )

    def _describe(self, check):
        """One coloured line for a check_token() result."""
        if check["state"] == "valid":
            text = self._s(30423).format(check.get("username") or "?")
            tier = tier_name(check.get("tier"))
            if tier:
                text += "  ·  " + self._s(30424).format(tier)
            return colour(text, GREEN)
        if check["state"] == "invalid":
            return colour(self._s(30425).format(check.get("http") or "?"), RED)
        return colour(self._s(30426).format(check.get("error") or "?"), ORANGE)

    def _store_status(self, check, unchecked=False):
        """
        Read-only summary shown in Settings > Account. A check that
        could not reach SoundCloud leaves the previous summary alone,
        unless the token was just saved without a check.
        """
        when = time.strftime("%d/%m %H:%M")
        if unchecked:
            text = self._s(30437)
        elif check is None:
            text = self._s(30438)
        elif check["state"] == "valid":
            who = check.get("username") or "?"
            tier = tier_name(check.get("tier"))
            text = self._s(30435).format(who + (" - " + tier if tier else ""), when)
        elif check["state"] == "invalid":
            text = self._s(30436).format(when)
        else:
            return
        self._write("auth.token_status", text)

    def _show_saved(self, check=None):
        token = self.settings.get_oauth_token()
        if not token:
            self._label(ID_SAVED, colour(self._s(30421), GREY))
            self._store_status(None)
            return
        if check is None:
            self._label(ID_SAVED, mask(token) + "   " + colour(self._s(30422), GREY))
            check = self.api.check_token(token)
        self._label(ID_SAVED, mask(token) + "   " + self._describe(check))
        self._store_status(check)
        if check["state"] == "valid" and check.get("tier") is not None:
            self._write("account.tier", check["tier"] or "")

    def _write(self, setting_id, value):
        """
        Write through the Addon instance this window was given. Kodi
        keeps one in-memory copy of the settings per Addon object and
        writes the WHOLE copy back when it saves, so every write of
        this window goes through the same instance (created when the
        script started, after Settings had saved and closed).
        """
        try:
            self.addon.setSetting(setting_id, value)
        except Exception as e:
            xbmc.log(
                "plugin.audio.soundcloud::TokenDialog cannot save %s: %s"
                % (setting_id, str(e)),
                xbmc.LOGERROR,
            )

    def _save(self, token, check):
        self._write("auth.oauth_token", token)
        # Unchecked save: the plan of the previous account no longer
        # applies, the next /me call fills it in again.
        valid = check and check["state"] == "valid"
        self._write("account.tier", (check.get("tier") or "") if valid else "")
        self.api.reset_auth_state()
        self.changed = True

    # ---------------------------------------------------------- lifecycle

    def onInit(self):
        self._label(ID_HELP, self._s(30434))
        self._label(ID_CANDIDATE, colour("—", GREY))
        self._label(ID_RESULT, "")
        try:
            self.setFocusId(ID_ENTER)
        except Exception:
            pass
        self._show_saved()
        # Announce the window to the browser extension only now: the
        # check above blocks this window's clicks while it runs, and
        # the extension gives up when the keyboard does not open
        # within a few seconds of its "Enter token" press.
        xbmcgui.Window(10000).setProperty(HOME_PROPERTY, "1")

    def close(self):
        xbmcgui.Window(10000).clearProperty(HOME_PROPERTY)
        super().close()

    def onAction(self, action):
        if action.getId() in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.close()

    def onClick(self, control_id):
        if control_id == ID_ENTER:
            self._enter()
        elif control_id == ID_SAVE:
            self._save_clicked()
        elif control_id == ID_DELETE:
            self._delete()
        elif control_id == ID_CLOSE:
            self.close()

    # ------------------------------------------------------------ actions

    def _enter(self):
        # The keyboard title must stay the addon's "OAuth token" string
        # (#30021): the browser extension checks it before typing.
        raw = xbmcgui.Dialog().input(self._s(30021), type=xbmcgui.INPUT_ALPHANUM)
        token = self.settings.clean_token(raw)
        if not token:
            return
        self.candidate = token
        self._label(ID_CANDIDATE, mask(token))
        hint = self._s(30427)
        if not TOKEN_SHAPE.match(token):
            hint = colour(self._s(30439), ORANGE) + "[CR]" + hint
        self._label(ID_RESULT, hint)
        try:
            self.setFocusId(ID_SAVE)
        except Exception:
            pass

    def _save_clicked(self):
        if not self.candidate:
            self._label(ID_RESULT, colour(self._s(30430), ORANGE))
            try:
                self.setFocusId(ID_ENTER)
            except Exception:
                pass
            return
        token = self.candidate
        self._label(ID_RESULT, colour(self._s(30422), GREY))
        check = self.api.check_token(token)
        if check["state"] == "valid":
            self._save(token, check)
            self.candidate = None
            self._label(ID_CANDIDATE, colour("—", GREY))
            self._label(ID_RESULT, colour(self._s(30428), GREEN) + "[CR]" + self._describe(check))
            self._show_saved(check)
            try:
                self.setFocusId(ID_CLOSE)
            except Exception:
                pass
            return
        if check["state"] == "invalid":
            self._label(ID_RESULT, self._describe(check) + "[CR]" + colour(self._s(30429), RED))
            return
        # SoundCloud unreachable: the user decides.
        if xbmcgui.Dialog().yesno(self._s(30414), self._s(30431).format(check.get("error") or "?")):
            self._save(token, None)
            self.candidate = None
            self._label(ID_CANDIDATE, colour("—", GREY))
            self._label(ID_RESULT, colour(self._s(30437), ORANGE))
            self._label(ID_SAVED, mask(token) + "   " + colour(self._s(30437), ORANGE))
            self._store_status(check, unchecked=True)
        else:
            self._label(ID_RESULT, self._describe(check) + "[CR]" + colour(self._s(30429), RED))

    def _delete(self):
        if not self.settings.get_oauth_token():
            self._label(ID_RESULT, colour(self._s(30421), GREY))
            return
        if not xbmcgui.Dialog().yesno(self._s(30414), self._s(30432)):
            return
        self._write("auth.oauth_token", "")
        self._write("account.tier", "")
        self.api.reset_auth_state()
        self.changed = True
        self._label(ID_RESULT, colour(self._s(30433), GREY))
        self._show_saved()


def open_token_dialog(addon, settings, api):
    """Show the window modally. Returns True when the token changed."""
    dialog = TokenDialog(
        WINDOW_XML,
        addon.getAddonInfo("path"),
        "default",
        "1080i",
        api=api,
        addon=addon,
        settings=settings,
    )
    try:
        dialog.doModal()
        return dialog.changed
    finally:
        xbmcgui.Window(10000).clearProperty(HOME_PROPERTY)
        del dialog
