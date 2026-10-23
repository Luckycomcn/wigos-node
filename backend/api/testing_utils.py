"""Helpers shared by the test modules.

The sample records live in ``test_data/`` next to ``backend/`` and are mounted
at ``/test_data`` inside the container, so the path must be resolved at run time
instead of hard-coded -- otherwise the suite only runs inside docker.
"""
from pathlib import Path

from django.conf import settings


def test_data_path(name):
    """Absolute path of a file in the repository's ``test_data`` directory."""
    candidates = [
        Path(settings.BASE_DIR).parent / "test_data" / name,  # backend/../test_data
        Path("/test_data") / name,                            # docker-compose mount
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    searched = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"找不到测试数据 {name}（已尝试: {searched}）")


def load_test_json(name):
    import json

    with open(test_data_path(name), encoding="utf-8") as handle:
        return json.load(handle)
