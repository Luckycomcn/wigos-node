"""方案 5.5 发布链路：通道选择、topic 构造、各通道独立的成败处理。

全部用例离线可跑：真实网络分支用假的 paho / requests 模块顶替，
重点验证「配置怎么翻译成投递行为」而不是三次握手本身。
"""
import json
import sys
import types
from unittest import mock

from django.test import SimpleTestCase, override_settings

from . import publishers


def _wnm():
    return {"properties": {"data_id": "wmdr2/test/0-20000-0-1/v1"}, "links": [{"href": "http://x/y.json"}]}


class StrategyParsingTests(SimpleTestCase):
    @override_settings(WNM_PUBLISH_STRATEGY="")
    def test_empty_strategy_is_local_only(self):
        self.assertEqual(publishers.configured_strategies(), [])

    @override_settings(WNM_PUBLISH_STRATEGY="", WNM_PUBLISH_URL="http://cat/inbox")
    def test_legacy_publish_url_implicitly_enables_http(self):
        """老配置只有 WNM_PUBLISH_URL，不能因为升级就悄悄停止外发。"""
        self.assertEqual(publishers.configured_strategies(), ["http"])

    @override_settings(WNM_PUBLISH_STRATEGY="mqtt, wis2node")
    def test_whitespace_and_order_preserved(self):
        self.assertEqual(publishers.configured_strategies(), ["mqtt", "wis2node"])

    @override_settings(WNM_PUBLISH_STRATEGY="mqtt,MQTT,http")
    def test_lowercased_and_deduplicated(self):
        self.assertEqual(publishers.configured_strategies(), ["mqtt", "http"])

    @override_settings(WNM_PUBLISH_STRATEGY="mqtt,smoke-signal,http")
    def test_unknown_strategy_ignored_not_fatal(self):
        """拼错一个通道名，应该忽略它而保留其它，不是整个都不发。"""
        with self.assertLogs(level="WARNING"):
            strategies = publishers.configured_strategies()
        self.assertEqual(strategies, ["mqtt", "http"])


class TopicTests(SimpleTestCase):
    @override_settings(WNM_CENTRE_ID="cn-cma-wigos")
    def test_topic_carries_centre_id(self):
        self.assertEqual(publishers.topic_for(), "origin/a/wigos/cn-cma-wigos/metadata")

    def test_explicit_centre_id_wins(self):
        self.assertEqual(publishers.topic_for("x-y"), "origin/a/wigos/x-y/metadata")

    @override_settings(WIS2_TOPIC_TEMPLATE="cache/a/wigos/{centre_id}/metadata")
    def test_template_is_configurable(self):
        self.assertEqual(publishers.topic_for("z"), "cache/a/wigos/z/metadata")


class UnconfiguredChannelTests(SimpleTestCase):
    """通道没配置就该明确说没配置，而不是静默跳过或抛异常。"""

    @override_settings(WIS2_BROKER_HOST="")
    def test_mqtt_without_host(self):
        ok, detail = publishers.publish_mqtt(_wnm())
        self.assertFalse(ok)
        self.assertIn("WIS2_BROKER_HOST", detail)

    @override_settings(WIS2_BROKER_HOST="broker")
    def test_mqtt_without_paho_installed(self):
        """本机没装 paho 也不能让发布视图 500。"""
        with mock.patch.dict(sys.modules, {"paho.mqtt.client": None}):
            ok, detail = publishers.publish_mqtt(_wnm())
        self.assertFalse(ok)
        self.assertIn("paho-mqtt", detail)

    @override_settings(WIS2_NODE_URL="")
    def test_wis2node_without_url(self):
        self.assertFalse(publishers.publish_wis2node(_wnm())[0])

    @override_settings(WNM_PUBLISH_URL="")
    def test_http_without_url(self):
        self.assertFalse(publishers.publish_http(_wnm())[0])


class _FakeInfo:
    def __init__(self, published):
        self._published = published

    def wait_for_publish(self, timeout=None):
        return None

    def is_published(self):
        return self._published


class _FakeClient:
    """替身 paho Client，记录连接与发布参数。"""

    instances = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.connect_args = None
        self.published = []
        self.username = None
        self.tls = False
        self.loops = 0
        self.disconnected = False
        self.publish_result = True
        self.raise_on_connect = None
        _FakeClient.instances.append(self)

    def username_pw_set(self, user, pwd):
        self.username = (user, pwd)

    def tls_set(self, *args, **kwargs):
        self.tls = True

    def connect(self, host, port, keepalive=None):
        if self.raise_on_connect:
            raise self.raise_on_connect
        self.connect_args = (host, port)

    def loop_start(self):
        self.loops += 1

    def loop_stop(self):
        self.loops -= 1

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))
        return _FakeInfo(self.publish_result)

    def disconnect(self):
        self.disconnected = True


def _install_fake_paho():
    """把假的 paho.mqtt.publish 模块插进 sys.modules。"""
    module = types.ModuleType("paho.mqtt.client")
    module.Client = _FakeClient
    module.CallbackAPIVersion = types.SimpleNamespace(VERSION2="v2")
    paho = types.ModuleType("paho")
    paho_mqtt = types.ModuleType("paho.mqtt")
    paho.mqtt = paho_mqtt
    paho_mqtt.client = module
    return {
        "paho": paho,
        "paho.mqtt": paho_mqtt,
        "paho.mqtt.client": module,
    }


