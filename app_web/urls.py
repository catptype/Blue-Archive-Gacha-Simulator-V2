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

    # --- NEW API ENDPOINT ---
    path('api/school/<int:school_id>/students/', views.get_students_by_school, name='get_students_by_school'),

    path('image/school/<int:school_id>', views.serve_school_image, name='serve_school_image'),
    path('image/student/<int:student_id>/<str:image_type>', views.serve_student_image, name='serve_student_image'),
    # path('image/student/<int:student_id>/artwork', views.serve_student_artwork, name='serve_student_artwork'),
    # path('image/student/<int:student_id>/portrait', views.serve_student_portrait, name='serve_student_portrait'),

]