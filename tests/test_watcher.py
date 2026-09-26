import threading
import time

from jobs_tui.watcher import watch_folder


def test_watch_folder_reports_names(tmp_path):
    seen = []
    stop = threading.Event()
    t = threading.Thread(target=watch_folder, args=(tmp_path, stop, lambda names: seen.append(names)), daemon=True)
    t.start()
    time.sleep(0.3)
    for i in range(50):
        if any("proposed-edits.json" in names for names in seen):
            break
        (tmp_path / "proposed-edits.json").write_text(str(i))
        time.sleep(0.1)
    stop.set()
    t.join(timeout=3)
    assert any("proposed-edits.json" in names for names in seen)
