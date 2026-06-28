# SoundCloud Add-on for [Kodi](https://github.com/xbmc/xbmc) — v5+ fork

<img align="right" src="https://github.com/xbmc/xbmc/raw/master/addons/webinterface.default/icon-128.png" alt="Kodi logo">

[![GitHub tag (latest SemVer)](https://img.shields.io/github/tag/TheWorms/kodi-addon-soundcloud.svg)](https://github.com/TheWorms/kodi-addon-soundcloud/releases)
[![Link to Kodi forum](https://img.shields.io/badge/Kodi-Forum-informational.svg)](https://forum.kodi.tv/showthread.php?tid=206635)
[![Link to Kodi wiki](https://img.shields.io/badge/Kodi-Wiki-informational.svg)](https://kodi.wiki/view/Add-on:SoundCloud)
[![Link to Kodi releases](https://img.shields.io/badge/Kodi-v19%20%22Matrix%22-green.svg)](https://kodi.wiki/view/Releases)

> 🍴 **This is a community fork** of
> [jaylinski/kodi-addon-soundcloud](https://github.com/jaylinski/kodi-addon-soundcloud)
> maintained at
> [github.com/TheWorms/kodi-addon-soundcloud](https://github.com/TheWorms/kodi-addon-soundcloud).
> It adds a full-screen "app-like" interface, OAuth token authentication,
> a French translation, skin home widgets and fullscreen now-playing
> overlays on top of the upstream addon. Bug reports and pull requests
> for v5+ features should go to **this** fork; for the classic plugin
> menu (v4 and earlier), please refer to the upstream project.

This [Kodi](https://github.com/xbmc/xbmc) Add-on provides a full-screen, modern
interface for SoundCloud, with a sidebar, horizontal carousel rows on the home
screen, autoplay, an integrated mini-player and four optional fullscreen
"now playing" overlay styles (Cinema, Waveform, Editorial, Vinyl).

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
* **Fullscreen "Now Playing" overlays** (v5.8+): pick from 4 visual
  styles — *Cinema* (Apple-Music-like Ken Burns), *Waveform* (animated
  audio visualizer), *Editorial* (magazine layout with pull quote from
  the track description), *Vinyl* (spinning record with cover in the
  central label). Disable entirely if you prefer the mini-player only.

Since v5.7 the full-screen UI is the only interface — the classic
plugin-style menu was removed. Skin home widgets continue to work via
the dedicated `/widget/*` routes (see "Widgets" below).

## Features

* Search
* Discover new music
* Play tracks, albums and playlists
* Optional sign-in via OAuth token to access your likes, playlists, following and reposts
* New full-screen interface with sidebar, carousel rows and mini-player (v5)
* Optional fullscreen "Now Playing" overlays in 4 styles (v5.8+)

## Installation

### Kodi Repository

Follow the instructions on [https://kodi.wiki/view/Add-on:SoundCloud](https://kodi.wiki/view/Add-on:SoundCloud).

### Manual

* [Download the latest release from this fork](https://github.com/TheWorms/kodi-addon-soundcloud/releases) (`plugin.audio.soundcloud.zip`)
* Copy the zip file to your Kodi system
* Open Kodi, go to Add-ons and select "Install from zip file"
* Select the file `plugin.audio.soundcloud.zip`

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
This flash is a Kodi behaviour we can only minimise, not eliminate, from
inside the addon.

To **launch the UI instantly with no flash at all**, bypass the music
browser entirely by calling the script directly. Two easy ways:

### Add a Kodi favourite

1. Right-click (or context-menu) on SoundCloud in *Music → Add-ons*
2. Choose **Add to favourites** — call it "SoundCloud" or whatever
3. Edit your favourites file at
   `~/.kodi/userdata/favourites.xml` and change the line for
   SoundCloud from
   `ActivateWindow(...)` to
   `RunScript(plugin.audio.soundcloud)`
4. Use the favourite from Kodi's home screen (or pin it to your skin's
   home menu)

### Add a home-menu shortcut in your skin

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

Press **Back** during playback to dismiss the overlay (the music keeps
playing). The overlay re-opens automatically on the next track.

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
shortcut, Kodi favourite) see the
["Launching SoundCloud without the music browser flash"](#launching-soundcloud-without-the-music-browser-flash)
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

* Implement remaining
  [enhancement ideas from upstream](https://github.com/jaylinski/kodi-addon-soundcloud/issues?q=is%3Aopen+is%3Aissue+label%3Aenhancement)
  that make sense for the v5+ full-screen experience
* Continue refining the fullscreen now-playing overlays based on user feedback
* Track any upstream improvements worth merging back

## Attributions

This v5+ fork is maintained by **[TheWorms](https://github.com/TheWorms)**,
who contributed the full-screen interface, OAuth token integration, the
widget routes, the four fullscreen "now playing" overlay styles, the
French translation and many UX improvements.

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
