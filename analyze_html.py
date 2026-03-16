
import os

file_path = r"c:\Users\nhat\Downloads\toolchorach\Ôn luyện.html"
search_term = "question-name"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if search_term in line:
                print(f"Found at line {i+1}")
                # Print context
                start = max(0, i - 5)
                end = min(len(lines), i + 20)
                for j in range(start, end):
                    print(f"{j+1}: {lines[j].strip()}")
                break
        else:
            print("Not found")
except Exception as e:
    print(f"Error: {e}")
