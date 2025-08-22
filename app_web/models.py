import hashlib
from django.db import models
from django.core.exceptions import ValidationError

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
        return f"[{self.id:03d}] {self.school} {self.fullname}"
        
    def clean(self):
        query = Student.objects.exclude(pk=self.pk)
        existing_student = query.filter(name=self.name).first()
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
