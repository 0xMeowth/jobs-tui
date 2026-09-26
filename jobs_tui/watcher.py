import threading
from collections.abc import Callable
from pathlib import Path

from watchfiles import watch


def watch_folder(folder: Path, stop: threading.Event, on_change: Callable[[set[str]], None]) -> None:
    for changes in watch(folder, stop_event=stop, debounce=300, rust_timeout=500):
        on_change({Path(p).name for _, p in changes})
