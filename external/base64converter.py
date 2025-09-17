import os
import base64
import json

def image_to_base64_json(image_path, output_dir="output"):
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Get file name without extension
    filename = os.path.splitext(os.path.basename(image_path))[0]

    # Read and encode image
    with open(image_path, "rb") as img_file:
        encoded_string = base64.b64encode(img_file.read()).decode("utf-8")

    # Prepare JSON data
    data = {
        "image_base64": encoded_string
    }

    # Save to JSON file
    json_path = os.path.join(output_dir, f"{filename}.json")
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2)

    print(f"Saved: {json_path}")


# Example usage
if __name__ == "__main__":
    input_dir = "images"
    output_dir = "output"

    # Ensure input directory exists
    if not os.path.isdir(input_dir):
        print(f"Directory '{input_dir}' not found.")
    else:
        # Loop through all image files
        for file in os.listdir(input_dir):
            if file.lower().endswith((".png", ".jpg")):
                image_path = os.path.join(input_dir, file)
                image_to_base64_json(image_path, output_dir)
