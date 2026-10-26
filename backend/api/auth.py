import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.core.cache import cache
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

logger = logging.getLogger(__name__)

User = get_user_model()


def _user_payload(user):
    return {
        "username": user.get_username(),
        "email": user.email,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


def _resolve_login_identifier(identifier):
    """The SPA login field accepts either the email (the USERNAME_FIELD) or the
    plain username; map a bare username to its email so authenticate() works."""
    if not identifier or "@" in identifier or User.USERNAME_FIELD == "username":
        return identifier
    try:
        return User.objects.get(username=identifier).get_username()
    except User.DoesNotExist:
        return identifier


def _client_ip(request):
    """Best-effort client address for rate limiting.

    REMOTE_ADDR is the socket peer. X-Forwarded-For is only trusted when it is
    present AND the peer is the local proxy — otherwise a client could pick its
    own bucket by sending a fake header, which defeats the throttle entirely.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded and request.META.get("REMOTE_ADDR") in getattr(settings, "TRUSTED_PROXIES", {"127.0.0.1", "::1"}):
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class LoginRateThrottle(AnonRateThrottle):
    """按 IP 限制登录尝试次数。

    原版没有任何限流：`REST_FRAMEWORK` 不配 DEFAULT_THROTTLE_CLASSES，登录
    接口也是不加限制的，口令强度只靠 AUTH_PASSWORD_VALIDATORS。对公网实例
    这意味着可以无限次爆破。

    这里按 IP 计数，用缓存后端（默认 locmem，多进程部署请配 Redis/Memcached，
    否则每个 worker 各算各的）。scope 名与 settings 的 DEFAULT_THROTTLE_RATES
    里的 "login" 对应。
    """

    scope = "login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": _client_ip(request)}


# 失败一次记一笔（成功不清零）：爆破的特征是"同一 IP 大量失败"，
# 只要能登进来就说明不是爆破，所以成功后清零反而更精确。见 login()。
FAILURE_KEY = "wigos:login-failures:{ip}"
FAILURE_WINDOW = 900  # 15 分钟
FAILURE_LIMIT = 10


def _failures(ip):
    return cache.get(FAILURE_KEY.format(ip=ip), 0)


def _record_failure(ip):
    key = FAILURE_KEY.format(ip=ip)
    try:
        # incr 在 key 不存在时（部分后端）抛 ValueError，先 add 再 incr。
        cache.add(key, 0, FAILURE_WINDOW)
        count = cache.incr(key)
    except (ValueError, NotImplementedError):
        count = _failures(ip) + 1
        cache.set(key, count, FAILURE_WINDOW)
    return count


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request):
    """Set the csrftoken cookie so the SPA can echo it in the X-CSRFToken header
    on subsequent unsafe (POST/PUT) requests."""
    return Response({"detail": "CSRF cookie set."})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login(request):
    ip = _client_ip(request)
    if _failures(ip) >= FAILURE_LIMIT:
        # 401 而不是 429：不让攻击者从状态码分辨"是口令错了还是被锁了"。
        # 但返回的文案说明"稍后再试"，正常用户不会困惑。
        return Response(
            {"detail": "Too many failed sign-in attempts. Try again in a few minutes."},
            status=429,
        )

    identifier = _resolve_login_identifier(request.data.get("username"))
    user = authenticate(request, username=identifier, password=request.data.get("password"))
    if user is None:
        count = _record_failure(ip)
        logger.warning("Failed sign-in for %r from %s (%d in window)", identifier, ip, count)
        return Response({"detail": "Invalid username or password."}, status=401)

    # 成功即清零：这条计数器只用来找爆破，不用来累计历史。
    cache.delete(FAILURE_KEY.format(ip=ip))
    django_login(request, user)  # sets the sessionid cookie, rotates the CSRF token
    return Response(_user_payload(user))


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    django_logout(request)
    return Response(status=204)


@api_view(["GET"])
@permission_classes([AllowAny])
def me(request):
    if not request.user.is_authenticated:
        return Response({"detail": "Not authenticated."}, status=401)
    return Response(_user_payload(request.user))