from django.contrib.auth.models import AbstractUser, Group
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.db.models import F, Func, GeneratedField, Value
from django.db.models.fields.json import KT
from django.db.models.functions import Cast
from jsonpath_ng import parse

from .utils import update_station_geometry
from .wsi import parse_wsi

wigos_identifier_expression = parse('$.id')
additional_wigos_identifier_expression = parse('$.properties.additionalIds')

class ExtractAndJoinJson(Func):
    function = 'join_jsonb_path_array'  # Matches the SQL function name exactly

# join_jsonb_path_array stores additional WSIs as ",wsi1,wsi2," (a comma can't
# appear in a WSI), so a whole WSI is matched by searching for it between
# separators rather than as a bare substring of a longer one.
ADDITIONAL_WSI_SEPARATOR = ','

def additional_wsi_lookup(wigos_identifier):
    return f"{ADDITIONAL_WSI_SEPARATOR}{wigos_identifier}{ADDITIONAL_WSI_SEPARATOR}"

class WIGOSNodeGroup(models.Model):

    # Establish the direct link to Django's Group
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='profile')

    issuer_identifier = models.IntegerField()

    def __str__(self):
        return f"{self.group.name} (Issuer ID: {self.issuer_identifier})"

class WIGOSNodeUser(AbstractUser):
    # 1. Require a unique email address
    email = models.EmailField(unique=True)

    # 2. Tell Django to use email as the login identifier
    USERNAME_FIELD = 'email'

    # 3. Specify fields prompted for when running 'createsuperuser'
    REQUIRED_FIELDS = ['username'] 

    def __str__(self):
        return self.email

class StationQuerySet(models.QuerySet):
    def with_additional_wigos_identifier(self, wigos_identifier):
        return self.filter(additional_wigos_identifiers__contains=additional_wsi_lookup(wigos_identifier))

    def check_wigos_identifier(self, wigos_identifier):
        return self.filter(wigos_identifier=wigos_identifier).exists() or self.with_additional_wigos_identifier(wigos_identifier).exists()

