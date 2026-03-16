"""
Quiz Solver - Image Sending Logic
Handles sending screenshot images to Gemini API for quiz solving
"""
import base64
import io
import json
import time
from typing import Optional, Tuple
import requests

# Try to import PIL for image processing
try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Try to import google.generativeai
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


class GeminiImageSolver:
    """
    Send images to Gemini API for quiz solving
    Supports both direct API and backend proxy
    """
    
    # Default prompt for quiz solving
    DEFAULT_PROMPT = """Analyze this quiz question image and determine THE CORRECT answer.

Rules:
1. If multiple choice (A/B/C/D): Return ONLY the letter (A, B, C, or D)
2. If True/False: Return ONLY "TRUE" or "FALSE"  
3. If short answer/fill blank: Return ONLY the answer text
4. Do NOT explain, just give the final answer
5. If you cannot determine, return "ERROR: [reason]"

Answer:"""

    def __init__(self, api_key: str = None, backend_url: str = None):
        """
        Initialize solver with API key or backend URL
        
        Args:
            api_key: Gemini API key for direct API calls
            backend_url: Backend URL for proxy (e.g., http://localhost:5000)
        """
        self.api_key = api_key
        self.backend_url = backend_url
        
        if api_key and HAS_GENAI:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None
    
    def capture_screen(self) -> Optional[Image.Image]:
        """Capture the current screen"""
        if not HAS_PIL:
            print("Error: PIL/Pillow not installed")
            return None
        
        try:
            screenshot = ImageGrab.grab()
            return screenshot
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return None
    
    def image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """Convert PIL Image to base64 string"""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    def image_to_bytes(self, image: Image.Image, format: str = "PNG") -> bytes:
        """Convert PIL Image to bytes"""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        buffer.seek(0)
        return buffer.read()
    
    def solve_with_api(self, image: Image.Image, prompt: str = None) -> str:
        """
        Send image to Gemini API directly
        
        Args:
            image: PIL Image to analyze
            prompt: Custom prompt (uses default if None)
            
        Returns:
            Answer string or error message
        """
        if not self.model:
            return "Error: Gemini API not configured"
        
        if prompt is None:
            prompt = self.DEFAULT_PROMPT
        
        try:
            # Convert image to bytes for Gemini
            image_bytes = self.image_to_bytes(image)
            
            # Create image part for Gemini
            image_part = {
                "mime_type": "image/png",
                "data": image_bytes
            }
            
            # Send to Gemini
            response = self.model.generate_content([prompt, image_part])
            
            if response and response.text:
                return response.text.strip()
            else:
                return "Error: Empty response from Gemini"
                
        except Exception as e:
            return f"Error: {str(e)}"
    
    def solve_with_backend(self, image: Image.Image, prompt: str = None, 
                           auth_token: str = None) -> str:
        """
        Send image to backend server for solving
        
        Args:
            image: PIL Image to analyze
            prompt: Custom prompt
            auth_token: JWT token for authentication
            
        Returns:
            Answer string or error message
        """
        if not self.backend_url:
            return "Error: Backend URL not configured"
        
        if prompt is None:
            prompt = self.DEFAULT_PROMPT
        
        try:
            # Convert image to base64
            image_base64 = self.image_to_base64(image)
            
            # Prepare request
            url = f"{self.backend_url}/api/solve/screenshot"
            headers = {"Content-Type": "application/json"}
            
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            
            payload = {
                "image": image_base64,
                "prompt": prompt
            }
            
            # Send request
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("answer", "Error: No answer in response")
                else:
                    return f"Error: {data.get('message', 'Unknown error')}"
            else:
                return f"Error: HTTP {response.status_code}"
                
        except requests.Timeout:
            return "Error: Request timeout"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def solve(self, image: Image.Image = None, prompt: str = None,
              auth_token: str = None, use_backend: bool = False) -> str:
        """
        Unified solve method - auto capture screen if no image provided
        
        Args:
            image: PIL Image (captures screen if None)
            prompt: Custom prompt
            auth_token: JWT token for backend
            use_backend: Force use backend instead of direct API
            
        Returns:
            Answer string
        """
        # Capture screen if no image
        if image is None:
            image = self.capture_screen()
            if image is None:
                return "Error: Failed to capture screen"
        
        # Use backend or direct API
        if use_backend or (self.backend_url and not self.api_key):
            return self.solve_with_backend(image, prompt, auth_token)
        else:
            return self.solve_with_api(image, prompt)


