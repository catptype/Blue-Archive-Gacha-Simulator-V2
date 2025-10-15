import hashlib
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import CheckConstraint, Q
from django.contrib.auth import get_user_model
from django.conf import settings

class Version(models.Model):
    version_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    version_name = models.CharField(max_length=100, unique=True, blank=False, verbose_name='Version')

    def __str__(self):
        return self.name
    
    @property
    def id(self) -> int:
        return self.version_id
    
    @property
    def name(self) -> str:
        return self.version_name
    
    class Meta:
        db_table = 'student_version_table'

class School(models.Model):
    school_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    school_name = models.CharField(max_length=100, unique=True, blank=False, verbose_name='School')
    school_image = models.BinaryField(null=True, verbose_name='Logo')

    def __str__(self) -> str:
        return self.name
    
    @property
    def id(self) -> int:
        return self.school_id
    
    @property
    def name(self) -> str:
        return self.school_name
    
    @property
    def image(self) -> bytes:
        return self.school_image
    
    class Meta:
        db_table = 'student_school_table'

class ImageAsset(models.Model):
    asset_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    asset_portrait_data = models.BinaryField(null=True, blank=True, verbose_name='Portrait')
    asset_artwork_data = models.BinaryField(null=True, blank=True, verbose_name='Artwork')
    asset_pair_hash = models.CharField(max_length=64, unique=True, editable=False)

    def save(self, *args, **kwargs):
        # Create a unique "fingerprint" for the pair of images by
        # combining their individual hashes and then hashing that result.
        
        # Calculate portrait hash (or use a fixed string if null)
        p_hash = hashlib.sha256(self.asset_portrait_data).hexdigest() if self.asset_portrait_data else "no-portrait"
        
        # Calculate full-body hash (or use a fixed string if null)
        f_hash = hashlib.sha256(self.asset_artwork_data).hexdigest() if self.asset_artwork_data else "no-fullbody"
        
        # Combine the two hashes in a deterministic way and create the final hash
        combined_hash_string = f"{p_hash}-{f_hash}"
        self.asset_pair_hash = hashlib.sha256(combined_hash_string.encode()).hexdigest()
        
        super().save(*args, **kwargs)
    
    @property
    def id(self) -> int:
        return self.asset_id
    
    @property
    def portrait_data(self) -> bytes:
        return self.asset_portrait_data
    
    @property
    def artwork_data(self) -> bytes:
        return self.asset_artwork_data

    class Meta:
        db_table = 'image_asset_table'

class Student(models.Model):
    student_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    student_name = models.CharField(max_length=100, blank=False)
    version_id = models.ForeignKey(Version, on_delete=models.CASCADE)
    student_rarity = models.PositiveIntegerField(choices=[(1, '★'), (2, '★★'), (3, '★★★')])
    school_id = models.ForeignKey(School, on_delete=models.CASCADE)
    asset_id = models.OneToOneField(ImageAsset, null=True, blank=True, on_delete=models.PROTECT)
    student_is_limited = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"[{self.id:03d}] {self.school} {self.fullname} {'★'*self.student_rarity}"
        
    def clean(self):
        query = Student.objects.exclude(pk=self.pk)
        existing_student = query.filter(student_name=self.name).first()
        if existing_student and existing_student.school != self.school:
            raise ValidationError({'name': f'A student \'{self.name}\' already exists in \'{existing_student.school}\' but you select \'{self.school}\'.'})
        
    @property
    def id(self) -> int:
        return self.student_id
    
    @property
    def fullname(self) -> int:
        if self.version.lower() == 'original':
            return self.name
        else:
            return f"{self.name} ({self.version})"
    
    @property
    def name(self) -> str:
        return self.student_name

    @property
    def version(self) -> str:
        return self.version_id.name
    
    @property
    def rarity(self) -> int:
        return self.student_rarity
    
    @property
    def school(self) -> str:
        return self.school_id.name
    
    @property
    def portrait(self) -> bytes:
        return self.asset_id.portrait_data
    
    @property
    def artwork(self) -> bytes:
        return self.asset_id.artwork_data
    
    @property
    def is_limited(self) -> bool:
        return self.student_is_limited

    class Meta:
        db_table = 'student_table'
        unique_together = ('student_name', 'version_id')
        indexes = [
            models.Index(fields=['version_id']),
            models.Index(fields=['student_rarity']),
            models.Index(fields=['school_id']),
        ]

