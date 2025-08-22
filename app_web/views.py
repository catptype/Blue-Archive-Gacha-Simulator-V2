from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render
from .models import School

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