class Station(models.Model):
    objects = StationQuerySet.as_manager()

    wmdrv2 = models.JSONField(null=False, blank=False)

    name = GeneratedField(
        expression=Cast(
            KT("wmdrv2__properties__title"), 
            output_field=models.CharField(max_length=255)
        ),
        output_field=models.CharField(max_length=255),
        db_persist=True,
    )

    wigos_identifier = GeneratedField(
        expression=Cast(
            KT("wmdrv2__id"),
            output_field=models.CharField(max_length=255)
        ),
        output_field=models.CharField(max_length=255),
        db_persist=True,
        unique=True,
    )

    additional_wigos_identifiers = models.GeneratedField(
        expression=ExtractAndJoinJson(F('wmdrv2'), Value('$.properties.additionalIds[*]')),
        output_field=models.CharField(max_length=255),
        db_persist=True,
        db_index=True,
    )

    location = gis_models.PointField(srid=4326, null=False, blank=False)
    
    
    owner = models.ForeignKey("WIGOSNodeUser", on_delete=models.CASCADE, related_name='stations')

    # F-19: records are archived (soft delete) rather than destroyed; archived
    # rows keep their identifiers reserved but drop out of the default listing.
    archived = models.BooleanField(default=False, db_index=True)

    # 方案 5.6 编辑工作流：草稿 → 提交 → 校验 → 发布。
    # 草稿允许不完整因此可以落库，但不允许发布 —— 发布前必须显式提交。
    # 新建记录的默认状态由 STATION_DEFAULT_STATUS 决定（视图层读取，不写死在
    # 迁移里），这样同一份代码既能跑「宽松」演示也能跑「提交才可发布」的生产。
    DRAFT = "draft"
    SUBMITTED = "submitted"
    STATUS_CHOICES = ((DRAFT, "Draft"), (SUBMITTED, "Submitted"))

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=SUBMITTED, db_index=True,
        help_text="Draft records can be saved but not published.",
    )

    @property
    def is_draft(self):
        return self.status == self.DRAFT
    archived_at = models.DateTimeField(null=True, blank=True)

    def get_wigos_identifiers(self):
        wsis = []
        if self.wmdrv2:
            wsi = wigos_identifier_expression.find(self.wmdrv2)
            if wsi and len(wsi) > 0:
                wsis.append(wsi[0].value)

            for match in additional_wigos_identifier_expression.find(self.wmdrv2):
                value = match.value
                if isinstance(value, (list, tuple)):
                    wsis.extend(v for v in value if v)
                elif value:
                    wsis.append(value)

        return wsis

    def save(self, *args, **kwargs):
        """override save method to update name and location from wmdrv2 JSON data"""

        # wigos_identifier is a GeneratedField (unreadable before the row is
        # written), so derive the primary WSI from the JSON to pre-check it.
        for wsi in self.get_wigos_identifiers():
            if wsi and Station.objects.filter(wigos_identifier=wsi).exclude(pk=self.pk).exists():
                raise ValueError(f"WIGOS identifier '{wsi}' is already in use in another station")

            if wsi and Station.objects.with_additional_wigos_identifier(wsi).exclude(pk=self.pk).exists():
                raise ValueError(f"WIGOS identifier '{wsi}' is already in use in additional identifiers in another station")


        update_station_geometry(self, self.wmdrv2)

        super().save(*args, **kwargs)

    def __str__(self):
        try:
            return (
                f"{self.name} ({self.wigos_identifier}) "
                f"lat: {self.location.y} lon: {self.location.x} wmdrvs: {self.wmdrv2}"
            )
        except (AttributeError, TypeError):
            # unsaved instance: generated fields / location not available yet
            wsis = self.get_wigos_identifiers()
            return f"Station({wsis[0] if wsis else 'unsaved'})"


class StationVersion(models.Model):
    """F-8: immutable snapshot of a station record at each save.

    UI/spec items that reference the lifecycle (create → update → archive)
    read from here. `version` is 1-based and increases per station."""

    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    wmdrv2 = models.JSONField()
    operation = models.CharField(max_length=16, default="create")  # create | update
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "WIGOSNodeUser", on_delete=models.SET_NULL, null=True, blank=True, related_name="station_versions"
    )

    class Meta:
        ordering = ["-version"]
        unique_together = ("station", "version")

    def __str__(self):
        return f"{self.station_id} v{self.version} ({self.operation})"


class StationGroup(models.Model):
    """F-6: records grouped into related collections, incl. cross-border clusters."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    stations = models.ManyToManyField(Station, related_name="groups", blank=True)
    owner = models.ForeignKey(
        "WIGOSNodeUser", on_delete=models.CASCADE, related_name="station_groups"
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class StationTemplate(models.Model):
    """F-22: fill-in template for common station types (field pre-fill + concatenation)."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    payload = models.JSONField()  # partial WMDR2 record used as prefill
    owner = models.ForeignKey(
        "WIGOSNodeUser", on_delete=models.CASCADE, related_name="station_templates"
    )
    shared = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("owner", "name")

    def __str__(self):
        return self.name


class StationGrade(models.Model):
    """F-24: configurable grades derived from record metadata.

    `criteria` is a list of {"path": "...", "op": "eq|ne|exists|contains|gt|lt",
    "value": ...}. A grade matches when every criterion matches."""

    code = models.SlugField(max_length=64, unique=True)
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    criteria = models.JSONField(default=list)
    order = models.IntegerField(default=100)

    class Meta:
        ordering = ["order", "code"]

    def __str__(self):
        return f"{self.code}: {self.label}"


