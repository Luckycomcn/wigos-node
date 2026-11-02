from django.db.models import Exists, OuterRef
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.stations import user_issuers

from . import actions
from .models import PublicationEvent
from .publishers import get_publishers


class EventPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


def visible_events(user):
    """Superusers see the full log; anyone else the events of their issuer
    groups, the same groups that let them edit those stations. That includes
    deleted stations and WIGOS IDs moved between issuers."""
    later = PublicationEvent.objects.filter(id__gt=OuterRef("id"), ordering_keys__overlap=OuterRef("ordering_keys"))
    events = (
        PublicationEvent.objects.annotate(has_later_event=Exists(later))
        .select_related("changed_by")
        .defer("wmdrv2", "previous_wmdrv2")
        .order_by("-id")
    )
    return events if user.is_superuser else events.filter(issuers__overlap=list(user_issuers(user)))


def event_data(event):
    return {
        "id": event.id,
        "operation": event.operation,
        "station_id": event.station_id,
        "wigos_identifier": event.wigos_identifier,
        "status": event.status,
        "source": event.source,
        "source_label": event.get_source_display(),
        # username, not get_username(), which is the email; never set for superusers
        "changed_by": event.changed_by.username if event.changed_by else None,
        "created_at": event.created_at,
        "finished_at": event.finished_at,
        "last_error": event.last_error,
        "needs_cleanup": event.needs_cleanup,
        "files": [d["url"] for d in event.deliveries if d["url"]],
        # the same rule as actions.retry, so a button can be hidden up front
        "can_retry": event.status == PublicationEvent.Status.FAILED and not event.has_later_event,
    }


class PublicationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        events = visible_events(request.user)
        for field in ("status", "source", "operation"):
            if field in request.query_params:
                events = events.filter(**{field: request.query_params[field]})
        if "station_id" in request.query_params:
            station_id = request.query_params["station_id"]
            if not station_id.isdigit():
                return Response({"detail": "station_id must be a number"}, status=400)
            events = events.filter(station_id=station_id)
        if "changed_by" in request.query_params:
            if request.query_params["changed_by"] != "me":
                return Response({"detail": "changed_by can only be 'me'"}, status=400)
            events = events.filter(changed_by=request.user)

        paginator = EventPagination()
        page = paginator.paginate_queryset(events, request, view=self)
        return paginator.get_paginated_response([event_data(event) for event in page])


class PublicationRetryView(APIView):
    """Publish a failed event again; see actions.retry. Cleaning up what a failed
    undo left in storage stays in the Django admin, for superusers."""

    permission_classes = [IsAuthenticated]

    def post(self, request, event_id):
        events = visible_events(request.user)
        if not events.filter(pk=event_id).exists():  # outside their groups looks the same
            return Response({"detail": f"Publication event {event_id} not found"}, status=404)
        try:
            actions.retry(event_id, get_publishers())
        except actions.ActionRefused as e:
            return Response({"detail": f"This event can't be retried: {e}."}, status=409)
        return Response(event_data(events.get(pk=event_id)))
