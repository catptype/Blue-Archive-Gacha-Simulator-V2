import tempfile
from django.http import JsonResponse, HttpRequest, HttpResponse, FileResponse, HttpResponseNotFound
from django.shortcuts import render
from .models import School, Student
from django.contrib.staticfiles import finders
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

CACHE_IMAGE_TIMEOUT = 300 # 5 minutes 

#######################################
#####        HTTPRESPONSE         #####
#######################################
def home(request:HttpRequest) -> HttpResponse:
    context = {}
    return render(request, 'app_web/index.html', context)

@cache_page(300)
def student(request:HttpRequest) -> HttpResponse:
    school_obj = School.objects.all()
    context = {
        "school": school_obj
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
            cache.set(cache_key, image_data, timeout=60 * 15)

        except Student.DoesNotExist:
            # Cache the "not found" result to prevent future DB hits
            image_data = "NOT_FOUND"
            cache.set(cache_key, image_data, timeout=60 * 5)
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
