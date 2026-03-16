"""
Gemini Web Image Solver
Send images to Gemini Web (gemini.google.com) using browser cookies
This mimics the Chrome extension's behavior for sending images to Gemini Web

Requirements:
- pip install requests pillow
- Must be logged in to Gemini Web in browser first (to get cookies)

How to get cookies:
1. Open Chrome DevTools (F12
2. Go to Application > Cookies > gemini.google.com
3. Copy the values of __Secure-1PSID, __Secure-1PSIDTS, __Secure-1PSIDCC
4. Or export cookies using browser extension like "EditThisCookie"
"""

import base64
import io
import re
import json
import time
import requests
from typing import Optional, Dict, Tuple

# Try to import PIL for image processing
try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL not installed. Run: pip install pillow")


class GeminiWebSolver:
    """
    Send images to Gemini Web (gemini.google.com) for quiz solving
    Uses browser cookies for authentication (no API key needed)
    """
    
    # Default prompt for quiz solving
    DEFAULT_PROMPT = """Phân tích ảnh câu hỏi quiz này và xác định đáp án ĐÚNG.

Quy tắc:
1. Nếu trắc nghiệm (A/B/C/D): Chỉ trả về CHỮ CÁI (A, B, C hoặc D)
2. Nếu Đúng/Sai: Chỉ trả về "TRUE" hoặc "FALSE"
3. Nếu tự luận/điền khuyết: Chỉ trả về CÂU TRẢ LỜI
4. KHÔNG giải thích, chỉ đưa đáp án cuối cùng
5. Nếu không xác định được, trả về "ERROR: [lý do]"

Đáp án:"""

    def __init__(self, cookies: Dict[str, str] = None):
        """
        Initialize with browser cookies
        
        Args:
            cookies: Dict of cookies from gemini.google.com
                     Required: __Secure-1PSID, __Secure-1PSIDTS, __Secure-1PSIDCC
        """
        self.cookies = cookies or {}
        self.session = requests.Session()
        
        # Update session cookies
        if cookies:
            self.session.cookies.update(cookies)
        
        # Tokens extracted from Gemini page
        self.access_token = None  # SNlM0e token
        self.bl_token = None      # cfb2h token
        self.feed_id = None       # For image upload
        
    def set_cookies(self, cookies: Dict[str, str]):
        """Set or update cookies"""
        self.cookies = cookies
        self.session.cookies.update(cookies)
        
    def set_cookies_from_string(self, cookie_string: str):
        """
        Parse cookies from string format (from browser)
        Format: "name1=value1; name2=value2; ..."
        """
        cookies = {}
        for part in cookie_string.split(';'):
            part = part.strip()
            if '=' in part:
                name, value = part.split('=', 1)
                cookies[name.strip()] = value.strip()
        self.set_cookies(cookies)
        
    def _get_tokens(self) -> bool:
        """
        Extract access token (SNlM0e) and bl token (cfb2h) from Gemini page
        """
        try:
            # Fetch Gemini app page
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
            
            resp = self.session.get(
                'https://gemini.google.com/app',
                headers=headers,
                timeout=30
            )
            
            if resp.status_code != 200:
                print(f"Error fetching Gemini page: HTTP {resp.status_code}")
                return False
            
            html = resp.text
            
            # Extract SNlM0e token (access token)
            at_match = re.search(r'"SNlM0e":"([^"]+)"', html)
            if at_match:
                self.access_token = at_match.group(1)
                print(f"Got access token: {self.access_token[:30]}...")
            else:
                # Try alternative pattern
                alt_match = re.search(r'\["SNlM0e"\s*,\s*"([^"]+)"', html)
                if alt_match:
                    self.access_token = alt_match.group(1)
                    print(f"Got access token (alt): {self.access_token[:30]}...")
                else:
                    print("Could not find access token (SNlM0e)")
                    return False
            
            # Extract bl token (cfb2h)
            bl_match = re.search(r'"cfb2h":"([^"]+)"', html)
            if bl_match:
                self.bl_token = bl_match.group(1)
                print(f"Got bl token: {self.bl_token}")
            else:
                self.bl_token = 'server_backend'  # Default fallback
                print(f"Using default bl token: {self.bl_token}")
            
            # Extract Feed ID for image upload
            feed_match = re.search(r'feeds/([a-z0-9]+)', html, re.I)
            if feed_match:
                self.feed_id = feed_match.group(0)
                print(f"Got Feed ID: {self.feed_id}")
            
            return True
            
        except Exception as e:
            print(f"Error getting tokens: {e}")
            return False
    
    def _upload_image(self, image_bytes: bytes) -> Optional[str]:
        """
        Upload image to Google's push server
        Returns the uploaded image URL/path
        """
        try:
            filename = f"screenshot_{int(time.time())}.jpg"
            
            # Step 1: Start resumable upload session
            upload_headers = {
                'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
                'X-Goog-Upload-Command': 'start',
                'X-Goog-Upload-Header-Content-Length': str(len(image_bytes)),
                'X-Goog-Upload-Header-Content-Type': 'image/jpeg',
                'X-Goog-Upload-Protocol': 'resumable',
                'X-Tenant-Id': 'bard-storage',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            if self.feed_id:
                upload_headers['Push-Id'] = self.feed_id
                print(f"Using Push-Id: {self.feed_id}")
            
            init_payload = json.dumps({
                'protocolVersion': '0.8',
                'createSessionRequest': {
                    'fields': [{
                        'external': {
                            'name': 'file',
                            'filename': filename,
                            'put': {},
                            'size': len(image_bytes)
                        }
                    }]
                }
            })
            
            init_resp = self.session.post(
                'https://push.clients6.google.com/upload/',
                headers=upload_headers,
                data=init_payload,
                timeout=30
            )
            
            print(f"Upload init status: {init_resp.status_code}")
            
            if init_resp.status_code != 200:
                print(f"Upload init failed: {init_resp.text[:200]}")
                return None
            
            upload_url = init_resp.headers.get('X-Goog-Upload-URL')
            if not upload_url:
                print("No upload URL in response")
                return None
            
            print(f"Got upload URL: {upload_url[:80]}...")
            
            # Step 2: Upload file content
            upload_content_headers = {
                'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
                'X-Goog-Upload-Command': 'upload, finalize',
                'X-Goog-Upload-Offset': '0',
                'X-Tenant-Id': 'bard-storage'
            }
            
            upload_resp = self.session.post(
                upload_url,
                headers=upload_content_headers,
                data=image_bytes,
                timeout=60
            )
            
            print(f"Upload status: {upload_resp.status_code}")
            
            if upload_resp.status_code != 200:
                print(f"Upload failed: {upload_resp.text[:200]}")
                return None
            
            # Parse response to get image URL
            result_text = upload_resp.text
            print(f"Upload result: {result_text[:200]}...")
            
            try:
                result = json.loads(result_text)
                image_url = result.get('sessionStatus', {}).get('externalFieldTransfers', [{}])[0].get('scottyUrl')
                if image_url:
                    print(f"Got image URL from JSON: {image_url[:80]}...")
                    return image_url
            except json.JSONDecodeError:
                # Not JSON - might be direct URL
                if result_text.startswith('/contrib_') or result_text.startswith('http'):
                    if result_text.startswith('/'):
                        image_url = 'https://push.clients6.google.com' + result_text.strip()
                    else:
                        image_url = result_text.strip()
                    print(f"Got image URL (raw): {image_url[:80]}...")
                    return image_url
            
            print("Could not extract image URL from response")
            return None
            
        except Exception as e:
            print(f"Image upload error: {e}")
            return None
    
    def solve(self, image: 'Image.Image' = None, image_bytes: bytes = None, 
              image_path: str = None, prompt: str = None) -> Tuple[bool, str]:
        """
        Send image to Gemini Web and get answer
        
        Args:
            image: PIL Image object
            image_bytes: Raw image bytes
            image_path: Path to image file
            prompt: Custom prompt
            
        Returns:
            (success: bool, answer: str)
        """
        # Validate input
        if not any([image, image_bytes, image_path]):
            return False, "Error: No image provided"
        
        # Get image bytes
        if image_path:
            try:
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
            except Exception as e:
                return False, f"Error reading image file: {e}"
        elif image:
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)
            image_bytes = buffer.read()
        
        # Use default prompt if not provided
        if not prompt:
            prompt = self.DEFAULT_PROMPT
        
        # Get tokens if not already done
        if not self.access_token:
            if not self._get_tokens():
                return False, "Error: Could not get access token. Check cookies."
        
        try:
            # Upload image
            print("Uploading image...")
            image_url = self._upload_image(image_bytes)
            
            # Build request payload
            if image_url:
                # Remove domain for payload
                image_path_for_payload = image_url
                if image_url.startswith('https://push.clients6.google.com'):
                    image_path_for_payload = image_url.replace('https://push.clients6.google.com', '')
                
                filename = f"screenshot_{int(time.time())}.jpg"
                
                # Payload with image
                inner_payload = json.dumps([
                    [prompt, 0, None, [[[image_path_for_payload, 1, None, "image/jpeg"], filename, None, None, None, None, None, None, [0]]], None, None, 0],
                    ["vi"]
                ])
                print("Built payload with image")
            else:
                # Text-only payload (fallback)
                inner_payload = json.dumps([
                    [prompt],
                    None,
                    None
                ])
                print("Built text-only payload (image upload failed)")
            
            # Build StreamGenerate request
            endpoint = f"https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate?bl={self.bl_token}&_reqid={int(time.time() * 1000)}&rt=c"
            
            f_req = json.dumps([None, inner_payload])
            
            form_data = {
                'f.req': f_req,
                'at': self.access_token
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
                'Host': 'gemini.google.com',
                'Origin': 'https://gemini.google.com',
                'Referer': 'https://gemini.google.com/',
                'X-Same-Domain': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            print("Sending request to Gemini...")
            
            resp = self.session.post(
                endpoint,
                headers=headers,
                data=form_data,
                timeout=60
            )
            
            print(f"Response status: {resp.status_code}")
            
            if resp.status_code != 200:
                return False, f"Error: HTTP {resp.status_code}"
            
            text = resp.text
            print(f"Response length: {len(text)}")
            
            # Parse response
            answer = self._parse_response(text)
            if answer:
                return True, answer
            else:
                return False, "Error: Could not parse response"
                
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def _parse_response(self, text: str) -> Optional[str]:
        """
        Parse Gemini response to extract the answer text
        """
        try:
            # Remove the )]}' prefix
            clean_text = re.sub(r"^\)\]\}'?\n?", '', text)
            lines = clean_text.split('\n')
            
            for line in lines:
                line = line.strip()
                if line.startswith('['):
                    try:
                        parsed = json.loads(line)
                        # Format: [["wrb.fr", rpcName, jsonString, ...], ...]
                        if parsed[0] and len(parsed[0]) > 2 and parsed[0][2]:
                            inner_json = json.loads(parsed[0][2])
                            # Response text is usually at [4][0][1][0]
                            response_text = inner_json
                            
                            # Navigate to find text
                            if isinstance(response_text, list):
                                if len(response_text) > 4:
                                    candidates = response_text[4]
                                    if isinstance(candidates, list) and len(candidates) > 0:
                                        if isinstance(candidates[0], list) and len(candidates[0]) > 1:
                                            if isinstance(candidates[0][1], list) and len(candidates[0][1]) > 0:
                                                return candidates[0][1][0]
                            
                    except (json.JSONDecodeError, IndexError, TypeError):
                        continue
            
            return None
            
        except Exception as e:
            print(f"Parse error: {e}")
            return None
    
    def solve_with_screenshot(self, prompt: str = None) -> Tuple[bool, str]:
        """
        Capture screen and solve
        """
        if not HAS_PIL:
            return False, "Error: PIL not installed"
        
        try:
            screenshot = ImageGrab.grab()
            return self.solve(image=screenshot, prompt=prompt)
        except Exception as e:
            return False, f"Error capturing screen: {e}"


def get_cookies_from_file(filepath: str) -> Dict[str, str]:
    """
    Load cookies from JSON file
    
    File format:
    {
        "__Secure-1PSID": "value",
        "__Secure-1PSIDTS": "value",
        "__Secure-1PSIDCC": "value",
        ...
    }
    """
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading cookies: {e}")
        return {}


def solve_quiz_from_image(
    image_path: str,
    cookies: Dict[str, str] = None,
    cookie_file: str = None,
    prompt: str = None
) -> Tuple[bool, str]:
    """
    Convenience function to solve quiz from image file
    
    Args:
        image_path: Path to screenshot/image file
        cookies: Dict of cookies
        cookie_file: Path to JSON file with cookies
        prompt: Custom prompt
        
    Returns:
        (success: bool, answer: str)
    """
    # Load cookies
    if cookie_file:
        cookies = get_cookies_from_file(cookie_file)
    
    if not cookies:
        return False, "Error: No cookies provided"
    
    # Create solver and solve
    solver = GeminiWebSolver(cookies)
    return solver.solve(image_path=image_path, prompt=prompt)


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Gemini Web Image Solver - Test")
    print("=" * 70)
    
    # Example 1: Using cookies dict
    print("\n[Example 1] Using cookies dictionary")
    print("-" * 40)
    
    # Replace with your actual cookies from browser
    COOKIES = {
        '__Secure-1PSID': 'YOUR_PSID_VALUE',
        '__Secure-1PSIDTS': 'YOUR_PSIDTS_VALUE',
        '__Secure-1PSIDCC': 'YOUR_PSIDCC_VALUE',
        # Add other cookies as needed
    }
    
    # solver = GeminiWebSolver(cookies=COOKIES)
    # success, answer = solver.solve(image_path='screenshot.png')
    # print(f"Success: {success}")
    # print(f"Answer: {answer}")
    
    # Example 2: Using cookie file
    print("\n[Example 2] Using cookie file")
    print("-" * 40)
    
    # success, answer = solve_quiz_from_image(
    #     image_path='screenshot.png',
    #     cookie_file='gemini_cookies.json'
    # )
    # print(f"Success: {success}")
    # print(f"Answer: {answer}")
    
    # Example 3: Capture screen and solve
    print("\n[Example 3] Screen capture (requires PIL)")
    print("-" * 40)
    
    # solver = GeminiWebSolver(cookies=COOKIES)
    # success, answer = solver.solve_with_screenshot()
    # print(f"Success: {success}")
    # print(f"Answer: {answer}")
    
    print("\n" + "=" * 70)
    print("To use:")
    print("1. Export cookies from browser (gemini.google.com)")
    print("2. Save to JSON file or paste in COOKIES dict above")
    print("3. Uncomment and run desired example")
    print("=" * 70)
