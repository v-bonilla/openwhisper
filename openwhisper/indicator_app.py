"""GTK4 + gtk4-layer-shell floating recording indicator.

Invoked by ``openwhisper.indicator`` as a separate process running under the
**system** Python interpreter (typically ``/usr/bin/python3``) so it can import
``gi`` and the layer-shell typelib from the Debian-managed paths. The uv venv
is isolated from system site-packages, so the venv's Python cannot see ``gi``.

Lifecycle anchors:
  - explicit SIGTERM from the CLI (handled via ``GLib.unix_signal_add``)
  - ``GLib.FileMonitor`` on the recording state file: quit on DELETED/MOVED

Inputs (env vars set by the parent):
  - OPENWHISPER_STATE_PATH: absolute path to the state JSON file
  - OPENWHISPER_INDICATOR_TEXT: text rendered in the badge

A missing ``gi`` or layer-shell typelib produces a one-line stderr message
and exit 0 — recording is unaffected.
"""
from __future__ import annotations

import os
import signal
import sys


CSS = b"""
.openwhisper-indicator {
    background: rgba(20, 20, 20, 0.82);
    color: #ffffff;
    border-radius: 14px;
    padding: 10px 22px;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 0.5px;
}
.openwhisper-indicator .dot {
    color: #ff3b30;
    animation: ow-pulse 1.0s ease-in-out infinite;
}
@keyframes ow-pulse {
    0%   { opacity: 1.0; }
    50%  { opacity: 0.25; }
    100% { opacity: 1.0; }
}
"""


def _split_dot(raw: str) -> tuple[str, str]:
    """Return (dot, rest). The leading '●' (if any) becomes the pulsing
    dot label; the remainder is plain text. Falls back to ("", text)."""
    text = raw.strip()
    if text.startswith("●"):
        return "●", text[1:].lstrip()
    return "", text


def main() -> int:
    state_path = os.environ.get("OPENWHISPER_STATE_PATH")
    if not state_path:
        print("openwhisper indicator: OPENWHISPER_STATE_PATH unset.",
              file=sys.stderr)
        return 0

    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gdk, Gio, GLib, Gtk, Gtk4LayerShell  # noqa: F401
    except (ImportError, ValueError) as exc:
        print(f"openwhisper indicator: GTK4/layer-shell unavailable: {exc}",
              file=sys.stderr)
        return 0

    text = os.environ.get("OPENWHISPER_INDICATOR_TEXT", "● REC  openwhisper")
    dot, rest = _split_dot(text)

    app = Gtk.Application(
        application_id="dev.openwhisper.indicator",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    def on_activate(application: "Gtk.Application") -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        win = Gtk.ApplicationWindow(application=application)
        win.set_decorated(False)

        Gtk4LayerShell.init_for_window(win)
        Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.TOP, True)
        Gtk4LayerShell.set_margin(win, Gtk4LayerShell.Edge.TOP, 24)
        Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.NONE)
        Gtk4LayerShell.set_namespace(win, "openwhisper-indicator")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.add_css_class("openwhisper-indicator")

        if dot:
            dot_label = Gtk.Label(label=dot)
            dot_label.add_css_class("dot")
            box.append(dot_label)
        if rest:
            text_label = Gtk.Label(label=rest)
            box.append(text_label)

        win.set_child(box)
        win.present()

    app.connect("activate", on_activate)

    def on_term(_user_data=None) -> bool:
        app.quit()
        return GLib.SOURCE_REMOVE

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, on_term, None)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, on_term, None)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGHUP, on_term, None)

    state_gfile = Gio.File.new_for_path(state_path)
    monitor = state_gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)

    def on_state_change(_mon, _file, _other_file, event_type) -> None:
        if event_type in (
            Gio.FileMonitorEvent.DELETED,
            Gio.FileMonitorEvent.MOVED,
            Gio.FileMonitorEvent.MOVED_OUT,
        ):
            app.quit()

    monitor.connect("changed", on_state_change)

    return app.run([])


if __name__ == "__main__":
    sys.exit(main())
