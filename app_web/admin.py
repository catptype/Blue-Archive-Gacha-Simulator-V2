from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.template.loader import render_to_string

from .models import Student, School, Version

class RarityFilter(admin.SimpleListFilter):
    title = "rarity"
    parameter_name = "rarity"

    def lookups(self, request, model_admin):
        queryset = model_admin.get_queryset(request)
        rarity_values = queryset.order_by('-student_rarity').values_list('student_rarity', flat=True).distinct()

        # this code has strange behaviour "instance duplication" when I put ordering = ['name'] in class StudentAdmin 
        # rarity_values = queryset.values_list('rarity', flat=True).distinct()
        # Details https://docs.djangoproject.com/en/5.0/ref/models/querysets/#django.db.models.query.QuerySet.distinct

        # Filter out options with zero items
        return [(str(rarity), f"{'★' * rarity}") for rarity in rarity_values if queryset.filter(student_rarity=rarity).exists()]
    
    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(student_rarity=value)

class SchoolAdminForm(forms.ModelForm):
    class Meta:
        model = School
        fields = '__all__'

class SchoolAdmin(admin.ModelAdmin):
    form = SchoolAdminForm
    list_display = ['school_id', 'school_name', 'school_logo']
    ordering = ['school_name'] 

    def school_logo(self, obj:School):
        context = { 
            'school_id': obj.pk,
            'school_name': obj.name,
        }
        print(context)
        return render_to_string('admin/school_logo.html', context)