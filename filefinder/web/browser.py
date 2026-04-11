"""Browser-based launcher for FileFinder.

Runs the FastAPI server and opens the UI in the user's default browser.
Use this when PyWebView isn't available (e.g. Python 3.14 where pythonnet
has no wheels yet).
"""

import argparse
import logging
import socket
import threading
import time
import webbrowser

logger = logging.getLogger(__name__)


def find_free_port(preferred=8765):
    """Try the preferred port first, fall back to any free port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", preferred))
            return preferred
    except OSError:
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(host, port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def run_server(host, port):
    """Run uvicorn (blocking)."""
    import uvicorn
    from .server import app

    config = uvicorn.Config(
        app, host=host, port=port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    server.run()


def launch_browser(directory=None, no_browser=False):
    """Launch FastAPI server and open the UI in a browser.

    Args:
        directory: Optional directory to auto-index on startup.
        no_browser: If True, just run the server without opening a browser.
    """
    host = "127.0.0.1"
    port = find_free_port(8765)

    # Start server in a background thread
    server_thread = threading.Thread(
        target=run_server, args=(host, port), daemon=True
    )
    server_thread.start()

    if not wait_for_server(host, port):
        print("Error: Server failed to start.")
        return

    url = f"http://{host}:{port}/"
    if directory:
        import urllib.parse
        url += f"?dir={urllib.parse.quote(directory)}"

    print(f"\n  FileFinder is running at: {url}")
    print("  Press Ctrl+C to stop.\n")

    if not no_browser:
        webbrowser.open(url)

    # Keep the main thread alive until Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")


def main():
    parser = argparse.ArgumentParser(
        description="FileFinder - Browser-based file search app",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Optional directory to auto-index on launch",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open a browser window",
    )
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    launch_browser(directory=args.directory, no_browser=args.no_browser)


if __name__ == "__main__":
    main()
