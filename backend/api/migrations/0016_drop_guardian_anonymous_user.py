"""删掉 django-guardian 遗留在用户表里的匿名用户行。

guardian 用 ``USERNAME_FIELD`` 当键去建那条「匿名用户」记录，而本项目把
``USERNAME_FIELD`` 设成了 ``email``，于是每次 migrate 都会多出一行
``username='' / email='AnonymousUser'``。它没有可用密码、不属于任何人，却会
出现在用户管理列表里。

设置层已经把 ``ANONYMOUS_USER_NAME`` 关掉（不再新建），这条迁移负责把已经
建出来的那行清掉。只按「username 为空 + email 正好是那个哨兵值」匹配，不会
误删真实账号。
"""

from django.db import migrations

SENTINEL = "AnonymousUser"


def drop_placeholder(apps, schema_editor):
    User = apps.get_model("api", "WIGOSNodeUser")
    User.objects.filter(username="", email=SENTINEL).delete()


def noop(apps, schema_editor):
    """无需回滚：这行是垃圾数据，重新出现也没有意义。"""


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0015_station_status"),
    ]

    operations = [
        migrations.RunPython(drop_placeholder, reverse_code=noop),
    ]