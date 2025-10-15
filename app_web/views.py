import itertools
import json
import statistics
import tempfile
from decimal import Decimal
from django.core.cache import cache
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Count, Min
from django.http import JsonResponse, HttpRequest, HttpResponse, FileResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET
from collections import Counter, defaultdict

from .models import School, Student, Version, GachaBanner, GachaTransaction, UserInventory, Achievement, UnlockAchievement
from .util.GachaEngine import GachaEngine
from .util.AchievementEngine import AchievementEngine

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

def get_user_pull_data(user):
    """
    This is the core of the optimization. It fetches all of a user's pull data
    once, caches it, and is reused by all widget views.
    """
    # Define a unique cache key for this user's data.
    cache_key = f"user_dashboard_data:{user.id}"
    
    # Try to get the data from the cache first.
    cached_data = cache.get(cache_key)
    if cached_data:
        print(f"CACHE HIT for user {user.id}")
        return cached_data

    print(f"CACHE MISS for user {user.id}. Fetching from DB.")
    
    # If not in cache, perform the expensive query ONCE.
    all_pulls = list(
        GachaTransaction.objects.filter(transaction_user=user).select_related(
            'student_id', 'banner_id'
        ).order_by('transaction_create_on')
    )
    
    # Store the result in a simple dictionary.
    data_to_cache = {'all_pulls': all_pulls}
    
    # Set the data in the cache. A short timeout (e.g., 10 seconds) is good for dashboards.
    cache.set(cache_key, data_to_cache, timeout=10)
    
    return data_to_cache

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

    return render(request, 'app_web/components/banner_details.html', context)

@require_POST
def gacha_results(request: HttpRequest) -> HttpResponse:
    """
    Takes a list of augmented student OBJECTS from a POST request and renders
    the student cards for the results modal.
    """
    try:
        request_data = json.loads(request.body)
        pulled_data = request_data.get('results', [])
        if not pulled_data:
            return HttpResponse("No student data provided.", status=400)
        
        student_ids = [item['id'] for item in pulled_data]
        
        # Fetch the full student objects.
        unique_student_ids = set(student_ids)
        students_queryset = Student.objects.filter(pk__in=unique_student_ids)
        student_map = {student.pk: student for student in students_queryset}

        # Re-assemble the list, now adding the flags from the original pull.
        pulled_students_in_order = []
        for item in pulled_data:
            student_obj = student_map.get(item['id'])
            if student_obj:
                student_obj.is_new = item['is_new']
                student_obj.is_pickup = item['is_pickup']
                pulled_students_in_order.append(student_obj)

        context = {'pulled_students': pulled_students_in_order}
        return render(request, 'app_web/components/banner_result.html', context)

    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid request body.")

@login_required
def get_top_students_by_rarity(request: HttpRequest, rarity: int) -> HttpResponse:
    """
    API endpoint that fetches the top 3 most-pulled students for a given rarity
    and renders the podium partial template.
    """
    user = request.user

    cache_key = f"user_podium:{user}:{rarity}"
    top_students = cache.get(cache_key)

    if top_students is None:
        print(f"CACHE MISS for key: {cache_key}")
        # Fetch the top 3 students for the requested rarity.
        top_students = (
            Student.objects.filter(gachatransaction__transaction_user=user, student_rarity=rarity)
            .annotate(count=Count('pk'), first_obtained=Min('gachatransaction__transaction_create_on'))
            .order_by( '-count', 'first_obtained')[:3]
        )
        cache.set(cache_key, top_students, timeout=CACHE_IMAGE_TIMEOUT)

    context = {
        'top_students': top_students,
        'rarity': rarity, # Pass the rarity for styling in the template
    }
    # Render a NEW partial template just for the podium.
    return render(request, 'app_web/components/dashboard_podium.html', context)

@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, 'app_web/dashboard.html')

