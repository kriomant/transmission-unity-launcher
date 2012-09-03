What is this?
=============

This is small script for integrating Transmission with Unity Launcher.
Transmission icon in launcher will show number of downloading torrents
and total progress.
Quicklist menu item allows to view and toggle "Turtle mode".

Prerequisites
=============

`python-gobject` and `python-transmissionrpc` packages. Both are available
in Ubuntu repositories.

Installation
============

Start **Transmission**, open preferences and enable **Web client**. Default configuration
with port 9091, no authentication and connection allowed from 127.0.0.1 only is fine.

However, if you want to use authorization, you will have to provide additional
parameters to script. Use `--help` for details.

Download `transmission-unity-launcher.py` script anywhere and make it
executable.

Copy `transmission-gtk.desktop` file from `/usr/share/applications` to
`~/.local/share/applications` and edit it:

 * Prepend `/path/to/transmission-unity-launcher.py` to command,
   so if it was `transmission-gtk %U` now it should be
   `/path/to/transmission-unity-launcher.py transmission-gtk %U`;
 * Make copied .desktop file executable.


That's all. Now start Transmission using new .desktop file or from Unity Dash.

Troubleshooting
===============

If script doesn't work, start it manually from command line, it will write
log messages to console.

Feel free to create issue if there are any problems.

Plans
=====

Planned features:

 * Extending launcher item menu with items to control speed, to start and stop torrents.

