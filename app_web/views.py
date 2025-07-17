from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render

#######################################
#####        HTTPRESPONSE         #####
#######################################  
def home(request:HttpRequest) -> HttpResponse:

    context = {}
    return render(request, 'app_web/index.html', context)