@login_required
def dashboard_widget_kpis(request: HttpRequest) -> HttpResponse:
    """
    API endpoint that calculates all KPI metrics and renders the partial
    HTML template for the KPI widget.
    """
    user = request.user
    cached_data = get_user_pull_data(user)
    all_pulls = cached_data.get('all_pulls', [])

    # --- Perform all necessary calculations ---
    total_pulls = len(all_pulls)
    rarity_counter = Counter(pull.student_id.student_rarity for pull in all_pulls)
    
    context = {
        'total_pulls': total_pulls,
        'total_pyroxene_spent': total_pulls * 120,
        'r3_count': rarity_counter.get(3, 0),
        'r2_count': rarity_counter.get(2, 0),
        'r1_count': rarity_counter.get(1, 0),
    }
    
    # Render the specific partial template for this widget.
    return render(request, 'app_web/components/widgets/kpi.html', context)

@login_required
def dashboard_widget_top_students(request: HttpRequest) -> HttpResponse:
    """
    Renders the HTML shell for the 'Top Students' podium widget, including
    the tabs. The initial podium content (for 3-stars) is also pre-rendered.
    """
    top_r3_students = (
        Student.objects.filter(gachatransaction__transaction_user=request.user, student_rarity=3)
        .annotate(count=Count('pk'), first_obtained=Min('gachatransaction__transaction_create_on'))
        .order_by('-count', 'first_obtained')[:3]
    )

    context = {'top_r3_students': top_r3_students}
    
    return render(request, 'app_web/components/widgets/top_students.html', context)

@login_required
def dashboard_widget_first_r3_pull(request: HttpRequest) -> HttpResponse:
    """
    Renders the HTML for the 'First 3-Star Pull' widget.
    """
    user = request.user
    cached_data = get_user_pull_data(user)
    all_pulls = cached_data.get('all_pulls', [])

    first_r3_pull = next((pull for pull in all_pulls if pull.student_id.student_rarity == 3), None)

    context = {'first_r3_pull': first_r3_pull}
    
    return render(request, 'app_web/components/widgets/first_r3_pull.html', context)

@login_required
def dashboard_widget_chart_overall_rarity(request: HttpRequest) -> HttpResponse:
    """
    API endpoint that calculates the overall rarity distribution and renders the
    complete HTML widget, including the <script> block with the data.
    """
    user = request.user
    
    # --- Step 1: Get the data from our fast, central cache ---
    # This call is now instantaneous after the first load.
    cached_data = get_user_pull_data(user)
    all_pulls = cached_data.get('all_pulls', [])
    
    # --- Step 2: Perform the calculation in Python (extremely fast) ---
    # We no longer need a separate database query here.
    if all_pulls:
        rarity_counter = Counter(pull.student_id.student_rarity for pull in all_pulls)
        chart_data = {
            'r3': rarity_counter.get(3, 0),
            'r2': rarity_counter.get(2, 0),
            'r1': rarity_counter.get(1, 0),
        }
    else:
        # Handle the case where the user has no pulls.
        chart_data = {'r3': 0, 'r2': 0, 'r1': 0}

    context = {
        # THE FIX: We pass the data to the template as a JSON string.
        'chart_data_json': json.dumps(chart_data)
    }
    
    # Render the self-contained widget template.
    return render(request, 'app_web/components/widgets/chart_overall_rarity.html', context)

