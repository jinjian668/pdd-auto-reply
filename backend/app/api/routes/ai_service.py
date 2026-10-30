# -*- coding: utf-8 -*-
"""
backend.app.api.routes.ai_service - AI 客服服务控制接口
======================================================
提供工作台仪表盘的 AI 客服进程状态与上线下线操作：

- ``GET  /ai-service/status``：查询 websocket 客服进程是否在线；
- ``POST /ai-service/online``：启动 websocket 客服进程；
- ``POST /ai-service/offline``：停止 websocket 客服进程。

状态查询沿用 dashboard 资源的 view 权限；上线和下线仅管理员可执行。
下线只停止 websocket 进程，不停止 backend、frontend、scheduler 与 MySQL，
因此管理后台仍可继续访问并重新上线。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import permission
from app.core.business_codes import CODE_FORBIDDEN, MSG_FORBIDDEN
from app.services import ai_service_control
from common.db.session import get_db
from common.models.user_models import SysUser
from common.schemas.common import ApiResponse, error_response, success_response

router = APIRouter(tags=["AI 客服服务"])

RESOURCE_DASHBOARD: str = "dashboard"


def _ensure_dashboard_view(
    user: SysUser, session: Session
) -> Optional[ApiResponse]:
    if permission.load_auth_context(user, session).is_admin:
        return None
    if permission.check(user, RESOURCE_DASHBOARD, "view", session=session):
        return None
    return error_response(CODE_FORBIDDEN, MSG_FORBIDDEN)


def _ensure_admin(user: SysUser, session: Session) -> Optional[ApiResponse]:
    if permission.load_auth_context(user, session).is_admin:
        return None
    return error_response(CODE_FORBIDDEN, MSG_FORBIDDEN)


@router.get(
    "/ai-service/status",
    response_model=ApiResponse,
    summary="AI 客服进程状态",
)
def get_ai_service_status(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    denied = _ensure_dashboard_view(current_user, db)
    if denied is not None:
        return denied
    return success_response(ai_service_control.get_status(), "获取 AI 客服状态成功")


@router.post(
    "/ai-service/online",
    response_model=ApiResponse,
    summary="上线 AI 客服",
)
def online_ai_service(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    denied = _ensure_admin(current_user, db)
    if denied is not None:
        return denied
    return ai_service_control.start_service()


@router.post(
    "/ai-service/offline",
    response_model=ApiResponse,
    summary="下线 AI 客服",
)
def offline_ai_service(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse:
    denied = _ensure_admin(current_user, db)
    if denied is not None:
        return denied
    return ai_service_control.stop_service()


__all__ = ["router"]
