# -*- coding: utf-8 -*-
"""导出可版本化的客服业务资产。

本脚本只读取业务规则与话术表，排除凭据、客户隐私和运行日志，输出 JSON
快照供 Git 版本管理。数据库连接信息来自环境变量或仓库根目录的 .env。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "project-assets" / "exports"
BEIJING = timezone(timedelta(hours=8))
MANIFEST_VERSION = 1

ASSET_SPECS = [
    {"asset_type": "customer-service-knowledge", "label": "客服话术知识库", "table": "pdd_customer_service_knowledge", "file": "customer-service-knowledge.json"},
    {"asset_type": "product-knowledge", "label": "商品知识", "table": "pdd_product_knowledge", "file": "product-knowledge.json"},
    {"asset_type": "keyword-rules", "label": "关键词回复规则", "table": "pdd_keyword_rule", "file": "keyword-rules.json"},
    {"asset_type": "default-replies", "label": "默认回复模板", "table": "pdd_default_reply", "file": "default-replies.json"},
    {"asset_type": "goods-replies", "label": "商品专属回复", "table": "pdd_goods_reply", "file": "goods-replies.json"},
    {"asset_type": "business-hours", "label": "营业时间规则", "table": "pdd_business_hours", "file": "business-hours.json"},
    {"asset_type": "message-filter-rules", "label": "消息过滤规则", "table": "pdd_message_filter_rule", "file": "message-filter-rules.json"},
    {"asset_type": "risk-rules", "label": "风控规则", "table": "pdd_risk_rule", "file": "risk-rules.json"},
    {"asset_type": "transfer-keywords", "label": "转人工关键词", "table": "pdd_transfer_keyword", "file": "transfer-keywords.json"},
    {"asset_type": "scheduled-tasks", "label": "定时任务配置", "table": "pdd_scheduled_task", "file": "scheduled-tasks.json", "exclude": {"last_run_at", "next_run_at"}},
    {"asset_type": "llm-configs", "label": "AI 模型与指令", "table": "pdd_llm_config", "file": "llm-configs.json", "exclude": {"api_key_enc", "api_base"}},
    {"asset_type": "announcements", "label": "系统公告", "table": "pdd_announcement", "file": "announcements.json", "where": "COALESCE(deleted_flag, 0) = 0"},
]

EXCLUDED_COLUMN_NAMES = {
    "created_by", "updated_by", "user_id", "owner_user_id", "nickname",
    "password", "password_hash", "passwd", "secret", "api_key", "api_key_enc",
    "token", "access_token", "refresh_token", "cookie", "cookies", "cookie_enc",
    "authorization", "credential", "credentials", "smtp_password", "webhook_secret",
    "customer_uid", "buyer_id", "buyer_name", "phone", "mobile", "email", "address", "target", "contact",
    "order_id", "order_sn", "thumb_url", "image_url", "avatar", "raw_payload",
    "request", "response", "login_state", "webhook_url", "api_base",
}
EXCLUDED_COLUMN_SUFFIXES = (
    "_password", "_secret", "_token", "_cookie", "_enc", "_credential",
    "_phone", "_mobile", "_email", "_address", "_uid",
)


def is_sensitive_column(name: str) -> bool:
    """判断列名是否属于凭据、隐私或运行态字段。"""
    lowered = name.lower()
    return lowered.startswith(("buyer_", "receiver_")) or lowered in EXCLUDED_COLUMN_NAMES or any(
        lowered.endswith(suffix) for suffix in EXCLUDED_COLUMN_SUFFIXES
    )


def json_value(value: Any) -> Any:
    """把数据库值转换为稳定的 JSON 值。"""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def fetch_asset_rows(cursor: Any, spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """读取单个资产表，并跳过敏感列。"""
    table = spec["table"]
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position",
        (table,),
    )
    all_columns = [row["COLUMN_NAME"] for row in cursor.fetchall()]
    if not all_columns:
        raise RuntimeError(f"资产表不存在：{table}")

    excluded = set(spec.get("exclude", set()))
    selected = [
        column
        for column in all_columns
        if column not in excluded and not is_sensitive_column(column)
    ]
    if not selected:
        return [], all_columns

    query = "SELECT " + ", ".join(f"`{column}`" for column in selected) + f" FROM `{table}`"
    if spec.get("where"):
        query += " WHERE " + spec["where"]
    if "id" in selected:
        query += " ORDER BY `id`"
    cursor.execute(query)
    rows = [
        {column: json_value(row[column]) for column in selected}
        for row in cursor.fetchall()
    ]
    excluded_columns = sorted(set(all_columns) - set(selected))
    return rows, excluded_columns


def write_json(path: Path, payload: dict[str, Any]) -> str:
    """写入 UTF-8 JSON 并返回内容 SHA-256。"""
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(content, encoding="utf-8", newline="\n")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def main() -> int:
    """执行全部资产业务表导出。"""
    load_dotenv(ROOT / ".env")
    host = os.getenv("MYSQL_HOST", "127.0.0.2")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "pdd_auto_reply")
    if not user or not password:
        raise RuntimeError("缺少 MYSQL_USER 或 MYSQL_PASSWORD 环境变量")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(BEIJING).isoformat(timespec="seconds")
    files: list[dict[str, Any]] = []

    connection = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=10,
        ssl_disabled=True,
    )
    try:
        with connection.cursor() as cursor:
            for spec in ASSET_SPECS:
                rows, excluded_columns = fetch_asset_rows(cursor, spec)
                payload = {
                    "schema_version": MANIFEST_VERSION,
                    "asset_type": spec["asset_type"],
                    "label": spec["label"],
                    "source_table": spec["table"],
                    "generated_at": generated_at,
                    "row_count": len(rows),
                    "excluded_columns": excluded_columns,
                    "items": rows,
                }
                file_path = OUT_DIR / spec["file"]
                checksum = write_json(file_path, payload)
                files.append(
                    {
                        "file": spec["file"],
                        "asset_type": spec["asset_type"],
                        "label": spec["label"],
                        "source_table": spec["table"],
                        "row_count": len(rows),
                        "excluded_columns": excluded_columns,
                        "sha256": checksum,
                    }
                )
    finally:
        connection.close()

    manifest = {
        "schema_version": MANIFEST_VERSION,
        "generated_at": generated_at,
        "source_database": database,
        "asset_count": len(files),
        "total_rows": sum(item["row_count"] for item in files),
        "files": files,
    }
    write_json(OUT_DIR / "manifest.json", manifest)
    print(f"已导出 {len(files)} 个业务资产文件，共 {manifest['total_rows']} 行。")
    print(f"输出目录：{OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
