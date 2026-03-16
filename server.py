from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import os
import hashlib
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for API calls from website
DB_FILE = "licenses.json"
VERSION_FILE = "version.json"

# Current version info
def load_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return json.load(f)
    return {
        "version": "2.0.0",
        "download_url": "",
        "changelog": "Initial release",
        "force_update": False
    }

def save_version(data):
    with open(VERSION_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def home():
    """Serve the landing page"""
    return render_template('index.html')

@app.route('/admin')
def admin_page():
    """Serve the admin dashboard"""
    return render_template('admin.html')

# ==========================================
# VERSION & UPDATE API
# ==========================================

@app.route('/check_update', methods=['GET', 'POST'])
def check_update():
    """Check if there's a new version available"""
    version_info = load_version()
    client_version = "0.0.0"
    
    if request.method == 'POST' and request.json:
        client_version = request.json.get('version', '0.0.0')
    
    # Compare versions
    def parse_version(v):
        return [int(x) for x in v.split('.')]
    
    try:
        server_v = parse_version(version_info['version'])
        client_v = parse_version(client_version)
        needs_update = server_v > client_v
    except:
        needs_update = True
    
    return jsonify({
        "current_version": version_info['version'],
        "download_url": version_info.get('download_url', ''),
        "changelog": version_info.get('changelog', ''),
        "force_update": version_info.get('force_update', False),
        "auto_update": version_info.get('auto_update', True),
        "needs_update": needs_update
    }), 200

@app.route('/admin/set_version', methods=['POST'])
def set_version():
    """Admin: Set new version"""
    data = request.json
    admin_secret = data.get('admin_secret')
    
    if admin_secret != "Ml135791":
        return jsonify({"error": "Unauthorized"}), 401
    
    version_info = load_version()
    version_info['version'] = data.get('version', version_info['version'])
    version_info['download_url'] = data.get('download_url', version_info['download_url'])
    version_info['changelog'] = data.get('changelog', version_info['changelog'])
    version_info['force_update'] = data.get('force_update', False)
    save_version(version_info)
    
    return jsonify({"success": True}), 200

@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    """Get admin statistics"""
    db = load_db()
    version_info = load_version()
    
    total = len(db)
    active = sum(1 for k, v in db.items() if v.get('active', True))
    
    # Format licenses for display
    licenses = []
    for key, data in db.items():
        licenses.append({
            "key": key,
            "hwid": data.get('hwid', ''),
            "active": data.get('active', True),
            "created_at": data.get('created_at', '')
        })
    
    return jsonify({
        "total_licenses": total,
        "active_licenses": active,
        "online_users": len(VERIFIED_HWIDS),  # Users with active verification
        "current_version": version_info['version'],
        "licenses": licenses
    }), 200

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)

@app.route('/verify', methods=['POST'])
def verify_license():
    data = request.json
    hwid = data.get('hwid')
    key = data.get('key')
    
    if not hwid or not key:
        return jsonify({"valid": False, "message": "Missing HWID or Key"}), 400
        
    db = load_db()
    
    # Check if key exists and matches HWID
    if key in db:
        license_data = db[key]
        if license_data['hwid'] == hwid:
            if not license_data.get('active', True):
                return jsonify({"valid": False, "message": "Key is banned/inactive"}), 403
            return jsonify({"valid": True, "message": "License valid"}), 200
        else:
            return jsonify({"valid": False, "message": "Key is for another machine"}), 403
            
    return jsonify({"valid": False, "message": "Invalid key"}), 403

@app.route('/gen_key', methods=['POST'])
def generate_key():
    """Admin endpoint to generate key for a HWID"""
    data = request.json
    hwid = data.get('hwid')
    admin_secret = data.get('admin_secret')
    
    # Simple protection
    if admin_secret != "Ml135791": 
        return jsonify({"error": "Unauthorized"}), 401
        
    if not hwid:
        return jsonify({"error": "Missing HWID"}), 400
        
    # Generate a simple key based on HWID + salt
    raw = f"{hwid}-SECRET_SALT-{datetime.now().timestamp()}"
    key = hashlib.md5(raw.encode()).hexdigest().upper()[:16] # 16 chars key
    
    db = load_db()
    db[key] = {
        "hwid": hwid,
        "created_at": str(datetime.now()),
        "active": True
    }
    save_db(db)
    
    return jsonify({"key": key, "hwid": hwid}), 200

    return jsonify({"key": key, "hwid": hwid}), 200

# ==========================================
# LINK VERIFICATION SYSTEM
# ==========================================

YEUMONEY_TOKEN = "6af82f57b373b08729d590a89736da1e1bd8100130d43aaf826bbeaacafa94a8"
VERIFIED_HWIDS = {}  # In-memory storage: {hwid: expire_timestamp}
PENDING_TOKENS = {}  # In-memory storage: {token: {hwid, created_at}}
VERIFICATION_HOURS = 4  # Valid for 4 hours
TOKEN_EXPIRE_MINUTES = 10  # Token expires after 10 minutes

