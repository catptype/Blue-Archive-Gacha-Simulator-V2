# app_database/signals.py
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .models import Student, Version, ImageAsset, GachaBanner

@receiver(post_delete, sender=Student)
def delete_asset_after_student(sender, instance:Student, using, **kwargs):
    asset_id = instance.asset_id
    if not asset_id:
        return

    def _cleanup():
        # With OneToOne, there can't be another Student on this ImageAsset.
        ImageAsset.objects.using(using).filter(asset_id=asset_id.id).delete()

    transaction.on_commit(_cleanup)

@receiver(post_save, sender=Student)
def update_standard_banner_exclusions(sender, instance:Student, **kwargs):
    """
    After a student is saved, ensure they are correctly included or excluded
    from the "Standard" banner based on their version and limited status.
    
    - Adds non-Original or limited students to the exclusion list.
    - Removes Original, non-limited students from the exclusion list.
    """
    try:
        # Use get_or_create to be safe. If the banner doesn't exist, this will
        # create it instead of crashing. This is crucial for initial setup.
        banner_obj, created = GachaBanner.objects.get_or_create(banner_name="Standard")
        if created:
            # You could log a message here if you want to know the banner was auto-created.
            print("Created a new 'Standard' Gacha Banner.")

        # --- CORRECTED LOGIC ---
        # 1. Compare the version's name, not the object itself.
        # 2. Check if the student meets the criteria for exclusion.
        is_excluded = (instance.version != 'Original') or (instance.is_limited)

        if is_excluded:
            # If they should be excluded, add them.
            banner_obj.banner_exclude.add(instance)
        else:
            # --- CRITICAL FIX: Handle the "reversal" case ---
            # If they do NOT meet exclusion criteria, ensure they are REMOVED from the list.
            banner_obj.banner_exclude.remove(instance)

    except Exception as e:
        # It's good practice to catch potential errors in signals to avoid crashing
        # the main application flow. You could log this error.
        print(f"Error in update_standard_banner_exclusions signal for student {instance.pk}: {e}")

@receiver(pre_delete, sender=Student)
def delete_student_from_banners(sender, instance:Student, **kwargs):
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

@receiver(post_save, sender=Student)
def add_student_to_banners(sender, instance:Student, **kwargs):
    pass