class ImageSendingUtils:
    """Utility functions for sending images"""
    
    @staticmethod
    def load_image_from_file(filepath: str) -> Optional[Image.Image]:
        """Load image from file path"""
        if not HAS_PIL:
            return None
        try:
            return Image.open(filepath)
        except Exception as e:
            print(f"Error loading image: {e}")
            return None
    
    @staticmethod
    def resize_image(image: Image.Image, max_width: int = 1280, 
                     max_height: int = 720) -> Image.Image:
        """Resize image while maintaining aspect ratio"""
        width, height = image.size
        
        if width <= max_width and height <= max_height:
            return image
        
        ratio = min(max_width / width, max_height / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    @staticmethod
    def crop_question_area(image: Image.Image, 
                           top_ratio: float = 0.15,
                           bottom_ratio: float = 0.85) -> Image.Image:
        """Crop to question area (remove header/footer)"""
        width, height = image.size
        top = int(height * top_ratio)
        bottom = int(height * bottom_ratio)
        
        return image.crop((0, top, width, bottom))
    
    @staticmethod
    def image_to_data_uri(image: Image.Image) -> str:
        """Convert image to data URI for HTML/web use"""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        base64_data = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{base64_data}"


def send_image_to_gemini_api(
    image_path_or_bytes: str | bytes | Image.Image,
    api_key: str,
    prompt: str = None,
    model_name: str = "gemini-1.5-flash"
) -> Tuple[bool, str]:
    """
    Standalone function to send image to Gemini API
    
    Args:
        image_path_or_bytes: File path, bytes, or PIL Image
        api_key: Gemini API key
        prompt: Custom prompt
        model_name: Model to use
        
    Returns:
        (success: bool, result: str)
    """
    if not HAS_GENAI:
        return False, "Error: google-generativeai not installed"
    
    if not HAS_PIL:
        return False, "Error: PIL/Pillow not installed"
    
    try:
        # Configure API
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        # Load image
        if isinstance(image_path_or_bytes, str):
            image = Image.open(image_path_or_bytes)
        elif isinstance(image_path_or_bytes, bytes):
            image = Image.open(io.BytesIO(image_path_or_bytes))
        elif isinstance(image_path_or_bytes, Image.Image):
            image = image_path_or_bytes
        else:
            return False, "Error: Invalid image input"
        
        # Convert to bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        image_bytes = buffer.read()
        
        # Prepare prompt
        if prompt is None:
            prompt = GeminiImageSolver.DEFAULT_PROMPT
        
        # Create image part
        image_part = {
            "mime_type": "image/png",
            "data": image_bytes
        }
        
        # Generate response
        response = model.generate_content([prompt, image_part])
        
        if response and response.text:
            return True, response.text.strip()
        else:
            return False, "Error: Empty response"
            
    except Exception as e:
        return False, f"Error: {str(e)}"


def send_image_to_backend(
    image_path_or_bytes: str | bytes | Image.Image,
    backend_url: str,
    auth_token: str = None,
    prompt: str = None
) -> Tuple[bool, str]:
    """
    Standalone function to send image to backend API
    
    Args:
        image_path_or_bytes: File path, bytes, or PIL Image
        backend_url: Backend server URL
        auth_token: JWT authentication token
        prompt: Custom prompt
        
    Returns:
        (success: bool, result: str)
    """
    if not HAS_PIL:
        return False, "Error: PIL/Pillow not installed"
    
    try:
        # Load image
        if isinstance(image_path_or_bytes, str):
            image = Image.open(image_path_or_bytes)
        elif isinstance(image_path_or_bytes, bytes):
            image = Image.open(io.BytesIO(image_path_or_bytes))
        elif isinstance(image_path_or_bytes, Image.Image):
            image = image_path_or_bytes
        else:
            return False, "Error: Invalid image input"
        
        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        
        # Prepare request
        url = f"{backend_url}/api/solve/screenshot"
        headers = {"Content-Type": "application/json"}
        
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        if prompt is None:
            prompt = GeminiImageSolver.DEFAULT_PROMPT
        
        payload = {
            "image": image_base64,
            "prompt": prompt
        }
        
        # Send request
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return True, data.get("answer", "No answer")
            else:
                return False, data.get("message", "Unknown error")
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except requests.Timeout:
        return False, "Request timeout"
    except Exception as e:
        return False, f"Error: {str(e)}"


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Quiz Solver - Image Sending Test")
    print("=" * 60)
    
    # Example 1: Using GeminiImageSolver class
    print("\n[Example 1] Using GeminiImageSolver class")
    print("-" * 40)
    
    # Replace with your actual API key
    API_KEY = "YOUR_GEMINI_API_KEY"
    BACKEND_URL = "https://tool.1amsleep.xyz"
    
    # Initialize solver
    solver = GeminiImageSolver(
        api_key=API_KEY,
        backend_url=BACKEND_URL
    )
    
    # Capture and solve (requires screen capture permission)
    # answer = solver.solve()  
    # print(f"Answer: {answer}")
    
    # Example 2: Using standalone function with file
    print("\n[Example 2] Sending image file to Gemini API")
    print("-" * 40)
    
    # success, result = send_image_to_gemini_api(
    #     "screenshot.png",
    #     api_key=API_KEY
    # )
    # print(f"Success: {success}")
    # print(f"Result: {result}")
    
    # Example 3: Using backend
    print("\n[Example 3] Sending image to backend")
    print("-" * 40)
    
    # success, result = send_image_to_backend(
    #     "screenshot.png",
    #     backend_url=BACKEND_URL,
    #     auth_token="your_jwt_token"
    # )
    # print(f"Success: {success}")
    # print(f"Result: {result}")
    
    print("\n" + "=" * 60)
    print("Test complete! Uncomment examples to run actual tests.")
    print("=" * 60)
