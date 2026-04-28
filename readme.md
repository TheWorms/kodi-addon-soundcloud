# SoundCloud Add-on for [Kodi](https://github.com/xbmc/xbmc)

<img align="right" src="https://github.com/xbmc/xbmc/raw/master/addons/webinterface.default/icon-128.png" alt="Kodi logo">

[![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/jaylinski/kodi-addon-soundcloud.svg)](https://github.com/jaylinski/kodi-addon-soundcloud/releases)
[![CI Build Status](https://github.com/jaylinski/kodi-addon-soundcloud/actions/workflows/ci.yml/badge.svg)](https://github.com/jaylinski/kodi-addon-soundcloud/actions)
[![Link to Kodi forum](https://img.shields.io/badge/Kodi-Forum-informational.svg)](https://forum.kodi.tv/showthread.php?tid=206635)
[![Link to Kodi wiki](https://img.shields.io/badge/Kodi-Wiki-informational.svg)](https://kodi.wiki/view/Add-on:SoundCloud)
[![Link to Kodi releases](https://img.shields.io/badge/Kodi-v19%20%22Matrix%22-green.svg)](https://kodi.wiki/view/Releases)

This [Kodi](https://github.com/xbmc/xbmc) Add-on provides a full-screen, modern
interface for SoundCloud, with a sidebar, horizontal carousel rows on the home
screen, autoplay, and an integrated mini-player.

## What's new in v5

The v5 release introduces a **brand-new full-screen interface** that replaces
the classic plugin-style menu with an "app-like" experience:

* **Sidebar navigation** — Home, Search, Likes, My playlists, Following, Settings
* **Home screen with up to 4 horizontal rows** (configurable order and content):
  Likes, Trending, My playlists, Following
* **Mini-player** at the bottom showing cover, title, artist, time and a
  SoundCloud-orange progress bar — with optional play/pause/next/prev controls
* **Auto-play next track**: clicking a track queues all visible tracks so Kodi
  plays them in sequence automatically
* **Pagination**: pages show a "Next page" item at the end when there are more
  results
* **Selection follows the playing track** during autoplay
* **Configurable everywhere** — toggles in Settings (layout, mini-player
  mode, autoplay, shuffle, row contents)

Since v5.7 the full-screen UI is the only interface — the classic
plugin-style menu was removed. Skin home widgets continue to work via
the dedicated `/widget/*` routes (see "Widgets" below).

## Features

* Search
* Discover new music
* Play tracks, albums and playlists
* Optional sign-in via OAuth token to access your likes, playlists, following and reposts
* New full-screen interface with sidebar, carousel rows and mini-player (v5)

## Installation

### Kodi Repository

Follow the instructions on [https://kodi.wiki/view/Add-on:SoundCloud](https://kodi.wiki/view/Add-on:SoundCloud).

### Manual

* [Download the latest release](https://github.com/jaylinski/kodi-addon-soundcloud/releases) (`plugin.audio.soundcloud.zip`)
* Copy the zip file to your Kodi system
* Open Kodi, go to Add-ons and select "Install from zip file"
* Select the file `plugin.audio.soundcloud.zip`

## Authentication (optional)

The add-on can access your personal SoundCloud data (likes, playlists,
following, reposts) by authenticating with an OAuth token that you paste
into the settings.

There is no "Sign in" button: SoundCloud's public API registration has
been closed since 2021, so we reuse the token the SoundCloud website
itself uses. The token is stored locally in Kodi's addon settings and
sent only to `api-v2.soundcloud.com`.

### How to get your OAuth token

The recommended way is to read the **`Authorization` header** of any
authenticated request your browser makes to the SoundCloud API.

1. Open [https://soundcloud.com](https://soundcloud.com) in Chrome or
   Firefox and **sign in** (verify your avatar shows top-right — important).
2. Press `F12` to open the developer tools.
3. Go to the **Network** tab.
4. In the filter box, type: `api-v2`
5. Reload the page (`F5`) so requests appear in the list.
6. Click on any request in the list (e.g. `me`, `featured-tracks`, etc.).
7. In the right panel, scroll to **Request Headers**.
8. Find the line: `Authorization: OAuth XXXXXXXXX`
9. Copy **only what comes after** `OAuth ` (the token itself, no prefix,
   no leading space).
10. In Kodi, go to the addon settings → **Account** → paste the value
    into the **OAuth token** field.
11. Click **Test OAuth token**. You should see "Token valid: <yourname>".

#### Common pitfalls

* **Do not** copy the cookie named `oauth_token` (under
  *Application → Cookies* in DevTools). It looks similar but is rejected
  by the API and will silently break authentication.
* **Do not** include the word `OAuth` or any leading/trailing space in the
  pasted value (the addon will strip them defensively, but it's cleaner
  to copy just the token).
* If your token starts with `2-` it's a recent format; older accounts may
  see `1-` — both are valid.
* If you can't find the `Authorization` header, you're probably not
  signed in — check the avatar in the top-right of soundcloud.com.

### Test your token

The settings page has a **Test OAuth token** button right below the
token field. Click it after pasting to verify the token actually works:
the dialog will show your username on success, or the exact HTTP error
returned by SoundCloud on failure (with a token-length preview to help
spot truncated pastes).

### Token expiration

The token expires occasionally (usually after several months, or if you
sign out from the SoundCloud website). When that happens, lists under
"My profile", "Likes", etc. come back empty and you see a warning
notification in Kodi. Just repeat the steps above to get a fresh token,
paste it into the settings and click **Test OAuth token** to confirm.

The addon now picks up token changes immediately — no need to restart
Kodi after pasting a new token.

### Privacy

* The token is stored **only** on your device, in Kodi's addon profile folder.
* It is sent **only** to `api-v2.soundcloud.com` as the `Authorization` request header.
* It is **redacted** from debug logs (the header value is replaced by `<redacted>` in `kodi.log`).


## Copyright and license

This add-on is licensed under the MIT License - see `LICENSE.txt` for details.
