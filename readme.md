# SoundCloud Add-on for [Kodi](https://github.com/xbmc/xbmc)

<img align="right" src="https://github.com/xbmc/xbmc/raw/master/addons/webinterface.default/icon-128.png" alt="Kodi logo">

[![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/jaylinski/kodi-addon-soundcloud.svg)](https://github.com/jaylinski/kodi-addon-soundcloud/releases)
[![CI Build Status](https://github.com/jaylinski/kodi-addon-soundcloud/actions/workflows/ci.yml/badge.svg)](https://github.com/jaylinski/kodi-addon-soundcloud/actions)
[![Link to Kodi forum](https://img.shields.io/badge/Kodi-Forum-informational.svg)](https://forum.kodi.tv/showthread.php?tid=206635)
[![Link to Kodi wiki](https://img.shields.io/badge/Kodi-Wiki-informational.svg)](https://kodi.wiki/view/Add-on:SoundCloud)
[![Link to Kodi releases](https://img.shields.io/badge/Kodi-v19%20%22Matrix%22-green.svg)](https://kodi.wiki/view/Releases)

This [Kodi](https://github.com/xbmc/xbmc) Add-on provides a minimal interface for SoundCloud.

## Features

* Search
* Discover new music
* Play tracks, albums and playlists
* Optional sign-in via OAuth token to access your likes, playlists, following and reposts

## Installation

### Kodi Repository

Follow the instructions on [https://kodi.wiki/view/Add-on:SoundCloud](https://kodi.wiki/view/Add-on:SoundCloud).

### Manual

* [Download the latest release](https://github.com/jaylinski/kodi-addon-soundcloud/releases) (`plugin.audio.soundcloud.zip`)
* Copy the zip file to your Kodi system
* Open Kodi, go to Add-ons and select "Install from zip file"
* Select the file `plugin.audio.soundcloud.zip`

## Authentication (optional)

The add-on can access your personal SoundCloud data (likes, playlists, following, reposts)
by authenticating with an OAuth token that you paste into the settings.

There is no "Sign in" button: SoundCloud's public API registration has been closed since 2021,
so we reuse the token the SoundCloud website itself uses. The token is stored locally in
Kodi's addon settings and sent only to `api-v2.soundcloud.com`.

### How to get your OAuth token

1. Open [https://soundcloud.com](https://soundcloud.com) in a web browser and sign in.
2. Open the developer tools (press `F12`).
3. Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
4. In the left sidebar, expand **Cookies** and select `https://soundcloud.com`.
5. Find the cookie named `oauth_token` and copy its value
   (looks like `1-12345-67890-abcdefghijklmno`).
6. In Kodi, go to the addon settings → **Account** → paste the value into **OAuth token**.

**Alternative method** (if the cookie is HttpOnly or not visible):
open the **Network** tab of the developer tools, find any request to `api-v2.soundcloud.com`,
look at the `Authorization` request header, and copy the value after `OAuth `.

### Token expiration

The token expires occasionally (usually after several months, or if you sign out from the
SoundCloud website). When that happens, lists under "My profile" come back empty and you
see a warning notification in Kodi. Just repeat the steps above to get a fresh token.

### Privacy

* The token is stored **only** on your device, in Kodi's addon profile folder.
* It is sent **only** to `api-v2.soundcloud.com` as the `Authorization` request header.
* It is **redacted** from debug logs (the header value is replaced by `<redacted>` in `kodi.log`).

## API

Documentation of the **public** interface.

### plugin://plugin.audio.soundcloud/play/?[track_id|playlist_id|url]

Examples:

* `plugin://plugin.audio.soundcloud/play/?track_id=1`
* `plugin://plugin.audio.soundcloud/play/?playlist_id=1`
* `plugin://plugin.audio.soundcloud/play/?url=https%3A%2F%2Fsoundcloud.com%2Fpslwave%2Fallwithit`

Legacy (will be removed in v5.0):

* `plugin://plugin.audio.soundcloud/play/?audio_id=1` Use `track_id=1` instead.

## Development

This add-on uses [Pipenv](https://pypi.org/project/pipenv/) to manage its dependencies.

### Setup

[Install Pipenv](https://pipenv.pypa.io/en/latest/installation.html#installing-pipenv) and run `pipenv install --dev`.

### Build

Run `pipenv run build`.

### Lint

Run `pipenv run lint`.

### Test

Run `pipenv run test`.

## Roadmap

* Re-implement all features from original add-on
* Implement [enhancements](https://github.com/jaylinski/kodi-addon-soundcloud/issues?q=is%3Aopen+is%3Aissue+label%3Aenhancement)

## Attributions

This add-on is strongly inspired by the [original add-on](https://github.com/SLiX69/plugin.audio.soundcloud)
developed by [bromix](https://kodi.tv/addon-author/bromix) and [SLiX](https://github.com/SLiX69).

## Copyright and license

This add-on is licensed under the MIT License - see `LICENSE.txt` for details.
