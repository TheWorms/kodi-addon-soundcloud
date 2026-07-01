[Français](readme.md) &nbsp;|&nbsp; **English**

# SoundCloud Add-on for [Kodi](https://github.com/xbmc/xbmc) — v5+ fork

<!-- version:auto -->
**Version : 5.9.6020**
<!-- /version:auto -->

## Installation

**Recommended — TheWorms repository** (automatic updates).

Download the repository by clicking **[HERE](https://raw.githubusercontent.com/TheWorms/kodi-repo/main/zips/repository.theworms/repository.theworms.zip)**, then in Kodi:

1. **Add-ons** → **Install from zip file** → select the downloaded zip
   *(if Kodi blocks it, enable **Unknown sources** under Settings → Add-ons)*
2. **Install from repository** → **TheWorms Repository** → pick the add-on
3. Updates will then be automatic

**Manual install (alternative):** download the add-on zip from the [Releases](../../releases) page, then **Add-ons** → **Install from zip file**.

## What's new in v5

The v5 release introduced a **brand-new full-screen interface** that replaces
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
* **Fullscreen "Now Playing" overlays** (v5.8+): pick from 4 visual
  styles — *Cinema* (Apple-Music-like Ken Burns), *Waveform* (animated
  audio visualizer), *Editorial* (magazine layout with pull quote from
  the track description), *Vinyl* (spinning record with cover in the
  central label). Disable entirely if you prefer the mini-player only.
* **Account tier detection** — the addon reads your
  consumer subscription product from `/me` and stores it (Free /
  Go / Go+) so future code paths can adapt.
* **Keyboard navigation in fullscreen Now Playing**  —
  Left/Right seek ±10 s, Up skips to next track, Down restarts the
  current track (or jumps to previous if you're within the first 3
  seconds), OK toggles pause/play.
* **One-click token helper page** — a companion web page at
  [theworms.github.io/kodi-addon-soundcloud](https://theworms.github.io/kodi-addon-soundcloud/)
  with a console snippet that grabs your SoundCloud OAuth token in a
  single click — no more F12 / Network tab manual fiddling.
  
Since v5.7 the full-screen UI is the only interface — the classic
plugin-style menu was removed. Skin home widgets continue to work via
the dedicated `/widget/*` routes (see "Widgets" below).

## Features

* Search
* Discover new music
* Play tracks, albums and playlists (Free tier compatible)
* Optional sign-in via OAuth token to access your likes, playlists, following and reposts
* Full-screen interface with sidebar, carousel rows and mini-player (v5)
* Fullscreen "Now Playing" overlays in 4 styles (v5.8+)
* Keyboard shortcuts in fullscreen Now Playing (v5.9.6008+)
* Optional background service for instant startup (v5.9.6017+)

## Installation

### Kodi Repository

Follow the instructions on [https://kodi.wiki/view/Add-on:SoundCloud](https://kodi.wiki/view/Add-on:SoundCloud).

### Manual

* [Download the latest release from this fork](https://github.com/TheWorms/kodi-addon-soundcloud/releases) (`plugin.audio.soundcloud-X.Y.Z.zip`)
* Copy the zip file to your Kodi system
* Open Kodi, go to Add-ons and select "Install from zip file"
* Select the file `plugin.audio.soundcloud-X.Y.Z.zip`

### Optional dependency — Pillow

The fullscreen "Now Playing" overlays (Cinema/Waveform/Editorial/Vinyl)
look noticeably better with [Pillow](https://pypi.org/project/Pillow/)
installed, because Pillow lets the addon generate a real Gaussian-blurred
version of the cover art for the background. Without Pillow, the cover
is just shown dimmed.

To install: Kodi → *Add-ons → Install from repository → Kodi Add-on
repository → Look and feel → Pillow* (or directly search for
`script.module.pil`). The addon will pick it up automatically on next
playback.

Pillow is **optional**: the addon still works without it, you just lose
the blur effect.

## Launching SoundCloud without the music browser flash

When you click SoundCloud from Kodi's *Music → Add-ons* page, Kodi
briefly shows the music browser before the full-screen UI takes over.
There are three ways to deal with this, from least to most invasive:

### Option 1 — Background service (v5.9.6017+, recommended)

The addon includes an optional background service that runs from Kodi
login until Kodi shutdown. Its only job is to pre-create the loading
splash window so it appears in ~50 ms when you click the addon,
masking the music browser entirely.

1. *Settings → Account → Background service (faster open)* → toggle ON
2. Restart Kodi (the service only starts at login)
3. Click SoundCloud — the splash now appears instantly, hiding the
   music browser

Cost: a few MB of RAM consumed continuously by the running service.
Default: off (opt-in).

### Option 2 — Add a Kodi favourite

This bypasses the music browser entirely and is the fastest possible
launch path.

1. Right-click (or context-menu) on SoundCloud in *Music → Add-ons*
2. Choose **Add to favourites** — call it "SoundCloud" or whatever you like
3. Edit your favourites file at
   `~/.kodi/userdata/favourites.xml` and change the line for
   SoundCloud from
   `ActivateWindow(...)` to
   `RunScript(plugin.audio.soundcloud)`
4. Use the favourite from Kodi's home screen (or pin it to your skin's
   home menu)

### Option 3 — Add a home-menu shortcut in your skin

In Arctic Zephyr Reloaded:
1. *Settings → Interface → Skin → Configure skin → Customise Home Menu*
2. Pick (or add) a menu item
3. For "Activate window" or "Action", use:
   `RunScript(plugin.audio.soundcloud)`

In Estuary / Estuary MOD:
1. *Customise Home Menu → choose item → Action*
2. Set: `RunScript(plugin.audio.soundcloud)`

With either approach the UI opens immediately on top of the Kodi home
screen — no music-browser flash, no detour.

## Authentication (optional)

The add-on can access your personal SoundCloud data (likes, playlists,
following, reposts) by authenticating with an OAuth token that you paste
into the settings.

There is no "Sign in" button: SoundCloud's public API registration has
been closed since 2021, so we reuse the token the SoundCloud website
itself uses. The token is stored locally in Kodi's addon settings and
sent only to `api-v2.soundcloud.com`.

### How to get your OAuth token

Open the helper page:
**[https://theworms.github.io/kodi-addon-soundcloud/](https://theworms.github.io/kodi-addon-soundcloud/)**

The page walks you through a one-click console snippet that grabs your
token from soundcloud.com and shows it in a popup with a Copy button.
The snippet runs entirely in your browser — the token never leaves
your machine.

The helper page also includes a fallback manual procedure (F12
DevTools, `Authorization` header) for the rare cases where the
snippet doesn't work.

Tokens expire after a few months or when you sign out from
soundcloud.com — just repeat the procedure on the helper page when
needed. The addon picks up token changes immediately, no Kodi restart
required.

### Free, Go, Go+ — what works?

Since v5.9.6005 the addon detects your SoundCloud subscription tier
from `/me` and stores it. Today all three tiers work for streaming
your own tracks and tracks marked as fully playable. Go+ exclusive
tracks return a 30-second preview snippet on Free accounts (this is a
SoundCloud server-side limitation, not an addon one).

You can see your detected tier under *Settings → Account → Test
authentication*.

### Privacy

* The token is stored **only** on your device, in Kodi's addon profile folder.
* It is sent **only** to `api-v2.soundcloud.com` as the `Authorization` request header.
* It is **redacted** from debug logs (the header value is replaced by `<redacted>` in `kodi.log`).

## Fullscreen "Now Playing" overlays

When audio playback starts, the addon can open a custom fullscreen
overlay on top of the home UI showing the cover, title, artist and
progress. Pick one of four visual styles in
*Settings → Playback → Fullscreen on playback*, or keep it disabled
to rely on the mini-player only.

| Style       | Look                                                                                                                |
| ----------- | ------------------------------------------------------------------------------------------------------------------- |
| **Off**     | No overlay. The mini-player at the bottom of the home UI is the only feedback.                                       |
| **Cinema**  | Apple-Music style. Centred cover with slow Ken Burns zoom, blurred background, large title and artist underneath.    |
| **Waveform**| 90 orange bars at the bottom animated continuously to simulate an audio visualizer. Real progress bar above the bars.|
| **Editorial** | Magazine layout. Cover on the left third, large title and artist on the right, with a pull quote pulled from the SoundCloud track description (URLs and hashtag chains stripped, truncated at a sentence boundary). |
| **Vinyl**   | A detailed black vinyl record on the left with the cover embedded in the central label, both rotating together at ~33⅓ RPM. Title and artist on the right.|

### Keyboard shortcuts in Now Playing (v5.9.6008+)

While a fullscreen overlay is visible, the following keys work:

| Key            | Action                                                                |
| -------------- | --------------------------------------------------------------------- |
| **OK / Enter** | Toggle pause / play                                                   |
| **Left**       | Seek backward 10 seconds                                              |
| **Right**      | Seek forward 10 seconds                                               |
| **Up**         | Next track                                                            |
| **Down**       | Restart current track — or jump to previous if you're within the first 3 seconds |
| **Back**       | Dismiss the overlay (music keeps playing, overlay re-opens on next track) |

### Honest limitations

* **Waveform is not actually audio-reactive.** Kodi's Python API
  doesn't expose audio samples to addons, so the bars are animated by a
  pseudo-random sinusoidal pattern. It LOOKS audio-reactive but is
  decoupled from the actual music. The progress bar above the
  visualizer however reflects real playback position.
* **Vinyl rotation** uses Kodi's native continuous-rotate animation.
  It's smooth on modern boxes but may stutter on lower-end devices
  (Raspberry Pi 3 etc.). If so, switch to a different style.
* **Editorial pull quote** depends on the SoundCloud track having a
  description. Many user uploads don't, in which case the quote area
  is left empty (intentional editorial restraint, not a bug).
* **Custom fonts**: Kodi's Python WindowXML system does not allow addons
  to register their own TTF fonts. All overlays therefore use the
  standard Kodi font names. The editorial style achieves its feel
  through layout and hierarchy, not through a bundled serif font.

## Integration with Kodi

Since v5.7 there is no classic plugin-style menu — the addon opens
directly into its full-screen "app-like" interface.

For different ways to launch the addon (Music browser, skin home
shortcut, Kodi favourite, background service) see the
[Launching SoundCloud without the music browser flash](#launching-soundcloud-without-the-music-browser-flash)
section above. This section covers integration on Kodi's home screen
through skin widgets.

### Widgets (skin home menu)

For users who want SoundCloud content directly on their Kodi home menu
(e.g. a "My Likes" carousel on Arctic Zephyr Reloaded), the addon
exposes flat directory routes that any skin's widget pane can target:

| Route | Returns |
|---|---|
| `plugin://plugin.audio.soundcloud/widget/likes/` | Tracks you've liked (requires OAuth token) |
| `plugin://plugin.audio.soundcloud/widget/playlists/` | Your own playlists (requires OAuth token) |
| `plugin://plugin.audio.soundcloud/widget/following/` | Artists you follow (requires OAuth token) |
| `plugin://plugin.audio.soundcloud/widget/trending/` | Worldwide trending tracks |
| `plugin://plugin.audio.soundcloud/widget/discover/` | SoundCloud's "Discover" mix |
| `plugin://plugin.audio.soundcloud/widgets/` | Browseable list of all the above |

#### Setting up widgets in Arctic Zephyr Reloaded

Arctic Zephyr Reloaded only lets widgets point at an addon's root URL —
it doesn't let you pick a specific sub-directory like
`/widget/likes/`. To work around this, the addon has a **Widget mode**
setting that changes what the root URL returns:

1. In Kodi, open SoundCloud's **Settings → Display**, scroll to the
   bottom and find **Skin home widget → Widget mode**.
2. Pick the content you want the widget to show (Likes / My playlists /
   Following / Trending / Discover).
3. Now go to *Settings → Interface → Skin → Configure skin →
   Customise Home Menu* in Arctic Zephyr Reloaded.
4. Pick a menu item and click **+ Use as widget** on SoundCloud.
5. The widget now displays the content you chose in step 2.

Important: while Widget mode is set to anything but "Off", opening
SoundCloud from the Add-ons screen will *also* return the chosen
content instead of the full-screen UI. To get the full UI back, set
Widget mode to "Off (show full UI)" in the addon settings.

If you want **multiple different widgets** (e.g. one for Likes and one
for Trending), Arctic Zephyr Reloaded alone can't do it because all
SoundCloud widgets share the same root URL. You need a more advanced
skin that supports custom widget paths (e.g. via Skin Helper Service)
to point each widget at a different `/widget/...` route.

#### Setting up widgets in Estuary / Estuary MOD

Estuary lets you navigate sub-directories when picking a widget. Go to
*Customise Home Menu → choose item → Add Widget* and navigate to
*Add-ons → Music add-ons → SoundCloud → Widgets* — pick the widget you
want directly without needing the Widget mode workaround.

## Attributions

This v5+ fork is maintained by **[TheWorms](https://github.com/TheWorms)**,
who contributed the full-screen interface, OAuth token integration, the
widget routes, the four fullscreen "now playing" overlay styles, the
French translation, the background service architecture, and many UX
improvements.

It is built on top of the
[Kodi SoundCloud add-on by jaylinski](https://github.com/jaylinski/kodi-addon-soundcloud),
which itself was strongly inspired by the
[original add-on](https://github.com/SLiX69/plugin.audio.soundcloud)
developed by [bromix](https://kodi.tv/addon-author/bromix) and
[SLiX](https://github.com/SLiX69).

All upstream and original contributions remain licensed under the MIT
License — see `LICENSE.txt` and the upstream repositories for details.

## Copyright and license

This add-on is licensed under the MIT License - see `LICENSE.txt` for details.