class RecordProvider(models.Model):
    """F-13: several organisations may provide one record.

    WMDR2 has no slot for a provider chain (its ``properties.contacts`` is a
    contact list, not an attribution), so the node keeps the attribution here
    and exposes it at ``/api/wmdrv2/<id>/providers/``. The record's owner is
    always reported as an implicit ``owner`` provider, so a record can never
    look unowned.
    """

    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="providers")
    organization = models.CharField(max_length=255)
    role = models.CharField(max_length=32, default="dataProvider")
    contact = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "WIGOSNodeUser", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="record_providers",
    )

    class Meta:
        ordering = ["role", "organization"]
        unique_together = ("station", "organization", "role")

    def __str__(self):
        return f"{self.organization} ({self.role}) @ {self.station_id}"


class PublishedRecord(models.Model):
    """F-14/F-15 publishing: each publish emits a WIS2 Notification Message
    (api/wnm.py) for a record version and records where the file landed."""

    station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name="publications")
    version = models.CharField(max_length=128)  # record properties.updated/created
    wnm = models.JSONField()
    url = models.URLField(max_length=1024)
    operation = models.CharField(max_length=16, default="canonical")  # canonical|update|deletion
    published = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(
        "WIGOSNodeUser", on_delete=models.SET_NULL, null=True, blank=True, related_name="publications"
    )

    class Meta:
        ordering = ["-published"]

    def __str__(self):
        return f"{self.station_id} @ {self.version}"


class WsiAllocation(models.Model):
    """方案 5.3：centre-id 与 WSI 授权范围的对应关系（WSI 注册表）。

    WSI 形如 ``<issuer>-<series>-<number>[-<local>]``。一个 centre-id
    （issuer 段）通常被授予一段连续 number 区间，所以按区间登记；需要精确到
    单个 WSI 时让 low == high 即可，需要枚举散号时登记多条。

    发布时用 :meth:`covers` 校验目标 WSI 是否落在授权范围内，超范围发布在
    本地即被拒绝并写入 :class:`AuditLog`。注册表可整体导出（JSON/CSV），供
    目录侧同步校验——目录侧对无权发布的消息按不合规处理。
    """

    issuer_identifier = models.IntegerField(db_index=True)
    series = models.IntegerField(default=0)
    number_low = models.IntegerField()
    number_high = models.IntegerField()
    note = models.TextField(blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["issuer_identifier", "series", "number_low"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(number_low__lte=models.F("number_high")),
                name="wsi_allocation_low_le_high",
            ),
        ]

    def __str__(self):
        return f"issuer {self.issuer_identifier}: {self.issuer_identifier}-{self.series}-{self.number_low}..{self.number_high}"

    @property
    def wsi_prefix(self):
        return f"{self.issuer_identifier}-{self.series}"

    def covers(self, wsi):
        """wsi 是否落在本区间内。格式不符返回 False（由调用方区分并报错）。"""
        parsed = parse_wsi(wsi)
        if parsed is None:
            return False
        issuer, series, number, _local = parsed
        return (
            issuer == self.issuer_identifier
            and series == self.series
            and self.number_low <= number <= self.number_high
        )

    def as_export_dict(self, include_id=False):
        payload = {
            "issuer": self.issuer_identifier,
            "series": self.series,
            "numberFrom": self.number_low,
            "numberTo": self.number_high,
            "note": self.note,
        }
        if include_id:
            payload = {"id": self.id, **payload}
        return payload


class AuditLog(models.Model):
    """NF-6 节点操作审计。

    记录"谁对哪条记录做了什么"，重点是发布与**发布被拒**两类：超范围发布
    在本地被拒绝时必须留痕，否则事后无法追溯是谁尝试过越权发布。
    """

    actor = models.ForeignKey(
        "WIGOSNodeUser", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries"
    )
    action = models.CharField(max_length=64, db_index=True)
    station = models.ForeignKey(
        Station, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries"
    )
    detail = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        who = self.actor.get_username() if self.actor else "anonymous"
        return f"{self.created:%Y-%m-%d %H:%M} {who} {self.action}"
