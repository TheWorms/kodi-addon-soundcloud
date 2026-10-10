/*
 * SoundCloud token for Kodi - popup.
 * Shows the token captured by background.js, copies it, and can type it
 * into Kodi's on-screen keyboard through Kodi's HTTP JSON-RPC
 * (Input.SendText), after an explicit click and permission prompt, and
 * only when the keyboard Kodi shows is the addon's "OAuth token" one.
 */
const api = globalThis.browser || globalThis.chrome;
const SC_ORIGINS = ["https://api-v2.soundcloud.com/*", "https://soundcloud.com/*"];
const TOKEN_RE = /^[12]-\d+-\d+-[A-Za-z0-9_-]+$/;
const KEYBOARD_WINDOW_ID = 10103; // Kodi DialogKeyboard
const KEYBOARD_HEADING = "Control.GetLabel(311)"; // its title label
// The addon's "OAuth token" window (6.0.1+) sets this home-window
// property while it is open; 9101 is its "Enter token" button.
const TOKEN_WINDOW_PROP = "Window(Home).Property(soundcloud.tokenwindow)";
const FOCUSED_CONTROL = "System.CurrentControlId";
const ENTER_TOKEN_BUTTON = "9101";
// Title of the addon's token keyboard (strings.po #30021) in every
// language the addon ships, normalised (lowercase, letters and digits).
const TOKEN_HEADINGS = ["oauthtoken", "jetonoauth"];

const $ = (id) => document.getElementById(id);
const t = (key, subs) => {
  try {
    return api.i18n.getMessage(key, subs) || key;
  } catch (e) {
    return key;
  }
};

let current = null; // { token, verified, rejected, source, endpoint, at }

function applyI18n() {
  document.documentElement.lang = (api.i18n.getUILanguage() || "en").slice(0, 2);
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
}

async function hasSoundCloudAccess() {
  try {
    return await api.permissions.contains({ origins: SC_ORIGINS });
  } catch (e) {
    return true;
  }
}

async function readCookie() {
  const query = { domain: "soundcloud.com", name: "oauth_token" };
  let cookies = [];
  try {
    cookies = await api.cookies.getAll(query);
  } catch (e) {
    try {
      // Firefox with first-party isolation requires this key.
      cookies = await api.cookies.getAll(Object.assign({ firstPartyDomain: null }, query));
    } catch (e2) {
      cookies = [];
    }
  }
  for (const c of cookies || []) {
    let v = (c.value || "").trim();
    try {
      v = decodeURIComponent(v);
    } catch (e) {
      // keep raw value
    }
    v = v.replace(/^OAuth\s+/i, "");
    if (TOKEN_RE.test(v)) return v;
  }
  return null;
}

async function loadState() {
  try {
    const data = await api.storage.session.get("sc");
    if (data && data.sc && data.sc.token) return data.sc;
  } catch (e) {
    // fall through to the cookie
  }
  const cookie = await readCookie();
  return cookie ? { token: cookie, verified: false, rejected: false, source: "cookie" } : null;
}

function setStatus(text, kind) {
  const el = $("status");
  el.textContent = text;
  el.className = "status" + (kind ? " " + kind : "");
}

function render(state) {
  current = state;
  const has = !!(state && state.token);
  $("tokenBox").hidden = !has;
  $("clear").hidden = !has;
  $("kodi").hidden = !has;
  $("open").className = has ? "" : "primary";
  if (!has) {
    $("token").value = "";
    $("meta").textContent = "";
    setStatus(t("statusNone"), "");
    return;
  }
  $("token").value = state.token;
  if (state.verified) setStatus(t("statusVerified"), "ok");
  else if (state.rejected) setStatus(t("statusRejected"), "err");
  else if (state.source === "cookie") setStatus(t("statusCookie"), "warn");
  else setStatus(t("statusCaptured"), "warn");

  const parts = [];
  if (state.endpoint) parts.push(t("capturedFrom") + " " + state.endpoint);
  if (state.at) {
    const minutes = Math.max(0, Math.round((Date.now() - state.at) / 60000));
    parts.push(t("minutesAgo", [String(minutes)]));
  }
  $("meta").textContent = parts.join(" · ");
}

