"""命令列的模式分派。

真正的渲染與即時行為由 test_compose / test_live 負責，這裡只驗
「什麼情況該走哪條路」——那是 cli.py 唯一的職責。
"""

from __future__ import annotations

import pytest

from nvitiny import cli
from nvitiny.core.sample import from_fixture


@pytest.fixture
def fake_gpu(monkeypatch):
    """把 NVML 換成 fixture，讓 CLI 測試不需要真的有顯示卡。"""
    monkeypatch.setattr("nvitiny.core.sample.from_live", lambda: from_fixture("gb10"))


def test_demo_needs_no_gpu(capsys):
    assert cli.main(["--demo"]) == 0
    assert "GPU0" in capsys.readouterr().out


def test_falls_back_to_once_when_not_a_tty(fake_gpu, monkeypatch, capsys):
    """導進管線時即時模式做不到，必須自動退回單次輸出。"""
    monkeypatch.setattr("nvitiny.app.live.supported", lambda: False)
    assert cli.main([]) == 0
    assert "GPU0" in capsys.readouterr().out


def test_once_flag_skips_live_even_on_a_tty(fake_gpu, monkeypatch, capsys):
    monkeypatch.setattr("nvitiny.app.live.supported", lambda: True)
    monkeypatch.setattr("nvitiny.app.live.run", lambda *a, **k: pytest.fail("不該走即時模式"))
    assert cli.main(["--once"]) == 0
    assert "GPU0" in capsys.readouterr().out


def test_live_is_the_default_on_a_tty(fake_gpu, monkeypatch):
    monkeypatch.setattr("nvitiny.app.live.supported", lambda: True)
    called = {}

    def fake_run(sample, interval):
        called["interval"] = interval
        return 0

    monkeypatch.setattr("nvitiny.app.live.run", fake_run)
    assert cli.main(["-i", "0.25"]) == 0
    assert called["interval"] == 0.25


def test_ctrl_c_exits_with_130(fake_gpu, monkeypatch):
    monkeypatch.setattr("nvitiny.app.live.supported", lambda: True)
    monkeypatch.setattr("nvitiny.app.live.run", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    assert cli.main([]) == 130
