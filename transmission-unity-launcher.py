"""Unity launcher plugin for Transmission.

Requires:
	python-gobject
	python-transmissionrpc

References:
	Launcher API: https://wiki.ubuntu.com/Unity/LauncherAPI
	Transmission RPC protocol: https://trac.transmissionbt.com/browser/trunk/extras/rpc-spec.txt
	transmissionrpc documentation: http://packages.python.org/transmissionrpc/
	https://blueprints.launchpad.net/ubuntu/+spec/desktop-o-default-apps-unity-integration
"""
import logging
from gi.repository import Unity, Gio, GObject, Dbusmenu
import transmissionrpc

logging.basicConfig(level=logging.DEBUG)

TRANSMISSION_RPC_HOST = 'localhost'
TRANSMISSION_RPC_PORT = 9091
TRANSMISSION_RPC_USER = None
TRANSMISSION_RPC_PASSWORD = None

LAUNCHER_ENTRY_NAME = 'transmission-gtk.desktop'

UPDATE_INTERVAL = 20 # seconds

# Connect to Transmission.
logging.info("Try to connect to Transmision at %s:%d as %s.",
	TRANSMISSION_RPC_HOST, TRANSMISSION_RPC_PORT, TRANSMISSION_RPC_USER
)
transmission = transmissionrpc.Client(
	address=TRANSMISSION_RPC_HOST,
	port=TRANSMISSION_RPC_PORT,
	user=TRANSMISSION_RPC_USER,
	password=TRANSMISSION_RPC_PASSWORD,
)

logging.debug("Get launcher entry %s", LAUNCHER_ENTRY_NAME)
launcher = Unity.LauncherEntry.get_for_desktop_id(LAUNCHER_ENTRY_NAME)

def update_status():
	# Get list of torrents.
	logging.debug("Get torrents list.")
	torrents = transmission.list()

	# Filter only downloading ones.
	downloading_torrent_ids = [t.id for t in torrents.values() if t.status == 'downloading']

	logging.debug("%d of %d are downloading", len(downloading_torrent_ids), len(torrents))

	# Get detailed information about downloading torrents.
	# 'id' fields is required by transmissionrpc to sort results and 'name' field
	# is used by Torrent.__repr__.
	infos = transmission.info(downloading_torrent_ids, ['id', 'name', 'sizeWhenDone', 'leftUntilDone'])

	# Calculate total torrents size and downloaded amount.
	total_size = left_size = 0
	for info in infos.itervalues():
		total_size += info.sizeWhenDone
		left_size  += info.leftUntilDone

	# Calculate progress.
	torrents_count = len(downloading_torrent_ids)
	progress = float(total_size - left_size) / total_size
	logging.info("Downloading torrents count: %d, progress: %f", torrents_count, progress)

	# Set launcher properties.
	launcher.set_property('count', torrents_count)
	launcher.set_property('count_visible', torrents_count > 0)

	launcher.set_property('progress', progress)
	launcher.set_property('progress_visible', torrents_count > 0)

loop = GObject.MainLoop()

update_status()
GObject.timeout_add_seconds(UPDATE_INTERVAL, update_status)

loop.run()
