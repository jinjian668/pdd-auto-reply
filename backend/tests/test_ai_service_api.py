# -*- coding: utf-8 -*-
"""AI 客服状态与上线下线接口测试。"""
from __future__ import annotations

from app.core.business_codes import CODE_FORBIDDEN, CODE_EXTERNAL_ERROR
from app.services import ai_service_control
from common.schemas.common import error_response, success_response

API_PREFIX = "/api/v1"
STATUS_URL = f"{API_PREFIX}/ai-service/status"
ONLINE_URL = f"{API_PREFIX}/ai-service/online"
OFFLINE_URL = f"{API_PREFIX}/ai-service/offline"


def _login(client, username: str, password: str) -> str:
    response = client.post(
        f"{API_PREFIX}/login",
        json={"username": username, "password": password},
    )
    body = response.json()
    assert body["success"] is True, body
    return body["data"]["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_read_status(client, test_users, monkeypatch):
    monkeypatch.setattr(
        ai_service_control,
        "get_status",
        lambda: {
            "online": True,
            "state": "online",
            "desired_state": "online",
            "control_supported": True,
            "pid": 1234,
        },
    )
    token = _login(
        client, test_users["admin"]["username"], test_users["admin"]["password"]
    )

    response = client.get(STATUS_URL, headers=_headers(token))
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"]["online"] is True


def test_status_requires_dashboard_view(client, test_users):
    token = _login(
        client, test_users["manager"]["username"], test_users["manager"]["password"]
    )

    response = client.get(STATUS_URL, headers=_headers(token))
    body = response.json()

    assert body["success"] is False
    assert body["code"] == CODE_FORBIDDEN


def test_only_admin_can_control_service(client, test_users, monkeypatch):
    called = []
    monkeypatch.setattr(
        ai_service_control,
        "start_service",
        lambda: called.append("start")
        or success_response({"online": True}, "AI 客服已上线"),
    )
    monkeypatch.setattr(
        ai_service_control,
        "stop_service",
        lambda: called.append("stop")
        or success_response({"online": False}, "AI 客服已下线"),
    )
    manager_token = _login(
        client, test_users["manager"]["username"], test_users["manager"]["password"]
    )

    online_response = client.post(ONLINE_URL, headers=_headers(manager_token))
    offline_response = client.post(OFFLINE_URL, headers=_headers(manager_token))

    assert online_response.json()["code"] == CODE_FORBIDDEN
    assert offline_response.json()["code"] == CODE_FORBIDDEN
    assert called == []


def test_admin_control_endpoints_delegate_to_service(client, test_users, monkeypatch):
    called = []
    monkeypatch.setattr(
        ai_service_control,
        "start_service",
        lambda: called.append("start")
        or success_response({"online": True}, "AI 客服已上线"),
    )
    monkeypatch.setattr(
        ai_service_control,
        "stop_service",
        lambda: called.append("stop")
        or success_response({"online": False}, "AI 客服已下线"),
    )
    token = _login(
        client, test_users["admin"]["username"], test_users["admin"]["password"]
    )

    online_response = client.post(ONLINE_URL, headers=_headers(token))
    offline_response = client.post(OFFLINE_URL, headers=_headers(token))

    assert online_response.json()["success"] is True
    assert offline_response.json()["success"] is True
    assert called == ["start", "stop"]


def test_control_failure_uses_unified_response(client, test_users, monkeypatch):
    monkeypatch.setattr(
        ai_service_control,
        "start_service",
        lambda: error_response(CODE_EXTERNAL_ERROR, "启动失败"),
    )
    token = _login(
        client, test_users["admin"]["username"], test_users["admin"]["password"]
    )

    response = client.post(ONLINE_URL, headers=_headers(token))
    body = response.json()

    assert response.status_code == 200
    assert body["success"] is False
    assert body["code"] == CODE_EXTERNAL_ERROR
    assert body["message"] == "启动失败"
