# -*- coding: utf-8 -*-
"""AI 客服进程控制服务的纯单元测试（不启动真实进程）。"""
from __future__ import annotations

from app.core.business_codes import CODE_EXTERNAL_ERROR
from app.services import ai_service_control


def _prepare(monkeypatch, tmp_path, online: bool, supported: bool = True):
    state = {"online": online}
    monkeypatch.setattr(ai_service_control, "_runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(
        ai_service_control, "_is_online", lambda timeout=2.0: state["online"]
    )
    monkeypatch.setattr(
        ai_service_control, "control_supported", lambda: supported
    )
    return state


def test_status_reports_online_and_pid(monkeypatch, tmp_path):
    state = _prepare(monkeypatch, tmp_path, online=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "websocket.pid").write_text("4321", encoding="ascii")

    data = ai_service_control.get_status()

    assert state["online"] is True
    assert data["online"] is True
    assert data["state"] == "online"
    assert data["desired_state"] == "online"
    assert data["control_supported"] is True
    assert data["pid"] == 4321


def test_start_is_idempotent_when_already_online(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, online=True)
    marker = tmp_path / "run" / "ai-service.offline"
    marker.parent.mkdir()
    marker.write_text("offline\n", encoding="ascii")
    called = []
    monkeypatch.setattr(
        ai_service_control,
        "_run_control_script",
        lambda action: called.append(action) or {"success": True, "online": True},
    )

    response = ai_service_control.start_service()

    assert response.success is True
    assert called == []
    assert marker.exists() is False


def test_start_runs_script_and_clears_offline_marker(monkeypatch, tmp_path):
    state = _prepare(monkeypatch, tmp_path, online=False)
    marker = tmp_path / "run" / "ai-service.offline"
    marker.parent.mkdir()
    marker.write_text("offline\n", encoding="ascii")
    called = []

    def fake_run(action):
        called.append(action)
        state["online"] = True
        return {"success": True, "online": True, "pid": 1234}

    monkeypatch.setattr(ai_service_control, "_run_control_script", fake_run)

    response = ai_service_control.start_service()

    assert response.success is True
    assert called == ["start"]
    assert marker.exists() is False
    assert response.data["online"] is True


def test_stop_runs_script_and_writes_offline_marker(monkeypatch, tmp_path):
    state = _prepare(monkeypatch, tmp_path, online=True)

    def fake_run(action):
        assert action == "stop"
        state["online"] = False
        return {"success": True, "online": False}

    monkeypatch.setattr(ai_service_control, "_run_control_script", fake_run)

    response = ai_service_control.stop_service()

    marker = tmp_path / "run" / "ai-service.offline"
    assert response.success is True
    assert marker.is_file()
    assert response.data["desired_state"] == "offline"
    assert response.data["online"] is False


def test_control_unsupported_returns_external_error(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, online=False, supported=False)
    monkeypatch.setattr(
        ai_service_control, "_unsupported_reason", lambda: "当前部署不支持进程控制"
    )

    response = ai_service_control.start_service()

    assert response.success is False
    assert response.code == CODE_EXTERNAL_ERROR
    assert response.message == "当前部署不支持进程控制"


def test_stop_script_failure_keeps_service_online(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path, online=True)
    monkeypatch.setattr(
        ai_service_control,
        "_run_control_script",
        lambda action: {"success": False, "code": "stop_failed"},
    )

    response = ai_service_control.stop_service()

    assert response.success is False
    assert response.code == CODE_EXTERNAL_ERROR
    assert (tmp_path / "run" / "ai-service.offline").exists() is False
