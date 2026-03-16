
import os
from bs4 import BeautifulSoup

file_path = r"c:\Users\nhat\Downloads\toolchorach\Ôn luyện.html"

try:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f, "html.parser")
        
    print("--- BUTTONS ---")
    buttons = soup.find_all("button")
    for btn in buttons:
        print(f"Text: {btn.get_text(strip=True)}, Class: {btn.get('class')}, ID: {btn.get('id')}")

    print("\n--- LINKS (A tags) ---")
    links = soup.find_all("a")
    for link in links:
        # Filter for likely buttons
        classes = link.get("class", [])
        if any("btn" in c for c in classes) or "tiếp" in link.get_text(strip=True).lower() or "next" in link.get_text(strip=True).lower():
             print(f"Text: {link.get_text(strip=True)}, Class: {classes}, ID: {link.get('id')}")

except Exception as e:
    print(f"Error: {e}")
