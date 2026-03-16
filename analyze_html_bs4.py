
import os
from bs4 import BeautifulSoup

file_path = r"c:\Users\nhat\Downloads\toolchorach\Ôn luyện.html"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
        
    question_div = soup.find("div", class_="question-name")
    if question_div:
        print("Found question container:")
        print(question_div.prettify())
        
        # Look for siblings or parents to find answers
        parent = question_div.parent
        if parent:
            print("\nParent container:")
            print(parent.prettify()[:500]) # Print first 500 chars
            
            # Try to find answers
            answers = parent.find_all("div", class_="answer-item") # Guessing class name
            if not answers:
                 answers = soup.find_all("div", class_="answer-item")

            if answers:
                print(f"\nFound {len(answers)} answers (guessed selector):")
                for i, ans in enumerate(answers):
                    print(f"Answer {i}: {ans.prettify()[:100]}...")
            else:
                print("\nCould not find answers with 'answer-item'. Printing parent children classes:")
                for child in parent.children:
                    if child.name:
                        print(f"Child tag: {child.name}, Classes: {child.get('class')}")

    else:
        print("Could not find div with class 'question-name'")

except Exception as e:
    print(f"Error: {e}")
