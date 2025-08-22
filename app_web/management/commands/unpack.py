import json
import os
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from app_web.models import Version, School, Student, ImageAsset
# from gacha_app.models import GachaRatePreset
from .utils.Converter import Converter
from .utils.TextProgressBar import TextProgressBar
from .utils.DirectoryProcessor import DirectoryProcessor

class Command(BaseCommand):
    help = 'Import data from JSON files into model'
    def handle(self, *args, **options):
        ROOT_DIR = os.path.join(settings.BASE_DIR, 'app_web', 'management', 'data', 'json')

        # student_json = os.path.join(base_path, 'student.json')
        school_dir = os.path.join(ROOT_DIR, 'schools')
        student_dir = os.path.join(ROOT_DIR, 'students')
        # gacha_preset_json = os.path.join(base_path, 'gacha_preset.json')

        self.stdout.write(self.style.SUCCESS('Start unpack'))

        # self.unpack_gacha_preset(gacha_preset_json)
        self.unpack_school(school_dir)
        self.unpack_student(student_dir)

        self.stdout.write(self.style.SUCCESS('Data unpack complete'))

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
        self.stdout.write(self.style.NOTICE(f'Unpacking {data_count} student records...'))
        prog_bar = TextProgressBar(data_count)

        for json_file in json_file_list:

            with open(json_file) as file:
                data = json.load(file)
        
            student_name = data['name']
            student_version = data['version']
            student_school = data['school']
            student_rarity = data['rarity']
            student_is_limited = data['is_limited']
            student_portrait = Converter.base64_to_byte(data['base64']['portrait'])
            student_artwork = Converter.base64_to_byte(data['base64']['artwork'])

            try:
                version_obj:Version = Version.objects.get(version_name=student_version)
            except ObjectDoesNotExist:
                version_obj:Version = Version.objects.create(version_name=student_version)

            try:
                # self.stdout.write(self.style.WARNING(f'\nStudent data \'{student_name} {student_version}\' has error'))

                student_obj:Student = Student.objects.get(
                    student_name=student_name,
                    version_id=version_obj,
                )

                # Track if any changes are made
                changes = {
                    'school_id': School.objects.get(school_name=student_school),
                    'student_rarity': student_rarity,
                    'student_is_limited': student_is_limited,
                }

                # Check for changes and update the student object only if necessary
                is_change = False
                for field, new_value in changes.items():
                    if getattr(student_obj, field) != new_value:
                        setattr(student_obj, field, new_value)
                        is_change = True

                if is_change:    
                    student_obj.save()

            except ObjectDoesNotExist:
                student_obj = Student.objects.create(
                    student_name=student_name,
                    version_id=version_obj,
                    student_rarity=student_rarity,
                    school_id=School.objects.get(school_name=student_school),
                    student_is_limited=student_is_limited,
                )

                asset_obj = ImageAsset.objects.create(
                    asset_portrait_data=student_portrait,
                    asset_artwork_data=student_artwork
                )

                student_obj.asset_id = asset_obj
                student_obj.save()

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'\nStudent data \'{student_name}\' has error, {e}'))
            
            prog_bar.add_step()
        
        self.stdout.write(self.style.SUCCESS(f'\nUnpack student data COMPLETE'))

    # def unpack_gacha_preset(self, json_file):
    #     with open(json_file) as file:
    #         data_list = json.load(file)
            
    #     data_count = len(data_list)
    #     self.stdout.write(self.style.NOTICE(f'Unpacking {data_count} gacha preset records...'))
    #     prog_bar = TextProgressBar(data_count)

    #     for data in data_list:
    #         preset_name = data['name']
    #         preset_feature_rate = data['feature']
    #         preset_r3_rate = data['r3']
    #         preset_r2_rate = data['r2']
    #         preset_r1_rate = data['r1']

    #         try:
    #             preset_obj:GachaRatePreset = GachaRatePreset.objects.get(preset_name=preset_name)
                        
    #         except ObjectDoesNotExist:
    #             GachaRatePreset.objects.create(
    #                 preset_name=preset_name,
    #                 preset_feature_rate=preset_feature_rate,
    #                 preset_r3_rate=preset_r3_rate,
    #                 preset_r2_rate=preset_r2_rate,
    #                 preset_r1_rate=preset_r1_rate,
    #             )

    #         prog_bar.add_step()
        
    #     self.stdout.write(self.style.SUCCESS(f'\nUnpack gacha preset data total {data_count}'))