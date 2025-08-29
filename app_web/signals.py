# app_database/signals.py
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .models import Student, Version, ImageAsset, GachaBanner

@receiver(post_delete, sender=Student)
def delete_asset_after_student(sender, instance:Student, using, **kwargs):
    asset_id = getattr(instance, "asset_id", None) # Same as instance.asset_id
    if not asset_id:
        return

    def _cleanup():
        # With OneToOne, there can't be another Student on this ImageAsset.
        ImageAsset.objects.using(using).filter(asset_id=asset_id).delete()

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
    Before a student is deleted, cleanly remove them from all M2M relationships
    on the "Standard" banner to prevent dangling references.
    """
    try:
        # Here, a simple get() is acceptable, but wrapping it in a try/except
        # block makes it robust. If the banner doesn't exist, there's nothing to do.
        banner_obj = GachaBanner.objects.get(banner_name="Standard")
        
        # The .remove() calls are idempotent and safe.
        banner_obj.banner_exclude.remove(instance)
        banner_obj.banner_pickup.remove(instance)

    except GachaBanner.DoesNotExist:
        pass

    except Exception as e:
        print(f"Error in delete_student_from_banners signal for student {instance.pk}: {e}")
