#!/bin/sh
set -e

python manage.py migrate --noinput

# 原版是无参调用 `python manage.py populate_codelists`。这条命令在 Python ≤3.11
# 上必然崩：argparse 的 `nargs="*"` 配 `choices` 时，空列表会被当成非法取值。
# 作者靠 python:3.12-slim 镜像侥幸绕过；一旦运维换系统 Python 部署，
# 容器根本起不来，报错还是 argparse 的 usage 提示，指不到真正原因。
#
# 这里显式传 --if-missing：码表已经缓存过就跳过，不联网重拉。
# 离线环境也就不会因为访问 codes.wmo.int 失败而卡在启动阶段。
if [ "${WIGOS_SKIP_CODELISTS:-false}" = "true" ]; then
    echo "entrypoint: 跳过码表刷新（WIGOS_SKIP_CODELISTS=true）"
else
    python manage.py populate_codelists --if-missing || {
        echo "entrypoint: 码表刷新失败，继续启动。可能是离线环境。"
        echo "entrypoint: 已有缓存仍可用；需要补齐请联网后手工执行"
        echo "            python manage.py populate_codelists --if-missing"
    }
fi

python manage.py collectstatic --noinput

exec "$@"