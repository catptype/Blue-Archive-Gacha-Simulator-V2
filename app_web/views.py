import tempfile
from django.http import JsonResponse, HttpRequest, HttpResponse, FileResponse, HttpResponseNotFound
from django.shortcuts import render
from .models import School, Student
from django.contrib.staticfiles import finders

#######################################
#####        HTTPRESPONSE         #####
#######################################  
def home(request:HttpRequest) -> HttpResponse:

    context = {}
    return render(request, 'app_web/index.html', context)

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

def serve_student_image(request:HttpRequest, student_id:int):
    try:
        student_obj = Student.objects.get(student_id=student_id)
        student_name = student_obj.name
        student_version = student_obj.version
        student_image_bytes = student_obj.portrait

        if student_image_bytes is None:
            raise Student.DoesNotExist
        
    except Student.DoesNotExist:
        # Find the SVG file in the static folder
        svg_path = finders.find("icon/website/portrait_404.png")  # Replace with your SVG's path in static
        if not svg_path:
            return HttpResponseNotFound("SVG not found in static files.")
        
        return FileResponse(open(svg_path, "rb"), content_type="image/png")
    
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(student_image_bytes)
    temp_file.seek(0)

    response = FileResponse(temp_file, content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{student_name}_{student_version}.png"'

    return response