class MqttDeliveryTests(SimpleTestCase):
    def setUp(self):
        _FakeClient.instances = []

    def test_publishes_to_topic_qos1(self):
        with mock.patch.dict(sys.modules, _install_fake_paho()), override_settings(
            WIS2_BROKER_HOST="broker", WNM_CENTRE_ID="cn-cma-wigos"
        ):
            ok, detail = publishers.publish_mqtt(_wnm())
        self.assertTrue(ok, detail)
        client = _FakeClient.instances[0]
        self.assertEqual(len(client.published), 1)
        topic, payload, qos = client.published[0]
        self.assertEqual(topic, "origin/a/wigos/cn-cma-wigos/metadata")
        self.assertEqual(qos, 1)
        self.assertEqual(json.loads(payload)["properties"]["data_id"], "wmdr2/test/0-20000-0-1/v1")

    def test_credentials_and_tls_applied(self):
        with mock.patch.dict(sys.modules, _install_fake_paho()), override_settings(
            WIS2_BROKER_HOST="broker", WIS2_BROKER_USERNAME="u", WIS2_BROKER_PASSWORD="p",
            WIS2_BROKER_TLS=True, WIS2_BROKER_PORT=8883,
        ):
            ok, detail = publishers.publish_mqtt(_wnm())
        self.assertTrue(ok, detail)
        client = _FakeClient.instances[0]
        self.assertEqual(client.username, ("u", "p"))
        self.assertTrue(client.tls)
        self.assertEqual(client.connect_args, ("broker", 8883))

    def test_client_is_always_closed(self):
        """异常也必须收好连接 —— 否则重连几轮就把 broker 连接数耗尽。"""
        with mock.patch.dict(sys.modules, _install_fake_paho()), override_settings(WIS2_BROKER_HOST="broker"):
            with mock.patch.object(_FakeClient, "connect", side_effect=OSError("no route")):
                publishers.publish_mqtt(_wnm())
        self.assertTrue(_FakeClient.instances[0].disconnected)

    def test_unacknowledged_message_reported_as_failure(self):
        with mock.patch.dict(sys.modules, _install_fake_paho()), override_settings(WIS2_BROKER_HOST="broker"):
            original = _FakeClient.__init__

            def broken_init(self, *args, **kwargs):
                original(self, *args, **kwargs)
                self.publish_result = False

            with mock.patch.object(_FakeClient, "__init__", broken_init):
                ok, detail = publishers.publish_mqtt(_wnm())
        self.assertFalse(ok)
        self.assertIn("not acknowledged", detail)


class Wis2NodeDeliveryTests(SimpleTestCase):
    def test_bearer_token_sent(self):
        captured = {}

        class Resp:
            status_code = 202
            text = ""

        def fake_post(url, json=None, headers=None, timeout=None):
            captured.update(url=url, json=json, headers=headers)
            return Resp()

        fake = types.ModuleType("requests")
        fake.post = fake_post
        with mock.patch.dict(sys.modules, {"requests": fake}), override_settings(
            WIS2_NODE_URL="https://wis2.cma.cn/publish", WIS2_NODE_TOKEN="t0k"
        ):
            ok, detail = publishers.publish_wis2node(_wnm())
        self.assertTrue(ok, detail)
        self.assertEqual(captured["url"], "https://wis2.cma.cn/publish")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer t0k")
        self.assertEqual(captured["json"]["properties"]["data_id"], "wmdr2/test/0-20000-0-1/v1")

    def test_error_status_surfaces_body(self):
        class Resp:
            status_code = 422
            text = "unprocessable: missing integrity"

        fake = types.ModuleType("requests")
        fake.post = lambda *a, **k: Resp()
        with mock.patch.dict(sys.modules, {"requests": fake}), override_settings(WIS2_NODE_URL="https://n/publish"):
            ok, detail = publishers.publish_wis2node(_wnm())
        self.assertFalse(ok)
        self.assertIn("422", detail)
        self.assertIn("missing integrity", detail)

    def test_network_error_captured(self):
        fake = types.ModuleType("requests")

        def boom(*a, **k):
            raise OSError("connection refused")

        fake.post = boom
        with mock.patch.dict(sys.modules, {"requests": fake}), override_settings(WIS2_NODE_URL="https://n/publish"):
            ok, detail = publishers.publish_wis2node(_wnm())
        self.assertFalse(ok)
        self.assertIn("connection refused", detail)


class DeliveryFanOutTests(SimpleTestCase):
    @override_settings(WNM_PUBLISH_STRATEGY="")
    def test_no_strategy_returns_empty(self):
        self.assertEqual(publishers.deliver(_wnm()), [])

    @override_settings(WNM_PUBLISH_STRATEGY="http,mqtt,wis2node")
    def test_one_failing_channel_does_not_mask_others(self):
        """这是分发层存在的全部理由：broker 挂了，HTTP 那一条照样算成功。"""
        results = publishers.deliver(_wnm())
        self.assertEqual([r.channel for r in results], ["http", "mqtt", "wis2node"])
        # 三个都未配置，所以都失败，但都被记录了 —— 不是抛异常中断
        self.assertTrue(all(not r.ok for r in results))
        self.assertEqual(publishers.delivered_channels(results), [])

    @override_settings(WNM_PUBLISH_STRATEGY="http,mqtt")
    def test_results_are_serialisable(self):
        payload = [item.as_dict() for item in publishers.deliver(_wnm())]
        # 发布响应里带了明细，必须能直接 JSON 化
        json.dumps(payload)
        self.assertEqual(payload[0]["channel"], "http")
        self.assertIn("detail", payload[0])
