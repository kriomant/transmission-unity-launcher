What is this?
=============

This is small script for integrating Transmission with Unity Launcher.
Transmission icon in launcher will show number of downloading torrents
and total progress.

Prerequisites
=============

`python-gobject` and `python-transmissionrpc` packages. Both are available
in Ubuntu repositories.

Installation
============

Download `transmission-unity-launcher.py` script anywhere and make it
executable.

Copy `transmission-gtk.desktop` file from `/usr/share/applications` to
`~/.local/share/applications` and edit it:

 * Prepend `/path/to/transmission-unity-launcher.py` to command,
   so if it was `transmission-gtk %U` now it should be
   `/path/to/transmission-unity-launcher.py transmission-gtk %U`;
 * Make copied .desktop file executable.

That's all. Now start Transmission using new .desktop file or from Unity Dash.

Plans
=====

Planned features:

 * Extending launcher item menu with items to control speed, to start and stop torrents.