@login_required
def dashboard_widget_chart_banner_breakdown(request: HttpRequest) -> HttpResponse:
    """
    API endpoint that calculates per-banner rarity stats and renders the
    complete HTML widget for the interactive 'Banner Breakdown' chart.
    """
    user = request.user
    # --- Step 1: Get the data from our fast, central cache ---
    # This call is instantaneous after the first load.
    cached_data = get_user_pull_data(user)
    all_pulls = cached_data.get('all_pulls', [])

    # --- Step 2: Perform all calculations in Python (extremely fast) ---
    # We no longer need a separate database query here.
    
    # Group pulls by banner to perform calculations.
    pulls_by_banner = defaultdict(list)
    for pull in all_pulls:
        pulls_by_banner[pull.banner_id.banner_name].append(pull)

    # Calculate rarity distribution for each banner.
    per_banner_rarity_data = {}
    for banner_name, pulls in pulls_by_banner.items():
        rarity_counter = Counter(p.student_id.student_rarity for p in pulls)
        per_banner_rarity_data[banner_name] = {
            'r3': rarity_counter.get(3, 0),
            'r2': rarity_counter.get(2, 0),
            'r1': rarity_counter.get(1, 0),
        }
    
    # Get a sorted list of banner names for the dropdown.
    banner_names = sorted(pulls_by_banner.keys())

    context = {
        'banner_names': banner_names,
        'per_banner_rarity_json': json.dumps(per_banner_rarity_data)
    }
    
    return render(request, 'app_web/components/widgets/chart_banner_breakdown.html', context)

@login_required
def dashboard_widget_chart_banner_activity(request: HttpRequest) -> HttpResponse:
    """
    API endpoint that calculates the total pulls per banner and renders the
    complete HTML widget for the 'Banner Activity' chart.
    """
    user = request.user
    
    # --- Step 1: Get the data from our fast, central cache ---
    cached_data = get_user_pull_data(user)
    all_pulls = cached_data.get('all_pulls', [])

    # --- Step 2: Perform the calculation in Python (extremely fast) ---
    # We no longer need a separate database query here.
    if all_pulls:
        # Use Counter to efficiently group and count pulls by banner name.
        banner_counter = Counter(pull.banner_id.banner_name for pull in all_pulls)
        
        # Transform the Counter result into the list of dictionaries that the chart expects.
        chart_data_list = [
            {'banner_id__banner_name': name, 'count': count}
            for name, count in banner_counter.most_common()
        ]
    else:
        chart_data_list = []

    context = {
        'chart_data_json': json.dumps(chart_data_list)
    }
    
    return render(request, 'app_web/components/widgets/chart_banner_activity.html', context)

@login_required
def dashboard_widget_performance_table(request: HttpRequest) -> HttpResponse:
    """
    API endpoint that performs the per-banner luck and gap analysis and
    renders the complete HTML widget for the performance table.
    """
    user = request.user
    cached_data = get_user_pull_data(user)
    all_pulls = cached_data.get('all_pulls', [])
    
    # Group pulls by banner for analysis.
    pulls_by_banner = defaultdict(list)
    for pull in all_pulls:
        pulls_by_banner[pull.banner].append(pull)

    banner_analysis = []
    for banner_name, pulls_in_banner in pulls_by_banner.items():

        r3_indices = [i + 1 for i, pull in enumerate(pulls_in_banner) if pull.student_id.student_rarity == 3]
        r3_count = len(r3_indices)
        total_banner_pulls = len(pulls_in_banner)

        # Calculate user's actual rate for this banner
        user_rate = (Decimal(r3_count) / Decimal(total_banner_pulls)) * 100 if total_banner_pulls > 0 else Decimal('0.0')

        # Get the banner's advertised rate from its preset
        if len(pulls_in_banner) > 0:
            banner_rate = pulls_in_banner[0].banner_id.preset_id.preset_r3_rate
        else:
            banner_rate = Decimal('0.0')

        analysis_data = {
            'banner_name': banner_name,
            'total_pulls': total_banner_pulls,
            'r3_count': r3_count,
            'user_rate': f"{user_rate:.2f}%",
            'banner_rate': f"{banner_rate:.2f}%",
            'luck_variance': f"{user_rate - banner_rate:+.2f}%",
            'gaps': None
        }

        if r3_count > 1:
            gaps = [r3_indices[i] - r3_indices[i-1] for i in range(1, r3_count)]
            analysis_data['gaps'] = {
                'min': min(gaps), 'max': max(gaps), 'avg': f"{statistics.mean(gaps):.1f}",
                'stdev': f"{statistics.stdev(gaps):.2f}" if len(gaps) > 1 else "N/A"
            }
        
        banner_analysis.append(analysis_data)

    context = {'banner_analysis': banner_analysis}
    
    return render(request, 'app_web/components/widgets/performance_table.html', context)

