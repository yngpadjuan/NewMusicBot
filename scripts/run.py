"""Entry point: wait for network connectivity, then start listeners."""
import os
import sys
import socket
import time

# Ensure the repo root is on sys.path so `src` is importable as a package.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _wait_for_network(host='discord.com', port=443, timeout=5, max_attempts=60):
    print(f'Waiting for network connectivity to {host}...', flush=True)
    for attempt in range(1, max_attempts + 1):
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            print('Network is up.', flush=True)
            return
        except OSError:
            if attempt % 10 == 0:
                print(f'  Still waiting ({attempt}/{max_attempts})...', flush=True)
            time.sleep(2)
    print('WARNING: network not reachable after maximum attempts; continuing anyway.', flush=True)


if __name__ == '__main__':
    _wait_for_network()
    # Import and start the bot — runs until the process is killed.
    import src.listeners  # noqa: F401 — module-level startup runs on import
