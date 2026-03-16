import google.generativeai as genai
import PIL.Image
import cv2
import os
import json

# Config
API_KEY = "AIzaSyD0dyuke56FurEOQf3Yx1Ow5T49-IoeEsM"
UPLOAD_DIR = r"C:\Users\nhat\.gemini\antigravity\brain\e901d8f7-4c19-4de0-a926-b661f87f901d"
OUTPUT_DIR = r"android_source\app\src\main\assets\templates"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Files
IMG_MC = os.path.join(UPLOAD_DIR, "uploaded_image_0_1765113945848.jpg")
IMG_TF = os.path.join(UPLOAD_DIR, "uploaded_image_1_1765113945848.jpg")
IMG_SA = os.path.join(UPLOAD_DIR, "uploaded_image_2_1765113945848.jpg")

genai.configure(api_key=API_KEY)

import time

MODEL_NAMES = ['gemini-1.5-flash']

def get_bounding_boxes(img_path, query):
    print(f"Asking Gemini for '{query}' in {img_path}...")
    try:
        img = PIL.Image.open(img_path)
    except Exception as e:
        print(f"Failed to open image: {e}")
        return []

    prompt = f"""
    Return bounding box for {query}.
    Return JSON format: {{"boxes": [ymin, xmin, ymax, xmax]}} or {{"boxes": [[ymin, xmin, ymax, xmax], ...]}}
    Coordinates should be normalized (0-1000).
    Only return valid JSON. Do not use markdown blocks.
    """
    
    MAX_RETRIES = 5
    for attempt in range(MAX_RETRIES):
        try:
            # Using the exact model name from quiz_solver.py
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([prompt, img])
            text = response.text
            text = text.replace("```json", "").replace("```", "").strip()
            # Find first [ and last ]
            p1 = text.find("[")
            p2 = text.rfind("]")
            if p1 != -1 and p2 != -1:
                text = text[p1:p2+1]
                # Wrap in dictionary if it's just a list
                if text.startswith("[") and not text.startswith("[["):
                     # boxes: [y,x,y,x]
                     pass
                
            # Just parse JSON
            try:
                data = json.loads(text)
                if isinstance(data, list): return data # Box list
                return data.get("boxes", [])
            except:
                # Try to parse raw text if simple list
                if "," in text:
                     nums = [float(x.strip()) for x in text.replace("[","").replace("]","").split(",")]
                     if len(nums) == 4: return [nums]
                
            return []
        except Exception as e:
            print(f"Error (Attempt {attempt}): {e}")
            if "429" in str(e) or "ResourceExhausted" in str(e):
                time.sleep(10 * (attempt + 1))
            else:
                break
    return []

def crop_box(img_path, box, name):
    img = cv2.imread(img_path)
    h, w, _ = img.shape
    
    ymin, xmin, ymax, xmax = box
    
    x = int((xmin / 1000) * w)
    y = int((ymin / 1000) * h)
    w_crop = int(((xmax - xmin) / 1000) * w)
    h_crop = int(((ymax - ymin) / 1000) * h)
    
    # Padding
    pad = 5
    x = max(0, x + pad)
    y = max(0, y + pad)
    w_crop = max(1, w_crop - 2*pad)
    h_crop = max(1, h_crop - 2*pad)

    crop = img[y:y+h_crop, x:x+w_crop]
    out_path = os.path.join(OUTPUT_DIR, name)
    cv2.imwrite(out_path, crop)
    print(f"Saved {name}")

def process_mc():
    if not os.path.exists(IMG_MC): return
    # Ask for all 4 options
    # We ask for "Bounding boxes for labels A, B, C, D"
    # Actually ask for "The bounding box of option A container", etc.
    
    for label, filename in [("A", "option_a.png"), ("B", "option_b.png"), ("C", "option_c.png"), ("D", "option_d.png")]:
        query = f"the clickable button containing option {label}"
        boxes = get_bounding_boxes(IMG_MC, query)
        if boxes:
            # Usually returns list of boxes or single box
            box = boxes[0] if isinstance(boxes[0], list) else boxes
            crop_box(IMG_MC, box, filename)

def process_tf():
    if not os.path.exists(IMG_TF): return
    
    # Ask for True button
    boxes = get_bounding_boxes(IMG_TF, "the button labeled 'Đúng' or 'True'")
    if boxes:
        box = boxes[0] if isinstance(boxes[0], list) else boxes
        crop_box(IMG_TF, box, "btn_true.png")
        
    # Ask for False button
    boxes = get_bounding_boxes(IMG_TF, "the button labeled 'Sai' or 'False'")
    if boxes:
        box = boxes[0] if isinstance(boxes[0], list) else boxes
        crop_box(IMG_TF, box, "btn_false.png")

def process_sa():
    if not os.path.exists(IMG_SA): return
    
    # Ask for Input field
    boxes = get_bounding_boxes(IMG_SA, "the empty text input field box for typing answer")
    if boxes:
        box = boxes[0] if isinstance(boxes[0], list) else boxes
        crop_box(IMG_SA, box, "input_field.png")

if __name__ == "__main__":
    process_mc()
    process_tf()
    process_sa()
