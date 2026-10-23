"""F-9 的对外入口：发布前自检。

    POST /api/validate/            {"record": {...}}
    POST /api/validate/            {"records": [...]}
    可选 {"ets": true}             同时跑 pywmdr ETS（装了就跑，没装自动降级）
    可选 {"dry_run": true}         同上，仅为语义明确

返回逐条结果，结构固定：

    {
      "ok": bool,                  # 全部记录都没有 error
      "results": [
        {"index": 0, "id": "0-...", "ok": bool,
         "errors": [...], "warnings": [...],
         "ets": {...} | {"available": false, "reason": "..."}}
      ]
    }

与 /api/import/ 的 dry-run 是两件事：那里校验的是"能不能落库"，这里校验的是
"能不能发出去"，后者口径更严（业务规则 + 受控词表 + ETS）。
"""
import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import ets, rules

logger = logging.getLogger(__name__)


def check_one(record, run_ets=False):
    """对单条记录跑 业务规则 + 受控词表（+ 可选 ETS）。"""
    outcome = rules.check_record(record)
    result = {
        "id": record.get("id") if isinstance(record, dict) else None,
        "ok": outcome["ok"],
        "errors": outcome["errors"],
        "warnings": outcome["warnings"],
    }
    if run_ets:
        report = ets.run_ets(record)
        result["ets"] = report
        # ETS 是目录侧的口径：它说不合格，本地就不该认为可以发布
        if report.get("available") and not report.get("passed", True):
            result["ok"] = False
            result["errors"] = result["errors"] + [{
                "code": "ets",
                "rule": "pywmdr ETS",
                "severity": "error",
                "messages": [
                    f"{t.get('code')}: {t.get('id', '').rsplit('/', 1)[-1]} "
                    f"{'; '.join(t.get('errors') or [t.get('message')])}"
                    for t in report.get("tests", []) if t.get("code") == "FAILED"
                ],
            }]
    return result


class ValidateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        run_ets = bool(body.get("ets", False))

        records = body.get("records")
        if records is None:
            records = [body.get("record")]
        if not isinstance(records, list) or not records or any(not isinstance(r, dict) for r in records):
            return Response(
                {"detail": 'Expected {"record": {...}} or {"records": [{...}, ...]}.'},
                status=400,
            )
        if len(records) > 200:
            return Response({"detail": "At most 200 records per request."}, status=400)

        results = [check_one(record, run_ets=run_ets) for record in records]
        for index, result in enumerate(results):
            result["index"] = index
        return Response({
            "ok": all(r["ok"] for r in results),
            "checked": len(results),
            "ets_requested": run_ets,
            "ets_available": ets.ets_available()[0] if run_ets else None,
            "results": results,
        })
