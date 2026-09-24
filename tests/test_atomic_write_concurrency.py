"""atomic_write_text must survive CONCURRENT writers, not just a crash.

THE BUG (24-Sep-2026). The temp path was `path + ".tmp"` — one fixed name shared by
every caller — so it was atomic against a kill mid-write and not against two writers:

    A  open(tmp,"w") ....... writing .......  os.replace(tmp, path)
    B       open(tmp,"w")  <- truncates A's temp under it
                              os.replace(tmp, path)  <- one of them raises

On Windows that surfaces as PermissionError [WinError 5] and the write is LOST. Callers
that wrap the save in try/except record nothing, which is how gm_armed.json kept the same
mtime for eleven days while the UI believed it was saving, and why logs/gm_errors.log
holds 440 "store unreadable" lines with nothing to diagnose.

Every caller shares this primitive: the board cache, FINAL_*.csv, MASTER_Golden_Picks,
the catalyst history, gm_settings, the armed register.
"""
import json
import os
import threading
import time

from io_utils import atomic_write_text

BIG = json.dumps({"S%04d" % i: {"a": "x" * 40} for i in range(300)}, indent=2)
SMALL = json.dumps({"S0001": {"a": "y"}}, indent=2)


def test_temp_name_is_unique_per_call(tmp_path, monkeypatch):
    """Two calls must never pick the same temp path — that is the whole bug."""
    seen = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append(src)
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    p = str(tmp_path / "x.json")
    for _ in range(20):
        atomic_write_text(p, SMALL)
    assert len(set(seen)) == len(seen), "temp names collide: %s" % seen[:4]
    assert not any(s.endswith("x.json.tmp") for s in seen), "the old fixed name is back"


def test_concurrent_writers_all_succeed_and_no_reader_sees_a_torn_file(tmp_path):
    path = str(tmp_path / "reg.json")
    atomic_write_text(path, BIG)
    stop = threading.Event()
    wrote, failed, torn = [0], [], []

    def writer(text, n):
        for _ in range(n):
            try:
                atomic_write_text(path, text)
                wrote[0] += 1
            except Exception as e:
                failed.append(type(e).__name__)
            time.sleep(0.002)

    def reader():
        while not stop.is_set():
            try:
                with open(path, encoding="utf-8") as f:
                    json.load(f)
            except OSError:
                pass            # busy during the swap — not corruption
            except Exception as e:
                torn.append(str(e))
            time.sleep(0.003)

    ts = [threading.Thread(target=writer, args=(BIG, 120)),
          threading.Thread(target=writer, args=(SMALL, 120)),
          threading.Thread(target=reader, daemon=True)]
    for t in ts:
        t.start()
    for t in ts[:2]:
        t.join()
    stop.set()
    ts[2].join(timeout=2)

    assert not failed, "writes lost under concurrency: %s" % failed[:5]
    assert wrote[0] == 240, "only %d of 240 writes landed" % wrote[0]
    assert not torn, "a reader saw a TORN file (the real damage): %s" % torn[:3]


def test_no_temp_files_are_left_behind(tmp_path):
    path = str(tmp_path / "y.json")
    for _ in range(10):
        atomic_write_text(path, SMALL)
    leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]
    assert not leftovers, "temp files left on disk: %s" % leftovers


def test_the_content_is_exactly_what_was_written(tmp_path):
    path = str(tmp_path / "z.json")
    atomic_write_text(path, BIG)
    atomic_write_text(path, SMALL)          # shorter over longer — the "Extra data" shape
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == json.loads(SMALL)
    assert open(path, encoding="utf-8").read() == SMALL, "old tail survived the overwrite"
