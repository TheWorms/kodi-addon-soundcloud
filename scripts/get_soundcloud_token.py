#!/usr/bin/env python3
"""
Get your SoundCloud OAuth token from Firefox and hand it to Kodi.

No browser console, no copy-paste of code: the script reads the
`oauth_token` cookie that soundcloud.com stores in your Firefox profile,
checks it against SoundCloud (GET https://api-v2.soundcloud.com/me) and then
either copies it to the clipboard or types it straight into Kodi's
on-screen keyboard through Kodi's JSON-RPC interface.

Usage (on the computer where you are signed in to soundcloud.com in Firefox):

    python3 get_soundcloud_token.py                    # verify + copy to clipboard
    python3 get_soundcloud_token.py --kodi <kodi-ip>   # verify + type it into Kodi

With --kodi: in Kodi, open the SoundCloud addon settings > Account >
Manage the OAuth token and leave the window on "Enter token"; the script
opens its keyboard, types the token, and you press Save in Kodi (the
window checks the token with SoundCloud before keeping it). Kodi needs Settings > Services > Control > "Allow remote
control from applications on other systems" (JSON-RPC on TCP port 9090),
or the web server ("Allow remote control via HTTP", port 8080).

Privacy: the token is only sent to api-v2.soundcloud.com (the check) and,
with --kodi, to the Kodi host you name. It is never printed in full unless
you pass --show. Python 3.8+ standard library only.

Limits: Firefox only (Chrome encrypts its cookies). If SoundCloud refuses
the cookie value, use the Network-tab method of the helper page:
https://theworms.github.io/kodi-addon-soundcloud/
"""
import argparse
import base64
import glob
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ME_URL = os.environ.get("SCTOKEN_ME_URL", "https://api-v2.soundcloud.com/me")
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64; rv:142.0) "
              "Gecko/20100101 Firefox/142.0")
KEYBOARD_WINDOW_ID = 10103  # Kodi's DialogKeyboard

FR = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
      or os.environ.get("LANG") or "").lower().startswith("fr")


def t(en, fr):
    return fr if FR else en


def mask(token):
    return token[:6] + "…" + token[-4:] if len(token) > 12 else "…"


# --------------------------------------------------------------------------
# Firefox cookies
# --------------------------------------------------------------------------

