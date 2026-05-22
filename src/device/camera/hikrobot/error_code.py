"""MVS SDK error code to human-readable Chinese message mapping."""
from __future__ import annotations

ERROR_MAP: dict[int, str] = {
    0x00000000: "成功",
    0x80000001: "错误或无效的句柄",
    0x80000002: "不支持的相机操作",
    0x80000003: "函数参数错误",
    0x80000004: "函数调用顺序错误",
    0x80000005: "不允许的函数调用",
    0x80000006: "资源申请失败",
    0x80000007: "无权限",
    0x80000008: "超时",
    0x80000009: "缓冲区不足",
    0x8000000A: "无效的地址",
    0x8000000B: "重复操作",
    0x8000000C: "操作被取消",
    0x8000000D: "数据不足",
    0x80001000: "通用异常",
    0x80001001: "GigE 网络异常",
    0x80001002: "设备未连接",
    0x80001003: "设备已被其他程序占用",
    0x80001004: "设备断开连接",
    0x80001005: "设备连接失败",
    0x80001006: "取流失败",
    0x80001007: "参数设置失败",
    0x80001008: "参数读取失败",
    0x80001009: "触发失败",
    0x8000100A: "采集未开始",
    0x8000100B: "写入参数失败",
    0x8000100C: "读取参数失败",
}


def get_error_message(error_code: int) -> str:
    """Return Chinese error message for an MVS SDK error code."""
    return ERROR_MAP.get(error_code, f"未知错误 (0x{error_code:08X})")
