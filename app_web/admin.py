from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.template.loader import render_to_string

from .models import Student, School, Version, GachaBanner, GachaPreset, GachaTransaction, UserInventory, Achievement

def create_image_display(image_type, description):
    """
    A factory function that creates a method for the Django admin list_display.
    This avoids duplicating the logic for each image type.
    """
    def image_display_method(self, obj: Student):
        context = {
            'student_id': obj.pk,
            'student_name': f"{obj.name} {obj.version}",
            'image_type': image_type,  # Pass the specific image type to the template
        }
        return render_to_string('admin/student-image.html', context)

    # Set attributes required by the Django admin
    image_display_method.short_description = description
    return image_display_method

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

class StudentAdminForm(forms.ModelForm):
    rarity = forms.TypedChoiceField(
        choices=Student._meta.get_field('student_rarity').choices,
        widget=forms.RadioSelect(),
        coerce=int,
        empty_value=None,
    )
    version = forms.ModelChoiceField(
        queryset=Version.objects.all(),
        empty_label="Select version",  # Set the custom text for the blank choice
        required=True,
    )
    school = forms.ModelChoiceField(
        queryset=School.objects.all().order_by('school_name'),
        empty_label="Select school",  # Set the custom text for the blank choice
        required=True,
    )
    is_limited = forms.TypedChoiceField(
        label="Is limited",
        choices=((True, 'Yes'), (False, 'No')),
        widget=forms.RadioSelect(),
        coerce=lambda x: x == 'True',  # Ensure True/False values are used
        initial=False,
    )
    # image = forms.ImageField(
    #     label="Portrait",
    #     widget=forms.ClearableFileInput(), 
    #     required=False,
    # )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['image'].widget.template_name = 'admin/widgets-portrait.html'

    class Meta:
        model = Student
        fields = '__all__'

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ['school_id', 'school_name', 'school_logo']
    ordering = ['school_name'] 

    def school_logo(self, obj:School):
        context = { 
            'school_id': obj.pk,
            'school_name': obj.name,
        }
        print(context)
        return render_to_string('admin/school-logo.html', context)

@admin.register(Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = [
        'version_id',
        'version_name'
    ]
    list_per_page = 10
    ordering = ['version_id']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm
    list_display = [
        'student_id', 
        'student_portrait', 
        'student_artwork', 
        'student_name', 
        'version_id', 
        'student_rarity', 
        'school_id', 
        'student_is_limited', 
        'edit_button'
    ]
    list_per_page = 10
    ordering = ['student_id']

    show_facets = admin.ShowFacets.ALWAYS
    search_fields = ['student_name']
    list_filter = [RarityFilter, 'school_id', 'version_id', 'student_is_limited']

    student_portrait = create_image_display(image_type='portrait', description='Portrait')
    student_artwork = create_image_display(image_type='artwork', description='Artwork')

    @admin.display(description="")
    def edit_button(self, obj):
        app = obj._meta.app_label
        model = obj._meta.model_name
        edit_url = reverse(f'admin:{app}_{model}_change',  args=[obj.id])
        context = { 'edit_url': edit_url }
        return render_to_string('admin/edit-button.html', context)

@admin.register(GachaPreset)
class GachaPresetAdmin(admin.ModelAdmin):
    list_display = [
        'preset_id', 
        'preset_name', 
        'preset_pickup_rate', 
        'preset_r3_rate', 
        'preset_r2_rate', 
        'preset_r1_rate', 
    ]
    list_per_page = 10
    ordering = ['preset_id']

@admin.register(GachaBanner)
class GachaBannerAdmin(admin.ModelAdmin):
    list_display = [
        'banner_id',
        'banner_image_custom',
        'banner_name',
        'preset_id',
    ]

    # Use filter_horizontal for a much better user experience with ManyToManyFields.
    filter_horizontal = ('banner_pickup', 'banner_include_version', 'banner_exclude')

    @admin.display(description='Image')
    def banner_image_custom(self, obj:GachaBanner):
        context = {
            'banner_id': obj.pk,
            'banner_name': obj.name
        }
        return render_to_string('admin/banner-image.html', context)

    list_per_page = 10
    ordering = ['banner_id']

@admin.register(GachaTransaction)
class GachaTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id',
        'transaction_user',
        'banner_id',
        'student_id',
        'transaction_create_on'
    ]

    list_filter = ['transaction_user', 'banner_id']

    list_per_page = 50

@admin.register(UserInventory)
class UserInventoryAdmin(admin.ModelAdmin):
    list_display = [
        'inventory_id',
        'inventory_user',
        'student_id',
        'inventory_num_obtained',
        'inventory_first_obtained_on'
    ]

    list_per_page = 10
    
    list_filter = ['student_id']

@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = [
        'achievement_id',
        'achievement_category',
        'achievement_icon_custom',
        'achievement_name',
        'achievement_description',
        'achievement_key',
    ]

    list_per_page = 10

    ordering = ['achievement_id']

    @admin.display(description='Image')
    def achievement_icon_custom(self, obj:Achievement):
        context = {
            'achievement_id': obj.pk,
            'achievement_name': obj.name
        }
        return render_to_string('admin/achievement-image.html', context)
