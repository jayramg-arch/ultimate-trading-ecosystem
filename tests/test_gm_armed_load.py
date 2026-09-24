"""The armed register must not declare itself empty because the file was BUSY.

Every armed name lives only here. `load()` returning {} means the board silently drops
all of them — and between 31-Jul and 23-Sep it said so 440 times, in a line that carried
no size, no bytes and no copy, so there was nothing to diagnose after the fact.

A file being briefly unopenable during os.replace is not a file that is broken.
"""
import json
import os

import pytest

import gm_armed


@pytest.fixture
def store(tmp_path, monkeypatch):
    p = tmp_path / "gm_armed.json"
    monkeypatch.setattr(gm_armed, "_STORE", str(p))
    return p


def test_a_good_store_loads(store):
    store.write_text(json.dumps({"RELIANCE": {"status": "ARMED"}}), encoding="utf-8")
    assert list(gm_armed.load()) == ["RELIANCE"]


def test_a_missing_store_is_empty_and_silent(store, monkeypatch):
    said = []
    monkeypatch.setattr(gm_armed._log, "warning", lambda *a, **k: said.append(a))
    assert gm_armed.load() == {}
    assert not said, "a store that was never created is not a fault"


def test_a_transient_busy_file_is_RETRIED_not_declared_corrupt(store, monkeypatch):
    """The 24-Sep fix. Windows refuses to open the destination during os.replace, so a
    reader racing a save used to get {} — losing every armed name for that rebuild."""
    store.write_text(json.dumps({"TITAN": {"status": "ARMED"}}), encoding="utf-8")
    real_open, calls = open, {"n": 0}

    def flaky(path, *a, **k):
        if str(path) == str(store) and calls["n"] < 2:
            calls["n"] += 1
            raise PermissionError(13, "Permission denied")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", flaky)
    assert list(gm_armed.load()) == ["TITAN"], "gave up on a file that was merely busy"
    assert calls["n"] == 2, "did not actually retry"


def test_a_genuinely_broken_store_reports_what_it_saw(store, monkeypatch):
    """When it IS broken, the log must carry enough to diagnose it next time."""
    store.write_text("{", encoding="utf-8")          # the exact shape from the real log
    said = []
    monkeypatch.setattr(gm_armed._log, "warning", lambda m, *a: said.append(str(m)))
    assert gm_armed.load() == {}
    joined = " ".join(said)
    assert "1 bytes" in joined, "no size reported: %r" % joined
    assert "b'{'" in joined, "no first bytes reported: %r" % joined


def test_a_broken_store_is_preserved_for_inspection(store, monkeypatch):
    store.write_text("{", encoding="utf-8")
    monkeypatch.setattr(gm_armed._log, "warning", lambda *a, **k: None)
    gm_armed.load()
    kept = [p for p in os.listdir(store.parent) if ".unreadable-" in p]
    assert kept, "the bad file was not kept — the evidence is gone again"
    assert (store.parent / kept[0]).read_text(encoding="utf-8") == "{"


def test_it_does_not_hoard_a_copy_per_read(store, monkeypatch):
    """This can fire dozens of times a minute; one snapshot a day is the point."""
    store.write_text("{", encoding="utf-8")
    monkeypatch.setattr(gm_armed._log, "warning", lambda *a, **k: None)
    for _ in range(5):
        gm_armed.load()
    kept = [p for p in os.listdir(store.parent) if ".unreadable-" in p]
    assert len(kept) == 1, "kept %d copies" % len(kept)


def test_a_non_dict_payload_is_empty_not_an_exception(store):
    store.write_text("[1, 2, 3]", encoding="utf-8")
    assert gm_armed.load() == {}
