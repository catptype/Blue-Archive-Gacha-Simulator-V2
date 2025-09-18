import itertools
import json
import tempfile
from decimal import Decimal
from django.core.cache import cache
from django.contrib.staticfiles import finders
from django.http import JsonResponse, HttpRequest, HttpResponse, FileResponse, HttpResponseNotFound
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.urls import reverse

from .models import School, Student, Version, GachaBanner

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
    Renders the initial "shell" of the student page, containing only the list of schools.
    All student data will be loaded dynamically via API calls.
    """
    schools = School.objects.all().order_by('school_name')
    context = { 'schools': schools }
    return render(request, 'app_web/student.html', context)

def gacha(request):
    """
    Renders the main gacha page, fetching all banners for the carousel.
    """
    # We don't need to prefetch here, as the initial page only needs banner info.
    # Details will be loaded on demand.
    banners = GachaBanner.objects.all().order_by('banner_id')
    context = {
        'banners': banners
    }
    return render(request, 'app_web/gacha.html', context)

def banner_details(request, banner_id):
    """
    Fetches and prepares all data for the banner details modal using the
    NEW inclusion-based logic.
    """
    banner = get_object_or_404(
        GachaBanner.objects.select_related('preset_id').prefetch_related('banner_pickup__asset_id', 'banner_include_version'), 
        pk=banner_id
    )
    
    # --- Step 1: Get the included versions and pickup students ---
    included_versions = banner.banner_include_version.all()
    pickup_students = banner.banner_pickup.all()
    
    # --- Step 2: Build the base pool of all possible students ---
    base_pool = Student.objects.filter(version_id__in=included_versions)
    
    # --- Step 3: Apply the "limited" filter if necessary ---
    if not banner.banner_include_limited:
        base_pool = base_pool.exclude(student_is_limited=True)
        
    # --- Step 4: Exclude the pickup students to get the final "regular" pool ---
    regular_pool = base_pool.exclude(pk__in=pickup_students.values_list('pk', flat=True))

    # --- Step 5: Categorize the regular pool by rarity ---
    r3_regulars = regular_pool.filter(student_rarity=3).prefetch_related('asset_id')
    r2_regulars = regular_pool.filter(student_rarity=2).prefetch_related('asset_id')
    r1_regulars = regular_pool.filter(student_rarity=1).prefetch_related('asset_id')
    
    # --- Step 6: Prepare the rate calculations (same logic as before, but with new pools) ---
    rates = {}
    if banner.preset_id:
        preset = banner.preset_id
        
        # Category rates
        rates['pickup_r3_rate'] = preset.preset_pickup_rate
        rates['non_pickup_r3_rate'] = preset.preset_r3_rate - preset.preset_pickup_rate
        rates['r2_rate'] = preset.preset_r2_rate
        rates['r1_rate'] = preset.preset_r1_rate

        # Individual student rates (handle division by zero)
        pickup_count = pickup_students.count()
        rates['pickup_student_rate'] = (rates['pickup_r3_rate'] / pickup_count) if pickup_count > 0 else Decimal('0.0')
        
        r3_reg_count = r3_regulars.count()
        rates['r3_regular_student_rate'] = (rates['non_pickup_r3_rate'] / r3_reg_count) if r3_reg_count > 0 else Decimal('0.0')
        
        r2_reg_count = r2_regulars.count()
        rates['r2_regular_student_rate'] = (rates['r2_rate'] / r2_reg_count) if r2_reg_count > 0 else Decimal('0.0')
        
        r1_reg_count = r1_regulars.count()
        rates['r1_regular_student_rate'] = (rates['r1_rate'] / r1_reg_count) if r1_reg_count > 0 else Decimal('0.0')

    context = {
        'banner': banner,
        'pickup_students': pickup_students,
        'r3_regulars': r3_regulars,
        'r2_regulars': r2_regulars,
        'r1_regulars': r1_regulars,
        'rates': rates
    }

    return render(request, 'app_web/components/banner-details.html', context)

def student_HEAVY(request:HttpRequest) -> HttpResponse:
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
#####   REQUEST -> JSONRESPONSE   #####
#######################################
def get_students_by_school(request: HttpRequest, school_id: int) -> JsonResponse:
    """
    API endpoint that returns a list of students for a given school_id.
    Filters for the 'Original' version of students.
    """
    try:
        original_version = Version.objects.get(version_name='Original')
    except Version.DoesNotExist:
        # If there's no "Original" version, we can't find any students.
        return JsonResponse({'students': []})

    # Query for the students of the requested school and version.
    students = Student.objects.filter(
        school_id=school_id,
        version_id=original_version
    ).order_by('student_name')

    # Convert the QuerySet into a list of simple dictionaries for JSON serialization.
    # The frontend only needs the ID (for the image URL) and the name.
    students_data = [
        {
            'id': student.student_id,
            'name': student.student_name
        }
        for student in students
    ]

    return JsonResponse({'students': students_data})

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

def serve_banner_image(request:HttpRequest, banner_id:int):

    try:
        banner_obj = GachaBanner.objects.get(banner_id=banner_id)
        banner_name = banner_obj.name
        banner_bytes = banner_obj.image

        if banner_bytes is None:
            raise GachaBanner.DoesNotExist
        
    except GachaBanner.DoesNotExist:
        # Find the SVG file in the static folder
        svg_path = finders.find("icon/website/portrait_404.png")  # Replace with your SVG's path in static
        if not svg_path:
            return HttpResponseNotFound("SVG not found in static files.")
        
        return FileResponse(open(svg_path, "rb"), content_type="image/png")
    
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(banner_bytes)
    temp_file.seek(0)

    response = FileResponse(temp_file, content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{banner_name}.png"'

    return response

def serve_student_image(request: HttpRequest, student_id: int, image_type: str):
    """
    Serves a student image (portrait or artwork) with a robust caching strategy
    and correct model logic.
    """
    cache_key = f"student_image:{student_id}:{image_type}"
    image_data = cache.get(cache_key)

    if image_data is None:  # CACHE MISS
        print(f"CACHE MISS for key: {cache_key}")

        # Define the correct field names on the ImageAsset model
        allowed_image_fields = {
            'portrait': 'asset_portrait_data',
            'artwork': 'asset_artwork_data'
        }
        field_name = allowed_image_fields.get(image_type)

        if not field_name:
            return HttpResponseNotFound("Invalid image type specified.")

        try:
            # Use select_related to fetch the student and its related asset in one DB query
            student_obj = Student.objects.select_related('asset_id', 'version_id').get(student_id=student_id)

            # Check if the student has an asset assigned
            if not student_obj.asset_id:
                raise Student.DoesNotExist("Student has no linked ImageAsset.")

            # CORRECTLY get the image bytes from the related ImageAsset model
            image_bytes = getattr(student_obj.asset_id, field_name)

            if not image_bytes:
                raise Student.DoesNotExist("ImageAsset has no data for this image type.")

            # Prepare data for caching
            image_data = {
                'image_bytes': image_bytes,
                'filename': f"{student_obj.student_name}_{student_obj.version_id.version_name}_{image_type}.png"
            }
            # Use a longer, more sensible timeout
            cache.set(cache_key, image_data, timeout=CACHE_IMAGE_TIMEOUT) # Cache for 1 hour

        except Student.DoesNotExist as e:
            print(f"Data not found for {cache_key}: {e}")
            # Cache the "not found" result to prevent future DB hits
            image_data = "NOT_FOUND"
            cache.set(cache_key, image_data, timeout=60) # Cache "not found" for 1 minute

    else:
        print(f"CACHE HIT for key: {cache_key}")

    # --- SERVE THE RESPONSE ---
    if image_data == "NOT_FOUND":
        fallback_path = finders.find("icon/website/portrait_404.png")
        if not fallback_path:
            return HttpResponseNotFound("Student image and fallback image not found.")
        return FileResponse(open(fallback_path, "rb"), content_type="image/png")
    
    # We have valid image data
    response = HttpResponse(image_data['image_bytes'], content_type='image/png')
    response['Content-Disposition'] = f"inline; filename=\"{image_data['filename']}\""
    return response
