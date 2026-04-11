"""PyWebView-based desktop launcher for FileFinder.

Starts the FastAPI server in a background thread, then opens a native
OS window pointing at it. This is what turns FileFinder into a real
Windows/macOS/Linux desktop app.
"""

import argparse
import logging
import socket
import sys
import threading
import time

logger = logging.getLogger(__name__)


def find_free_port():
    """Find an unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(host, port, timeout=15):
    """Block until the server is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


class NativeAPI:
    """JavaScript-callable API exposed to the frontend via PyWebView.

    This lets the web UI call native OS dialogs (like folder picker).
    """

    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

    def pick_folder(self):
        """Open the OS native folder picker dialog."""
        import webview
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG,
            allow_multiple=False,
        )
        if result and len(result) > 0:
            return result[0]
        return None


def run_server(host, port):
    """Run uvicorn in the current thread (called from background thread)."""
    import uvicorn
    from .server import app

    # Bound to 127.0.0.1 only - never expose on network
    config = uvicorn.Config(
        app, host=host, port=port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    server.run()


def launch_desktop(directory=None, width=1200, height=800, dev=False):
    """Launch the desktop application.

    Args:
        directory: Optional directory to auto-index on startup.
        width, height: Window dimensions.
        dev: If True, enable dev tools.
    """
    try:
        import webview
    except ImportError:
        print(
            "Error: pywebview is not installed.\n"
            "Install it with: pip install pywebview\n"
            "On Windows, also install: pip install pywebview[cef]",
            file=sys.stderr,
        )
        sys.exit(1)

    host = "127.0.0.1"
    port = find_free_port()

    # Start FastAPI in a background thread
    server_thread = threading.Thread(
        target=run_server, args=(host, port), daemon=True
    )
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server(host, port):
        print("Error: Server failed to start within timeout.", file=sys.stderr)
        sys.exit(1)

    # Build the URL (optionally with auto-index directory)
    url = f"http://{host}:{port}/"
    if directory:
        import urllib.parse
        url += f"?dir={urllib.parse.quote(directory)}"

    # Create native API bridge
    api = NativeAPI()

    # Create the native window
    window = webview.create_window(
        title="FileFinder",
        url=url,
        js_api=api,
        width=width,
        height=height,
        min_size=(800, 500),
        resizable=True,
        confirm_close=False,
    )
    api.set_window(window)

    # Start the GUI event loop (blocks until window is closed)
    webview.start(debug=dev)


def main():
    parser = argparse.ArgumentParser(
        description="FileFinder - Desktop file search with AI",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Optional directory to auto-index on launch",
    )
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--dev", action="store_true", help="Enable dev tools")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    launch_desktop(
        directory=args.directory,
        width=args.width,
        height=args.height,
        dev=args.dev,
    )


if __name__ == "__main__":
    main()