function flashButton(btn, labelKey, ok) {
  const original = t(btn.dataset.i18n);
  btn.textContent = t(labelKey);
  btn.classList.toggle("done", !!ok);
  clearTimeout(btn._timer);
  btn._timer = setTimeout(() => {
    btn.textContent = original;
    btn.classList.remove("done");
  }, 1800);
}

function showToken(visible) {
  $("token").type = visible ? "text" : "password";
  $("toggle").textContent = t(visible ? "btnHide" : "btnShow");
}

async function copyToken() {
  if (!current) return;
  const btn = $("copy");
  try {
    await navigator.clipboard.writeText(current.token);
    flashButton(btn, "btnCopied", true);
    return;
  } catch (e) {
    // fall back to a selection copy
  }
  const input = $("token");
  const wasHidden = input.type === "password";
  showToken(true);
  input.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch (e) {
    ok = false;
  }
  // On failure the token stays visible and selected so it can be copied
  // by hand; the toggle label follows.
  if (ok && wasHidden) showToken(false);
  flashButton(btn, ok ? "btnCopied" : "btnCopyFailed", ok);
}

function clearToken() {
  api.runtime
    .sendMessage({ type: "clear" })
    .catch(() => {})
    .then(() => render(null));
}

function openSoundCloud() {
  api.tabs.create({ url: "https://soundcloud.com/you/likes" });
  window.close();
}

/* ---------------------------------------------------------------- Kodi */

function kodiMsg(text, kind) {
  const el = $("kodiMsg");
  el.textContent = text;
  el.className = "msg" + (kind ? " " + kind : "");
}

/*
 * Parse the address field ("192.168.1.20", "192.168.1.20:8080",
 * "http://kodi.lan:8080/") into a canonical { host, port }. The host comes
 * from the URL parser (lowercase, normalised IPv4, bracketed IPv6) so the
 * permission origin and the fetch URL always match.
 */
function kodiTarget() {
  const field = $("kHost").value.trim();
  if (!field) return null;
  const raw = /^https?:\/\//i.test(field) ? field : "http://" + field;
  let url;
  try {
    url = new URL(raw);
  } catch (e) {
    return null;
  }
  if (url.protocol !== "http:" || url.username || url.password || url.search || url.hash) return null;
  if (url.pathname && url.pathname !== "/") return null;
  const host = url.hostname;
  if (!host) return null;
  // An explicit port in the field wins (URL drops ":80", so read the text).
  const explicit = /:(\d{1,5})\/?$/.exec(raw.replace(/^https?:\/\//i, ""));
  let port = explicit ? parseInt(explicit[1], 10) : parseInt($("kPort").value, 10) || 8080;
  if (!(port >= 1 && port <= 65535)) return null;
  if (explicit) $("kPort").value = String(port);
  return { host, port, user: $("kUser").value.trim(), pass: $("kPass").value };
}

function basicAuth(user, pass) {
  const bytes = new TextEncoder().encode(user + ":" + pass);
  let bin = "";
  bytes.forEach((b) => {
    bin += String.fromCharCode(b);
  });
  return "Basic " + btoa(bin);
}

async function rpc(target, method, params) {
  const headers = { "Content-Type": "application/json" };
  if (target.user) headers.Authorization = basicAuth(target.user, target.pass);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const r = await fetch("http://" + target.host + ":" + target.port + "/jsonrpc", {
      method: "POST",
      headers,
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params: params || {} }),
      signal: ctrl.signal,
      credentials: "omit",
      cache: "no-store",
    });
    if (r.status === 401) throw new Error("auth");
    if (!r.ok) throw new Error("http " + r.status);
    const data = await r.json();
    if (data.error) throw new Error(data.error.message || "rpc");
    return data.result;
  } finally {
    clearTimeout(timer);
  }
}

async function keyboardOpen(target) {
  const props = await rpc(target, "GUI.GetProperties", { properties: ["currentwindow"] });
  return ((props && props.currentwindow) || {}).id === KEYBOARD_WINDOW_ID;
}

