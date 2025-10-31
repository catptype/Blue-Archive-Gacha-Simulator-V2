# your_student_app/views.py (or api.py)
from rest_framework import viewsets
from .models import Student
from .serializers import StudentSerializer # <-- Import your new serializer

class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Student.objects.select_related('version_id', 'school_id', 'asset_id').all()
    serializer_class = StudentSerializer

    def get_serializer_context(self):
        """
        Ensures the request object is passed to the serializer.
        This is crucial for `SerializerMethodField` to build absolute URLs.
        """
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context