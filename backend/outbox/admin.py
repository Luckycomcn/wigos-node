from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

from . import actions
from .models import PublicationEvent
from .publishers import get_publishers, opened_publishers

HELP = (
    "Retries are manual. <b>Retry</b> publishes a failed event again, regenerating its file; it is refused once a "
    "later change touches the same station or WIGOS IDs, so save the station again instead. "
    "A failed event only holds its station if <b>needs cleanup</b> is set: its undo failed too, so something may "
    "still be stored. Use <b>Retry cleanup</b> to undo it again, or <b>Mark as cleaned up</b> once it was removed "
    "by hand or no longer exists. All three are actions on the list of events."
)


@admin.register(PublicationEvent)
class PublicationEventAdmin(admin.ModelAdmin):
    """The full, read-only log of what was published, with the tools for failed
    events. For superusers; everyone else uses the frontend."""

    list_display = (
        "id", "operation", "wigos_identifier", "station_id", "status", "needs_cleanup", "source", "attempts",
        "created_at", "finished_at",
    )
    list_filter = ("status", "operation", "source", "needs_cleanup")
    search_fields = ("wigos_identifier",)
    ordering = ("-id",)
    actions = ("retry", "retry_cleanup", "mark_cleaned_up")
    fieldsets = (
        (None, {"fields": ("operation", "station_id", "wigos_identifier", "source", "changed_by", "created_at")}),
        ("Publishing", {
            "description": HELP,
            "fields": ("status", "needs_cleanup", "last_error", "attempts", "finished_at", "completed", "deliveries"),
        }),
        ("Record", {"classes": ("collapse",), "fields": ("wmdrv2", "previous_wmdrv2", "issuers", "ordering_keys")}),
    )

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_manage_permission(self, request):
        """Who may run the actions; the events themselves stay read-only."""
        return request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        count = PublicationEvent.objects.filter(needs_cleanup=True).count()
        if count and request.method == "GET":
            url = reverse("admin:outbox_publicationevent_changelist") + "?needs_cleanup__exact=1"
            self.message_user(
                request,
                format_html('{} failed events need cleaning up and hold their stations: <a href="{}">show them</a>.', count, url),
                messages.WARNING,
            )
        return super().changelist_view(request, extra_context)

    def _apply(self, request, queryset, action, done):
        """Run `action` on each event; one refused doesn't stop the others."""
        applied = 0
        for row in queryset:
            try:
                action(row.pk)
            except actions.ActionRefused as e:
                self.message_user(request, f"Event {row.pk} wasn't changed: {e}.", messages.ERROR)
            else:
                applied += 1
        if applied:
            self.message_user(request, f"{applied} {done}.", messages.SUCCESS)

    @admin.action(description="Retry", permissions=["manage"])
    def retry(self, request, queryset):
        publishers = get_publishers()
        self._apply(request, queryset, lambda pk: actions.retry(pk, publishers), "events queued again")

    @admin.action(description="Retry cleanup", permissions=["manage"])
    def retry_cleanup(self, request, queryset):
        with opened_publishers() as publishers:
            self._apply(request, queryset, lambda pk: actions.retry_cleanup(pk, publishers), "events cleaned up")

    @admin.action(description="Mark as cleaned up", permissions=["manage"])
    def mark_cleaned_up(self, request, queryset):
        publishers = get_publishers()
        username = request.user.get_username()
        if request.POST.get("confirmed"):
            self._apply(
                request, queryset, lambda pk: actions.mark_cleaned_up(pk, publishers, username), "events marked as cleaned up"
            )
            return None
        rows = queryset.filter(needs_cleanup=True)
        if not rows:
            self.message_user(request, "None of these events need cleaning up.", messages.ERROR)
            return None
        return TemplateResponse(request, "admin/outbox/mark_cleaned_up.html", {
            **self.admin_site.each_context(request),
            "title": "Mark as cleaned up",
            "opts": self.model._meta,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "events": [
                {"row": row, "urls": [d["url"] for d in actions.leftovers(row, publishers) if d["url"]]}
                for row in rows
            ],
        })
