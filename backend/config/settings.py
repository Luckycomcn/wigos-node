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

CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

# Allow the SPA to send the session cookie on cross-origin API calls (used when
# the frontend talks to :8000 directly instead of through the Vite dev proxy).
CORS_ALLOW_CREDENTIALS = True

# Origins Django trusts for unsafe (POST/PUT) requests. The Vite dev proxy keeps
# the browser on :5173 while forwarding to Django, so that origin must be listed
# or every login/write request is rejected with 403.
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

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
}

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',  # this is default
    'guardian.backends.ObjectPermissionBackend',
)
