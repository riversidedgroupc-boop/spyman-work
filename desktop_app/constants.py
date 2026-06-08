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
NAV_ITEM_MIN_HEIGHT = 48
NAV_ITEM_MAX_HEIGHT = 56

NAV_ITEMS: list[dict[str, str]] = [
    {"id": "workbench", "label": "项目工作台", "icon": "fa5s.th-large"},
    {"id": "device_setup", "label": "设备配置", "icon": "fa5s.cogs"},
    {"id": "site_capture", "label": "现场采集", "icon": "fa5s.camera"},
    {"id": "sample_review", "label": "样本复核", "icon": "fa5s.search"},
    {"id": "model_iteration", "label": "模型训练", "icon": "fa5s.brain"},
    {"id": "hybrid_runtime", "label": "联合检测", "icon": "fa5s.project-diagram"},
    {"id": "performance", "label": "性能验证", "icon": "fa5s.tachometer-alt"},
    {"id": "delivery", "label": "报告交付", "icon": "fa5s.file-alt"},
    {"id": "maintenance", "label": "系统维护", "icon": "fa5s.tools"},
    {"id": "auto_focus", "label": "换型自动对焦", "icon": "fa5s.crosshairs"},
]
