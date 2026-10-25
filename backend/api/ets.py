"""方案 5.4：与目录侧同一套 pywmdr ETS 的自检入口。

目录（wmo-resource-catalogue）用 pywmdr ETS 判定一条 WMDR2 记录合不合规。
节点如果只用自己的一套 schema 去判，就会出现"节点认为合格、目录判为不合格"
的口径差异。所以发布前应当跑同一套 ETS。

两个前提，缺一个就自动降级（不影响发布流程）：

1. **pywmdr 已安装**——它要求 Python >= 3.12（本项目的容器镜像正是
   python:3.12-slim，但本地开发环境常是 3.11，所以设为可选依赖，见
   ``requirements-ets.txt``）；
2. **bundle 缓存已就绪**——ETS 需要码表快照，执行 ``pywmdr bundle sync``
   下载到 ``~/.pywmdr/``。没有缓存时返回明确的提示，而不是抛异常。

降级时调用方拿到的结构里 ``available`` 为 False，``reason`` 说明缺什么；
此时应退回 api/rules.py 的业务规则 + 本地 jsonschema 校验。
"""
import logging

logger = logging.getLogger(__name__)

__all__ = ["run_ets", "ets_available", "MISSING_PYWMDR", "MISSING_BUNDLE"]

MISSING_PYWMDR = "pywmdr is not installed (it needs Python >= 3.12); " \
                 "see backend/requirements-ets.txt"
MISSING_BUNDLE = "pywmdr bundle cache is missing; run 'pywmdr bundle sync' " \
                 "to download the WMDS codelists and the WMDR2 schema"


def _bundle_ready() -> bool:
    from pywmdr.bundle import WMDR2_FILES
    schema = WMDR2_FILES / "wmdr2-bundled.json"
    return schema.exists()


def ets_available():
    """返回 (ok, reason)。不会抛异常。"""
    try:
        import pywmdr.wmdr2.ets  # noqa: F401
    except ImportError:
        return False, MISSING_PYWMDR
    try:
        if not _bundle_ready():
            return False, MISSING_BUNDLE
    except Exception as exc:  # pragma: no cover - 环境异常
        return False, f"pywmdr bundle check failed: {exc}"
    return True, None


def run_ets(record):
    """对单条记录跑 ETS，返回报告字典。

    成功时结构即 pywmdr 原生的 ets_report（含 summary 与逐项 tests），外加
    ``available: True``。不可用时返回 ``{"available": False, "reason": ...}``，
    与成功时的键名保持一致，调用方只需看 ``available``。
    """
    ok, reason = ets_available()
    if not ok:
        logger.info("ETS skipped: %s", reason)
        return {"available": False, "reason": reason}

    try:
        from pywmdr.wmdr2.ets import WMDR2TestSuite
        report = WMDR2TestSuite(record).run_tests()
    except Exception as exc:  # pragma: no cover - ETS 自身异常
        logger.exception("ETS run failed")
        return {"available": False, "reason": f"ETS run failed: {exc}"}

    report = dict(report)
    report["available"] = True
    report["passed"] = report.get("summary", {}).get("FAILED", 0) == 0
    return report
