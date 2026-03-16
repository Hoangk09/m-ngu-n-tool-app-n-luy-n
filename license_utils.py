import subprocess
import hashlib
import requests
import platform
import os

SERVER_URL = "http://127.0.0.1:8000"  # Production server

import uuid

def get_hwid():
    """Generate a Hardware ID based on machine unique identifiers"""
    try:
        # Method 1: UUID (MAC address based)
        node = uuid.getnode()
        serial = str(node)
        
        # Add some salt and hash it
        raw = f"{serial}-QUIZ_SOLVER_APP-{platform.node()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32].upper()
    except Exception as e:
        # Fallback to a random ID stored in file if everything fails
        try:
            fallback_file = "device_id.txt"
            if os.path.exists(fallback_file):
                with open(fallback_file, 'r') as f:
                    return f.read().strip()
            else:
                # Generate new random ID
                random_id = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:32].upper()
                with open(fallback_file, 'w') as f:
                    f.write(random_id)
                return random_id
        except:
            return "UNKNOWN_HWID_ERROR"

def verify_key(hwid, key):
    """Verify key with backend server"""
    try:
        response = requests.post(f"{SERVER_URL}/verify", json={
            "hwid": hwid,
            "key": key
        }, timeout=5)
        
        if response.status_code == 200:
            return True, "Success"
        else:
            data = response.json()
            return False, data.get("message", "Unknown error")
    except Exception as e:
        return False, f"Connection error: {e}"
