#!/usr/bin/python3

import json
import logging
import dbus
import dbus.bus
import dbus.mainloop.glib
import dbus.service
import gi
import os

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('WebKit2', '4.0')

from Xlib import X, XK, protocol
from Xlib.display import Display
from gi.repository import GLib, Gtk, WebKit2

class MainWindow(Gtk.Window):
    KM_DBUS_NAME = "com.Keyman"
    KM_DBUS_PATH  = "/com/Keyman/IBus"
    KM_DBUS_IFACE = "com.Keyman"

    def __init__(self) -> None:
        args = {
            "skip_taskbar_hint": True,
            "skip_pager_hint": True,
            "urgency_hint": False,
            "decorated": True,
            "accept_focus": False,
            "opacity": 1.0,
            "app_paintable": True,
        }

        super().__init__(title="OSK POC", **args)

        self.set_keep_above(True)
        self.display = Display()
        self.screen = self.display.screen()
        self.root = self.screen.root
        currentDir = os.path.dirname(os.path.realpath(__file__))
        self._homeUrl = GLib.filename_to_uri(os.path.join(currentDir, 'test.html'), None)
        self._onStartup()
        self._onActivate()

        # connect to session bus
        # Use D-bus main loop by default
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        try:
            self._bus = dbus.SessionBus()
        except dbus.exceptions.DBusException:
            raise RuntimeError("D-Bus session bus unavailable")
        self._bus.add_signal_receiver(self._on_name_owner_changed,
                                      "NameOwnerChanged",
                                      dbus.BUS_DAEMON_IFACE,
                                      arg0=self.KM_DBUS_NAME)
        # Initial state
        proxy = self._bus.get_object(
            dbus.BUS_DAEMON_NAME, dbus.BUS_DAEMON_PATH)
        result = proxy.NameHasOwner(
            self.KM_DBUS_NAME, dbus_interface=dbus.BUS_DAEMON_IFACE)
        self._set_connection(bool(result))

    def run(self) -> None:
        self.resize(576, 324)
        self.connect("destroy", self._onDestroy)
        self.show_all()
        Gtk.main()

    def _onDestroy(self, _) -> None:
        Gtk.main_quit()

    # Callback function for 'activate' signal presents windows when active
    def _onActivate(self) -> None:
        self.present()
        self._webView.load_uri(self._homeUrl)

    # Callback function for 'startup' signal builds the UI
    def _onStartup(self) -> None:
        self._buildUI()

        # Connect the UI signals
        self._connectSignals()

    # Build the application's UI
    def _buildUI(self) -> None:
        # Create a webview to show the web app
        self._webView = WebKit2.WebView()
        settings = self._webView.get_settings()
        settings.enableJavascript = True
        settings.enable_javascript_markup = True
        settings.set_javascript_can_access_clipboard(True)
        settings.set_javascript_can_open_windows_automatically(False)
        settings.allow_file_access_from_file_urls = True
        settings.allow_universal_access_from_file_urls = True

        # Put the webview into the window
        self.add(self._webView)

        # Show the window and all child widgets
        self.show_all()

    def _connectSignals(self) -> None:
        # Change the Window title when a new page is loaded
        self._webView.connect('notify::title', self._onConnect)

        self._webView.connect('decide-policy', self._keyman_policy)
        self._userContentManager = self._webView.get_user_content_manager()
        self._userContentManager.connect(
            'script-message-received::button', self._button_clicked)
        self._userContentManager.register_script_message_handler('button')

        gdkWindow = self.get_window()
        # This works on X11
        gdkWindow.set_accept_focus(False)

    def _onConnect(self, webview, arg) -> None:
        self.set_title(webview.get_title())

    def _keyman_policy(self, webview, decision, decision_type) -> bool:
        # allow loading local file
        decision.use()
        return True

    def _button_clicked(self, manager, jsResult) -> None:
        val = jsResult.get_js_value()
        logging.info('Button Clicked: ' + jsResult.get_js_value().to_string())
        if val.is_string():
            self._send_key(jsResult.get_js_value().to_string()[0])
        else:
            object = json.loads(val.to_json(0))
            assert('text' in object)
            self._send_text(object['text'])

    def _send_key(self, emulated_key):
        shift_mask = 0  # or Xlib.X.ShiftMask
        window = self.display.get_input_focus()._data["focus"]
        keysym = XK.string_to_keysym(emulated_key)
        keycode = self.display.keysym_to_keycode(keysym)
        event = protocol.event.KeyPress(
            time=X.CurrentTime,
            root=self.root,
            window=window,
            same_screen=0, child=X.NONE,
            root_x=0, root_y=0, event_x=0, event_y=0,
            state=shift_mask,
            detail=keycode
        )
        window.send_event(event, propagate=True)
        event = protocol.event.KeyRelease(
            time=X.CurrentTime,
            root=self.root,
            window=window,
            same_screen=0, child=X.NONE,
            root_x=0, root_y=0, event_x=0, event_y=0,
            state=shift_mask,
            detail=keycode
        )
        window.send_event(event, propagate=True)
        self.display.sync()

    def _send_text(self, text):
        if self.proxy:
            print(text)
            self.proxy.SendText(text, dbus_interface=self.KM_DBUS_IFACE)
        else:
            print('Keyman not active')

    def _on_name_owner_changed(self, name, old, new):
        '''
        The daemon has de/registered the name.
        Called when ibus-keyman un/loads a keyboard
        '''
        active = old == ""
        self._set_connection(active)

    def _set_connection(self, active):
        '''
        Update interface object, state and notify listeners
        '''
        if active:
            self.proxy = self._bus.get_object(self.KM_DBUS_NAME, self.KM_DBUS_PATH)
        else:
            self.proxy = None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
    w = MainWindow()
    w.run()
    w.destroy()
