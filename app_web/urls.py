from django.urls import path
from . import views

urlpatterns = [
    # HTTPRESPONSE
    path('', views.home, name='home'),
]