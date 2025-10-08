import json
import os
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction
from app_web.models import Version, School, Student, ImageAsset, GachaPreset, GachaBanner, Achievement
from .utils.Converter import Converter
from .utils.TextProgressBar import TextProgressBar
from .utils.DirectoryProcessor import DirectoryProcessor

class Command(BaseCommand):
    """
    A Django management command to import all initial data for the application
    from a structured directory of JSON files. The entire import process is
    wrapped in a single atomic transaction to ensure data integrity.
    """
    help = 'Import data from JSON files into the database.'

    # ===================================================================
    # --- MAIN HANDLER ---
    # ===================================================================
    @transaction.atomic
    def handle(self, *args, **options):
        """Main entry point for the command."""
        ROOT_DIR = os.path.join(settings.BASE_DIR, 'app_web', 'management', 'data', 'json')
        
        # Define directories for each data type
        dirs = {
            'presets': os.path.join(ROOT_DIR, 'presets'),
            'banners': os.path.join(ROOT_DIR, 'banners'),
            'schools': os.path.join(ROOT_DIR, 'schools'),
            'students': os.path.join(ROOT_DIR, 'students'),
            'achievements': os.path.join(ROOT_DIR, 'achievements'),
        }

        self.stdout.write(self.style.SUCCESS('--- Starting Data Unpack ---'))
        
        # Execute unpackers in an order that respects model dependencies
        self.unpack_presets(dirs['presets'])
        self.unpack_schools(dirs['schools'])
        self.unpack_students_and_versions(dirs['students']) # This also handles Versions
        self.unpack_banners(dirs['banners'])
        self.unpack_achievements(dirs['achievements'])

        self.stdout.write(self.style.SUCCESS('\n--- Data Unpack Complete ---'))

    # ===================================================================
    # --- UNPACKER METHODS ---
    # ===================================================================
    def unpack_presets(self, dir_path):
        """Unpacks GachaPreset data from a single JSON file."""
        self.stdout.write(self.style.NOTICE('\nUnpacking Gacha Presets...'))
        json_file = os.path.join(dir_path, 'presets.json')
        try:
            with open(json_file) as f:
                data_list = json.load(f)
            
            prog_bar = TextProgressBar(len(data_list))
            for data in data_list:
                GachaPreset.objects.update_or_create(
                    preset_name=data['name'],
                    defaults={
                        'preset_pickup_rate': data['pickup'],
                        'preset_r3_rate': data['r3'],
                        'preset_r2_rate': data['r2'],
                        'preset_r1_rate': data['r1'],
                    }
                )
                prog_bar.add_step()
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully unpacked {len(data_list)} presets.'))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('presets.json not found. Skipping.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nAn error occurred: {e}'))

    def unpack_schools(self, dir_path):
        """Unpacks School data from a single JSON file."""
        self.stdout.write(self.style.NOTICE('\nUnpacking Schools...'))
        json_file = os.path.join(dir_path, 'schools.json')
        try:
            with open(json_file) as f:
                data_list = json.load(f)

            prog_bar = TextProgressBar(len(data_list))
            for data in data_list:
                School.objects.update_or_create(
                    school_name=data['name'],
                    defaults={'school_image': Converter.base64_to_byte(data['image_base64'])}
                )
                prog_bar.add_step()
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully unpacked {len(data_list)} schools.'))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('schools.json not found. Skipping.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nAn error occurred: {e}'))

    def unpack_students_and_versions(self, dir_path):
        """Unpacks Version and Student data from a directory of JSON files."""
        self.stdout.write(self.style.NOTICE('\nUnpacking Students and Versions...'))
        json_files = DirectoryProcessor.get_only_files(dir_path, ['.json'])
        if not json_files:
            self.stdout.write(self.style.WARNING('No student JSON files found. Skipping.'))
            return
            
        # --- Stage 1: Discover and create all Version objects in sorted order ---
        all_version_names = {json.load(open(f))['version'] for f in json_files}
        final_version_list = ['Original'] + sorted(list(all_version_names - {'Original'}))
        
        versions_cache = {}
        for version_name in final_version_list:
            version_obj, _ = Version.objects.get_or_create(version_name=version_name)
            versions_cache[version_name] = version_obj
        self.stdout.write(self.style.SUCCESS(f'Created/verified {len(versions_cache)} versions.'))
        
        # --- Stage 2: Create all Student objects ---
        schools_cache = {school.school_name: school for school in School.objects.all()}
        prog_bar = TextProgressBar(len(json_files))
        for json_file in json_files:
            try:
                with open(json_file) as f:
                    data = json.load(f)
                
                student_obj, created = Student.objects.update_or_create(
                    student_name=data['name'],
                    version_id=versions_cache[data['version']],
                    defaults={
                        'student_rarity': data['rarity'],
                        'school_id': schools_cache[data['school']],
                        'student_is_limited': data['is_limited'],
                    }
                )

                if created:
                    asset_obj = ImageAsset.objects.create(
                        asset_portrait_data=Converter.base64_to_byte(data['base64']['portrait']),
                        asset_artwork_data=Converter.base64_to_byte(data['base64']['artwork'])
                    )
                    student_obj.asset_id = asset_obj
                    student_obj.save()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"\nError processing student file {os.path.basename(json_file)}: {e}"))
            prog_bar.add_step()
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully unpacked {len(json_files)} students.'))

    def unpack_banners(self, dir_path):
        """Unpacks GachaBanner data from a directory of JSON files."""
        self.stdout.write(self.style.NOTICE('\nUnpacking Banners...'))
        json_files = DirectoryProcessor.get_only_files(dir_path, ['.json'])
        if not json_files:
            self.stdout.write(self.style.WARNING('No banner JSON files found. Skipping.'))
            return

        sorted_files = sorted(json_files, key=lambda p: (0, p) if "Standard.json" in p else (1, p))
        
        # --- Cache all necessary related data for high performance ---
        presets_cache = {p.name: p for p in GachaPreset.objects.all()}
        versions_cache = {v.name: v for v in Version.objects.all()}
        students_cache = {(s.name, s.version): s for s in Student.objects.select_related('version_id')}
        
        prog_bar = TextProgressBar(len(sorted_files))
        for json_file in sorted_files:
            try:
                with open(json_file) as f:
                    data = json.load(f)

                banner_obj, _ = GachaBanner.objects.update_or_create(
                    banner_name=data["name"],
                    defaults={
                        'preset_id': presets_cache[data["preset"]],
                        'banner_image': Converter.base64_to_byte(data['image_base64']),
                        'banner_include_limited': data["limited"]
                    }
                )
                
                # --- Set Many-to-Many relationships using the cache ---
                version_objects = [versions_cache[v_name] for v_name in data["version"] if v_name in versions_cache]
                banner_obj.banner_include_version.set(version_objects)
                
                pickup_objects = [students_cache[(p["name"], p["version"])] for p in data["pickup"] if (p["name"], p["version"]) in students_cache]
                banner_obj.banner_pickup.set(pickup_objects)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"\nError processing banner file {os.path.basename(json_file)}: {e}"))
            prog_bar.add_step()
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully unpacked {len(sorted_files)} banners.'))

    def unpack_achievements(self, dir_path):
        """Unpacks Achievement definitions from a directory of JSON files."""
        self.stdout.write(self.style.NOTICE('\nUnpacking Achievements...'))
        json_files = DirectoryProcessor.get_only_files(dir_path, ['.json'])
        if not json_files:
            self.stdout.write(self.style.WARNING('No achievement JSON files found. Skipping.'))
            return

        prog_bar = TextProgressBar(len(json_files))
        for json_file in json_files:
            try:
                with open(json_file) as file:
                    data = json.load(file)
                
                Achievement.objects.update_or_create(
                    achievement_key=data["key"],
                    defaults={
                        'achievement_name': data["name"],
                        'achievement_description': data["description"],
                        'achievement_category': data["category"],
                        'achievement_image': Converter.base64_to_byte(data['image_base64'])
                    }
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"\nError processing achievement file {os.path.basename(json_file)}: {e}"))
            prog_bar.add_step()
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully unpacked {len(json_files)} achievements.'))