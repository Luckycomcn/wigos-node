"""WIGOS Identifier（WSI）解析与比较。

格式：``<scheme>-<issuer>-<series>-<number>[-<local>]``

* ``scheme`` 目前固定为 ``0``（WIGOS），为前向兼容仍解析但不参与比对；
* ``issuer`` 即 centre-id 的数字段，如 ``20000``、``20001``；
* ``series``/``number`` 是该 centre 内的系列与序号，注册表按这两段授权；
* ``local`` 是本地扩展段，可有可无。

纯函数、不依赖 Django，可单独单测。
"""
from typing import Optional, Tuple

__all__ = ["parse_wsi", "format_wsi", "normalise_wsi", "is_well_formed"]

WSI_PARTS_MIN = 4
WSI_PARTS_MAX = 5


def parse_wsi(wsi) -> Optional[Tuple[int, int, int, Optional[str]]]:
    """解析为 ``(issuer, series, number, local)``；格式不符返回 None。

    接受 str / int 形态的 issuer 段，忽略首尾空白。不接受带前导零以外的
    怪异写法，因为下游会拿这些数字做区间比较。
    """
    if not isinstance(wsi, str):
        return None
    parts = wsi.strip().split("-")
    if not (WSI_PARTS_MIN <= len(parts) <= WSI_PARTS_MAX):
        return None
    if parts[0].strip() != "0":  # scheme
        return None
    try:
        issuer = int(parts[1])
        series = int(parts[2])
        number = int(parts[3])
    except (TypeError, ValueError):
        return None
    local = parts[4].strip() if len(parts) == WSI_PARTS_MAX and parts[4].strip() else None
    if issuer < 0 or series < 0 or number < 0:
        return None
    return issuer, series, number, local


def format_wsi(issuer: int, series: int, number: int, local: Optional[str] = None) -> str:
    tail = f"-{local}" if local else ""
    return f"0-{issuer}-{series}-{number}{tail}"


def normalise_wsi(wsi) -> Optional[str]:
    """规范化表示，用于去重与比较；无法解析时返回 None。"""
    parsed = parse_wsi(wsi)
    if parsed is None:
        return None
    return format_wsi(*parsed)


def is_well_formed(wsi) -> bool:
    return parse_wsi(wsi) is not None
