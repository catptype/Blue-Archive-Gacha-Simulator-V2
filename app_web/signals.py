# app_database/signals.py
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .models import Student, Version, ImageAsset, GachaBanner, UserInventory
from .util.AchievementEngine import AchievementEngine

@receiver(post_delete, sender=Student)
def delete_asset_after_student(sender, instance:Student, using, **kwargs):
    asset_id = instance.asset_id
    if not asset_id:
        return

    def _cleanup():
        # With OneToOne, there can't be another Student on this ImageAsset.
        ImageAsset.objects.using(using).filter(asset_id=asset_id.id).delete()

    transaction.on_commit(_cleanup)

@receiver(pre_delete, sender=Student)
def remove_student_from_all_banners(sender, instance:Student, **kwargs):
    """
    Before a Student instance is deleted, this signal removes the student
    from ALL GachaBanner relationships (`banner_pickup` and `banner_exclude`)
    to ensure data integrity.
    """
    try:
        # --- THE FIX: Use the reverse relationship ---
        # Because you defined `related_name='pickup_in_banners'` on the ManyToManyField,
        # you can access all banners a student is a pickup in via `instance.pickup_in_banners`.
        # The .clear() method removes all associations for this student from that relationship.
        # This is highly efficient and performs a single database query.
        instance.pickup_in_banners.clear() 

        # The same logic applies to the exclusion list.
        instance.excluded_from_banners.clear()

    except Exception as e:
        # It's good practice to log errors in signals to avoid crashing the deletion process.
        print(f"Error in remove_student_from_all_banners signal for student {instance.pk}: {e}")

@receiver(post_save, sender=UserInventory)
def on_inventory_change(sender, instance: UserInventory, created, **kwargs):
    """
    When a user gets a new student, check all of their collection achievements.
    """
    if created and instance.inventory_user.is_authenticated:
        # Initialize the service for the user and run the collection check.
        achievement_service = AchievementEngine(instance.inventory_user)
        achievement_service.check_collection_achievements()