#!/usr/bin/python

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
import sys, gi
import logging
import argparse

gi.require_version('Unity', '7.0')
from gi.repository import Unity, Gio, GLib, GObject, Dbusmenu
import transmissionrpc

# Dirty hack.
# GLib functions `spawn_async` and `child_watch_add` in `python-gobject` package
# from Ubuntu 11.04 and 11.10 are completely different: they require arguments
# in different order and returns different results.
# Use adapter functions to work around.

(major, minor) = (GLib.MAJOR_VERSION, GLib.MINOR_VERSION)
if (major, minor) < (2, 30):
	def spawn_async(argv, flags):
		_, pid = GLib.spawn_async(
			None, # Inherit current directory,
			argv, # Command with arguments.
			None, # Inherit environment.
			flags,
			None, # Child setup callback.
			None  # User data.
		)
		return pid

	def child_watch_add(priority, pid, on_closed, data):
		return GLib.child_watch_add(priority, pid, on_closed, data)

elif (major, minor) >= (2, 36):
	def spawn_async(argv, flags):
		pid, _, _, _ = GLib.spawn_async(argv, flags=flags)
		return pid

	def child_watch_add(priority, pid, on_closed, data):
		return GLib.child_watch_add(priority, pid, on_closed, data)

else:
	def spawn_async(argv, flags):
		pid, _, _, _ = GLib.spawn_async(argv=argv, flags=flags)
		return pid

	def child_watch_add(priority, pid, on_closed, data):
		return GLib.child_watch_add(priority=priority, pid=pid, function=on_closed, data=data)

# Another dirty hack.
# transmissionrpc in Ubuntu 12.04 fails trying to return
# information about torrent because it tries to find corresponding
# field in torrent.fields with simple string key while information
# in torrent.fields is stored with unicode names.
# This method tries to get value using property (for compatibility
# with older versions) and in case of error tries to get value by
# unicode name.
def get_torrent_field(torrent, field_name):
	try:
		return getattr(torrent, field_name)
	except KeyError:
		return torrent.fields[unicode(field_name)]

class UnityLauncherEntry:
	def __init__(self, name):
		self.name = name

		logging.debug("Get launcher entry %s", self.name)
		self.entry = Unity.LauncherEntry.get_for_desktop_id(self.name)

	def set_progress(self, progress):
		if progress is not None:
			self.entry.set_property('progress', progress)
			self.entry.set_property('progress_visible', True)
		else:
			self.entry.set_property('progress_visible', False)

	def set_count(self, count):
		if count is not None:
			self.entry.set_property('count', count)
			self.entry.set_property('count_visible', True)
		else:
			self.entry.set_property('count_visible', False)

	def set_quicklist_menu(self, menu):
		self.entry.set_property('quicklist', menu)

