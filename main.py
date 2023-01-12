#!/usr/bin/python3

import logging
import gi
import time

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('WebKit2', '4.0')

from Xlib import X, XK, protocol
from Xlib.display import Display
from gi.repository import Gdk, GLib, Gtk, WebKit2

class MainWindow(Gtk.Window):
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
        self._homeUrl = GLib.filename_to_uri(
            "/home/eberhard/Projects/TrashBin/keyman-osk-poc-x11/test.html", None)
        self._onStartup()
        self._onActivate()

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
        # self._webView.set_focus_on_click(False)
        # self.set_focus_on_click(False)
        # self.set_can_focus(False)
        # self.set_focus_on_map(False)

    def _onConnect(self, webview, arg) -> None:
        self.set_title(webview.get_title())

    def _keyman_policy(self, webview, decision, decision_type) -> bool:
        # allow loading local file
        decision.use()
        return True

    def _button_clicked(self, manager, jsResult) -> None:
        logging.info('Button Clicked: ' + jsResult.get_js_value().to_string())
        self._send_key(jsResult.get_js_value().to_string()[0])

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


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(message)s')
    w = MainWindow()
    w.run()
    w.destroy()
