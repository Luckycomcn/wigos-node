"""Queue a PublicationEvent for every saved or deleted Station.

The row is written by the save/delete itself, inside its transaction: a
change rolled back (a rejected batch update, a dry run) leaves no event.
Changes that bypass signals (QuerySet.update(), raw SQL) are not queued."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from api.models import Station
from api.stations import issuer_of, wsis_of
from publishing.base import Operation

from .models import PublicationEvent


def _wsis(wmdrv2):
    return wsis_of(wmdrv2) if wmdrv2 else []


def _queue(station, operation, wmdrv2, previous_wmdrv2=None):
    # who made the change, set by api.stations; popped so a later save of the
    # same instance isn't attributed to them
    changed_by = station.__dict__.pop("_changed_by", None)
    source = station.__dict__.pop("_source", PublicationEvent.Source.SYSTEM)
    wsis = list(dict.fromkeys(_wsis(previous_wmdrv2) + _wsis(wmdrv2)))
    PublicationEvent.objects.create(
        operation=operation,
        station_id=station.pk,
        wigos_identifier=wmdrv2.get("id") or "",
        wmdrv2=wmdrv2,
        previous_wmdrv2=previous_wmdrv2,
        changed_by=changed_by,
        source=source,
        issuers=list(dict.fromkeys(issuer_of(wsi) for wsi in wsis)),
        ordering_keys=[f"station:{station.pk}"] + [f"wsi:{wsi}" for wsi in wsis],
    )


@receiver(pre_save, sender=Station)
def remember_previous_record(sender, instance, raw=False, **kwargs):
    if raw or instance.pk is None:
        return
    instance._outbox_previous = Station.objects.filter(pk=instance.pk).values_list("wmdrv2", flat=True).first()


@receiver(post_save, sender=Station)
def queue_save(sender, instance, created, raw=False, **kwargs):
    if raw:  # loaddata: imported data, not a change to announce
        return
    previous = instance.__dict__.pop("_outbox_previous", None)
    if created:
        _queue(instance, Operation.CREATE, instance.wmdrv2)
    else:
        _queue(instance, Operation.UPDATE, instance.wmdrv2, previous)


@receiver(post_delete, sender=Station)
def queue_delete(sender, instance, **kwargs):
    _queue(instance, Operation.DELETE, instance.wmdrv2)
