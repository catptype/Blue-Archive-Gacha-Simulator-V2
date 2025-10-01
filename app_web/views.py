import itertools
import json
import tempfile
from decimal import Decimal
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse, HttpRequest, HttpResponse, FileResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET

from .models import School, Student, Version, GachaBanner, GachaTransaction, UserInventory
from .util.GachaEngine import GachaEngine

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
@require_GET
def home(request:HttpRequest) -> HttpResponse:
    context = {}
    return render(request, 'app_web/index.html', context)

@require_GET
def student(request:HttpRequest) -> HttpResponse:
    """
    Renders the initial "shell" of the student page, containing only the list of schools.
    All student data will be loaded dynamically via API calls.
    """
    schools = School.objects.all().order_by('school_name')
    context = { 'schools': schools }
    return render(request, 'app_web/student.html', context)

def student_card(request:HttpRequest, student_id:int) -> HttpResponse:
    """
    Renders the initial "shell" of the student page, containing only the list of schools.
    All student data will be loaded dynamically via API calls.
    """
    students = Student.objects.filter(student_id=student_id)
    context = { 'students': students }
    return render(request, 'app_web/debug.html', context)

@require_GET
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

@require_GET
def banner_details(request, banner_id):
    """
    Fetches and prepares all data for the banner details modal using the
    NEW inclusion-based logic.
    """
    banner = get_object_or_404(
        GachaBanner.objects.select_related('preset_id').prefetch_related('banner_pickup__asset_id', 'banner_include_version'), 
        pk=banner_id
    )
    
    # --- Step 1: Get all available students
    pickup_students = banner.pickup_students
    r3_regulars = banner.r3_students.prefetch_related('asset_id')
    r2_regulars = banner.r2_students.prefetch_related('asset_id')
    r1_regulars = banner.r1_students.prefetch_related('asset_id')
    
    # --- Step 6: Prepare the rate calculations (same logic as before, but with new pools) ---
    rates = {}
    if banner.preset_id:

        rates.update({
            # Category rates are pulled directly from model properties.
            'pickup_r3_rate': banner.pickup_r3_rate,
            'non_pickup_r3_rate': banner.non_pickup_r3_rate,
            'r2_rate': banner.r2_rate,
            'r1_rate': banner.r1_rate,
            
            # Individual student rates are calculated here.
            'pickup_student_rate': (banner.pickup_r3_rate / pickup_students.count()) if pickup_students.exists() else Decimal('0.0'),
            'r3_regular_student_rate': (banner.non_pickup_r3_rate / r3_regulars.count()) if r3_regulars.exists() else Decimal('0.0'),
            'r2_regular_student_rate': (banner.r2_rate / r2_regulars.count()) if r2_regulars.exists() else Decimal('0.0'),
            'r1_regular_student_rate': (banner.r1_rate / r1_regulars.count()) if r1_regulars.exists() else Decimal('0.0'),
        })
        
    context = {
        'banner': banner,
        'pickup_students': pickup_students,
        'r3_regulars': r3_regulars,
        'r2_regulars': r2_regulars,
        'r1_regulars': r1_regulars,
        'rates': rates
    }

    return render(request, 'app_web/components/banner-details.html', context)

@require_POST
def gacha_results(request: HttpRequest) -> HttpResponse:
    """
    Takes a list of student IDs from a POST request (preserving order and
    duplicates) and renders the student cards for the results modal.
    """
    try:
        # --- Step 1: Get the list of IDs. This is our "source of truth" for order and duplicates. ---
        student_ids = json.loads(request.body).get('student_ids', [])
        if not student_ids:
            return HttpResponse("No student IDs provided.", status=400)
        
        # --- Step 2: Fetch all UNIQUE student objects we'll need in a single, efficient query. ---
        # We get the unique set of IDs to avoid asking the database for the same student twice.
        unique_student_ids = set(student_ids)
        students_queryset = Student.objects.filter(pk__in=unique_student_ids)

        # --- Step 3: Create an efficient lookup map (dictionary) for fast access. ---
        # This maps each student's ID to its actual model object.
        student_map = {student.pk: student for student in students_queryset}

        # --- Step 4: Re-assemble the final list, preserving the original order and duplicates. ---
        # We loop through our original 'student_ids' list. For each ID, we find the
        # corresponding object in our map. This is extremely fast and gives us the
        # final list in the correct order with all duplicates included.
        pulled_students_in_order = [student_map[sid] for sid in student_ids if sid in student_map]

        context = {
            'pulled_students': pulled_students_in_order
        }
        return render(request, 'app_web/components/banner-result.html', context)

    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid request body.")

@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, 'app_web/dashboard.html')

