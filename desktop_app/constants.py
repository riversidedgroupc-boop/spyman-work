"""Application-wide constants."""
from __future__ import annotations

APP_NAME = "CX-vision"
APP_VERSION = "0.6.0"
APP_ORG = "CX-vision"

WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 760
WINDOW_MIN_WIDTH = 960
WINDOW_MIN_HEIGHT = 600

NAV_WIDTH = 200
NAV_COLLAPSED_WIDTH = 48
NAV_ITEM_MIN_HEIGHT = 36
NAV_ITEM_MAX_HEIGHT = 84

NAV_ITEMS: list[dict[str, str]] = [
    {"id": "project_center", "label": "项目中心", "icon": "🏠"},
    {"id": "capture", "label": "现场数据", "icon": "📷"},
    {"id": "training", "label": "训练中心", "icon": "🔄"},
    {"id": "evaluation", "label": "验证中心", "icon": "📊"},
    {"id": "production", "label": "生产运行", "icon": "⚙️"},
    {"id": "device_config", "label": "设备配置", "icon": "🔧"},
    {"id": "field_workflow", "label": "现场交付流程", "icon": "🚀"},
    {"id": "hybrid_retest", "label": "混合复检", "icon": "🔬"},
    {"id": "benchmark", "label": "压测中心", "icon": "📈"},
    {"id": "reports", "label": "报告中心", "icon": "📝"},
    {"id": "log_center", "label": "日志中心", "icon": "📋"},
    {"id": "backup", "label": "备份恢复", "icon": "💾"},
    {"id": "settings", "label": "系统设置", "icon": "⚙️"},
    {"id": "help", "label": "帮助", "icon": "❓"},
]
