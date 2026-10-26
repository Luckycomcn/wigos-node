# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _

from .models import Station, WIGOSNodeGroup, WIGOSNodeUser


# Define the inline layout for your extra fields
class WIGOSNodeGroupProfileInline(admin.StackedInline):
    model = WIGOSNodeGroup
    can_delete = False
    verbose_name = _("Issuer")
    verbose_name_plural = _("Issuer")


class WIGOSNodeUserCreationForm(UserCreationForm):
    """Two-box password form (password1/password2) with the configured
    validators. The stock ModelAdmin put a single plain `password` CharField on
    the page and stored whatever was typed verbatim: has_usable_password() then
    returned True (it only checks for a `!` or hasher prefix) while
    check_password() could never match, so every account created here was
    permanently unable to log in."""

    class Meta(UserCreationForm.Meta):
        model = WIGOSNodeUser
        fields = ("username", "email")


class WIGOSNodeUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = WIGOSNodeUser
        fields = "__all__"


@admin.register(WIGOSNodeUser)
class WIGOSNodeUserAdmin(UserAdmin):
    # WIGOSNodeUser.email is the USERNAME_FIELD and is unique, so it has to be
    # in the edit form; the stock UserAdmin layout only knows first/last name.
    form = WIGOSNodeUserChangeForm
    add_form = WIGOSNodeUserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )


admin.site.unregister(Group)


@admin.register(Group)
class CustomGroupAdmin(GroupAdmin):
    inlines = [WIGOSNodeGroupProfileInline]


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    """原版没有注册 Station —— 出问题时连后台都看不到数据，只能进 shell。

    注意：在后台直接删除台站会绕过授权范围的留痕，常规删除请用界面的删除
    按钮或 DELETE /api/wmdrv2/<id>。
    """

    list_display = ("id", "wigos_identifier", "name", "owner", "status", "archived")
    list_filter = ("status", "archived")
    search_fields = ("wigos_identifier", "name")
    # 生成列只读（由 wmdrv2 推导），编辑 wmdrv2 就够了。
    readonly_fields = ("wigos_identifier", "name", "additional_wigos_identifiers")
    raw_id_fields = ("owner",)