@login_required
def get_dashboard_content(request: HttpRequest, tab_name: str) -> JsonResponse:
    """
    API endpoint that fetches the correct data based on the requested tab
    and returns the rendered HTML as a JSON response.
    """
    user = request.user
    context = {'user': user}
    template_name = None

    if tab_name == 'dashboard':
        # --- Logic for the main dashboard summary ---
        all_pulls = GachaTransaction.objects.filter(transaction_user=user)
        context['total_pulls'] = all_pulls.count()
        context['unique_students_obtained'] = UserInventory.objects.filter(inventory_user=user).count()
        # Get rarity breakdown using Django's aggregation features
        context['rarity_counts'] = all_pulls.values('student_id__student_rarity').annotate(count=Count('student_id__student_rarity')).order_by('-student_id__student_rarity')
        template_name = 'app_web/components/dashboard-summary.html'

    elif tab_name == 'history':
        # --- Logic for the transaction history ---
        # Use select_related for a huge performance boost!
        context['transactions'] = GachaTransaction.objects.filter(transaction_user=user).select_related(
            'banner_id', 'student_id'
        ).order_by('-transaction_create_on')[:100] # Limit to the most recent 100 for now
        template_name = 'app_web/components/dashboard-history.html'

    elif tab_name == 'collection':
        # --- NEW, SUPERIOR LOGIC FOR THE COLLECTION TAB ---

        # 1. Get a simple, efficient set of all student IDs the user owns.
        owned_student_ids = set(
            UserInventory.objects.filter(inventory_user=user).values_list('student_id', flat=True)
        )

        # 2. Fetch ALL students in the game, efficiently pre-loading related data.
        all_students = Student.objects.select_related(
            'school_id', 'version_id', 'asset_id'
        ).order_by('student_name')

        # 3. Augment the student objects with the 'is_obtained' flag in Python.
        # This is extremely fast and keeps the database logic simple.
        for student in all_students:
            student.is_obtained = student.student_id in owned_student_ids

        # --- NEW: Calculate the completion stats ---
        obtained_count = len(owned_student_ids)
        total_students = all_students.count()
        
        # Handle division by zero if there are no students in the database.
        if total_students > 0:
            completion_percentage = (obtained_count / total_students) * 100
        else:
            completion_percentage = 0

        context['all_students'] = all_students
        # Pass the new stats to the template.
        context['obtained_count'] = obtained_count
        context['total_students'] = total_students
        context['completion_percentage'] = completion_percentage

        template_name = 'app_web/components/dashboard-collection.html'

    elif tab_name == 'achievements':
        # --- Placeholder for achievements ---
        template_name = 'app_web/components/dashboard-achievement.html'

    if template_name:
        # THE FIX: We now use render() to directly return the HTML fragment.
        # The frontend will receive this as a simple text/html response.
        return render(request, template_name, context)
    else:
        return HttpResponse("Invalid tab name.", status=400)


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

def _perform_gacha_pull(request: HttpRequest, banner_id: int, pull_count: int) -> JsonResponse:
    """
    This is the core, user-aware gacha logic.
    - It performs the pull using the GachaEngine.
    - If the user is logged in, it saves transactions and updates their inventory.
    - For guests, it does NOT save anything.
    - It returns the list of pulled student IDs.
    """
    banner = get_object_or_404(GachaBanner, pk=banner_id)
    user = request.user

    # Step 1: Initialize the engine and perform the pulls
    engine = GachaEngine(banner)

    if pull_count == 1:
        pulled_students = engine.draw_1()
    elif pull_count == 10:
        pulled_students = engine.draw_10()
    else:
        return JsonResponse({'success': False})
    
    print(pulled_students)

    # --- THIS IS THE KEY LOGIC ---
    if user.is_authenticated:
        # For logged-in users, we run the database operations inside a transaction.
        with transaction.atomic():
            # a) Save the transaction log
            transactions = [GachaTransaction(transaction_user=user, banner_id=banner, student_id=s) for s in pulled_students]
            GachaTransaction.objects.bulk_create(transactions)
            
            # b) Update the user's inventory
            for student in pulled_students:
                inventory_item, created = UserInventory.objects.get_or_create(
                    inventory_user=user,
                    student_id=student
                )
                if not created:
                    inventory_item.inventory_num_obtained += 1
                    inventory_item.save()

    # Step 2: Prepare the list of IDs for the JSON response.
    # This happens for both guests and logged-in users.
    pulled_student_ids = [student.id for student in pulled_students]
    
    return JsonResponse({'success': True, 'results': pulled_student_ids})

@require_POST
def draw_one_gacha(request: HttpRequest, banner_id: int) -> JsonResponse:
    return _perform_gacha_pull(request, banner_id, pull_count=1)

@require_POST
def draw_ten_gacha(request: HttpRequest, banner_id: int) -> JsonResponse:
    return _perform_gacha_pull(request, banner_id, pull_count=10)

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