@login_required
def dashboard_widget_milestone_timeline(request: HttpRequest) -> HttpResponse:
    """
    API endpoint that finds the user's first-time 3-star pulls and
    renders the HTML for the milestone timeline widget.
    """
    user = request.user

    # 1. Get all of the user's pulls, ordered chronologically.
    cached_data = get_user_pull_data(user)
    all_pulls = cached_data.get('all_pulls', [])
    
    # 2. Process in Python to find the first time each unique 3-star was obtained.
    milestone_pulls = []
    seen_student_ids = set()
    for i, pull in enumerate(all_pulls):
        if pull.student_id.student_rarity == 3:
            if pull.student_id.student_id not in seen_student_ids:
                # This is a milestone! Record it.
                seen_student_ids.add(pull.student_id.student_id)
                
                # Augment the object with the pull number (index + 1)
                pull.pull_number = i + 1 
                milestone_pulls.append(pull)

    # --- THE FIX: Calculate the adaptive width ---
    WIDTH_PER_MILESTONE = 100
    
    # 2. Calculate the total width. Ensure it's never less than a minimum (e.g., 800px) to look good.
    timeline_width = max(800, len(milestone_pulls) * WIDTH_PER_MILESTONE)

    context = {
        'milestone_pulls': milestone_pulls,
        'timeline_width': timeline_width, # Pass the calculated width to the template
    }
    
    return render(request, 'app_web/components/widgets/milestone_timeline.html', context)

