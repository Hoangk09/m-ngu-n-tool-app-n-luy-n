import cv2
import numpy as np
import os
from pathlib import Path

# Paths
UPLOAD_DIR = r"C:\Users\nhat\.gemini\antigravity\brain\e901d8f7-4c19-4de0-a926-b661f87f901d"
OUTPUT_DIR = r"android_source\app\src\main\assets\templates"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Files
IMG_MC = os.path.join(UPLOAD_DIR, "uploaded_image_0_1765113945848.jpg")
IMG_TF = os.path.join(UPLOAD_DIR, "uploaded_image_1_1765113945848.jpg")
IMG_SA = os.path.join(UPLOAD_DIR, "uploaded_image_2_1765113945848.jpg")

def crop_and_save(img, x, y, w, h, name):
    crop = img[y:y+h, x:x+w]
    out_path = os.path.join(OUTPUT_DIR, name)
    cv2.imwrite(out_path, crop)
    print(f"Saved {name} at {out_path} ({w}x{h})")

def process_mc(path):
    print(f"Processing MC: {path}")
    img = cv2.imread(path)
    if img is None: return
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Threshold to find light buttons on white/grey bg
    # Assuming buttons have a border or slight contrast
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter for button-like rectangles (A, B, C, D)
    candidates = []
    print(f"MC: Found {len(contours)} contours")
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Relaxed constraints
        if w > 50 and h > 30: 
            ratio = w/float(h)
            if 1.5 < ratio < 15: # Allow wider range
                candidates.append((x, y, w, h))
                
    # Sort by Y position
    candidates.sort(key=lambda c: c[1])
    
    # We want the 4 distinct options.
    # Usually they are stacked vertically.
    # Let's filter overlapping or small noise inside larger buttons.
    # Heuristic: Keep large ones.
    candidates = [c for c in candidates if c[2] > 200] # Assuming image width is large (~1000px)
    
    if len(candidates) >= 4:
        # Sort by Area to find the main option boxes
        by_area = sorted(candidates, key=lambda c: c[2]*c[3], reverse=True)
        # Take top 10 largest, then sort by Y
        top_candidates = sorted(by_area[:10], key=lambda c: c[1])
        
        # Now find the 4 that are vertically aligned
        final_4 = []
        if top_candidates:
            last = top_candidates[0]
            final_4.append(last)
            for cand in top_candidates[1:]:
                # Check if significantly lower (Y)
                if cand[1] > last[1] + 50: 
                    final_4.append(cand)
                    last = cand
                if len(final_4) == 4: break
        
        mapping = ['option_a.png', 'option_b.png', 'option_c.png', 'option_d.png']
        for i, (x, y, w, h) in enumerate(final_4):
            if i < 4:
                crop_and_save(img, x, y, w, h, mapping[i])
    else:
        print(f"MC: Only found {len(candidates)} candidates")

def process_tf(path):
    print(f"Processing TF: {path}")
    img = cv2.imread(path)
    if img is None: 
        print("TF Image not found")
        return
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    candidates = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if 50 < w < 500 and 30 < h < 200:
            candidates.append((x, y, w, h))
            
    candidates.sort(key=lambda c: c[1]) # Sort by Y
    
    if len(candidates) >= 2:
        # Looking for the row with True/False
        # Usually they are side-by-side
        pairs = []
        for i in range(len(candidates)):
            for j in range(i+1, len(candidates)):
                c1 = candidates[i]
                c2 = candidates[j]
                if abs(c1[1] - c2[1]) < 40: # Same Y row
                     if abs(c1[0] - c2[0]) > 50: # Different X
                         pairs.append((c1, c2))
        
        if pairs:
            # Take the pair lowest on screen? Or first?
            # Typically at bottom?
            pair = pairs[-1] # Take last pair (bottom)
            # Sort left/right
            left = min(pair, key=lambda c: c[0])
            right = max(pair, key=lambda c: c[0])
            
            crop_and_save(img, left[0], left[1], left[2], left[3], "btn_true.png")
            crop_and_save(img, right[0], right[1], right[2], right[3], "btn_false.png")

def process_sa(path):
    print(f"Processing SA: {path}")
    img = cv2.imread(path)
    if img is None: 
        print("SA Image not found")
        return
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Try Thresholding first
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    candidates = []
    print(f"SA: Found {len(contours)} contours")
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Input box: wide, not too tall
        if w > 150 and h > 30:
             # Check aspect ratio
             if w/float(h) > 2.5:
                 candidates.append((x, y, w, h, w*h))
            
    candidates.sort(key=lambda c: c[4], reverse=True) # Largest area first
    
    if candidates:
        # Pick the largest one that looks like an input box
        # Maybe skip the very largest if it's the whole screen?
        # Check area ratio
        img_area = img.shape[0] * img.shape[1]
        
        best = None
        for cand in candidates:
            if cand[4] < img_area * 0.5: # Skip if > 50% of screen
                best = cand
                break
        
        if best:
            crop_and_save(img, best[0], best[1], best[2], best[3], "input_field.png")
        else:
            print("SA: No suitable candidate found")
    else:
        print("SA: No candidates found")

if __name__ == "__main__":
    if os.path.exists(IMG_MC): process_mc(IMG_MC)
    if os.path.exists(IMG_TF): process_tf(IMG_TF)
    if os.path.exists(IMG_SA): process_sa(IMG_SA)