import requests
import time
import secrets

@app.route('/get_link', methods=['POST'])
def get_verification_link():
    """Generate a short link with unique token for the user to pass"""
    data = request.json
    hwid = data.get('hwid')
    
    if not hwid:
        return jsonify({"error": "Missing HWID"}), 400
    
    # Generate unique token
    token = secrets.token_hex(16)  # 32 chars random token
    
    # Store token with HWID and timestamp
    PENDING_TOKENS[token] = {
        "hwid": hwid,
        "created_at": time.time()
    }
    
    # Clean up old tokens
    current_time = time.time()
    expired_tokens = [t for t, data in PENDING_TOKENS.items() 
                      if current_time - data["created_at"] > TOKEN_EXPIRE_MINUTES * 60]
    for t in expired_tokens:
        del PENDING_TOKENS[t]
        
    # Destination URL includes token for verification
    destination_url = f"http://localhost:5000/pass_verification?token={token}"
    
    # Call YeuMoney API
    api_url = f"https://yeumoney.com/QL_api.php?token={YEUMONEY_TOKEN}&format=json&url={destination_url}"
    
    try:
        resp = requests.get(api_url)
        result = resp.json()
        
        if result.get("status") == "success":
            return jsonify({"url": result.get("shortenedUrl"), "token": token}), 200
        else:
            return jsonify({"error": "Failed to shorten link", "details": result}), 500
    except Exception as e:
        return jsonify({"error": f"API Error: {str(e)}"}), 500

@app.route('/pass_verification', methods=['GET'])
def pass_verification():
    """Endpoint hit when user successfully passes the link"""
    token = request.args.get('token')
    
    if not token:
        return """
        <html>
        <body style="background-color: #1a1a2e; color: #ef4444; font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h1>❌ LỖI: THIẾU TOKEN</h1>
            <p style="color: white;">Vui lòng sử dụng link từ tool, không truy cập trực tiếp.</p>
        </body>
        </html>
        """, 400
    
    # Validate token
    if token not in PENDING_TOKENS:
        return """
        <html>
        <body style="background-color: #1a1a2e; color: #ef4444; font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h1>❌ TOKEN KHÔNG HỢP LỆ HOẶC ĐÃ HẾT HẠN</h1>
            <p style="color: white;">Vui lòng lấy link mới từ tool.</p>
        </body>
        </html>
        """, 403
    
    token_data = PENDING_TOKENS[token]
    hwid = token_data["hwid"]
    
    # Check token expiry
    if time.time() - token_data["created_at"] > TOKEN_EXPIRE_MINUTES * 60:
        del PENDING_TOKENS[token]
        return """
        <html>
        <body style="background-color: #1a1a2e; color: #ef4444; font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h1>❌ TOKEN ĐÃ HẾT HẠN</h1>
            <p style="color: white;">Vui lòng lấy link mới từ tool.</p>
        </body>
        </html>
        """, 403
    
    # Token is valid - mark HWID as verified and delete token (one-time use)
    del PENDING_TOKENS[token]
    expire_time = time.time() + (VERIFICATION_HOURS * 3600)
    VERIFIED_HWIDS[hwid] = expire_time
    
    return f"""
    <html>
    <body style="background-color: #1a1a2e; color: #4ade80; font-family: sans-serif; text-align: center; padding-top: 50px;">
        <h1>✅ XÁC THỰC THÀNH CÔNG!</h1>
        <p style="color: white;">HWID: {hwid[:8]}...{hwid[-4:]}</p>
        <p style="color: white;">Hiệu lực: {VERIFICATION_HOURS} giờ</p>
        <p style="color: white;">Bạn có thể quay lại tool và nhấn "Tôi đã vượt link".</p>
        <script>window.close();</script>
    </body>
    </html>
    """

@app.route('/check_verification', methods=['POST'])
def check_verification():
    """Check if HWID is verified"""
    data = request.json
    hwid = data.get('hwid')
    
    if not hwid:
        return jsonify({"verified": False}), 400
        
    if hwid in VERIFIED_HWIDS:
        if time.time() < VERIFIED_HWIDS[hwid]:
            remaining = int((VERIFIED_HWIDS[hwid] - time.time()) / 60)
            return jsonify({"verified": True, "remaining_minutes": remaining}), 200
        else:
            del VERIFIED_HWIDS[hwid]  # Expired
            
    return jsonify({"verified": False}), 200

if __name__ == '__main__':
    print("License Server running on port 5000...")
    print("Features: License verification + Link bypass protection")
    app.run(host='0.0.0.0', port=5000)