class GachaPreset(models.Model):
    preset_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    preset_name = models.CharField(max_length=100, unique=True, null=False, blank=False, verbose_name='Name')
    preset_pickup_rate = models.DecimalField(max_digits=4, decimal_places=1, null=False, blank=False, verbose_name='Pickup ★★★ Rate')
    preset_r3_rate = models.DecimalField(max_digits=4, decimal_places=1, null=False, blank=False, verbose_name='Total ★★★ Rate')
    preset_r2_rate = models.DecimalField(max_digits=4, decimal_places=1, null=False, blank=False, verbose_name='Total ★★ Rate')
    preset_r1_rate = models.DecimalField(max_digits=4, decimal_places=1, null=False, blank=False, verbose_name='Total ★ Rate')

    def __str__(self):
        return self.preset_name
    
    def clean(self):
        """
        Custom validation for gacha rate integrity.
        
        This method now enforces two critical rules:
        1. The total sum of all rarities (R3 + R2 + R1) must equal 100%.
        2. The pickup rate must be less than or equal to the total 3-star rate.
        """
        
        # --- Rule 1: Validate the total sum of rates ---
        total_rate = self.preset_r3_rate + self.preset_r2_rate + self.preset_r1_rate
        if total_rate != Decimal('100.0'):
            raise ValidationError(
                f"The sum of the main rates (Total ★★★ + ★★ + ★) must be exactly 100.0%. "
                f"The current sum is {total_rate}%."
            )

        # --- Rule 2: Validate the pickup rate against the 3-star rate ---
        if self.preset_pickup_rate > self.preset_r3_rate:
            raise ValidationError(
                f"The 'Pickup ★★★ Rate' ({self.preset_pickup_rate}%) cannot be greater than the "
                f"'Total ★★★ Rate' ({self.preset_r3_rate}%)."
            )

        # --- Optional Rule 3: Validate for negative numbers ---
        # Although DecimalField has a default min_value of None, it's good practice to be explicit.
        if self.preset_pickup_rate < 0 or self.preset_r3_rate < 0 or self.preset_r2_rate < 0 or self.preset_r1_rate < 0:
            raise ValidationError("Rate values cannot be negative.")
    
    @property
    def name(self) -> str:
        return self.preset_name

    @property
    def pickup_rate(self) -> float:
        return float(self.preset_pickup_rate)
    
    @property
    def r3_rate(self) -> float:
        return float(self.preset_r3_rate)
    
    @property
    def r2_rate(self) -> float:
        return float(self.preset_r2_rate)
    
    @property
    def r1_rate(self) -> float:
        return float(self.preset_r1_rate)
    
    class Meta:
        db_table = 'gacha_preset_table'

class GachaBanner(models.Model):
    banner_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    banner_image = models.BinaryField(null=True, blank=True, verbose_name='Image')
    banner_name = models.CharField(max_length=100, unique=True, null=False, blank=False, verbose_name='Name')
    preset_id = models.ForeignKey(GachaPreset, null=True, blank=True, on_delete=models.PROTECT)

    banner_include_version = models.ManyToManyField(
        Version,
        blank=False, # A banner MUST include at least one version.
        verbose_name='Included Student Versions',
        help_text='Which student versions (e.g., Original, Summer) are in this banner\'s regular pool.'
    )
    
    banner_include_limited = models.BooleanField(
        default=False,
        verbose_name='Include Limited Students',
        help_text='If checked, limited-time students that match the versions above will be included.'
    )

    banner_pickup = models.ManyToManyField(
        Student, 
        blank=True, 
        related_name='pickup_in_banners',
        verbose_name='Pickup Students'
    )
    
    banner_exclude = models.ManyToManyField(
        Student,
        blank=True,
        related_name='excluded_from_banners',
        verbose_name='Excluded Regular Students',
        help_text='Students who will NOT appear in the regular pool for this banner.'
    )

    def __str__(self):
        return self.banner_name
    
    def clean(self):
        """
        Custom validation that collects ALL errors and displays them at once.
        """
        # This guard clause is essential for ManyToMany relationships.
        if not self.pk:
            return

        # This list will hold all the error messages we find.
        errors = []

        # --- Rule 1: A banner must include at least one version ---
        # We pre-fetch here to avoid extra DB queries later.
        included_versions = self.banner_include_version.all()
        if not included_versions.exists():
            errors.append("A banner must include at least one student version.")
        
        # --- Rule 2: Check if any pickup students are invalid for this banner's rules ---
        invalid_pickups = []
        for student in self.banner_pickup.all():
            # student:Student # Uncomment this line to see highlight IDE
            is_version_ok = student.version in included_versions
            is_limited_ok = self.banner_include_limited or not student.is_limited

            if not (is_version_ok and is_limited_ok):
                invalid_pickups.append(f"{student.name} ({student.version})")
        
        if invalid_pickups:
            # Add a detailed error message to our list.
            error_message = (
                "Invalid pickup students: The following students do not match this banner's "
                f"inclusion rules (version or limited status): {', '.join(invalid_pickups)}"
            )
            errors.append(error_message)

        # --- Final Step: If we found any errors, raise them all at once ---
        if errors:
            # Raising a ValidationError with a list of strings will render them
            # as a bulleted list in the Django Admin.
            raise ValidationError(errors)
        
    @property
    def name(self) -> str:
        return self.banner_name
    
    @property
    def pickup_students(self):
        return self.banner_pickup.all()
    
    @property
    def _base_pool(self):
        pool = Student.objects.filter(version_id__in=self.banner_include_version.all())
        if not self.banner_include_limited:
            pool = pool.exclude(student_is_limited=True)
        return pool
    
    @property
    def r3_students(self):
        return self._base_pool.filter(student_rarity=3).exclude(pk__in=self.pickup_students.values_list('pk', flat=True))

    @property
    def r2_students(self):
        return self._base_pool.filter(student_rarity=2)

    @property
    def r1_students(self):
        return self._base_pool.filter(student_rarity=1)
    
    @property
    def pickup_r3_rate(self):
        return self.preset_id.pickup_rate
    
    @property
    def non_pickup_r3_rate(self):
        return self.preset_id.r3_rate - self.preset_id.pickup_rate
    
    @property
    def r2_rate(self):
        return self.preset_id.r2_rate
    
    @property
    def r1_rate(self):
        return self.preset_id.r1_rate

    @property
    def image(self) -> bytes:
        return self.banner_image
    
    class Meta:
        db_table = 'gacha_banner_table'

