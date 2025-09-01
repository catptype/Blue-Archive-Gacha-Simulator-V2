import base64 
import json
import os
from io import BytesIO
from PIL import Image
from util.DirectoryProcessor import DirectoryProcessor

OUTPUT_DIR = r"json"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_base64(image_path):
    with Image.open(image_path) as img:
        # Ensure the image is in RGBA mode
        img = img.convert("RGBA")
        
        # Save the image to a BytesIO object
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        # Convert the image bytes to base64
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        return img_base64
    
def main():

    school_list = []

    path_list = DirectoryProcessor.get_all_files(r"images\school")
    for path in path_list:
        _, filename, _ = DirectoryProcessor.decompose_path(path)

        school_name = filename
        image_base64 = generate_base64(path)

        data = {
            'name': school_name,
            'image_base64': image_base64,
        }

        school_list.append(data)

    with open(os.path.join(OUTPUT_DIR, 'school.json'), "w") as json_file:
        json.dump(school_list, json_file, indent=4) 

if __name__ == "__main__":
    main()