def firefox_cookie_dbs(explicit=None):
    if explicit:
        path = os.path.expanduser(explicit)
        if os.path.isdir(path):
            path = os.path.join(path, "cookies.sqlite")
        return [path] if os.path.isfile(path) else []
    home = os.path.expanduser("~")
    roots = [
        os.path.join(home, ".mozilla", "firefox"),
        os.path.join(home, ".var", "app", "org.mozilla.firefox", ".mozilla", "firefox"),
        os.path.join(home, "snap", "firefox", "common", ".mozilla", "firefox"),
        os.path.join(home, ".librewolf"),
        os.path.join(home, "Library", "Application Support", "Firefox", "Profiles"),
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        roots.append(os.path.join(appdata, "Mozilla", "Firefox", "Profiles"))
    found = []
    for root in roots:
        found.extend(glob.glob(os.path.join(root, "*", "cookies.sqlite")))
    # Most recently used profile first.
    return sorted(set(found), key=lambda p: os.path.getmtime(p), reverse=True)


def read_oauth_cookies(db_path):
    """Return [(value, host, last_accessed)] for soundcloud oauth_token cookies.

    Firefox keeps the database locked and part of the data in the -wal file,
    so we query a private copy of the three files.
    """
    tmp = tempfile.mkdtemp(prefix="sctoken-")
    try:
        for suffix in ("", "-wal", "-shm"):
            src = db_path + suffix
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(tmp, "cookies.sqlite" + suffix))
        con = sqlite3.connect(os.path.join(tmp, "cookies.sqlite"))
        try:
            rows = con.execute(
                "SELECT value, host, lastAccessed FROM moz_cookies "
                "WHERE name = 'oauth_token' AND "
                "(host = 'soundcloud.com' OR host LIKE '%.soundcloud.com') "
                "ORDER BY lastAccessed DESC"
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error as e:
        print(t("  cannot read %s: %s", "  lecture impossible de %s : %s") % (db_path, e))
        rows = []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = []
    for value, host, last in rows:
        value = (value or "").strip().strip('"')
        if value.lower().startswith("oauth "):
            value = value[6:].strip()
        if value:
            out.append((value, host, last or 0))
    return out


# --------------------------------------------------------------------------
# SoundCloud check
# --------------------------------------------------------------------------

def verify(token):
    """(True, username) on 200, (False, 401) when refused, (None, info) otherwise."""
    req = urllib.request.Request(ME_URL, headers={
        "Authorization": "OAuth " + token,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "Origin": "https://soundcloud.com",
        "Referer": "https://soundcloud.com/",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8") or "{}")
            return True, data.get("username") or data.get("permalink") or "?"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, 401
        return None, "HTTP %d" % e.code
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, str(getattr(e, "reason", e))


# --------------------------------------------------------------------------
# Clipboard
# --------------------------------------------------------------------------

def copy_to_clipboard(text):
    candidates = [
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["pbcopy"],
        ["clip"],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5)
                return cmd[0]
            except (subprocess.SubprocessError, OSError):
                continue
    return None


# --------------------------------------------------------------------------
# Kodi JSON-RPC (TCP 9090 first, HTTP 8080 as fallback)
# --------------------------------------------------------------------------

class KodiTcp:
    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.buf = ""
        self.next_id = 1

    def call(self, method, params=None):
        rid = self.next_id
        self.next_id += 1
        msg = {"jsonrpc": "2.0", "method": method, "id": rid}
        if params is not None:
            msg["params"] = params
        self.sock.sendall(json.dumps(msg).encode("utf-8"))
        decoder = json.JSONDecoder()
        deadline = time.time() + 10
        while time.time() < deadline:
            # Kodi streams JSON objects back to back, notifications included.
            self.buf = self.buf.lstrip()
            while self.buf:
                try:
                    obj, end = decoder.raw_decode(self.buf)
                except ValueError:
                    break
                self.buf = self.buf[end:].lstrip()
                if isinstance(obj, dict) and obj.get("id") == rid:
                    if "error" in obj:
                        raise RuntimeError(obj["error"].get("message", "JSON-RPC error"))
                    return obj.get("result")
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("connection closed by Kodi")
            self.buf += chunk.decode("utf-8", "replace")
        raise TimeoutError("no answer from Kodi")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class KodiHttp:
    def __init__(self, host, port, user=None, password=None):
        self.url = "http://%s:%d/jsonrpc" % (host, port)
        self.auth = None
        if user:
            raw = ("%s:%s" % (user, password or "")).encode("utf-8")
            self.auth = "Basic " + base64.b64encode(raw).decode("ascii")
        self.next_id = 1

    def call(self, method, params=None):
        rid = self.next_id
        self.next_id += 1
        msg = {"jsonrpc": "2.0", "method": method, "id": rid}
        if params is not None:
            msg["params"] = params
        headers = {"Content-Type": "application/json"}
        if self.auth:
            headers["Authorization"] = self.auth
        req = urllib.request.Request(self.url, data=json.dumps(msg).encode("utf-8"),
                                     headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            obj = json.loads(r.read().decode("utf-8"))
        if "error" in obj:
            raise RuntimeError(obj["error"].get("message", "JSON-RPC error"))
        return obj.get("result")

    def close(self):
        pass


def connect_kodi(args):
    errors = []
    try:
        kodi = KodiTcp(args.kodi, args.kodi_port)
        kodi.call("JSONRPC.Ping")
        return kodi, "TCP %d" % args.kodi_port
    except (OSError, RuntimeError, TimeoutError, ConnectionError) as e:
        errors.append("TCP %d: %s" % (args.kodi_port, e))
    try:
        kodi = KodiHttp(args.kodi, args.kodi_http_port, args.kodi_user, args.kodi_password)
        kodi.call("JSONRPC.Ping")
        return kodi, "HTTP %d" % args.kodi_http_port
    except (OSError, RuntimeError, urllib.error.URLError, ValueError) as e:
        errors.append("HTTP %d: %s" % (args.kodi_http_port, e))
    raise ConnectionError("; ".join(errors))


KEYBOARD_HEADING = "Control.GetLabel(311)"  # title label of Kodi's keyboard
TOKEN_WINDOW_PROP = "Window(Home).Property(soundcloud.tokenwindow)"
FOCUSED_CONTROL = "System.CurrentControlId"
ENTER_TOKEN_BUTTON = "9101"  # "Enter token" button of the addon's token window
# Title of the addon's token keyboard (strings.po #30021) in every language
# the addon ships, normalised (lowercase, letters and digits only).
TOKEN_HEADINGS = {"oauthtoken", "jetonoauth"}


def _normalise(text):
    return "".join(ch for ch in (text or "").lower() if ch.isascii() and ch.isalnum())


def send_to_kodi(token, args):
    kodi, how = connect_kodi(args)
    print(t("Connected to Kodi (%s).", "Connecté à Kodi (%s).") % how)
    try:
        print(t(
            "In Kodi, open SoundCloud settings > Account > Manage the OAuth token "
            "and leave the window on \"Enter token\". Waiting up to %d s...",
            "Dans Kodi, ouvre Paramètres SoundCloud > Compte > Gérer le jeton OAuth "
            "et laisse la fenêtre sur « Saisir le jeton ». J'attends jusqu'à %d s...") % args.wait)
        deadline = time.time() + args.wait
        last_label = None
        pressed = False
        while True:
            props = kodi.call("GUI.GetProperties", {"properties": ["currentwindow"]})
            win = (props or {}).get("currentwindow") or {}
            if win.get("id") == KEYBOARD_WINDOW_ID:
                break
            # The addon's token window (6.0.1+) is open on "Enter token":
            # press it once so its keyboard (titled "OAuth token") opens.
            state = kodi.call("XBMC.GetInfoLabels", {"labels": [TOKEN_WINDOW_PROP, FOCUSED_CONTROL]}) or {}
            if (not pressed and state.get(TOKEN_WINDOW_PROP) == "1"
                    and str(state.get(FOCUSED_CONTROL)) == ENTER_TOKEN_BUTTON):
                kodi.call("Input.Select")
                pressed = True
            if win.get("label") != last_label:
                last_label = win.get("label")
                print(t("  Kodi screen: %s", "  Écran Kodi : %s") % (last_label or win.get("id")))
            if time.time() > deadline:
                # Without an open keyboard Kodi would type the text into
                # whatever control has the focus: never send blindly.
                print(t("Keyboard not detected: nothing was sent.",
                        "Clavier non détecté : rien n'a été envoyé."))
                return False
            time.sleep(1)
        labels = kodi.call("XBMC.GetInfoLabels", {"labels": [KEYBOARD_HEADING]}) or {}
        heading = (labels.get(KEYBOARD_HEADING) or "").strip()
        if heading and _normalise(heading) not in TOKEN_HEADINGS:
            print(t("The keyboard open in Kodi is \"%s\", not the addon's OAuth token field: nothing was sent.",
                    "Le clavier ouvert dans Kodi est « %s », pas le champ Jeton OAuth de l'addon : rien n'a été envoyé.")
                  % heading)
            return False
        if not heading:
            try:
                answer = input(t("A keyboard is open in Kodi but its title cannot be read. "
                                 "Is it the addon's OAuth token field? [y/N] ",
                                 "Un clavier est ouvert dans Kodi mais son titre est illisible. "
                                 "Est-ce bien le champ Jeton OAuth de l'addon ? [o/N] "))
            except EOFError:
                answer = ""
            if answer.strip().lower() not in ("y", "yes", "o", "oui"):
                print(t("Nothing was sent.", "Rien n'a été envoyé."))
                return False
        kodi.call("Input.SendText", {"text": token, "done": True})
        print(t("Token sent. In Kodi, press Save: the window shows at once whether SoundCloud accepts it.",
                "Jeton envoyé. Dans Kodi, appuie sur Enregistrer : la fenêtre indique aussitôt si SoundCloud l'accepte."))
        return True
    finally:
        kodi.close()


# --------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(
        description=t("Get the SoundCloud OAuth token from Firefox for the Kodi addon.",
                      "Récupère le jeton OAuth SoundCloud depuis Firefox pour l'addon Kodi."))
    p.add_argument("--profile", help=t("Firefox profile folder or cookies.sqlite to use",
                                       "dossier de profil Firefox ou cookies.sqlite à utiliser"))
    p.add_argument("--kodi", metavar="HOST", help=t("Kodi IP or host name: type the token into Kodi",
                                                     "IP ou nom de Kodi : saisir le jeton dans Kodi"))
    p.add_argument("--kodi-port", type=int, default=9090, help="JSON-RPC TCP port (9090)")
    p.add_argument("--kodi-http-port", type=int, default=8080, help="JSON-RPC HTTP port (8080)")
    p.add_argument("--kodi-user", help=t("web server user (HTTP only)", "utilisateur du serveur web (HTTP)"))
    p.add_argument("--kodi-password", help=t("web server password (HTTP only)", "mot de passe du serveur web (HTTP)"))
    p.add_argument("--wait", type=int, default=120, help=t("seconds to wait for Kodi's keyboard",
                                                            "secondes d'attente du clavier Kodi"))
    p.add_argument("--show", action="store_true", help=t("print the full token", "afficher le jeton complet"))
    p.add_argument("--no-copy", action="store_true", help=t("don't copy to the clipboard",
                                                            "ne pas copier dans le presse-papier"))
    args = p.parse_args(argv)

    dbs = firefox_cookie_dbs(args.profile)
    if not dbs:
        print(t("No Firefox profile found. Use --profile, or the helper page:",
                "Aucun profil Firefox trouvé. Utilise --profile, ou la page d'aide :"))
        print("  https://theworms.github.io/kodi-addon-soundcloud/")
        return 2

    seen, cands = set(), []
    for db in dbs:
        for value, _host, last in read_oauth_cookies(db):
            if value not in seen:
                seen.add(value)
                cands.append((value, os.path.basename(os.path.dirname(db)), last))
    if not cands:
        print(t("No SoundCloud 'oauth_token' cookie in Firefox. Sign in on soundcloud.com in Firefox "
                "(and close private windows), or use the Network-tab method of the helper page:",
                "Aucun cookie SoundCloud « oauth_token » dans Firefox. Connecte-toi sur soundcloud.com "
                "dans Firefox, ou utilise la méthode de l'onglet Réseau de la page d'aide :"))
        print("  https://theworms.github.io/kodi-addon-soundcloud/")
        return 3

    chosen = None
    fallback = None
    for token, profile, _ in cands:
        ok, info = verify(token)
        if ok is True:
            print(t("Token found in profile %s: %s — verified, signed in as %s.",
                    "Jeton trouvé dans le profil %s : %s — vérifié, connecté en tant que %s.")
                  % (profile, mask(token), info))
            chosen = token
            break
        if ok is False:
            print(t("Cookie in profile %s refused by SoundCloud (HTTP 401): %s",
                    "Cookie du profil %s refusé par SoundCloud (HTTP 401) : %s") % (profile, mask(token)))
        else:
            print(t("Cookie in profile %s could not be checked (%s): %s",
                    "Cookie du profil %s non vérifiable (%s) : %s") % (profile, info, mask(token)))
            fallback = fallback or token
    if chosen is None and fallback is not None:
        print(t("Using an unverified token: test it in Kodi.", "Jeton non vérifié utilisé : teste-le dans Kodi."))
        chosen = fallback
    if chosen is None:
        print(t("SoundCloud refuses the cookie value. Use the Network-tab method of the helper page:",
                "SoundCloud refuse la valeur du cookie. Utilise la méthode de l'onglet Réseau de la page d'aide :"))
        print("  https://theworms.github.io/kodi-addon-soundcloud/")
        return 4

    if args.show:
        print(chosen)
    if not args.no_copy:
        tool = copy_to_clipboard(chosen)
        if tool:
            print(t("Copied to the clipboard (%s).", "Copié dans le presse-papier (%s).") % tool)
        elif not args.kodi and not args.show:
            print(t("No clipboard tool found (wl-copy, xclip, xsel): re-run with --show or --kodi.",
                    "Aucun outil de presse-papier (wl-copy, xclip, xsel) : relance avec --show ou --kodi."))
    if args.kodi:
        try:
            if not send_to_kodi(chosen, args):
                return 5
        except (ConnectionError, OSError, RuntimeError, TimeoutError, urllib.error.URLError) as e:
            print(t("Cannot reach Kodi: %s", "Kodi injoignable : %s") % e)
            print(t("Enable Settings > Services > Control > remote control in Kodi, or paste the token by hand.",
                    "Active Paramètres > Services > Contrôle > contrôle à distance dans Kodi, ou colle le jeton à la main."))
            return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
