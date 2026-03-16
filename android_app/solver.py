"""
Gemini API Integration - solver.py
====================================
Gọi Gemini Web API để lấy đáp án
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request

GEMINI_URL = "https://gemini.google.com/app"


class GeminiSolver:
    """Gemini Web API wrapper for solving quizzes"""
    
    MODEL_HEADERS = {
        '2.5-flash': '[1,null,null,null,"9ec249fc9ad08861",null,null,0,[4]]',
        '2.5-pro': '[1,null,null,null,"4af6c7f5da75d65d",null,null,0,[4]]',
    }
    
    def __init__(self, cookies_path='gemini_cookies.json'):
        self.cookies_path = cookies_path
        self.cookies = self._load_cookies()
        self.access_token = None
        self.bl_token = None
        self.model = '2.5-flash'
    
    def _load_cookies(self):
        """Load saved cookies from file"""
        if os.path.exists(self.cookies_path):
            try:
                with open(self.cookies_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Solver] Error loading cookies: {e}")
        return {}
    
    def save_cookies(self, cookies):
        """Save cookies to file"""
        self.cookies = cookies
        try:
            with open(self.cookies_path, 'w') as f:
                json.dump(cookies, f)
            print("[Solver] Cookies saved successfully")
        except Exception as e:
            print(f"[Solver] Error saving cookies: {e}")
    
    def set_cookie(self, key, value):
        """Set a single cookie value"""
        self.cookies[key] = value
        self.save_cookies(self.cookies)
    
    def is_logged_in(self):
        """Check if we have valid Gemini cookies"""
        return '__Secure-1PSID' in self.cookies and bool(self.cookies['__Secure-1PSID'])
    
    def get_tokens(self):
        """Get access tokens from Gemini page"""
        try:
            cookie_str = '; '.join([f"{k}={v}" for k, v in self.cookies.items()])
            headers = {
                'Cookie': cookie_str,
                'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
            }
            
            req = urllib.request.Request(GEMINI_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8')
                
                # Extract SNlM0e (access token)
                match = re.search(r'"SNlM0e":"([^"]+)"', html)
                if match:
                    self.access_token = match.group(1)
                    print("[Solver] Got access token")
                
                # Extract bl token
                match = re.search(r'"cfb2h":"([^"]+)"', html)
                if match:
                    self.bl_token = match.group(1)
                else:
                    self.bl_token = 'boq_assistant-bard-web-server_20251217.07_p5'
                
                return bool(self.access_token)
        except Exception as e:
            print(f"[Solver] Get tokens error: {e}")
            return False
    
    def solve(self, question, options=None):
        """
        Solve a quiz question using Gemini
        
        Args:
            question: The question text
            options: Optional list of answer options (A, B, C, D)
        
        Returns:
            str: The answer letter (A, B, C, or D) or None if failed
        """
        if not self.cookies or not self.is_logged_in():
            print("[Solver] Not logged in")
            return None
        
        # Build prompt
        prompt = "Ban la chuyen gia giai quiz. "
        prompt += "Xem cau hoi va CHI tra loi DUNG 1 chu cai: A, B, C hoac D.\n\n"
        prompt += f"Cau hoi: {question}"
        
        if options:
            prompt += "\n\nCac dap an:\n"
            for opt in options:
                prompt += f"{opt}\n"
        
        prompt += "\n\nTra loi (chi 1 chu cai):"
        
        try:
            # Get tokens if needed
            if not self.access_token:
                if not self.get_tokens():
                    print("[Solver] Failed to get tokens")
                    return None
            
            # Build request payload
            inner_payload = json.dumps([[prompt], None, None])
            f_req = json.dumps([None, inner_payload])
            
            cookie_str = '; '.join([f"{k}={v}" for k, v in self.cookies.items()])
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'Cookie': cookie_str,
                'User-Agent': 'Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36',
                'x-goog-ext-525001261-jspb': self.MODEL_HEADERS[self.model]
            }
            
            data = f"f.req={urllib.parse.quote(f_req)}&at={urllib.parse.quote(self.access_token)}"
            
            endpoint = f"https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate?bl={self.bl_token}&_reqid={int(time.time()*1000)}&rt=c"
            
            req = urllib.request.Request(endpoint, data.encode(), headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode('utf-8')
                answer = self._parse_response(text)
                
                if answer:
                    print(f"[Solver] Answer: {answer}")
                    return answer
                else:
                    print("[Solver] Could not parse answer")
                    return None
        
        except Exception as e:
            print(f"[Solver] Error: {e}")
            # Reset tokens and retry once
            self.access_token = None
            return None
    
    def _parse_response(self, text):
        """Parse Gemini streaming response to extract answer letter"""
        try:
            # Find the wrb.fr response
            for line in text.split('\n'):
                if 'wrb.fr' in line:
                    match = re.search(r'\["wrb\.fr",null,"(.+?)(?:",null|\])', line, re.DOTALL)
                    if match:
                        inner = match.group(1).replace('\\"', '"')
                        try:
                            parsed = json.loads(inner)
                            if isinstance(parsed, list) and len(parsed) > 4:
                                candidates = parsed[4]
                                if candidates and candidates[0]:
                                    content = candidates[0][1][0] if candidates[0][1] else candidates[0][0]
                                    # Look for answer letter at start
                                    letter = re.match(r'^([A-Da-d])', content.strip())
                                    if letter:
                                        return letter.group(1).upper()
                                    # Look for answer letter anywhere
                                    letter = re.search(r'\b([A-Da-d])\b', content)
                                    if letter:
                                        return letter.group(1).upper()
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[Solver] Parse error: {e}")
        
        # Fallback: find any single letter A-D
        letter = re.search(r'\b([A-Da-d])\b', text)
        if letter:
            return letter.group(1).upper()
        
        return None
