from django.urls import path
from . import views

urlpatterns = [
    # HTTPRESPONSE
    path('', views.home, name='home'),
    path('', views.home, name='student'),
    path('', views.home, name='gacha'),
    path('', views.home, name='login'),
    path('', views.home, name='logout'),
    path('', views.home, name='dashboard'),
    path('', views.home, name='register'),
]