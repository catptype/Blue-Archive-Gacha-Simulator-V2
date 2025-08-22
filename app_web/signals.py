# app_database/signals.py
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Student, ImageAsset

@receiver(post_delete, sender=Student)
def delete_asset_after_student(sender, instance:Student, using, **kwargs):
    asset_id = getattr(instance, "asset_id", None) # Same as instance.asset_id
    if not asset_id:
        return

    def _cleanup():
        # With OneToOne, there can't be another Student on this ImageAsset.
        ImageAsset.objects.using(using).filter(asset_id=asset_id).delete()

    transaction.on_commit(_cleanup)
