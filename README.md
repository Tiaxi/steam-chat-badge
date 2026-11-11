# Steam Chat Badge

Never miss a Steam chat message on Linux again. When someone messages you,
the Steam icon on your taskbar lights up and shows how many messages are
waiting. The highlight goes away when you open Steam, and the number goes away
when you've read your messages.

<img src="docs/badge.png" alt="Steam taskbar icon highlighted with one unread message" width="100">

Steam does this on Windows, but not on Linux.

Made for KDE Plasma 6. Other desktops may work too.

> [!WARNING]
> This relies on how the Steam app works on the inside, which Valve can change
> at any time without notice. A Steam update could stop it from working. If
> that happens, the icon simply stops lighting up. Steam itself is unaffected.

## Install

You need Python 3.10 or newer and PyGObject (Fedora: `python3-gobject`,
Debian/Ubuntu: `python3-gi`, Arch: `python-gobject`).

```sh
git clone https://github.com/Tiaxi/steam-chat-badge.git
cd steam-chat-badge
./install.sh
```

Then quit Steam completely (Steam → Exit) and start it again.

If you close Steam to the tray, pin it to your taskbar so the icon is still
there to light up.

## Good to know

To read your messages, the installer turns on a Steam setting that lets
programs on your computer talk to the Steam app. It can't be reached from
other computers, but any program running on your computer could use it too.

Steam's own settings are respected. There's no highlight in Do Not Disturb
mode or when "Flash window when I receive a chat message" is set to "Never".
The number is still shown in both cases.

## Uninstall

```sh
./uninstall.sh
```

Then restart Steam to turn the setting back off.

## License

GPL-2.0-or-later

Not affiliated with or endorsed by Valve.
