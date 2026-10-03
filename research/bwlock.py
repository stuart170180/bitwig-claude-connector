"""Cross-process lock so several workers never drive the one live Bitwig at the same time.
Usage:   from bwlock import hold
         with hold("masking test"):     # waits until nobody else holds it, releases on exit (even on error)
             ...talk to Bitwig...
Hold it only for one short, self-contained batch of live calls (a minute or two), then release so others can run.
A lock older than 10 minutes is treated as abandoned."""
import contextlib
import os
import time
from pathlib import Path

LOCK = Path(__file__).resolve().parent / "bitwig.lock"
STALE = 600


@contextlib.contextmanager
def hold(who="worker", wait=900):
    t0 = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{who} {time.time()}".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - LOCK.stat().st_mtime > STALE:
                    LOCK.unlink()
                    continue
            except OSError:
                pass
            if time.time() - t0 > wait:
                raise TimeoutError("could not get the Bitwig lock")
            time.sleep(2)
    try:
        yield
    finally:
        try:
            LOCK.unlink()
        except OSError:
            pass