function normaliseHeading(text) {
  return (text || "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function sendToKodi(confirmedUnknownHeading) {
  if (!current) return;
  const target = kodiTarget();
  if (!target) {
    kodiMsg(t($("kHost").value.trim() ? "kodiBadHost" : "kodiNeedHost"), "err");
    return;
  }
  $("sendAnyway").hidden = true;
  // permissions.request must be the first async call of the click handler
  // (user gesture). Match patterns cannot contain a port (Firefox ignores
  // the URL port when matching), so the permission covers the host.
  api.permissions
    .request({ origins: ["http://" + target.host + "/*"] })
    .then(async (granted) => {
      if (!granted) {
        kodiMsg(t("kodiPermDenied"), "err");
        return;
      }
      try {
        await api.storage.local.set({
          kodi: { host: target.host, port: target.port, user: target.user },
        });
      } catch (e) {
        // remembering the address is optional
      }
      $("send").disabled = true;
      kodiMsg(t("kodiSending"), "");
      try {
        await rpc(target, "JSONRPC.Ping");
        if (!(await keyboardOpen(target))) {
          // Without an open keyboard Kodi would type the text into
          // whatever control has the focus: never do that. When the
          // addon's token window is open on "Enter token", press it to
          // open its keyboard (titled "OAuth token").
          const state = await rpc(target, "XBMC.GetInfoLabels", {
            labels: [TOKEN_WINDOW_PROP, FOCUSED_CONTROL],
          });
          if (((state && state[TOKEN_WINDOW_PROP]) || "") !== "1") {
            kodiMsg(t("kodiNoWindow"), "warn");
            return;
          }
          if (String((state && state[FOCUSED_CONTROL]) || "") !== ENTER_TOKEN_BUTTON) {
            kodiMsg(t("kodiFocusEnter"), "warn");
            return;
          }
          await rpc(target, "Input.Select");
          let opened = false;
          for (let i = 0; i < 20 && !opened; i++) {
            await new Promise((r) => setTimeout(r, 250));
            opened = await keyboardOpen(target);
          }
          if (!opened) {
            kodiMsg(t("kodiNoKeyboard"), "warn");
            return;
          }
        }
        const labels = await rpc(target, "XBMC.GetInfoLabels", { labels: [KEYBOARD_HEADING] });
        const heading = ((labels && labels[KEYBOARD_HEADING]) || "").trim();
        if (heading && TOKEN_HEADINGS.indexOf(normaliseHeading(heading)) < 0) {
          kodiMsg(t("kodiWrongKeyboard", [heading]), "warn");
          return;
        }
        if (!heading && !confirmedUnknownHeading) {
          kodiMsg(t("kodiUnknownKeyboard"), "warn");
          $("sendAnyway").hidden = false;
          return;
        }
        await rpc(target, "Input.SendText", { text: current.token, done: true });
        kodiMsg(t("kodiSent"), "ok");
      } catch (e) {
        kodiMsg(t(e && e.message === "auth" ? "kodiAuth" : "kodiUnreachable"), "err");
      } finally {
        $("send").disabled = false;
      }
    })
    .catch(() => kodiMsg(t("kodiPermDenied"), "err"));
}

async function restoreKodiFields() {
  try {
    const data = await api.storage.local.get("kodi");
    const k = data && data.kodi;
    if (k) {
      if (k.host) $("kHost").value = k.host;
      if (k.port) $("kPort").value = k.port;
      if (k.user !== undefined) $("kUser").value = k.user;
    }
  } catch (e) {
    // defaults stay
  }
}

/* ---------------------------------------------------------------- init */

async function init() {
  applyI18n();
  $("copy").addEventListener("click", copyToken);
  $("toggle").addEventListener("click", () => showToken($("token").type === "password"));
  $("clear").addEventListener("click", clearToken);
  $("open").addEventListener("click", openSoundCloud);
  $("send").addEventListener("click", () => sendToKodi(false));
  $("sendAnyway").addEventListener("click", () => sendToKodi(true));
  $("grant").addEventListener("click", () => {
    api.permissions
      .request({ origins: SC_ORIGINS })
      .then((granted) => {
        if (granted) window.location.reload();
      })
      .catch(() => {});
  });

  if (!(await hasSoundCloudAccess())) {
    $("perm").hidden = false;
    $("main").hidden = true;
    return;
  }
  await restoreKodiFields();
  render(await loadState());
}

init();
