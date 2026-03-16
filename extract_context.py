
import os

file_path = r"c:\Users\nhat\Downloads\toolchorach\Ôn luyện.html"
output_path = r"c:\Users\nhat\Downloads\toolchorach\context.txt"
search_term = "question-name"

try:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        
    index = content.find(search_term)
    if index != -1:
        start = max(0, index - 1000)
        end = min(len(content), index + 3000)
        context = content[start:end]
        
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(f"Found at index {index}\n")
            out.write("-" * 20 + "\n")
            out.write(context)
        print(f"Context written to {output_path}")
    else:
        print("Search term not found")
        
except Exception as e:
    print(f"Error: {e}")
