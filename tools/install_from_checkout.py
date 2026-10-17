"""Install the verified ZIP from this checkout, without fetching it from Pages."""
import functools, http.server, json, subprocess, sys, threading
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if any(a == "--site" or a.startswith("--site=") for a in args):
        raise ValueError("This entry point always uses the local checkout")
    docs = ROOT / "docs"
    if not (docs / "downloads/release.json").is_file():
        raise ValueError("Missing release bundle; use the complete checkout")
    handler = functools.partial(QuietHandler, directory=str(docs))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        command = [sys.executable, "-X", "utf8", str(ROOT / "install.py"),
                   "--site", "http://127.0.0.1:" + str(server.server_port) + "/"] + args
        return subprocess.run(command, check=False).returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

if __name__ == "__main__":
    sys.exit(main())
