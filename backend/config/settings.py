import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",")

INSTALLED_APPS = [
    "api.apps.ApiConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django.contrib.postgres",
    "guardian"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "app_db"),
        "USER": os.environ.get("POSTGRES_USER", "app_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "app_password"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = 'api.WIGOSNodeUser'

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Allow the SPA to send the session cookie on cross-origin API calls (used when
# the frontend talks to :8000 directly instead of through the Vite dev proxy).
CORS_ALLOW_CREDENTIALS = True

# Origins Django trusts for unsafe (POST/PUT/PATCH/DELETE) requests. The SPA runs
# on its own port and proxies to Django, so the browser's Origin header carries
# that port while Django only ever sees 127.0.0.1:800x. Without this list every
# write is rejected with "Origin checking failed" — and because curl does not
# send an Origin header at all, an API-only test suite never notices.
#
# The default used to hard-code :5173 (the demo track). That silently broke the
# i18n (:5174) and feature (:5175) tracks: reads worked, writes 403'd. Derive
# the origins from ALLOWED_HOSTS instead so a fresh port just works.
#
# ALLOWED_HOSTS='*' can't be enumerated (and the test runner appends
# 'testserver'), so fall back to loopback rather than ending up with an empty
# trust list — an empty list turns every browser write into a 403.
_TRACK_PORTS = (5173, 5174, 5175)
_HOST_NAMES = [
    host.strip()
    for host in ALLOWED_HOSTS
    if host.strip() and host.strip() not in {"*", "testserver"}
] or ["localhost", "127.0.0.1"]
_CSRF_DEFAULT = ",".join(
    f"http://{host}:{port}" for host in _HOST_NAMES for port in _TRACK_PORTS
)
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", _CSRF_DEFAULT).split(",")
    if origin.strip()
]

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", _CSRF_DEFAULT).split(",")
    if origin.strip()
]

# WIS2 Notification Messages (api/wnm.py): this node's WIS2 centre id, and the
# public web storage the announced record files are served from.
WNM_CENTRE_ID = os.environ.get("WNM_CENTRE_ID", "io-wis2dev-test-wigosnode")
WNM_STORAGE_URL = os.environ.get("WNM_STORAGE_URL", "https://wigosnode.test.wis2dev.io/webstorage")
# Where published record files are written, and an optional catalogue/broker
# endpoint the WNM is POSTed to (empty = local-only, offline safe).
WNM_STORAGE_DIR = os.environ.get("WNM_STORAGE_DIR", str(BASE_DIR / "webstorage"))
WNM_PUBLISH_URL = os.environ.get("WNM_PUBLISH_URL", "")

# 方案 5.5 发布链路：逗号分隔启用哪些投递通道，可选 http / mqtt / wis2node。
# 留空表示只本地发布（离线可用、不外发）。
#   http      —— 直连目录或中介端点，即原有的 WNM_PUBLISH_URL 行为
#   mqtt      —— 选项一：节点 → 本地代理 → 全局代理
#   wis2node  —— 选项二：节点 → 本国 WIS2 节点 → 全局代理
WNM_PUBLISH_STRATEGY = os.environ.get("WNM_PUBLISH_STRATEGY", "")

# 选项一：本地 MQTT 代理。留空时该通道跳过（不需要额外 pip 包也能跑）。
WIS2_BROKER_HOST = os.environ.get("WIS2_BROKER_HOST", "")
WIS2_BROKER_PORT = int(os.environ.get("WIS2_BROKER_PORT", "1883") or 1883)
WIS2_BROKER_USERNAME = os.environ.get("WIS2_BROKER_USERNAME", "")
WIS2_BROKER_PASSWORD = os.environ.get("WIS2_BROKER_PASSWORD", "")
WIS2_BROKER_TLS = os.environ.get("WIS2_BROKER_TLS", "false").lower() == "true"
WIS2_TOPIC_TEMPLATE = os.environ.get("WIS2_TOPIC_TEMPLATE", "origin/a/wigos/{centre_id}/metadata")

# 选项二：本国 WIS2 节点的接收端点（地址需与 WIS2 节点运维方确认）。
WIS2_NODE_URL = os.environ.get("WIS2_NODE_URL", "")
WIS2_NODE_TOKEN = os.environ.get("WIS2_NODE_TOKEN", "")

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    # DRF 默认把 `?format=` 当成「选渲染器」的开关（URL_FORMAT_OVERRIDE）。本项目的
    # 导出接口自己用 `?format=csv|json|xml` 表示文件格式，两个含义撞在一起：
    # 请求 `?format=xml` 时 DRF 先去找 XMLRenderer，没配就抛 404，视图根本进不去。
    # 关掉这个开关，`?format=` 就只是个普通查询参数。
    "URL_FORMAT_OVERRIDE": None,
}

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',  # this is default
    'guardian.backends.ObjectPermissionBackend',
)

# django-guardian 会为「匿名用户」准备一条真实用户记录，供 get_objects_for_user
# 在未登录时也能跑通对象权限查询。它建这条记录用的键是 USERNAME_FIELD，而本项目的
# USERNAME_FIELD 是 email —— 于是每次 migrate 都会往用户表里塞一行
# username='' / email='AnonymousUser' 的空账号。用户管理面板上线后，这一行就成了一
# 个能看见、改不了、也不该存在的"用户"。
#
# 本项目不需要这个机制：匿名用户在 stations.editable_station_ids() 里已经提前返回
# 空集合，永远不会走到 guardian 的对象权限查询。设成 None 就关闭了 post_migrate
# 里的自动创建，也关掉了 get_anonymous_user() 的惰性重建。
ANONYMOUS_USER_NAME = None
