"""附加 WIGOS 标识符字段从 varchar(255) 改到 text。

原字段是 ``GeneratedField(output_field=CharField(max_length=255))``，值是
``",wsi1,wsi2,"`` 这种拼接形态。实测一个 15 字符的 WSI 带分隔符占 17 字节，
15 个就是 255 —— 第 16 个直接 ``DataError: value too long for type character
varying(255)``，对客户端表现为 500。

这不是理论风险：换过编号、合并过台站的历史记录很容易累积到十几个附加标识符
（WMDR 里 ``additionalIds`` 本来就是数组，没有数量上限）。写入失败发生在
``station.save()``，用户填完的表单会整份丢掉。

改 text 之后，长度限制交给应用层。

⚠️ 生成列不能用 ``ALTER COLUMN ... TYPE text`` —— PostgreSQL 直接拒绝：
    ERROR: cannot specify USING when altering type of generated column
所以这里先 DROP 再 ADD。这一列的值完全由 ``wmdrv2`` 派生，删掉不会丢任何
用户数据；重建时数据库按原表达式把值再算一遍。
"""

from django.db import migrations, models

import api.models

FIELD_KWARGS = dict(
    db_index=True,
    db_persist=True,
    expression=api.models.ExtractAndJoinJson(
        models.F("wmdrv2"), models.Value("$.properties.additionalIds[*]")
    ),
    output_field=models.TextField(),
)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0016_drop_guardian_anonymous_user"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="station",
            name="additional_wigos_identifiers",
        ),
        migrations.AddField(
            model_name="station",
            name="additional_wigos_identifiers",
            field=models.GeneratedField(**FIELD_KWARGS),
        ),
    ]