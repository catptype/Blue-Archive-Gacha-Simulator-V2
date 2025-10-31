from rest_framework import serializers
from django.urls import reverse
from .models import Student, Version, School

# A simple serializer for the Version model
class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Version
        fields = ['version_name']

# A simple serializer for the School model
class SchoolSerializer(serializers.ModelSerializer):
    """
    Serializes School model data, adding a dynamically generated
    URL for the school's logo image.
    """
    # This is our new custom, computed field.
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = School
        # Add the new 'image_url' field to the list
        fields = ['school_name', 'image_url']

    def get_image_url(self, obj):
        """
        Generates the absolute URL for the school's image.
        `obj` is the School instance being serialized.
        """
        request = self.context.get('request')
        # Check that the school actually has an image and that we have a request context
        if obj.school_image and request:
            # Use Django's `reverse` with the name of your school image URL
            path = reverse('serve_school_image', args=[obj.school_id])
            return request.build_absolute_uri(path)
        return None # Return null if there's no image or request context

# The main serializer for the Student model
class StudentSerializer(serializers.ModelSerializer):
    """
    Serializes Student model data, turning foreign keys into nested objects
    and generating full URLs for the portrait and artwork images.
    """
    version = VersionSerializer(source='version_id', read_only=True)
    school = SchoolSerializer(source='school_id', read_only=True)

    portrait_url = serializers.SerializerMethodField()
    artwork_url = serializers.SerializerMethodField()

    class Meta:
        model = Student
        # List all the fields you want in your final JSON output
        fields = [
            'student_id',
            'student_name',
            'version',
            'school',
            'student_rarity',
            'student_is_limited',
            'portrait_url',
            'artwork_url',
        ]

    def get_portrait_url(self, obj):
        """
        Generates the absolute URL for the student's portrait image.
        `obj` is the Student instance being serialized.
        """
        # We need the request context to build a full URL (e.g., http://localhost:8000/...)
        request = self.context.get('request')
        if obj.asset_id and request:
            # Use Django's `reverse` to look up the URL by its name
            path = reverse('serve_student_image', args=[obj.student_id, 'portrait'])
            return request.build_absolute_uri(path)
        return None # Return null if there's no asset or request context

    def get_artwork_url(self, obj):
        """
        Generates the absolute URL for the student's artwork image.
        """
        request = self.context.get('request')
        if obj.asset_id and request:
            path = reverse('serve_student_image', args=[obj.student_id, 'artwork'])
            return request.build_absolute_uri(path)
        return None