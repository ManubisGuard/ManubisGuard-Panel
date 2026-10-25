from types import SimpleNamespace

import psutil

from app.utils.system import network_connection_stats


def test_network_connection_stats_counts_tcp_states_and_udp(monkeypatch):
    monkeypatch.setattr(
        psutil,
        "net_connections",
        lambda kind: (
            [
                SimpleNamespace(status=psutil.CONN_ESTABLISHED),
                SimpleNamespace(status=psutil.CONN_LISTEN),
                SimpleNamespace(status=psutil.CONN_TIME_WAIT),
            ]
            if kind == "tcp"
            else [SimpleNamespace(status=psutil.CONN_NONE), SimpleNamespace(status=psutil.CONN_NONE)]
        ),
    )

    result = network_connection_stats()

    assert result["available"] is True
    assert result["tcp_total"] == 3
    assert result["tcp_established"] == 1
    assert result["tcp_listen"] == 1
    assert result["tcp_other"] == 1
    assert result["udp_sockets"] == 2
    assert result["source"] == "psutil.net_connections"
    assert result["collected_at"]


def test_network_connection_stats_does_not_fake_zero_on_access_denied(monkeypatch):
    def denied(*, kind):
        raise psutil.AccessDenied(pid=123)

    monkeypatch.setattr(psutil, "net_connections", denied)
    result = network_connection_stats()

    assert result["available"] is False
    assert result["tcp_total"] is None
    assert result["udp_sockets"] is None
    assert result["unavailable_reason"] == "AccessDenied"
