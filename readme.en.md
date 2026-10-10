[Français](readme.md) &nbsp;|&nbsp; **English**

# SoundCloud Add-on for [Kodi](https://github.com/xbmc/xbmc)

<!-- version:auto -->
**Version : 6.0.2**
<!-- /version:auto -->

<img align="right" src="https://github.com/xbmc/xbmc/raw/master/addons/webinterface.default/icon-128.png" alt="Kodi logo">

[![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/TheWorms/kodi-addon-soundcloud.svg)](https://github.com/TheWorms/kodi-addon-soundcloud/releases)
[![Kodi forum link](https://img.shields.io/badge/Kodi-Forum-informational.svg)](https://forum.kodi.tv/showthread.php?tid=206635)
[![Kodi wiki link](https://img.shields.io/badge/Kodi-Wiki-informational.svg)](https://kodi.wiki/view/Add-on:SoundCloud)
[![Kodi versions link](https://img.shields.io/badge/Kodi-v21%20%22Omega%22-green.svg)](https://kodi.wiki/view/Releases)

SoundCloud in Kodi, with a real full-screen interface: side menu,
customisable home rows, automatic play queue, mini-player, stations and
four "Now playing" screens. Connect your account in one click with the
bundled browser extension and get your likes, playlists, followings and
listening history.

![Home screen in tiles layout: the playing track is marked by the orange wave, a "See more" card ends the row, mini-player at the bottom](docs/screenshots/home-playing.jpg)

> **Community fork** of
> [jaylinski/kodi-addon-soundcloud](https://github.com/jaylinski/kodi-addon-soundcloud),
> maintained at [TheWorms/kodi-addon-soundcloud](https://github.com/TheWorms/kodi-addon-soundcloud).
> Bug reports and requests about the full-screen interface (v5 and
> later) belong here; for the old plugin menu (v4 and earlier), see the
> original project.

## Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Connecting your SoundCloud account](#connecting-your-soundcloud-account)
- [Usage](#usage)
- [Settings](#settings)
- [Now playing screens](#now-playing-screens)
- [Opening SoundCloud faster](#opening-soundcloud-faster)
- [Home screen widgets](#home-screen-widgets)
- [Privacy](#privacy)
- [Troubleshooting](#troubleshooting)
- [What's new](#whats-new)
- [Credits and license](#credits-and-license)

## Features

**Interface**
- Side menu: Home, Search, Likes, Stations, My playlists, Following and
  Settings.
- Two layouts, switchable on the fly: **Tiles** (horizontal rows) or
  **List** (large vertical lists).
- **4 configurable home rows**, each opened as a full page by its
  **"See more"** card.
- **Mini-player** at the bottom of the screen (cover, title, progress),
  can be hidden.
- The playing track is marked everywhere: **orange wave** over the
  cover, orange title and duration in the List layout. Rows follow the
  play queue.

**Playback**
- Selecting a track queues every track of the row or page.
- Shuffle, **endless playback** (related tracks added when the queue
  ends), **sleep timer**.
- Choice of audio format: light Opus, adaptive MP3 HLS or progressive
  MP3.
- Automatic recovery when a SoundCloud stream URL expires mid-track.

**SoundCloud account** (with an OAuth token)
- Your likes, playlists, followings and listening history.
- Personal rows: "Recently played", "Mixed for you", "Based on what you
  like".
- Like and unlike tracks from Kodi (context menu).
- Your liked stations, on top of the genre stations.

**Also**
- Four fullscreen "Now playing" screens: Cinema, Waveform, Editorial
  and Vinyl.
- Widgets for the Kodi home screen.
- Optional background service for an instant start.
- French and English interface (German and Dutch partial).

## Screenshots

| Home, tiles layout | List layout |
|:---:|:---:|
| ![Home in tiles layout](docs/screenshots/home.jpg) | ![List layout, playing track in orange](docs/screenshots/list-layout.jpg) |
| **Stations** | **Inside a station** |
| ![Genre stations](docs/screenshots/stations.jpg) | ![Tracks of a station as a grid](docs/screenshots/station-tracks.jpg) |
| **Settings** | **"OAuth token" window** |
| ![Settings, Display tab](docs/screenshots/settings.jpg) | ![OAuth token window: token valid and saved](docs/screenshots/token-saved.jpg) |

The screenshots show the French interface; the add-on follows Kodi's
language.

## Installation

**Recommended: the TheWorms repository**, for automatic updates.

1. Download the repository:
   **[repository.theworms.zip](https://raw.githubusercontent.com/TheWorms/kodi-repo/main/zips/repository.theworms/repository.theworms.zip)**.
2. In Kodi: **Add-ons → Install from zip file** → pick the zip. If Kodi
   refuses, enable **Unknown sources** under *System → Add-ons*.
3. **Install from repository → TheWorms Repository → Music add-ons →
   SoundCloud**.

**Manual install**: download the add-on zip from the
[Releases](../../releases) page, then **Install from zip file**.
Updates are then not automatic.

**Requirements**: Kodi 21 "Omega". Dependencies
(`script.module.requests`) are installed automatically.

### Pillow (optional)

With [Pillow](https://pypi.org/project/Pillow/) (`script.module.pil`),
the "Now playing" screens show a blurred cover in the background.
Without Pillow the cover is simply dimmed. Install it from the official
Kodi repository (*Add-ons → Search → Pillow*); the add-on picks it up
with the next track.

## Connecting your SoundCloud account

The add-on works without an account (search, trending, genre
stations). For your likes, playlists, followings and history it needs
the **OAuth token** of your soundcloud.com session. SoundCloud has not
accepted new applications on its public API since 2021, so there is no
"Sign in" button: the add-on reuses the website's token.

The easiest way is the bundled **browser extension**, which picks up
the token and sends it to Kodi. The full, illustrated procedure is on
the help page:

**➜ [theworms.github.io/kodi-addon-soundcloud](https://theworms.github.io/kodi-addon-soundcloud/get-token.html)**

<img align="right" width="420" src="docs/screenshots/token-window.jpg" alt="OAuth token window in Kodi">

1. **Install the "SoundCloud token for Kodi" extension**
   ([download](https://theworms.github.io/kodi-addon-soundcloud/soundcloud-token-extension.zip);
   Firefox 128+, Chrome, Edge, Brave). In Firefox it loads as a
   temporary add-on, to be reloaded after the browser restarts; the
   help page details the install. Source code:
   [`tools/token-extension`](tools/token-extension).
2. **Open [soundcloud.com](https://soundcloud.com)** while signed in.
   The extension icon shows a green **OK** badge once the token is
   picked up and accepted by SoundCloud.
3. **In Kodi**, open *Settings → Account → Manage the OAuth token…*:
   the window tells you whether the saved token is still valid.
4. **In the extension, click "Send to Kodi"** (Kodi's IP address, web
   server user name and password). The extension opens the window's
   keyboard and types the token. Kodi must have *Settings → Services →
   Control → Allow remote control via HTTP* enabled.
5. **Press Save.** SoundCloud is asked right away: **valid** (with your
   name and plan), **refused** (expired or wrong token, it is not kept)
   or **could not be checked** (you choose whether to save it anyway).

<br clear="right">

**Without automatic sending**: *Copy token* in the extension, then
*Enter token* in Kodi and paste it (a remote app such as Kore or Yatse
can paste from your phone).

**Without the extension**: the help page also covers the browser
developer tools Network tab (F12), the `oauth_token` cookie, and the
[`scripts/get_soundcloud_token.py`](scripts/get_soundcloud_token.py)
script, which reads the token from your Firefox profile and can send it
to Kodi.

**Renewal**: a token expires after a few months, or when you sign out
of soundcloud.com. *Settings → Account → Token status* sums up the last
check. A new token is used immediately, without restarting Kodi: the
interface reloads its rows by itself.

**Free, Go, Go+**: all three plans work. On a Free account, SoundCloud
only serves a 30-second excerpt of Go+ tracks; the *Skip Go+ excerpts*
option keeps them out of the queue.

## Usage

- **Navigation**: Right from the side menu enters the content, Back
  returns to the previous page and then closes the add-on.
- **Playback**: OK on a track starts it and queues the rest of the row
  or page. On a playlist, an artist or a station, OK opens its content.
- **"See more"**: the last card of a full row opens the row as a full
  page, with *Next page* when SoundCloud has more.
- **Likes**: context menu (C key or long press) on a track → *Add to
  likes* / *Remove from likes*.
- **Mini-player**: cover, title and progress of the playing track; the
  remote's play/pause, next and previous keys drive the queue.
- **Settings**: the button at the bottom of the side menu. Display
  changes (layout, rows, trending genre) apply when you return to the
  interface, without reopening it.

## Settings

| Tab | Setting | What it does |
|---|---|---|
| **Display** | Layout | *Tiles* or *List* |
| | Mini-player | Show or hide the bottom bar |
| | Row 1 to 4 | Content of each home row: Your likes, Trending, Your playlists, You follow, Recently played, Mixed for you, Based on what you like, Created by SoundCloud, Buzzing artists, or off |
| | Trending genre | All genres, Techno, House, Deep House, Electronic, Hip-hop, Ambient, Jazz… |
| **Playback** | Audio format | Light Opus, adaptive MP3 HLS, progressive MP3 (default, the most stable) |
| | Auto-play next track, Shuffle playback | Play the queue through, in order or not |
| | Skip Go+ excerpts | Keep 30-second excerpts out of the queue |
| | Endless playback | Append related tracks when the queue ends |
| | Sleep timer | Stop after 15, 30, 60 or 120 min of actual listening (pausing suspends the countdown) |
| | Tracks per page | 10, 20, 30 or 50 items per row and per page |
| | Automatic fullscreen, style, delay | See [Now playing screens](#now-playing-screens) |
| **Account** | Manage the OAuth token… | Opens the token window |
| | Token status | Result of the last check (read-only) |
| | Clear cache | Deletes the SoundCloud answers cached by the add-on |
| | Background service | Instant add-on start (requires a Kodi restart) |

## Now playing screens

During playback, the add-on can show a fullscreen screen over the
interface. Pick the style in *Settings → Playback → Fullscreen style*;
*Automatic fullscreen overlay* and *Delay before opening* decide
whether it opens by itself and after how long.

| Style | Look |
|---|---|
| **Off** | No fullscreen screen, only the mini-player |
| **Cinema** | Centred cover with a slow zoom, blurred background, title and artist below |
| **Waveform** | Animated orange bars at the bottom, real progress bar above |
| **Editorial** | Magazine layout: cover on the left, large title and a quote taken from the track description |
| **Vinyl with sleeve** | Spinning vinyl record with the cover in the centre |

**Keys**

| Key | Action |
|---|---|
| OK | Pause / resume |
| Left / Right | Back / forward 10 s (*Seek interval*: 5 to 30 s) |
| Up | Next track |
| Down | Back to the start of the track, or previous track within the first 3 seconds |
| Back | Close the screen (playback continues) |

Kodi's Python API gives add-ons no access to the audio signal: the
*Waveform* animation is decorative, only the progress bar follows
playback. The vinyl rotation may stutter on older devices (Raspberry
Pi 3…). The *Editorial* quote stays empty when the track has no
description.

## Opening SoundCloud faster

Opened from *Music → Add-ons*, Kodi briefly shows its music browser
before the interface. Three ways to avoid it:

1. **Background service** (recommended): *Settings → Account →
   Background service*, then restart Kodi. The loading screen appears
   in ~50 ms. Cost: a few MB of memory.
2. **Kodi favourite**: add SoundCloud to your favourites, then in
   `userdata/favourites.xml` replace its action with
   `RunScript(plugin.audio.soundcloud)`.
3. **Home menu shortcut** in your skin, with the action
   `RunScript(plugin.audio.soundcloud)` (Arctic Zephyr Reloaded:
   *Configure skin → Customise home menu*; Estuary: *Customise home
   menu → Action*).

## Home screen widgets

The add-on provides plain lists that skin widgets can display:

| Path | Content |
|---|---|
| `plugin://plugin.audio.soundcloud/widget/likes/` | Your likes (token required) |
| `plugin://plugin.audio.soundcloud/widget/playlists/` | Your playlists (token required) |
| `plugin://plugin.audio.soundcloud/widget/following/` | Your followings (token required) |
| `plugin://plugin.audio.soundcloud/widget/trending/` | Trending |
| `plugin://plugin.audio.soundcloud/widget/discover/` | Discover |
| `plugin://plugin.audio.soundcloud/widgets/` | List of all the widgets above |

- **Estuary** and skins that let you browse an add-on: *Add widget →
  Add-ons → Music add-ons → SoundCloud*, then pick the widget you want.
- **Arctic Zephyr Reloaded** and skins that only take the root path:
  the widget shows the list of widgets (*Likes*, *My playlists*,
  *Trending*…) after *▶ Open SoundCloud*. For a direct content widget
  you need a skin that accepts a custom path (e.g. through Skin Helper
  Service).

A track picked in a widget opens the interface and plays it. With
*Continue with widget category after track ends*, the rest of the
category is queued.

## Privacy

- The token is stored **only** in the add-on settings on your device,
  and sent **only** to `api-v2.soundcloud.com`.
- It is masked in `kodi.log` (`OAuth <redacted>`).
- The extension keeps the token in memory only (forgotten when the
  browser closes) and contacts Kodi only when you click *Send to
  Kodi*. Kodi's remote control runs over plain HTTP, so the token then
  crosses your local network unencrypted, as with any Kodi remote app.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Personal rows show Trending | No token, or an expired one: open *Manage the OAuth token…*, the window tells you which |
| The extension says "Cannot reach Kodi" | Check Kodi's IP address and the *Allow remote control via HTTP* option |
| A track stops after 30 s | Go+ excerpt on a Free account; enable *Skip Go+ excerpts* |
| The music browser flashes on open | See [Opening SoundCloud faster](#opening-soundcloud-faster) |
| Lists do not update | *Settings → Account → Clear cache* |

## What's new

**6.0.2**
- Tiles layout: **"See more"** card at the end of the rows, as in the
  List layout.
- Playing wave over **the full height** of the cover.
- Rows **follow the queue**: the next track's tile comes into view.
- Fix: with the settings open, a whole row showed the playing wave.

**6.0.1**
- **"OAuth token" window** with a *Save* button and an instant check;
  token entry moved from the side menu to the settings.
- **Browser extension** "SoundCloud token for Kodi" and a help page
  rewritten around it.
- "Mixed for you" no longer copies "Recently played" (history read from
  the right endpoint).

**6.0**
- Stations, five new home rows, endless playback, sleep timer, likes
  from the add-on, List layout, simplified mini-player, automatic "Now
  playing" screen.
- Stability and security fixes from an audit (threads stopped cleanly,
  token never sent outside SoundCloud, API errors no longer crash).

**v5** introduced the full-screen interface, which has replaced the old
plugin menu since 5.7. The detailed history of every version is in the
`<news>` tag of [`addon.xml`](addon.xml).

## Credits and license

Fork maintained by **[TheWorms](https://github.com/TheWorms)**:
full-screen interface, OAuth token sign-in and browser extension,
widgets, "Now playing" screens, French translation, background service.

Based on [jaylinski's SoundCloud add-on](https://github.com/jaylinski/kodi-addon-soundcloud),
itself inspired by the [original add-on](https://github.com/SLiX69/plugin.audio.soundcloud)
by [bromix](https://kodi.tv/addon-author/bromix) and
[SLiX](https://github.com/SLiX69).

MIT licensed, like the original projects: see
[`LICENSE.txt`](LICENSE.txt). This add-on is not official, nor endorsed
by SoundCloud.
