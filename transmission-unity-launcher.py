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
import sys
import logging
import argparse

from gi.repository import Unity, Gio, GObject, Dbusmenu
import transmissionrpc

parser = argparse.ArgumentParser(description="Integrate Transmission into Unity Launcher.")
parser.add_argument('-l', '--launcher-entry-name',
	action='store', dest='launcher_entry_name',
	default='transmission-gtk.desktop',
	help="name of .desktop file (including extension) used to start Transmission"
)
parser.add_argument('-H', '--transmission-host',
	action='store', dest='transmission_host',
	default='localhost',
	help="address for connecting to Transmission RPC"
)
parser.add_argument('-p', '--transmission-port',
	action='store', dest='transmission_port', type=int,
	default=9091,
	help="port for connecting to Transmission RPC"
)
parser.add_argument('-U', '--transmission-user',
	action='store', dest='transmission_user',
	default=None,
	help="user name for connecting to Transmission RPC"
)
parser.add_argument('-P', '--transmission-password',
	action='store', dest='transmission_password',
	default=None,
	help="password for connecting to Transmission RPC"
)
parser.add_argument('-u', '--update-interval',
	action='store', dest='update_interval', type=int,
	default=20,
	help="interval (in seconds) between status updates"
)
args = parser.parse_args()

logging.basicConfig(level=logging.DEBUG)

def is_connection_error(error):
	http_error_class = transmissionrpc.httphandler.HTTPHandlerError
	return isinstance(error.original, http_error_class) and error.original.code == 111

# Connect to Transmission.
logging.info("Try to connect to Transmision at %s:%d as %s.",
	args.transmission_host, args.transmission_port, args.transmission_user
)
try:
	transmission = transmissionrpc.Client(
		address=args.transmission_host,
		port=args.transmission_port,
		user=args.transmission_user,
		password=args.transmission_password,
	)
except transmissionrpc.transmission.TransmissionError as error:
	logging.exception("Failed to connect")
	if is_connection_error(error):
		sys.stderr.write("""Unable to connect to Transmission at %s:%d.
Ensure it is running and web interface is enabled at this address.
""" % (args.transmission_host, args.transmission_port))
		sys.exit(1)
	else:
		raise

logging.debug("Get launcher entry %s", args.launcher_entry_name)
launcher = Unity.LauncherEntry.get_for_desktop_id(args.launcher_entry_name)

def update_status(quit):
	try:
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
	except transmissionrpc.transmission.TransmissionError as error:
		logging.exception("Failed to connect")
		if is_connection_error(error):
			sys.stderr.write("""Connection to Transmission is lost.
Quit.
""")
			quit() # Terminate application loop.
			return False # Stop timer.
		else:
			raise

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

	return True # Leave timer active.

loop = GObject.MainLoop()

update_status(loop.quit)
GObject.timeout_add_seconds(args.update_interval, update_status, loop.quit)

loop.run()

