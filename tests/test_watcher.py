import threading
import time

from jobs_tui.watcher import watch_folder


def test_watch_folder_reports_names(tmp_path):
    seen = []
    stop = threading.Event()
    t = threading.Thread(target=watch_folder, args=(tmp_path, stop, lambda names: seen.append(names)), daemon=True)
    t.start()
    time.sleep(0.3)
    (tmp_path / "proposed-edits.json").write_text("{}")
    for _ in range(50):
        if seen:
            break
        time.sleep(0.1)
    stop.set()
    t.join(timeout=3)
    assert seen and "proposed-edits.json" in seen[0]
