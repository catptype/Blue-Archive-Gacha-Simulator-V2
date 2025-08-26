import tempfile
from django.http import JsonResponse, HttpRequest, HttpResponse, FileResponse, HttpResponseNotFound
from django.shortcuts import render
from .models import School, Student, Version
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.db.models import Min
from django.utils.safestring import mark_safe
import json
import itertools
from django.urls import reverse
CACHE_IMAGE_TIMEOUT = 300 # 5 minutes 


def _process_students_for_template(students_queryset):
    """Helper function to group students and prepare their data for the template."""
    processed_groups = []
    # Order by name and version to ensure default is consistent
    students_queryset = students_queryset.order_by('student_name', 'version_id')

    for name, group in itertools.groupby(students_queryset, key=lambda s: s.student_name):
        versions_list = []
        for student in group:
            versions_list.append({
                'id': student.student_id,
                'version_name': student.version_id.version_name,
                # We pre-generate the image URL here for easy access in JS
                'image_url': reverse('serve_student_image', args=[student.student_id, 'portrait'])
            })
        
        if versions_list:
            processed_groups.append({
                'student_name': name,
                'versions': versions_list,
                # Safely dump the list of versions into a JSON string for Alpine
                'versions_json': json.dumps(versions_list)
            })
    return processed_groups

#######################################
#####        HTTPRESPONSE         #####
#######################################
def home(request:HttpRequest) -> HttpResponse:
    context = {}
    return render(request, 'app_web/index.html', context)

def student(request:HttpRequest) -> HttpResponse:
    """
    Prepares the data for the character list page.
    Groups students by their school, only including their 'Original' version.
    """
    # Find the 'Original' version object. You might want to cache this.
    try:
        original_version = Version.objects.get(version_name='Original')
    except Version.DoesNotExist:
        original_version = None

    schools = School.objects.all().order_by('school_name')
    
    schools_with_students = []

    for school in schools:
        student_query = Student.objects.filter(school_id=school.school_id)
        
        # Filter by the original version if it exists
        if original_version:
            student_query = student_query.filter(version_id=original_version)
            
        # We only add the school to the list if it has students of the original version
        if student_query.exists():
            schools_with_students.append({
                'school': school,
                'students': student_query.order_by('student_name')
            })

    context = {
        'schools_with_students': schools_with_students
    }
    return render(request, 'app_web/student.html', context)



#######################################
#####   REQUEST -> FILERESPONSE   #####
#######################################
def serve_school_image(request:HttpRequest, school_id:int):

    try:
        school_obj = School.objects.get(school_id=school_id)
        school_name = school_obj.name
        school_bytes = school_obj.image

        if school_bytes is None:
            raise School.DoesNotExist
        
    except School.DoesNotExist:
        # Find the SVG file in the static folder
        svg_path = finders.find("icon/website/portrait_404.png")  # Replace with your SVG's path in static
        if not svg_path:
            return HttpResponseNotFound("SVG not found in static files.")
        
        return FileResponse(open(svg_path, "rb"), content_type="image/png")
    
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(school_bytes)
    temp_file.seek(0)

    response = FileResponse(temp_file, content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{school_name}.png"'

    return response

def serve_student_image(request: HttpRequest, student_id: int, image_type: str):
    """
    A generic view to serve a student image, with a simplified and clear
    manual caching strategy.
    """
    cache_key = f"student_image:{student_id}:{image_type}"
    
    # --- STAGE 1: GET THE DATA ---
    
    image_data = cache.get(cache_key)

    if image_data is None:  # A true CACHE MISS
        print(f"CACHE MISS for key: {cache_key}")
        
        allowed_image_types = {'portrait': 'portrait', 'artwork': 'artwork'}
        field_name = allowed_image_types.get(image_type)
        if not field_name:
            return HttpResponseNotFound("Invalid image type specified.")

        try:
            student_obj = Student.objects.get(student_id=student_id)
            student_name = student_obj.name
            student_version = student_obj.version
            student_image_bytes = getattr(student_obj, field_name)

            if student_image_bytes is None:
                raise Student.DoesNotExist

            # Prepare the data structure to be cached
            image_data = {
                'image_bytes': student_image_bytes,
                'filename': f"{student_name}_{student_version}_{image_type}.png"
            }
            # Set the data in the cache for next time
            cache.set(cache_key, image_data, timeout=1)

        except Student.DoesNotExist:
            # Cache the "not found" result to prevent future DB hits
            image_data = "NOT_FOUND"
            cache.set(cache_key, image_data, timeout=1)
    else:
        print(f"CACHE HIT for key: {cache_key}")

    # --- STAGE 2: SERVE THE RESPONSE ---
    
    # By this point, image_data is guaranteed to be either the data dictionary or "NOT_FOUND"

    if image_data == "NOT_FOUND":
        fallback_path = finders.find("icon/website/portrait_404.png")
        if not fallback_path:
            return HttpResponseNotFound("Student image and fallback image not found.")
        return FileResponse(open(fallback_path, "rb"), content_type="image/png")

    # If we get here, we have the image data and can build the successful response
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(image_data['image_bytes'])
    temp_file.seek(0)
    
    response = FileResponse(temp_file, content_type='image/png')
    response['Content-Disposition'] = f"inline; filename=\"{image_data['filename']}\""
    return response
