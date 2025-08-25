from django.urls import path
from . import views

urlpatterns = [
    # HTTPRESPONSE
    path('', views.home, name='home'),
    path('student', views.student, name='student'),
    path('', views.home, name='gacha'),
    path('', views.home, name='login'),
    path('', views.home, name='logout'),
    path('', views.home, name='dashboard'),
    path('', views.home, name='register'),

    path('image/school/<int:school_id>', views.serve_school_image, name='serve_school_image'),
    path('image/student/<int:student_id>', views.serve_student_image, name='serve_student_image'),
]