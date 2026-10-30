# -*- coding: utf-8 -*-
"""
backend.app.services.ai_service_control - AI 客服进程生命周期控制
================================================================
工作台「上线 / 下线」对应的服务是独立运行的 websocket 进程
(``websocket/main.py``)。本模块只负责该进程的状态探测与启停，不停止
backend、frontend、scheduler 或 MySQL，因此下线后管理后台仍可正常使用。

安全边界：
- 仅 Windows 本机部署且显式配置 ``PDD_RUNTIME_DIR`` 时允许网页内启停；
- 启停统一委托 ``tools/ai-service-control.ps1``；
- 脚本只按完整 websocket 入口路径匹配进程，不按端口杀进程；
- 下线意图写入运行时标记文件，Windows 登录自启动据此保持离线。
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from app.core.business_codes import CODE_EXTERNAL_ERROR
from common.core.config import get_settings
from common.schemas.common import ApiResponse, error_response, success_response

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CONTROL_SCRIPT = _PROJECT_ROOT / "tools" / "ai-service-control.ps1"
_PROJECT_PYTHON = _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
_OFFLINE_MARKER = "ai-service.offline"
_PID_FILE = "websocket.pid"
_CONTROL_LOCK = threading.Lock()
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_ERROR_MESSAGES: dict[str, str] = {
    "runtime_not_configured": "未配置 AI 客服运行时目录，无法启停服务",
    "control_script_missing": "AI 客服控制脚本不存在，请检查部署文件",
    "python_missing": "未找到项目 Python 解释器，无法启动 AI 客服",
    "port_in_use": "AI 客服端口已被其他程序占用，未执行启动",
    "health_failed": "AI 客服启动超时，请查看运行时日志",
    "process_not_found": "未找到可停止的 AI 客服进程",
    "stop_failed": "AI 客服未能完全停止，请查看运行时日志",
    "control_script_failed": "AI 客服控制脚本执行失败，请查看运行时日志",
}


def _runtime_dir() -> Path | None:
    configured = (get_settings().pdd_runtime_dir or "").strip()
    if not configured:
        return None
    return Path(os.path.expandvars(os.path.expanduser(configured))).resolve()


def _python_executable() -> Path:
    if _PROJECT_PYTHON.is_file():
        return _PROJECT_PYTHON
    return Path(sys.executable)


def _powershell_executable() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = (
        Path(system_root)
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    return str(candidate)


def _marker_path() -> Path | None:
    runtime = _runtime_dir()
    return runtime / "run" / _OFFLINE_MARKER if runtime else None


def _pid_path() -> Path | None:
    runtime = _runtime_dir()
    return runtime / "run" / _PID_FILE if runtime else None


def _health_url() -> str:
    base = (get_settings().websocket_service_url or "").strip().rstrip("/")
    return f"{base}/health"


def _is_online(timeout: float = 2.0) -> bool:
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(_health_url(), timeout=timeout) as response:
            return 200 <= int(getattr(response, "status", 0)) < 300
    except (URLError, TimeoutError, OSError, ValueError):
        return False


def _read_pid() -> int | None:
    path = _pid_path()
    if path is None:
        return None
    try:
        value = int(path.read_text(encoding="ascii").strip())
        return value if value > 0 else None
    except (OSError, ValueError):
        return None


def control_supported() -> bool:
    runtime = _runtime_dir()
    return bool(
        platform.system().lower() == "windows"
        and runtime is not None
        and _CONTROL_SCRIPT.is_file()
        and _python_executable().is_file()
    )


def _unsupported_reason() -> str:
    if platform.system().lower() != "windows":
        return "当前系统不支持网页内启停 AI 客服"
    if _runtime_dir() is None:
        return "未配置 PDD_RUNTIME_DIR，无法在网页内启停 AI 客服"
    if not _CONTROL_SCRIPT.is_file():
        return "AI 客服控制脚本不存在，请检查部署文件"
    return "未找到项目 Python 解释器，无法启动 AI 客服"


def _run_control_script(action: str) -> dict[str, Any]:
    runtime = _runtime_dir()
    if runtime is None:
        return {"success": False, "code": "runtime_not_configured"}
    if not _CONTROL_SCRIPT.is_file():
        return {"success": False, "code": "control_script_missing"}
    if not _python_executable().is_file():
        return {"success": False, "code": "python_missing"}

    command = [
        _powershell_executable(),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(_CONTROL_SCRIPT),
        "-Action",
        action,
        "-RuntimeDir",
        str(runtime),
        "-PythonExecutable",
        str(_python_executable()),
        "-WebsocketUrl",
        (get_settings().websocket_service_url or "").strip(),
    ]
    log_dir = runtime / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"ai-service-control-{action}.out.log"
    stderr_path = log_dir / f"ai-service-control-{action}.err.log"
    try:
        # 重定向到文件而不是管道：控制脚本会拉起常驻 websocket 子进程，
        # 若子进程继承管道句柄，subprocess.run 可能一直等待 EOF 而挂起请求。
        with stdout_path.open("w", encoding="utf-8") as stdout_file, (
            stderr_path.open("w", encoding="utf-8")
        ) as stderr_file:
            completed = subprocess.run(
                command,
                cwd=str(_PROJECT_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=115,
                creationflags=_CREATE_NO_WINDOW,
                check=False,
            )
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "success": False,
            "code": "control_script_failed",
            "detail": str(exc),
        }

    for line in reversed(stdout_text.splitlines()):
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    detail = (stderr_text or stdout_text).strip()[-500:]
    return {
        "success": False,
        "code": "control_script_failed",
        "detail": detail,
    }


def _result_message(result: dict[str, Any]) -> str:
    code = str(result.get("code") or "control_script_failed")
    message = _ERROR_MESSAGES.get(code, _ERROR_MESSAGES["control_script_failed"])
    detail = str(result.get("detail") or "").strip()
    if detail and detail.lower() not in message.lower():
        return f"{message}（{detail[:200]}）"
    return message


def _is_offline_marked() -> bool:
    path = _marker_path()
    return bool(path and path.is_file())


def _set_offline_marker() -> None:
    path = _marker_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("offline\n", encoding="ascii")
    except OSError:
        return


def _clear_offline_marker() -> None:
    path = _marker_path()
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def get_status() -> dict[str, Any]:
    online = _is_online()
    supported = control_supported()
    return {
        "service": "websocket",
        "online": online,
        "state": "online" if online else "offline",
        "desired_state": "offline" if _is_offline_marked() else "online",
        "control_supported": supported,
        "unsupported_reason": "" if supported else _unsupported_reason(),
        "pid": _read_pid() if online else None,
    }


def start_service() -> ApiResponse:
    if not _CONTROL_LOCK.acquire(timeout=5):
        return error_response(
            CODE_EXTERNAL_ERROR, "另一个 AI 客服启停操作正在进行，请稍后重试"
        )
    try:
        if _is_online():
            _clear_offline_marker()
            return success_response(get_status(), "AI 客服已在线")
        if not control_supported():
            return error_response(CODE_EXTERNAL_ERROR, _unsupported_reason())

        result = _run_control_script("start")
        if not result.get("success") or not result.get("online"):
            return error_response(CODE_EXTERNAL_ERROR, _result_message(result))

        _clear_offline_marker()
        status = get_status()
        if not status["online"]:
            return error_response(
                CODE_EXTERNAL_ERROR, _ERROR_MESSAGES["health_failed"]
            )
        return success_response(status, "AI 客服已上线")
    finally:
        _CONTROL_LOCK.release()


def stop_service() -> ApiResponse:
    if not _CONTROL_LOCK.acquire(timeout=5):
        return error_response(
            CODE_EXTERNAL_ERROR, "另一个 AI 客服启停操作正在进行，请稍后重试"
        )
    try:
        if not control_supported():
            return error_response(CODE_EXTERNAL_ERROR, _unsupported_reason())

        result = _run_control_script("stop")
        if not result.get("success"):
            return error_response(CODE_EXTERNAL_ERROR, _result_message(result))

        _set_offline_marker()
        status = get_status()
        if status["online"]:
            return error_response(CODE_EXTERNAL_ERROR, _ERROR_MESSAGES["stop_failed"])
        return success_response(status, "AI 客服已下线")
    finally:
        _CONTROL_LOCK.release()


__all__ = [
    "control_supported",
    "get_status",
    "start_service",
    "stop_service",
]
