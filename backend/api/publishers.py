"""
方案 5.5：发布链路。

架构会议给了两种参与选项，本节点同时实现、按运行策略择一（或并行）启用：

    选项一（节点为主要发布方）
        节点 → 本地代理 → 全局代理
        MQTT 发布到 topic ``origin/a/wigos/<centre-id>/metadata``。
        节点直接参与 WIS2 数据面，权威性与可追溯性最强。

    选项二（WIS2 节点作为中介发布方）
        节点 → 本国 WIS2 节点 → 全局代理
        把 WNM 交给本国 WIS2 节点的接收端点，由它转发到全局代理。
        复用既有 WIS2 节点基础设施与运维体系，降低节点侧出站要求。

    另有 http 通道：直接把 WNM POST 给某个目录/中介端点。这是仓库原有的
    ``WNM_PUBLISH_URL`` 行为，保留它以便在没有 MQTT 代理的环境下也能联调。

两种选项下，目录侧消费的都是 ``cache/a/wigos/<centre-id>/metadata``，
对下游无差异 —— 所以换了这里的实现不会影响订阅方。

每条通道独立返回成败，互不影响：一条通道挂掉不该让整次发布失败。
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# 可选的通道名，与 WNM_PUBLISH_STRATEGY 环境变量的取值一一对应。
STRATEGIES = ("http", "mqtt", "wis2node")

WIS2_TOPIC_TEMPLATE = "origin/a/wigos/{centre_id}/metadata"


class DeliveryResult:
    """一次投递的结果。之所以不用异常，是因为单通道失败不是整次发布失败。"""

    __slots__ = ("channel", "ok", "detail")

    def __init__(self, channel, ok, detail=""):
        self.channel = channel
        self.ok = bool(ok)
        self.detail = detail

    def as_dict(self):
        return {"channel": self.channel, "ok": self.ok, "detail": self.detail}

    def __repr__(self):  # pragma: no cover - 调试用
        return f"<DeliveryResult {self.channel} ok={self.ok} {self.detail!r}>"


def configured_strategies():
    """读 WNM_PUBLISH_STRATEGY，返回去重且有序的通道名列表。

    留空表示不发到任何外部端点（本地发布，离线可用）。非法值一律忽略并记录，
    不因为配置拼错就悄悄什么都不发。
    """
    raw = getattr(settings, "WNM_PUBLISH_STRATEGY", "") or ""
    wanted = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not wanted:
        # 向后兼容：老配置只有 WNM_PUBLISH_URL，等于隐式启用 http 通道。
        if getattr(settings, "WNM_PUBLISH_URL", ""):
            return ["http"]
        return []
    known, unknown = [], []
    for name in wanted:
        (known if name in STRATEGIES else unknown).append(name)
    if unknown:
        logger.warning("Ignoring unknown publish strategies %s (known: %s)", unknown, ", ".join(STRATEGIES))
    # 保持配置顺序去重
    return list(dict.fromkeys(known))


def topic_for(centre_id=None):
    """选项一使用的 WIS2 发布 topic。"""
    template = getattr(settings, "WIS2_TOPIC_TEMPLATE", WIS2_TOPIC_TEMPLATE)
    centre = centre_id or getattr(settings, "WNM_CENTRE_ID", "unknown")
    return template.format(centre_id=centre)


# ---------------------------------------------------------------------------
# 选项一：MQTT → 本地代理 → 全局代理
# ---------------------------------------------------------------------------

def publish_mqtt(wnm):
    """把 WNM 发布到 WIS2 topic。返回 (ok, detail)。"""
    host = getattr(settings, "WIS2_BROKER_HOST", "")
    if not host:
        return False, "WIS2_BROKER_HOST is not configured"
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return False, "paho-mqtt is not installed (pip install paho-mqtt)"

    port = int(getattr(settings, "WIS2_BROKER_PORT", 1883) or 1883)
    username = getattr(settings, "WIS2_BROKER_USERNAME", "") or None
    password = getattr(settings, "WIS2_BROKER_PASSWORD", "") or None
    use_tls = bool(getattr(settings, "WIS2_BROKER_TLS", False))
    topic = topic_for()
    try:
        payload = json.dumps(wnm, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        return False, f"WNM is not serialisable: {exc}"

    client = None
    try:
        # paho 2.x 要求显式给出 callback API 版本；1.x 不接受这个参数。
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            client = mqtt.Client()
        if username:
            client.username_pw_set(username, password)
        if use_tls:
            client.tls_set()
        client.connect(host, port, keepalive=60)
        client.loop_start()
        info = client.publish(topic, payload, qos=1)
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            return False, f"message to {topic} was not acknowledged"
        return True, f"{topic} qos=1"
    except Exception as exc:  # pragma: no cover - 网络分支
        logger.warning("MQTT publish to %s failed: %s", topic, exc)
        return False, str(exc)
    finally:
        if client is not None:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:  # pragma: no cover
                pass


# ---------------------------------------------------------------------------
# 选项二：交给本国 WIS2 节点
# ---------------------------------------------------------------------------

def publish_wis2node(wnm):
    """把 WNM 推送给本国 WIS2 节点，由它转发到全局代理。返回 (ok, detail)。

    端点地址经 WIS2_NODE_URL 配置。本体 {"operation"?, "wnm": ...} 还是裸 WNM
    取决于节点侧的接收契约 —— 后者更贴近 wis2box 的 pub/sub 语义，因此默认发
    裸 WNM，需要包装时改包一层即可。
    """
    url = getattr(settings, "WIS2_NODE_URL", "")
    if not url:
        return False, "WIS2_NODE_URL is not configured"
    try:
        import requests
    except ImportError:  # pragma: no cover - requests 是硬依赖
        return False, "requests is not installed"

    headers = {"Content-Type": "application/json"}
    token = getattr(settings, "WIS2_NODE_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.post(url, json=wnm, headers=headers, timeout=15)
    except Exception as exc:
        logger.warning("WIS2 node delivery to %s failed: %s", url, exc)
        return False, str(exc)
    if response.status_code >= 400:
        body = ""
        try:
            body = response.text[:200]
        except Exception:  # pragma: no cover
            pass
        return False, f"WIS2 node returned {response.status_code} {body}".strip()
    return True, f"{url} → {response.status_code}"


# ---------------------------------------------------------------------------
# http：直连目录/中介端点（原有行为，保留）
# ---------------------------------------------------------------------------

def publish_http(wnm):
    url = getattr(settings, "WNM_PUBLISH_URL", "")
    if not url:
        return False, "WNM_PUBLISH_URL is not configured"
    try:
        import requests
    except ImportError:  # pragma: no cover
        return False, "requests is not installed"
    try:
        response = requests.post(url, json=wnm, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("HTTP delivery to %s failed: %s", url, exc)
        return False, str(exc)
    return True, f"{url} → {response.status_code}"


_HANDLERS = {
    "http": publish_http,
    "mqtt": publish_mqtt,
    "wis2node": publish_wis2node,
}


def deliver(wnm):
    """按 WNM_PUBLISH_STRATEGY 依次投递。返回 DeliveryResult 列表。

    每条通道独立捕获异常：broker 不通不该连带让已成功的 HTTPS 推送看起来失败。
    """
    results = []
    for name in configured_strategies():
        handler = _HANDLERS.get(name)
        if handler is None:  # pragma: no cover - configured_strategies 已过滤
            results.append(DeliveryResult(name, False, f"no handler for '{name}'"))
            continue
        ok, detail = handler(wnm)
        results.append(DeliveryResult(name, ok, detail))
    return results


def delivered_channels(results):
    return [item.channel for item in results if item.ok]
