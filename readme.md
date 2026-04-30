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
