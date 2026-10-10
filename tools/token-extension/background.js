/*
 * SoundCloud token for Kodi - background script.
 *
 * Watches the requests that soundcloud.com itself sends to
 * api-v2.soundcloud.com and reads their "Authorization: OAuth <token>"
 * header (the exact value the Kodi addon needs). A token is marked
 * "verified" when the SoundCloud request that carried it came back with a
 * 2xx status from the network: no extra request is ever made to check it.
 *
 * Privacy: the token is kept in storage.session (memory only, cleared when
 * the browser closes). Nothing is sent anywhere by this script.
 */
const api = globalThis.browser || globalThis.chrome;

const API_FILTER = { urls: ["https://api-v2.soundcloud.com/*"] };
const AUTH_RE = /^OAuth\s+([12]-\d+-\d+-[A-Za-z0-9_-]+)\s*$/i;
const SOUNDCLOUD_PAGE_RE = /^https:\/\/([a-z0-9-]+\.)*soundcloud\.com(\/|$)/i;
const KEY = "sc";
const REFRESH_MS = 60 * 1000;

// requestId -> { token, ts } for requests still in flight (memory only;
// losing it when the background sleeps only delays verification to the
// next request).
const pending = new Map();

async function getState() {
  try {
    const data = await api.storage.session.get(KEY);
    return data[KEY] || null;
  } catch (e) {
    return null;
  }
}

async function setState(state) {
  try {
    if (state) await api.storage.session.set({ [KEY]: state });
    else await api.storage.session.remove(KEY);
  } catch (e) {
    // storage unavailable: nothing else we can do
  }
  updateBadge(state);
}

// Serialise read-modify-write cycles: onSendHeaders and onCompleted for
// the same request can race on the async storage API.
let chain = Promise.resolve();
function update(fn) {
  chain = chain
    .then(async () => {
      const next = fn(await getState());
      if (next !== undefined) await setState(next);
    })
    .catch(() => {});
  return chain;
}

function updateBadge(state) {
  try {
    let text = "";
    let color = "#ff5500";
    if (state && state.token) {
      if (state.verified) {
        text = "OK";
        color = "#2e7d32";
      } else if (state.rejected) {
        text = "!";
        color = "#c62828";
      } else {
        text = "?";
      }
    }
    api.action.setBadgeText({ text });
    api.action.setBadgeBackgroundColor({ color });
  } catch (e) {
    // badge is cosmetic
  }
}

function endpointOf(url) {
  try {
    return new URL(url).pathname;
  } catch (e) {
    return "";
  }
}

function fromSoundCloudPage(details) {
  // tabId < 0: requests made by extensions or the browser itself.
  if (details.tabId < 0) return false;
  // Chrome: initiator; Firefox: originUrl / documentUrl.
  const origin = details.initiator || details.originUrl || details.documentUrl || "";
  return SOUNDCLOUD_PAGE_RE.test(origin);
}

function onSendHeaders(details) {
  if (!fromSoundCloudPage(details)) return;
  const header = (details.requestHeaders || []).find(
    (h) => h.name && h.name.toLowerCase() === "authorization"
  );
  if (!header || !header.value) return;
  const match = AUTH_RE.exec(header.value.trim());
  if (!match) return;
  const token = match[1];
  const ts = details.timeStamp || Date.now();
  pending.set(details.requestId, { token, ts });
  update((state) => {
    // Never replace a verified token with an unconfirmed one: a new token
    // value takes over once one of its own requests succeeds.
    if (state && state.token === token) return undefined;
    if (state && state.verified) return undefined;
    return {
      token,
      verified: false,
      rejected: false,
      endpoint: endpointOf(details.url),
      ts,
      at: Date.now(),
    };
  });
}

function onCompleted(details) {
  const sent = pending.get(details.requestId);
  if (!sent) return;
  pending.delete(details.requestId);
  // A cached 200 proves nothing about the token.
  if (details.fromCache) return;
  const ok = details.statusCode >= 200 && details.statusCode < 300;
  update((state) => {
    if (ok) {
      if (state && state.token === sent.token && state.verified) {
        // Same token confirmed again: keep the newest confirmation time
        // (used to ignore late requests carrying an older token) and
        // refresh the displayed "last seen" time at most once a minute.
        const ts = Math.max(state.ts || 0, sent.ts);
        const at = Date.now() - (state.at || 0) >= REFRESH_MS ? Date.now() : state.at;
        if (ts === state.ts && at === state.at) return undefined;
        return Object.assign({}, state, { ts, at });
      }
      // A different token: only take over if this request was sent after
      // the one that confirmed the current token (an old request
      // finishing late must not bring an old token back).
      if (state && state.verified && state.token !== sent.token && sent.ts < (state.ts || 0)) {
        return undefined;
      }
      return {
        token: sent.token,
        verified: true,
        rejected: false,
        endpoint: endpointOf(details.url),
        ts: sent.ts,
        at: Date.now(),
      };
    }
    if (details.statusCode === 401 && state && state.token === sent.token) {
      // A later 2xx with the same token clears this again.
      return Object.assign({}, state, { verified: false, rejected: true, at: Date.now() });
    }
    return undefined;
  });
}

function onErrorOccurred(details) {
  pending.delete(details.requestId);
}

// Listeners must be registered synchronously at top level (MV3).
api.webRequest.onSendHeaders.addListener(onSendHeaders, API_FILTER, ["requestHeaders"]);
api.webRequest.onCompleted.addListener(onCompleted, API_FILTER);
api.webRequest.onErrorOccurred.addListener(onErrorOccurred, API_FILTER);

// Signed out of SoundCloud (oauth_token cookie deleted): forget the token.
api.cookies.onChanged.addListener((change) => {
  const c = change && change.cookie;
  if (!c || c.name !== "oauth_token" || !/(^|\.)soundcloud\.com$/i.test(c.domain || "")) return;
  if (change.removed && change.cause !== "overwrite") {
    pending.clear();
    update(() => null);
  }
});

api.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // Only our own popup may ask (no content scripts, no external pages).
  if (!msg || msg.type !== "clear" || (sender && sender.id && sender.id !== api.runtime.id)) {
    return false;
  }
  pending.clear();
  update(() => null).then(() => {
    try {
      sendResponse({ ok: true });
    } catch (e) {
      // popup already closed
    }
  });
  return true;
});

// Restore the badge after a background restart.
getState().then(updateBadge);
