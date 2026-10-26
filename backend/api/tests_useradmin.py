"""用户管理的纯逻辑单元测试（不碰数据库）。

    python manage.py test api.tests_useradmin

需要数据库的部分（列表、建号、删号、改密）在 tests_api 里由真机跑；这里只覆盖
能在 SimpleTestCase 下运行的三块：密码强度、请求体解析、自锁保护。
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from .useradmin import account_payload, guard_self, is_guardian_placeholder, password_errors

User = get_user_model()


class FakeUser:
    """最小可用的 user 替身：guard_self 只看 pk 与 is_authenticated。"""

    def __init__(self, pk, is_authenticated=True, is_staff=True, username="", email=""):
        self.pk = pk
        self.is_authenticated = is_authenticated
        self.is_staff = is_staff
        self.username = username
        self.email = email


class PasswordStrengthTests(SimpleTestCase):
    def test_empty_password_rejected(self):
        self.assertTrue(password_errors(""))
        self.assertTrue(password_errors(None))

    def test_non_string_password_rejected(self):
        self.assertTrue(password_errors(12345))

    def test_all_digits_rejected(self):
        """NumericPasswordValidator：纯数字不能当密码。"""
        self.assertTrue(password_errors("1234567890"))

    def test_common_password_rejected(self):
        self.assertTrue(password_errors("password"))

    def test_too_short_rejected(self):
        self.assertTrue(password_errors("Ab1"))

    def test_reasonable_password_accepted(self):
        self.assertEqual(password_errors("Wigos-node-42!"), [])

    def test_similarity_to_the_user_is_caught(self):
        """UserAttributeSimilarityValidator：密码不能就是账号名。

        该校验器要读 ``user._meta``，所以这里用未保存的真实模型实例（构造
        模型不查库，SimpleTestCase 允许）。
        """
        user = User(username="wigosoperator", email="operator@example.org")
        self.assertTrue(password_errors("wigosoperator", user))


class AccountPayloadTests(SimpleTestCase):
    def test_requires_username_and_email_to_create(self):
        payload, errors = account_payload({"username": "ann"})
        self.assertEqual(payload.get("username"), "ann")
        self.assertTrue(errors)  # email missing

    def test_creates_with_both_fields(self):
        payload, errors = account_payload({"username": "ann", "email": "ann@example.org"})
        self.assertEqual(payload, {"username": "ann", "email": "ann@example.org"})
        self.assertEqual(errors, [])

    def test_partial_update_does_not_demand_anything(self):
        payload, errors = account_payload({"is_active": False}, partial=True)
        self.assertEqual(payload, {"is_active": False})
        self.assertEqual(errors, [])

    def test_blank_values_are_not_written(self):
        """清空 username 会被当成"没传"，而不是把账号名改成空字符串。"""
        payload, _ = account_payload({"username": "   "}, partial=True)
        self.assertNotIn("username", payload)

    def test_group_name_may_be_a_plain_string(self):
        payload, _ = account_payload({"groups": "nfps_Switzerland"})
        self.assertEqual(payload["groups"], ["nfps_Switzerland"])

    def test_group_list_is_trimmed(self):
        payload, _ = account_payload({"groups": [" nfps_Brazil ", "", None]})
        self.assertEqual(payload["groups"], ["nfps_Brazil"])

    def test_group_of_the_wrong_type_is_an_error(self):
        payload, errors = account_payload({"groups": 7})
        self.assertNotIn("groups", payload)
        self.assertTrue(errors)

    def test_non_dict_body_is_ignored(self):
        payload, errors = account_payload("nonsense")
        self.assertEqual(payload, {})
        self.assertTrue(errors)

    def test_flags_are_coerced_to_booleans(self):
        payload, _ = account_payload({"is_staff": "yes", "is_active": 0}, partial=True)
        self.assertTrue(payload["is_staff"])
        self.assertFalse(payload["is_active"])


class GuardSelfTests(SimpleTestCase):
    def test_deleting_yourself_is_refused(self):
        me = FakeUser(1)
        self.assertEqual(guard_self(me, me, "delete"), "You cannot delete your own account.")

    def test_deactivating_yourself_is_refused(self):
        me = FakeUser(1)
        self.assertEqual(guard_self(me, me, "deactivate"), "You cannot deactivate your own account.")

    def test_dropping_your_own_staff_flag_is_refused(self):
        me = FakeUser(1)
        self.assertEqual(guard_self(me, me, "unstaff"), "You cannot remove your own node administrator role.")

    def test_somebody_else_is_fair_game(self):
        me = FakeUser(1)
        other = FakeUser(2)
        for action in ("delete", "deactivate", "unstaff"):
            self.assertIsNone(guard_self(me, other, action), action)

    def test_anonymous_actor_is_not_blocked(self):
        """未登录请求走不到这里（权限先拦），但函数本身不该因此崩。"""
        anon = FakeUser(1, is_authenticated=False)
        self.assertIsNone(guard_self(anon, FakeUser(2), "delete"))

    def test_unrelated_action_is_allowed(self):
        me = FakeUser(1)
        self.assertIsNone(guard_self(me, me, "update"))


class GuardianPlaceholderTests(SimpleTestCase):
    """guardian 的匿名用户行不能被当成真实账号。

    它用 USERNAME_FIELD 当键建记录，本项目 USERNAME_FIELD 是 email，所以那条
    记录长成 username='' / email='AnonymousUser'。真机上的用户表里确实出现过
    这样一行（0016 迁移负责清掉），这里守住别再让它出现在列表与详情接口里。
    """

    def test_the_row_guardian_actually_creates_is_recognised(self):
        self.assertTrue(is_guardian_placeholder(FakeUser(None, username="", email="AnonymousUser")))

    def test_a_real_account_is_not_flagged(self):
        self.assertFalse(is_guardian_placeholder(FakeUser(7, username="obs1", email="obs1@example.org")))

    def test_a_username_less_account_with_a_normal_email_is_not_flagged(self):
        """只有 username 为空还不够 —— email 必须正好是那个哨兵值。"""
        self.assertFalse(is_guardian_placeholder(FakeUser(8, username="", email="nobody@example.org")))