class GachaTransaction(models.Model):
    transaction_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    transaction_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='User')
    banner_id = models.ForeignKey(GachaBanner, on_delete=models.PROTECT, verbose_name='Banner')
    student_id = models.ForeignKey(Student, on_delete=models.PROTECT, verbose_name='Student')
    transaction_create_on = models.DateTimeField(auto_now_add=True, editable=False, verbose_name='Create On')

    def __str__(self):
        return f'{self.transaction_user} {self.banner} {self.student}'

    @property
    def banner(self):
        return self.banner_id.name

    @property
    def student(self):
        return self.student_id.name
    
    @property
    def create_on(self):
        return self.transaction_create_on.strftime('%Y-%m-%d %H:%M:%S')
    
    class Meta:
        db_table = 'gacha_transaction_table'

        # Define indexes.
        indexes = [
            models.Index(fields=['transaction_user']),
            models.Index(fields=['banner_id']),
            models.Index(fields=['student_id']),
        ]

        # It's good practice to set a more readable name for the admin.
        verbose_name = "Gacha Transaction"
        verbose_name_plural = "Gacha Transactions"

        # Ordering by newest first is common for transaction logs.
        ordering = ['-transaction_create_on']

class UserInventory(models.Model):
    inventory_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    inventory_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='User')
    student_id = models.ForeignKey(Student, on_delete=models.CASCADE, verbose_name="Student")
    inventory_num_obtained = models.PositiveIntegerField(default=1, verbose_name="Number Obtained")
    
    # This is a highly useful field to add for sorting and achievements.
    inventory_first_obtained_on = models.DateTimeField(auto_now_add=True, editable=False)

    def __str__(self):
        return f'{self.inventory_user.username} - {self.student_id.name} (x{self.inventory_num_obtained})'
    
    class Meta:
        db_table = 'user_inventory_table'

        # Define indexes.
        indexes = [
            models.Index(fields=['inventory_user']),
            models.Index(fields=['student_id']),
        ]
        # This is the most important part. It creates a database constraint
        # that ensures a user can only have ONE row for each unique student.
        unique_together = ('inventory_user', 'student_id')
        
        verbose_name = "User Inventory"
        verbose_name_plural = "User Inventories"
        ordering = ['-inventory_first_obtained_on']
        
class Achievement(models.Model):
    achievement_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    achievement_name = models.CharField(max_length=100, unique=True, verbose_name='Name')
    achievement_description = models.TextField(null=True, blank=True, verbose_name='Description')
    achievement_image = models.BinaryField(null=True, blank=True, verbose_name='Image')
    
    # You can add a category for easier filtering in the UI
    CATEGORY_CHOICES = [
        ('COLLECTION', 'Collection'),
        ('MILESTONE', 'Milestone'),
        ('LUCK', 'Feats of Luck'),
    ]
    achievement_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='MILESTONE', verbose_name='Category')
    
    # A hidden field to link this achievement to the logic that unlocks it.
    achievement_key = models.CharField(max_length=50, unique=True, editable=False, verbose_name='Key')

    def __str__(self):
        return self.achievement_name
    
    @property
    def id(self):
        return self.achievement_id

    @property
    def name(self):
        return self.achievement_name
    
    @property
    def image(self):
        return self.achievement_image
    
    class Meta:
        db_table = 'achievement_table'
    
class UnlockAchievement(models.Model):
    unlock_id = models.AutoField(primary_key=True, auto_created=True, editable=False, verbose_name='ID')
    unlock_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='achievements', verbose_name='user')
    achievement_id = models.ForeignKey(Achievement, on_delete=models.CASCADE, verbose_name='Description')
    unlock_on = models.DateTimeField(auto_now_add=True, editable=False, verbose_name='Description')
    
    class Meta:
        db_table = 'unlock_achievement_table'
        unique_together = ('unlock_user', 'achievement_id') # A user can only get an achievement once.

    def __str__(self):
        return f'{self.unlock_user.username} unlocked "{self.achievement_id.name}"'
