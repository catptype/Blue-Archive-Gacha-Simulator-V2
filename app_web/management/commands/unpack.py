import json
import os
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from app_web.models import Version, School, Student, ImageAsset, GachaPreset, GachaBanner
# from gacha_app.models import GachaRatePreset
from .utils.Converter import Converter
from .utils.TextProgressBar import TextProgressBar
from .utils.DirectoryProcessor import DirectoryProcessor

class Command(BaseCommand):
    help = 'Import data from JSON files into model'
    def handle(self, *args, **options):
        ROOT_DIR = os.path.join(settings.BASE_DIR, 'app_web', 'management', 'data', 'json')

        preset_dir = os.path.join(ROOT_DIR, 'presets')        
        banner_dir = os.path.join(ROOT_DIR, 'banners')        
        school_dir = os.path.join(ROOT_DIR, 'schools')
        student_dir = os.path.join(ROOT_DIR, 'students')

        self.stdout.write(self.style.SUCCESS('Start unpack'))

        # self.unpack_gacha_preset(gacha_preset_json)
        self.unpack_preset(preset_dir)
        self.unpack_banner(banner_dir)
        self.unpack_school(school_dir)
        self.unpack_student(student_dir)

        self.stdout.write(self.style.SUCCESS('Data unpack complete'))

    def unpack_preset(self, dir):

        json_file = os.path.join(dir, 'preset.json')

        with open(json_file) as file:
            data_list = json.load(file)

        data_count = len(data_list)
        self.stdout.write(self.style.NOTICE(f'Unpacking {data_count} gacha preset records...'))
        prog_bar = TextProgressBar(data_count)

        for data in data_list:
            preset_name = data['name']
            preset_pickup = data['pickup']
            preset_r3 = data['r3']
            preset_r2 = data['r2']
            preset_r1 = data['r1']

            try:
                preset_obj:GachaPreset = GachaPreset.objects.get(preset_name=preset_name)
                        
            except ObjectDoesNotExist:
                GachaPreset.objects.create(
                    preset_name=preset_name,
                    preset_pickup_rate=preset_pickup,
                    preset_r3_rate=preset_r3,
                    preset_r2_rate=preset_r2,
                    preset_r1_rate=preset_r1,
                )

            prog_bar.add_step()

        self.stdout.write(self.style.SUCCESS(f'\nUnpack gacha preset data total {data_count}'))

    def unpack_banner(self, dir):
        """
        Unpacks all banner data from a directory of JSON files in a single, efficient pass.
        
        This function ensures the "Standard" banner is processed first, followed by
        all other banners sorted alphabetically. It also caches presets to minimize
        database queries.
        """
        json_file_list = DirectoryProcessor.get_only_files(dir, ['.json'])
        if not json_file_list:
            self.stdout.write(self.style.WARNING('No banner JSON files found to unpack.'))
            return

        # --- Step 1: Sort the file list to process "Standard.json" first ---
        # We use a custom sort key. The tuple (0, path) will always sort before (1, path).
        sorted_files = sorted(
            json_file_list,
            key=lambda path: (0, path) if "Standard.json" in path else (1, path)
        )

        # --- Step 2: Cache all GachaPreset objects to avoid lookups in the loop ---
        # This is a huge performance optimization.
        self.stdout.write(self.style.NOTICE('Caching gacha presets...'))
        presets_cache = {preset.preset_name: preset for preset in GachaPreset.objects.all()}
        
        # --- Step 3: Process all files in a single, unified loop ---
        self.stdout.write(self.style.NOTICE(f'Unpacking {len(sorted_files)} banners...'))
        prog_bar = TextProgressBar(len(sorted_files))
        created_count = 0
        updated_count = 0

        for json_file in sorted_files:
            try:
                with open(json_file) as file:
                    data = json.load(file)

                banner_name = data["name"]
                preset_name = data["preset"]
                image_bytes = Converter.base64_to_byte(data['image_base64'])

                # Get the preset object from our fast in-memory cache.
                preset_obj = presets_cache.get(preset_name)
                if not preset_obj:
                    self.stdout.write(self.style.ERROR(f"\nPreset '{preset_name}' not found for banner '{banner_name}'. Skipping."))
                    prog_bar.add_step()
                    continue
                
                # Use get_or_create for a clean, atomic operation.
                # It finds an existing banner or creates a new one in a single step.
                banner_obj, created = GachaBanner.objects.get_or_create(
                    banner_name=banner_name,
                    defaults={
                        'preset_id': preset_obj,
                        'banner_image': image_bytes  # Assuming you have this field
                    }
                )

                if created:
                    created_count += 1
                else:
                    # Optional: If you want to update existing banners, you can add logic here.
                    # For example: banner_obj.banner_image = image_bytes; banner_obj.save()
                    updated_count += 1
            
            except Exception as e:
                # A general catch-all for JSON errors or other issues.
                banner_name_for_error = data.get("name", json_file)
                self.stdout.write(self.style.ERROR(f"\nFailed to process banner '{banner_name_for_error}': {e}"))
            
            prog_bar.add_step()

        self.stdout.write(self.style.SUCCESS(f'\nBanner unpacking complete.'))
        self.stdout.write(self.style.SUCCESS(f'Summary: {created_count} created, {updated_count} found/updated.'))
        
    def unpack_school(self, dir):

        json_file = os.path.join(dir, 'school.json')

        with open(json_file) as file:
            data_list = json.load(file)
            
        data_count = len(data_list)
        self.stdout.write(self.style.NOTICE(f'Unpacking {data_count} school records...'))
        prog_bar = TextProgressBar(data_count)
        
        for data in data_list:
            school_name = data['name']
            school_image_bytes = Converter.base64_to_byte(data['image_base64'])

            try:
                school_obj:School = School.objects.get(school_name=school_name)

                # Check if the existing school's image is different
                if school_obj.image != school_image_bytes:
                    school_obj.school_image = school_image_bytes
                    school_obj.save()
                        
            except ObjectDoesNotExist:
                School.objects.create(
                    school_name=school_name,
                    school_image=school_image_bytes,
                )

            prog_bar.add_step()

        self.stdout.write(self.style.SUCCESS(f'\nUnpack school data total {data_count}'))

    def unpack_student(self, dir):
        json_file_list = DirectoryProcessor.get_only_files(dir, ['.json'])
        data_count = len(json_file_list)
        if data_count == 0:
            self.stdout.write(self.style.WARNING('No JSON files found to unpack.'))
            return

        # ===================================================================
        # STAGE 1: Discover and create all Version objects in the correct order.
        # ===================================================================
        self.stdout.write(self.style.NOTICE('First pass: Discovering all student versions...'))
        
        # Use a set to efficiently collect all unique version names.
        all_version_names = set()
        for json_file in json_file_list:
            with open(json_file) as file:
                data = json.load(file)
            all_version_names.add(data['version'])

        # --- Enforce the "Original" first, then sorted order ---
        # 1. Start with 'Original' if it exists.
        final_version_list = []
        if 'Original' in all_version_names:
            final_version_list.append('Original')
            all_version_names.remove('Original')
        
        # 2. Add the rest of the versions, sorted alphabetically.
        final_version_list.extend(sorted(list(all_version_names)))
        
        # Now, create the Version objects in the database in this specific order.
        # This ensures 'Original' gets ID=1, followed by the others.
        self.stdout.write(self.style.NOTICE(f'Creating {len(final_version_list)} version records...'))
        versions_cache = {}
        for version_name in final_version_list:
            # Using get_or_create is still efficient here. It will create them in our desired order.
            version_obj, _ = Version.objects.get_or_create(version_name=version_name)
            versions_cache[version_name] = version_obj # Cache the result for Stage 2.

        self.stdout.write(self.style.SUCCESS('Version creation complete.'))

        # ===================================================================
        # STAGE 2: Create all Student objects, using the cached versions.
        # ===================================================================
        self.stdout.write(self.style.NOTICE(f'Second pass: Unpacking {data_count} student records...'))
        prog_bar = TextProgressBar(data_count)

        for json_file in json_file_list:
            try:
                with open(json_file) as file:
                    data = json.load(file)
            
                student_name = data['name']
                student_version_name = data['version']
                student_school_name = data['school']
                student_rarity = data['rarity']
                student_is_limited = data['is_limited']
                student_portrait = Converter.base64_to_byte(data['base64']['portrait'])
                student_artwork = Converter.base64_to_byte(data['base64']['artwork'])

                # Retrieve the already created version object from our cache.
                version_obj = versions_cache[student_version_name]
                
                # We assume this is a one-time script, so we use create().
                # Using get_or_create is safer if you might re-run it.
                student_obj, created = Student.objects.get_or_create(
                    student_name=student_name,
                    version_id=version_obj,
                    defaults={
                        'student_rarity': student_rarity,
                        'school_id': School.objects.get(school_name=student_school_name),
                        'student_is_limited': student_is_limited,
                    }
                )

                # Only create assets for newly created students.
                if created:
                    asset_obj = ImageAsset.objects.create(
                        asset_portrait_data=student_portrait,
                        asset_artwork_data=student_artwork
                    )
                    student_obj.asset_id = asset_obj
                    student_obj.save()

            except Exception as e:
                student_name_for_error = data.get('name', 'N/A')
                self.stdout.write(self.style.ERROR(f"\nAn unexpected error occurred for student data '{student_name_for_error}': {e}"))
            
            prog_bar.add_step()
        
        self.stdout.write(self.style.SUCCESS(f'\nUnpack student data COMPLETE'))

    