@login_required
def get_dashboard_content(request: HttpRequest, tab_name: str) -> JsonResponse:
    """
    API endpoint that fetches the correct data based on the requested tab
    and returns the rendered HTML as a JSON response.
    """
    user = request.user
    context = {'user': user}
    template_name = None

    if tab_name == 'summary': # I've renamed this from 'summary' for clarity

        get_user_pull_data(request.user) 
        template_name = 'app_web/components/dashboard_summary.html'

    elif tab_name == 'history':
        # --- NEW, PAGINATED LOGIC FOR THE TRANSACTION HISTORY ---
        
        # 1. Get the full, ordered list of all transactions for the user.
        # We pre-fetch related data for high performance.
        transaction_list = GachaTransaction.objects.filter(transaction_user=user).select_related(
            'banner_id', 'student_id'
        ).order_by('-transaction_create_on')
        
        # 2. Get the requested page number from the URL query (e.g., ?page=2). Default to page 1.
        page_number = request.GET.get('page', 1)
        
        # 3. Create a Paginator object, with 10 items per page.
        paginator = Paginator(transaction_list, 5)
        
        # 4. Get the specific page object. This handles invalid page numbers gracefully.
        transactions_page = paginator.get_page(page_number)

        context['transactions_page'] = transactions_page

        template_name = 'app_web/components/dashboard_history.html'

    elif tab_name == 'collection':
        # --- NEW, SUPERIOR LOGIC FOR THE COLLECTION TAB ---

        # 1. Get a simple, efficient set of all student IDs the user owns.
        owned_student_ids = set(
            UserInventory.objects.filter(inventory_user=user).values_list('student_id', flat=True)
        )

        # 2. Fetch ALL students in the game, efficiently pre-loading related data.
        all_students = Student.objects.order_by('-student_rarity', 'student_name')

        # 3. Augment the student objects with the 'is_obtained' flag in Python.
        # This is extremely fast and keeps the database logic simple.
        for student in all_students:
            student.is_obtained = student.student_id in owned_student_ids

        # --- NEW: Calculate the completion stats ---
        obtained_count = len(owned_student_ids)
        total_students = len(list(all_students))
        
        # Handle division by zero if there are no students in the database.
        if total_students > 0:
            completion_percentage = (obtained_count / total_students) * 100
        else:
            completion_percentage = 0

        context['all_students'] = all_students
        context['obtained_count'] = obtained_count
        context['total_students'] = total_students
        context['completion_percentage'] = completion_percentage

        template_name = 'app_web/components/dashboard_collection.html'

    elif tab_name == 'achievements':
        # --- LOGIC FOR THE ACHIEVEMENTS TAB ---

        # 1. Get a set of the IDs of all achievements the user has unlocked.
        # MODIFIED: Query the renamed 'UnlockAchievement' model
        unlocked_achievement_ids = set(
            UnlockAchievement.objects.filter(unlock_user=user).values_list('achievement_id', flat=True)
        )

        # 2. Fetch ALL achievement definitions.
        all_achievements = Achievement.objects.all().order_by('achievement_category', 'achievement_name')

        # 3. Augment the achievement objects.
        # MODIFIED: Query the renamed 'UnlockAchievement' model
        user_unlocks = {ua.achievement_id: ua.unlock_on for ua in UnlockAchievement.objects.filter(unlock_user=user)}

        for ach in all_achievements:
            ach.is_unlocked = ach.achievement_id in unlocked_achievement_ids
            ach.unlocked_on = user_unlocks.get(ach)

        context['all_achievements'] = all_achievements
        template_name = 'app_web/components/dashboard_achievement.html'

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
    banner = get_object_or_404(GachaBanner.objects.prefetch_related('banner_pickup'), pk=banner_id)
    user = request.user

    # --- Step 1: Get the user's state BEFORE the pull ---
    owned_student_ids_before_pull = set()
    if user.is_authenticated:
        owned_student_ids_before_pull = set(
            UserInventory.objects.filter(inventory_user=user).values_list('student_id', flat=True)
        )

    # --- Step 2: Initialize the engine and perform the pulls ---
    engine = GachaEngine(banner)

    if pull_count == 1:     pulled_students = engine.draw_1() # Return List of Student object in model
    elif pull_count == 10:  pulled_students = engine.draw_10() # Return List of Student object in model
    else:                   return JsonResponse({'success': False, 'error': 'Invalid pull count'}, status=400)
    
    # --- Step 3: Augment, Save, and Prepare JSON ---
    results_json = []
    seen_in_this_pull = set()
    transactions_to_create = []
    
    pickup_student_ids = set(banner.banner_pickup.values_list('pk', flat=True))

    for student in pulled_students:
        is_new = (student.student_id not in owned_student_ids_before_pull) and \
                 (student.student_id not in seen_in_this_pull)
        is_pickup = student.student_id in pickup_student_ids
        seen_in_this_pull.add(student.student_id)

        results_json.append({
            'id': student.student_id,
            'is_new': is_new,
            'is_pickup': is_pickup
        })
        
        if user.is_authenticated:
            transactions_to_create.append(GachaTransaction(transaction_user=user, banner_id=banner, student_id=student))
    
    # --- Step 4: Save to the database if the user is logged in ---
    # This list will hold all achievements unlocked during this transaction.
    unlocked_achievements = []

    if user.is_authenticated:

        with transaction.atomic():
            GachaTransaction.objects.bulk_create(transactions_to_create)
            for student in pulled_students:
                inventory_item, created = UserInventory.objects.get_or_create(inventory_user=user, student_id=student)
                if not created:
                    inventory_item.inventory_num_obtained += 1
                    inventory_item.save()

        # --- Achievement Checks ---
        # 1. Initialize the service for this user.
        achievement_services = AchievementEngine(user)
        # 2. Check for luck achievements based on THIS pull's results.
        unlocked_achievements.extend(achievement_services.check_luck_achievements(pulled_students))
        
        
        # --- THE FIX: The view is now much cleaner ---
        # 3. Tell the service that new pulls have been made.
        #    The view doesn't know or care about *how* the cache works.
        achievement_services.increment_pull_count(pull_count)
        
        # 4. Tell the service to check milestones with the new, updated count.
        unlocked_achievements.extend(achievement_services.check_milestone_achievements())

    unlocked_achievements = [achievement.id for achievement in unlocked_achievements]

    achievements_json = [
        {
            'id': ach.id,
            'name': ach.name,
        }
        for ach in unlocked_achievements
    ]

    data_response = {
        'success': True, 
        'results': results_json,
        'unlocked_achievements': achievements_json,
    }    

    return JsonResponse(data_response)

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

