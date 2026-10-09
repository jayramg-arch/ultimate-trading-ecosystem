"""S4 alert-path check (9-Oct-2026): ngrok edge errors and a down receiver are named,
any uvicorn answer is OK, and the alarm fires on the first failure and once on recovery."""
import types

import scheduler_daemon as sd


class _R:
    def __init__(self, status=200, headers=None, payload=None):
        self.status_code, self.headers, self._p = status, headers or {}, payload
        self.ok = status < 400

    def json(self):
        return self._p


def _fake(monkeypatch, public):
    import requests

    def get(url, timeout=None, headers=None):
        if "4040" in url:
            if public is None:
                raise ConnectionError("no agent")
            return _R(payload={"tunnels": [{"public_url": "https://x.ngrok-free.dev"}]})
        return public
    monkeypatch.setattr(requests, "get", get)


def test_ok_when_uvicorn_answers(monkeypatch):
    _fake(monkeypatch, _R(404, {"Server": "uvicorn"}))      # old receiver without /health
    assert sd.tunnel_status() == (True, "ok")


def test_offline_tunnel_named(monkeypatch):
    _fake(monkeypatch, _R(404, {"Ngrok-Error-Code": "ERR_NGROK_3200"}))
    ok, why = sd.tunnel_status()
    assert not ok and "OFFLINE" in why


def test_receiver_down_named(monkeypatch):
    _fake(monkeypatch, _R(502, {"Ngrok-Error-Code": "ERR_NGROK_8012"}))
    ok, why = sd.tunnel_status()
    assert not ok and "receiver" in why


def test_no_agent(monkeypatch):
    _fake(monkeypatch, None)
    ok, why = sd.tunnel_status()
    assert not ok and "NOT running" in why


def test_alarm_edges(monkeypatch):
    sent = []
    monkeypatch.setattr(sd, "send_telegram", lambda m, **k: sent.append(m))
    import data_provider
    monkeypatch.setattr(data_provider, "nse_market_open", lambda: True)
    seq = iter([(False, "x"), (False, "x"), (True, "ok"), (True, "ok")])
    monkeypatch.setattr(sd, "tunnel_status", lambda: next(seq))
    monkeypatch.setattr(sd, "_tunnel_last_ok", None)
    for _ in range(4):
        sd.job_tunnel_check()
    assert len(sent) == 2 and "DOWN" in sent[0] and "recovered" in sent[1]
