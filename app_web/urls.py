from django.urls import path
from . import views

urlpatterns = [
    # HTTPRESPONSE
    path('', views.home, name='home'),
    path('student/', views.student, name='student'),

    path('gacha/', views.gacha, name='gacha'),
    path('banner-details/<int:banner_id>/', views.banner_details, name='banner_details'),
    path('banner-result/', views.gacha_results, name='gacha_results'),
    path('student-card/<int:student_id>/', views.student_card, name='student_card'),
    path('', views.home, name='login'),
    path('', views.home, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/<str:tab_name>/', views.get_dashboard_content, name='get_dashboard_content'),
    path('dashboard/widget/kpis/', views.dashboard_widget_kpis, name='dashboard_widget_kpis'),
    path('dashboard/widget/top-students/', views.dashboard_widget_top_students, name='dashboard_widget_top_students'),
    path('dashboard/widget/top-students/<int:rarity>/', views.get_top_students_by_rarity, name='get_top_students_by_rarity'),
    path('dashboard/widget/first-r3-pull/', views.dashboard_widget_first_r3_pull, name='dashboard_widget_first_r3_pull'),
    path('dashboard/widget/chart-overall-rarity/', views.dashboard_widget_chart_overall_rarity, name='dashboard_widget_chart_overall_rarity'),
    path('dashboard/widget/chart-banner-breakdown/', views.dashboard_widget_chart_banner_breakdown, name='dashboard_widget_chart_banner_breakdown'),
    path('dashboard/widget/chart-banner-activity/', views.dashboard_widget_chart_banner_activity, name='dashboard_widget_chart_banner_activity'),
    path('dashboard/widget/performance-table/', views.dashboard_widget_performance_table, name='dashboard_widget_performance_table'),
    path('dashboard/widget/milestone-timeline/', views.dashboard_widget_milestone_timeline, name='dashboard_widget_milestone_timeline'),

    path('', views.home, name='register'),

    # --- NEW API ENDPOINT ---
    path('api/school/<int:school_id>/students/', views.get_students_by_school, name='get_students_by_school'),
    path('api/gacha/<int:banner_id>/draw_one/', views.draw_one_gacha, name='draw_one_gacha'),
    path('api/gacha/<int:banner_id>/draw_ten/', views.draw_ten_gacha, name='draw_ten_gacha'),

    path('image/school/<int:school_id>/', views.serve_school_image, name='serve_school_image'),
    path('image/banner/<int:banner_id>/', views.serve_banner_image, name='serve_banner_image'),
    path('image/achievement/<int:achievement_id>/', views.serve_achievement_image, name='serve_achievement_image'),
    path('image/student/<int:student_id>/<str:image_type>/', views.serve_student_image, name='serve_student_image'),
    # path('image/student/<int:student_id>/artwork', views.serve_student_artwork, name='serve_student_artwork'),
    # path('image/student/<int:student_id>/portrait', views.serve_student_portrait, name='serve_student_portrait'),

]