def serve_banner_image(request: HttpRequest, banner_id: int) -> HttpResponse:
    """
    Serves the banner_image for a given GachaBanner, using an efficient
    caching strategy that stores raw data.
    """
    cache_key = f"banner_image:{banner_id}"
    image_data = cache.get(cache_key)

    if image_data is None:
        print(f"CACHE MISS for key: {cache_key}")
        try:
            # Query the database for only the necessary fields.
            banner = GachaBanner.objects.values('banner_name', 'banner_image').get(pk=banner_id)
            
            if not banner['banner_image']:
                raise GachaBanner.DoesNotExist

            # Create a lightweight dictionary with the raw data to cache.
            image_data = {
                'name': banner['banner_name'],
                'image_bytes': banner['banner_image']
            }
            # Cache this dictionary for one hour.
            cache.set(cache_key, image_data, timeout=3600)

        except GachaBanner.DoesNotExist:
            # Cache a "not found" marker to prevent repeated invalid queries.
            image_data = "NOT_FOUND"
            cache.set(cache_key, image_data, timeout=60)
    else:
        print(f"CACHE HIT for key: {cache_key}")

    # --- Serve the response based on the retrieved data ---

    if image_data == "NOT_FOUND":
        # If the image doesn't exist, serve a static fallback image.
        fallback_path = finders.find("icon/website/portrait_404.png")
        if fallback_path:
            return FileResponse(open(fallback_path, "rb"), content_type="image/png")
        else:
            return HttpResponseNotFound("Banner image and fallback image not found.")

    # If data was found, build the response directly from the bytes in memory.
    response = HttpResponse(image_data['image_bytes'], content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{image_data["name"]}.png"'
    
    return response

def serve_achievement_image(request: HttpRequest, achievement_id: int) -> HttpResponse:
    """
    Serves the achievement_image for a given Achievement, using an efficient
    caching strategy that stores raw data.
    """
    cache_key = f"achievement_image:{achievement_id}"
    image_data = cache.get(cache_key)

    if image_data is None:
        print(f"CACHE MISS for key: {cache_key}")
        try:
            # Query the database for only the necessary fields.
            achievement = Achievement.objects.values('achievement_name', 'achievement_image').get(pk=achievement_id)
            
            if not achievement['achievement_image']:
                raise Achievement.DoesNotExist

            # Create a lightweight dictionary to cache.
            image_data = {
                'name': achievement['achievement_name'],
                'image_bytes': achievement['achievement_image']
            }
            # Cache the dictionary.
            cache.set(cache_key, image_data, timeout=60)

        except Achievement.DoesNotExist:
            # Cache a "not found" marker to prevent repeated invalid queries.
            image_data = "NOT_FOUND"
            cache.set(cache_key, image_data, timeout=60)
    else:
        print(f"CACHE HIT for key: {cache_key}")

    # --- Serve the response based on the retrieved data ---
    
    if image_data == "NOT_FOUND":
        # If the image doesn't exist, serve a static fallback image.
        fallback_path = finders.find("icon/website/portrait_404.png")
        if fallback_path:
            return FileResponse(open(fallback_path, "rb"), content_type="image/png")
        else:
            return HttpResponseNotFound("Achievement image and fallback image not found.")

    # If data was found, build the response directly from the bytes in memory.
    response = HttpResponse(image_data['image_bytes'], content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{image_data["name"]}.png"'
    
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