class TransmissionUnityController:
	def __init__(self, transmission, launcher_entry, options):
		logging.debug("Create controller.")

		self.transmission = transmission
		self.launcher_entry = launcher_entry
		self.options = options

		quicklist_menu = self._create_quicklist_menu()

		# Show quicklist items, add handlers.
		self.turtle_mode_item.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
		self.turtle_mode_item.connect('item-activated', self._on_toggle_turtle_mode, None)

		self.launcher_entry.set_quicklist_menu(quicklist_menu)

	def update(self):
		# Get list of torrents.
		logging.debug("Get torrents list.")
		torrents = self.transmission.list()

		# Filter only downloading ones.
		downloading_torrent_ids = [t.id for t in torrents.values() if get_torrent_field(t, 'status') == 'downloading']

		logging.debug("%d of %d are downloading", len(downloading_torrent_ids), len(torrents))

		# Get detailed information about downloading torrents.
		# 'id' fields is required by transmissionrpc to sort results and 'name' field
		# is used by Torrent.__repr__.
		infos = self.transmission.get_torrents(downloading_torrent_ids, ['id', 'name', 'sizeWhenDone', 'leftUntilDone'])

		# Calculate total torrents size and downloaded amount.
		total_size = left_size = 0
		for info in infos:
			total_size += info.sizeWhenDone
			left_size  += info.leftUntilDone

		# Calculate progress.
		torrents_count = len(downloading_torrent_ids)
		if torrents_count > 0:
			progress = float(total_size - left_size) / total_size
			logging.info("Downloading torrents count: %d, progress: %f", torrents_count, progress)

			# Set launcher entry properties.
			self.launcher_entry.set_count(torrents_count)
			self.launcher_entry.set_progress(progress)

		else:
			self.launcher_entry.set_count(None)
			self.launcher_entry.set_progress(None)

		# Get session info.
		session = self.transmission.get_session()

		turtle_mode = session.alt_speed_enabled
		logging.debug("Turtle mode: %s", turtle_mode)

		menu_item_state = Dbusmenu.MENUITEM_TOGGLE_STATE_CHECKED if turtle_mode else Dbusmenu.MENUITEM_TOGGLE_STATE_UNCHECKED
		self.turtle_mode_item.property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, menu_item_state)

	def _create_quicklist_menu(self):
		# Create menu.
		menu = Dbusmenu.Menuitem.new()
		turtle_mode_item = Dbusmenu.Menuitem.new()
		turtle_mode_item.property_set(Dbusmenu.MENUITEM_PROP_LABEL, "Turtle mode")
		turtle_mode_item.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
		turtle_mode_item.property_set(Dbusmenu.MENUITEM_PROP_TOGGLE_TYPE, Dbusmenu.MENUITEM_TOGGLE_CHECK)
		turtle_mode_item.property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, Dbusmenu.MENUITEM_TOGGLE_STATE_UNKNOWN)
		self.turtle_mode_item = turtle_mode_item
		menu.child_append(turtle_mode_item)

		return menu

	def _on_toggle_turtle_mode(self, menuitem, _, data):
		current_state = menuitem.property_get_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE)
		turtle_mode = current_state == Dbusmenu.MENUITEM_TOGGLE_STATE_CHECKED

		turtle_mode = not turtle_mode
		logging.info("Turtle mode: %s", turtle_mode)
		self.transmission.set_session(alt_speed_enabled=turtle_mode)

		new_state = Dbusmenu.MENUITEM_TOGGLE_STATE_CHECKED if turtle_mode else Dbusmenu.MENUITEM_TOGGLE_STATE_UNCHECKED
		menuitem.property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, new_state)

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
parser.add_argument('-t', '--startup-timeout',
	default=4,
	help="time (in seconds) between Transmission start and first connection attempt"
)
parser.add_argument('-u', '--update-interval',
	action='store', dest='update_interval', type=int,
	default=10,
	help="interval (in seconds) between status updates"
)
parser.add_argument('transmission_command',
	nargs='+',
	help="command and arguments to start Transmission"
)
args = parser.parse_args()

logging.basicConfig(level=logging.DEBUG)

loop = GLib.MainLoop()

def start_process(command):
	flags = (
		# Inherit PATH environment variable.
		GLib.SpawnFlags.SEARCH_PATH |

		# Don't reap process automatically so it is possible
		# to detect when it is closed.
		GLib.SpawnFlags.DO_NOT_REAP_CHILD
	)
	pid = spawn_async(command, flags)
	return pid

transmission_pid = start_process(args.transmission_command)
logging.info("Transmission started (pid: %d).", transmission_pid)

# Exit when Transmission is closed.
def transmission_closed(pid, status, data):
	logging.info("Transmission exited with status %d, exiting.", status)
	GLib.spawn_close_pid(pid)
	loop.quit()
child_watch_add(GLib.PRIORITY_DEFAULT, transmission_pid, transmission_closed, None)

def is_connection_error(error):
	http_error_class = transmissionrpc.httphandler.HTTPHandlerError
	return isinstance(error.original, http_error_class) and error.original.code == 111

def first_update():
	try:
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
				loop.quit()
			else:
				raise

		launcher_entry = UnityLauncherEntry(args.launcher_entry_name)

		# Create controller.
		controller = TransmissionUnityController(transmission, launcher_entry, args)

		# Try to update status for the first time.
		controller.update()

		# If all is ok, start main timer.
		GLib.timeout_add_seconds(args.update_interval, periodic_update, controller)

	except transmissionrpc.transmission.TransmissionError as error:
		loop.quit() # Terminate application loop.
		if is_connection_error(error):
			sys.stderr.write("""Can't connect to Transmission. Quit.""")
		else:
			raise

	finally:
		return False # Stop timer.

def periodic_update(controller):
	try:
		controller.update()
	except transmissionrpc.transmission.TransmissionError as error:
		if is_connection_error(error):
			logging.error("Connection to Transmission is lost.")
			sys.stderr.write("""Connection to Transmission is lost. Quit.""")
			loop.quit() # Terminate application loop.
			return False # Stop timer.
		else:
			logging.exception("Failed to connect")
			raise

	return True # Leave timer active.

GLib.timeout_add_seconds(args.startup_timeout, first_update)

loop.run()
