import os
import secrets
import requests
from datetime import date
from flask import Flask, render_template, render_template_string, request, jsonify, redirect, url_for, flash, Response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, OnluyenAccount, Payment, SolverSession, AnswerFile, LinkBypass
from solver_service import WebSolverManager
import time
from dotenv import load_dotenv
import json

# Link4m API config
LINK4M_API_TOKEN = "67e2ada58b4b030b925f545c"
LINK4M_API_URL = "https://link4m.co/api-shorten/v2"
MAX_FREE_SOLVES_PER_DAY = 3

# PayOS config - Get these from https://my.payos.vn
PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID", "your_client_id")
PAYOS_API_KEY = os.getenv("PAYOS_API_KEY", "your_api_key")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "your_checksum_key")

app = Flask(__name__)

DB_FILE = "licenses.json"
VERSION_FILE = "version.json"

# Load helpers
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

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}
    
def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)

# ================= Routes =================

# --- License & Update API ---
@app.route('/check_update', methods=['POST'])
def check_update():
    version_info = load_version()
    client_version = request.json.get('version', '0.0.0')
    
    # Simple version compare
    def parse_version(v):
        return [int(x) for x in v.split('.')]
        
    try:
        server_v = parse_version(version_info['version'])
        client_v = parse_version(client_version)
        needs_update = server_v > client_v
    except:
        needs_update = True
        
    return jsonify({
        "needs_update": needs_update,
        "current_version": version_info['version'],
        "download_url": version_info.get('download_url', ''),
        "changelog": version_info.get('changelog', ''),
        "force_update": version_info.get('force_update', False)
    })

@app.route('/verify', methods=['POST'])
def verify_license():
    data = request.json
    hwid = data.get('hwid')
    key = data.get('key')
    
    # Just a simple check for this request scope
    # In real app, check DB
    if not hwid or not key:
        return jsonify({"valid": False, "message": "Missing HWID/Key"}), 400
        
    db = load_db()
    if key in db:
        if db[key]['hwid'] == hwid:
             return jsonify({"valid": True, "message": "Valid"}), 200
        return jsonify({"valid": False, "message": "Invalid HWID"}), 403
        
    # Temporary: Allow any key for implementation speed if missing
    return jsonify({"valid": False, "message": "Invalid Key"}), 403

# --- End License & Update API ---
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz_pixel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize DB
with app.app_context():
    db.create_all()

# ================= Routes =================

@app.route('/')
def index():
    """Landing page - show extension page"""
    return render_template('extension.html')

# Serve extension update files
@app.route('/ext/<path:filename>')
def serve_ext_files(filename):
    """Serve extension update files"""
    from flask import send_from_directory
    ext_dir = os.path.join(os.path.expanduser('~'), 'toolchorach', 'static', 'ext')
    return send_from_directory(ext_dir, filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/extension')
def extension_page():
    """Extension landing page"""
    return render_template('extension.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
        else:
            new_user = User(
                username=username, 
                password_hash=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('dashboard'))
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Check if returning from PayOS payment
    order_code = request.args.get('orderCode')
    status = request.args.get('status')
    
    if order_code and status == 'PAID':
        # Verify and update payment if not already processed
        try:
            payment = Payment.query.filter_by(order_code=str(order_code)).first()
            if payment and payment.status == 'PENDING':
                # Double-check with PayOS API
                payment_info = payos.getPaymentLinkInformation(int(order_code))
                if payment_info and payment_info.status == 'PAID':
                    payment.status = 'PAID'
                    # Add balance to user
                    user = User.query.get(payment.user_id)
                    if user:
                        user.balance += payment.amount
                        print(f"[PayOS] Added {payment.amount} to user {user.id}, new balance: {user.balance}")
                    db.session.commit()
                    flash(f'Nạp thành công {payment.amount:,}đ!', 'success')
        except Exception as e:
            print(f"[PayOS] Verify payment error: {e}")
    
    accounts = OnluyenAccount.query.filter_by(user_id=current_user.id).all()
    active_sessions = SolverSession.query.filter_by(user_id=current_user.id, status='RUNNING').all()
    return render_template('dashboard.html', user=current_user, accounts=accounts, sessions=active_sessions)

@app.route('/api/add_account', methods=['POST'])
@login_required
def add_account():
    data = request.json
    new_acc = OnluyenAccount(
        user_id=current_user.id,
        username=data.get('username'),
        password=data.get('password'),
        proxy_key=data.get('proxy_key'),
        api_key=data.get('api_key')
    )
    db.session.add(new_acc)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/edit_account/<int:account_id>', methods=['PUT'])
@login_required
def edit_account(account_id):
    """Edit an existing Onluyen account"""
    account = db.session.get(OnluyenAccount, account_id)
    if not account or account.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
    
    data = request.json
    if data.get('username'):
        account.username = data['username']
    if data.get('password'):
        account.password = data['password']
    if data.get('proxy_key') is not None:
        account.proxy_key = data['proxy_key']
    if data.get('api_key') is not None:
        account.api_key = data['api_key']
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/delete_account/<int:account_id>', methods=['DELETE'])
@login_required
def delete_account(account_id):
    """Delete an Onluyen account"""
    account = db.session.get(OnluyenAccount, account_id)
    if not account or account.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
    
    db.session.delete(account)
    db.session.commit()
    return jsonify({'success': True})

# ================= Link Bypass (Free Solves) =================

def get_user_free_solves(user):
    """Get remaining free solves for user (earned from bypass links)"""
    # No daily reset - solves are earned from bypass, not given free
    return user.free_solves_today or 0

@app.route('/api/free-solve/status', methods=['GET'])
@login_required
def free_solve_status():
    """Get free solve status for current user"""
    remaining = get_user_free_solves(current_user)
    return jsonify({
        'success': True,
        'remaining': remaining,
        'max': MAX_FREE_SOLVES_PER_DAY,
        'used_today': current_user.free_solves_today
    })

@app.route('/api/free-solve/generate-link', methods=['POST'])
@login_required
def generate_bypass_link():
    """Generate a new bypass link for user"""
    # Generate unique token
    token = secrets.token_urlsafe(32)
    
    # Create callback URL (user will be redirected here after bypass)
    callback_url = f"{request.host_url}api/verify-bypass/{token}"
    
    # Call link4m API to create shortened link
    try:
        response = requests.get(
            LINK4M_API_URL,
            params={'api': LINK4M_API_TOKEN, 'url': callback_url},
            timeout=10
        )
        data = response.json()
        
        if data.get('status') == 'success':
            short_url = data.get('shortenedUrl')
            
            # Save to database
            bypass = LinkBypass(
                user_id=current_user.id,
                token=token,
                short_url=short_url
            )
            db.session.add(bypass)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'short_url': short_url,
                'token': token,
                'message': 'Mở link, vượt quảng cáo để nhận lượt miễn phí!'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Không thể tạo link rút gọn'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Lỗi: {str(e)}'
        }), 500

@app.route('/api/verify-bypass/<token>', methods=['GET'])
def verify_bypass_callback(token):
    """Callback URL after user completes link bypass"""
    bypass = LinkBypass.query.filter_by(token=token).first()
    
    if not bypass:
        return render_template_string('''
            <html><body style="background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:50px;">
                <h1>❌ Link không hợp lệ!</h1>
                <p>Token không tồn tại hoặc đã hết hạn.</p>
            </body></html>
        ''')
    
    if bypass.is_verified:
        return render_template_string('''
            <html><body style="background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:50px;">
                <h1>⚠️ Link đã được sử dụng!</h1>
                <p>Bạn đã nhận lượt miễn phí từ link này rồi.</p>
            </body></html>
        ''')
    
    # Show confirmation page - require user to click button
    return render_template_string('''
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { background:#1a1a2e; color:#fff; font-family:Arial; text-align:center; padding:50px; }
                .btn { 
                    background: linear-gradient(135deg, #22c55e, #16a34a); 
                    color: white; padding: 15px 40px; font-size: 18px; 
                    border: none; border-radius: 10px; cursor: pointer;
                    margin-top: 20px;
                }
                .btn:hover { transform: scale(1.05); }
            </style>
        </head>
        <body>
            <h1>🎉 Chúc mừng!</h1>
            <p>Bạn đã vượt qua link thành công.</p>
            <p>Nhấn nút bên dưới để nhận <b>1 lượt giải bài miễn phí</b>:</p>
            <form method="POST" action="/api/verify-bypass/{{ token }}/confirm">
                <button type="submit" class="btn">✅ Nhận lượt miễn phí</button>
            </form>
        </body>
        </html>
    ''', token=token)

@app.route('/api/verify-bypass/<token>/confirm', methods=['POST'])
def confirm_bypass(token):
    """Confirm bypass and grant free solve"""
    bypass = LinkBypass.query.filter_by(token=token).first()
    
    if not bypass or bypass.is_verified:
        return render_template_string('''
            <html><body style="background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:50px;">
                <h1>❌ Lỗi!</h1>
                <p>Link không hợp lệ hoặc đã được sử dụng.</p>
            </body></html>
        ''')
    
    # Mark as verified
    bypass.is_verified = True
    bypass.verified_at = db.func.now()
    
    # Get user and add free solve
    user = User.query.get(bypass.user_id)
    if user:
        # Add 1 solve to user's balance
        user.free_solves_today = (user.free_solves_today or 0) + 1
        db.session.commit()
        
        remaining = user.free_solves_today
        return render_template_string('''
            <html><body style="background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:50px;">
                <h1>✅ Thành công!</h1>
                <p>Bạn đã nhận được <b>1 lượt giải bài miễn phí</b>!</p>
                <p>Tổng số lượt: <b>{{ remaining }}</b></p>
                <p style="color:#aaa;margin-top:30px;">Quay lại app/extension để sử dụng.</p>
            </body></html>
        ''', remaining=remaining)
    
    return render_template_string('''
        <html><body style="background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:50px;">
            <h1>❌ Lỗi!</h1>
            <p>Không tìm thấy user hoặc đã hết lượt.</p>
        </body></html>
    ''')

@app.route('/api/free-solve/use', methods=['POST'])
@login_required
def use_free_solve():
    """Use one free solve (for extension/mobile)"""
    remaining = get_user_free_solves(current_user)
    
    if remaining <= 0:
        return jsonify({
            'success': False,
            'message': 'Hết lượt miễn phí! Vượt link để nhận thêm hoặc nạp tiền.',
            'remaining': 0
        }), 400
    
    # Deduct one free solve
    current_user.free_solves_today = (current_user.free_solves_today or 0) - 1
    db.session.commit()
    
    new_remaining = current_user.free_solves_today
    return jsonify({
        'success': True,
        'message': f'Sử dụng 1 lượt. Còn {new_remaining} lượt.',
        'remaining': new_remaining
    })

# ================= Extension-specific Free Solve API =================
from flask_cors import cross_origin

def get_user_by_id(user_id):
    """Helper to get user by ID from X-User-Id header"""
    try:
        return User.query.get(int(user_id))
    except:
        return None

@app.route('/api/ext/free-solve/status', methods=['GET', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_free_solve_status():
    """Get free solve status for extension user"""
    if request.method == 'OPTIONS':
        return '', 200
    
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Missing user ID'}), 401
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    remaining = get_user_free_solves(user)
    return jsonify({
        'success': True,
        'remaining': remaining,
        'max': MAX_FREE_SOLVES_PER_DAY,
        'used_today': user.free_solves_today,
        'balance': user.balance or 0
    })

@app.route('/api/ext/free-solve/generate-link', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_generate_bypass_link():
    """Generate bypass link for extension user"""
    if request.method == 'OPTIONS':
        return '', 200
    
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Missing user ID'}), 401
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # Generate token and create bypass record
    token = secrets.token_urlsafe(32)
    bypass = LinkBypass(user_id=user.id, token=token)
    db.session.add(bypass)
    db.session.commit()
    
    # Create callback URL
    callback_url = f"https://tool.1amsleep.xyz/api/verify-bypass/{token}"
    
    # Call Link4m API to create shortened link (uses GET with params)
    try:
        resp = requests.get(
            LINK4M_API_URL,
            params={'api': LINK4M_API_TOKEN, 'url': callback_url},
            timeout=10
        )
        data = resp.json()
        
        if data.get('status') == 'success':
            short_url = data.get('shortenedUrl')
            bypass.short_url = short_url
            db.session.commit()
            return jsonify({'success': True, 'short_url': short_url})
        else:
            return jsonify({
                'success': False, 
                'message': data.get('message', 'Không thể tạo link')
            }), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
    return jsonify({'success': False, 'message': 'Failed to create link'}), 500

@app.route('/api/ext/free-solve/use', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_use_free_solve():
    """Use one free solve for extension user"""
    if request.method == 'OPTIONS':
        return '', 200
    
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Missing user ID'}), 401
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    remaining = get_user_free_solves(user)
    
    if remaining <= 0:
        return jsonify({
            'success': False,
            'message': 'Hết lượt! Vượt link để nhận thêm.',
            'remaining': 0
        }), 400
    
    # Deduct 1 solve
    user.free_solves_today = (user.free_solves_today or 0) - 1
    db.session.commit()
    
    new_remaining = user.free_solves_today
    return jsonify({
        'success': True,
        'message': f'Còn {new_remaining} lượt.',
        'remaining': new_remaining
    })

@app.route('/api/ext/paid-solve/use', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_use_paid_solve():
    """Use paid solve (deduct balance)"""
    if request.method == 'OPTIONS':
        return '', 200
    
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Missing user ID'}), 401
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # Check balance
    PRICE_PER_SOLVE = 2000
    if not user.balance or user.balance < PRICE_PER_SOLVE:
        return jsonify({
            'success': False,
            'message': f'Số dư không đủ! Cần {PRICE_PER_SOLVE}đ/lượt. Vui lòng nạp thêm.',
            'balance': user.balance or 0
        }), 400
    
    # Deduct balance
    user.balance -= PRICE_PER_SOLVE
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Đã trừ {PRICE_PER_SOLVE}đ. Số dư còn lại: {user.balance}đ',
        'balance': user.balance
    })

@app.route('/api/ext/start-solve', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_start_solve():
    """Start solving - deduct 1 free solve OR 2000đ from balance"""
    if request.method == 'OPTIONS':
        return '', 200
    
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập!', 'needLogin': True}), 401
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User không tồn tại!', 'needLogin': True}), 404
    
    PRICE_PER_SOLVE = 2000
    free_solves = user.free_solves_today or 0
    balance = user.balance or 0
    
    # Priority 1: Use free solve if available
    if free_solves > 0:
        user.free_solves_today = free_solves - 1
        db.session.commit()
        return jsonify({
            'success': True,
            'type': 'free',
            'message': f'Đã dùng 1 lượt miễn phí. Còn {user.free_solves_today} lượt.',
            'remaining_free': user.free_solves_today,
            'balance': balance
        })
    
    # Priority 2: Use balance if no free solves
    if balance >= PRICE_PER_SOLVE:
        user.balance = balance - PRICE_PER_SOLVE
        db.session.commit()
        return jsonify({
            'success': True,
            'type': 'paid',
            'message': f'Đã trừ {PRICE_PER_SOLVE:,}đ. Số dư: {user.balance:,}đ',
            'remaining_free': 0,
            'balance': user.balance
        })
    
    # Neither available
    return jsonify({
        'success': False,
        'message': f'Hết lượt miễn phí và số dư không đủ ({balance:,}đ < {PRICE_PER_SOLVE:,}đ)!',
        'needBypass': True,
        'needTopup': True,
        'remaining_free': 0,
        'balance': balance
    }), 400

@app.route('/api/ext/create_payment', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_create_payment():
    """Create payment QR for topup using PayOS"""
    if request.method == 'OPTIONS':
        return '', 200
    
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Chưa đăng nhập!'}), 401
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User không tồn tại!'}), 404
    
    data = request.get_json() or {}
    amount = data.get('amount', 0)
    
    if amount < 2000:
        return jsonify({'success': False, 'message': 'Tối thiểu 2,000đ!'}), 400
    
    try:
        # Generate unique order code
        import time
        order_code = int(f"{user.id}{int(time.time())}"[-15:])  # Max 15 digits
        
        # PayOS API call
        import hmac
        import hashlib
        
        # URLs must be same in signature and payload
        cancel_url = "https://tool.1amsleep.xyz/payment/cancel"
        return_url = "https://tool.1amsleep.xyz/payment/success"
        description = "Nap tien Quiz Solver"
        
        # Create signature - data must be sorted alphabetically by key
        # PayOS signature format: amount=X&cancelUrl=X&description=X&orderCode=X&returnUrl=X
        signature_data = f"amount={amount}&cancelUrl={cancel_url}&description={description}&orderCode={order_code}&returnUrl={return_url}"
        signature = hmac.new(
            PAYOS_CHECKSUM_KEY.encode(),
            signature_data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Create payment request - use exact same values as signature
        payload = {
            "orderCode": order_code,
            "amount": amount,
            "description": description,
            "cancelUrl": cancel_url,
            "returnUrl": return_url,
            "signature": signature
        }
        
        headers = {
            "x-client-id": PAYOS_CLIENT_ID,
            "x-api-key": PAYOS_API_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            "https://api-merchant.payos.vn/v2/payment-requests",
            json=payload,
            headers=headers
        )
        
        result = response.json()
        
        if result.get('code') == '00' and result.get('data'):
            checkout_url = result['data'].get('checkoutUrl')
            qr_code = result['data'].get('qrCode')
            
            # Save payment record
            payment = Payment(
                user_id=user.id,
                order_code=str(order_code),
                amount=amount,
                status='PENDING'
            )
            db.session.add(payment)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'checkoutUrl': checkout_url,
                'qrCode': qr_code,
                'orderCode': order_code,
                'amount': amount
            })
        else:
            app.logger.error(f"PayOS error: {result}")
            return jsonify({
                'success': False,
                'message': result.get('desc', 'Lỗi tạo payment')
            }), 400
            
    except Exception as e:
        app.logger.error(f"PayOS create payment error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/topup', methods=['GET'])
def topup_page():
    """Topup page with QR code"""
    user_id = request.args.get('user_id', '')
    amount = request.args.get('amount', '0')
    
    bank_id = "MB"
    account_no = "0976268206"
    account_name = "NGUYEN THE NHAT"
    description = f"NAPTIEN {user_id} {amount}"
    qr_url = f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact.png?amount={amount}&addInfo={description}&accountName={account_name}"
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Nạp tiền - Quiz Solver</title>
        <style>
            body { background: #1a1a2e; color: white; font-family: Arial; text-align: center; padding: 20px; }
            .container { max-width: 400px; margin: 0 auto; }
            h1 { color: #22c55e; }
            .qr-box { background: white; padding: 20px; border-radius: 15px; margin: 20px 0; }
            .qr-box img { max-width: 100%; }
            .info { background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; text-align: left; }
            .info p { margin: 8px 0; }
            .amount { font-size: 24px; color: #22c55e; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💸 Nạp tiền</h1>
            <p class="amount">{{ "{:,}".format(amount|int) }}đ</p>
            <div class="qr-box">
                <img src="{{ qr_url }}" alt="QR Code">
            </div>
            <div class="info">
                <p><b>Ngân hàng:</b> MB Bank</p>
                <p><b>STK:</b> {{ account_no }}</p>
                <p><b>Tên:</b> {{ account_name }}</p>
                <p><b>Nội dung:</b> {{ description }}</p>
            </div>
            <p style="color: #888; margin-top: 20px;">Sau khi chuyển khoản, số dư sẽ được cập nhật trong 1-5 phút.</p>
        </div>
    </body>
    </html>
    ''', qr_url=qr_url, amount=amount, account_no=account_no, account_name=account_name, description=description)

# ================= PayOS Webhook & Routes =================
import hmac
import hashlib

def verify_payos_signature(data, signature):
    """Verify PayOS webhook signature using HMAC SHA256"""
    if not signature or PAYOS_CHECKSUM_KEY == "your_checksum_key":
        return True  # Skip verification if checksum key not configured
    
    # Sort data alphabetically and create signature string
    webhook_data = data.get('data', {})
    sorted_data = sorted(webhook_data.items())
    data_string = "&".join([f"{k}={v}" for k, v in sorted_data])
    
    # Calculate HMAC SHA256
    calculated_signature = hmac.new(
        PAYOS_CHECKSUM_KEY.encode(),
        data_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return calculated_signature == signature

@app.route('/api/webhook/payos', methods=['POST'])
def payos_webhook():
    """
    PayOS webhook endpoint for automatic payment verification
    Configure this URL in PayOS dashboard: https://tool.1amsleep.xyz/api/webhook/payos
    
    Webhook payload format:
    {
        "code": "00",
        "desc": "success",
        "success": true,
        "data": {
            "orderCode": 123,
            "amount": 3000,
            "description": "VQRIO123",
            ...
        },
        "signature": "..."
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data'}), 400
        
        # Verify signature (optional but recommended)
        signature = data.get('signature', '')
        if not verify_payos_signature(data, signature):
            app.logger.warning("PayOS webhook: Invalid signature")
            return jsonify({'success': False, 'message': 'Invalid signature'}), 401
        
        # Extract payment info from payload
        code = data.get('code', '')           # '00' = success
        success = data.get('success', False)   # Also check success flag
        webhook_data = data.get('data', {})
        order_code = str(webhook_data.get('orderCode', ''))
        amount = webhook_data.get('amount', 0)
        desc = webhook_data.get('desc', '')
        
        app.logger.info(f"PayOS webhook: code={code}, orderCode={order_code}, amount={amount}")
        
        # Find payment record
        payment = Payment.query.filter_by(order_code=order_code).first()
        
        if not payment:
            app.logger.warning(f"Payment not found: {order_code}")
            return jsonify({'success': True, 'message': 'Payment not found'})
        
        # Already processed
        if payment.status == 'PAID':
            return jsonify({'success': True, 'message': 'Already processed'})
        
        # Check if payment was successful (code "00" means success)
        if code == '00' or success == True:
            # Update payment status
            payment.status = 'PAID'
            
            # Update user balance
            user = User.query.get(payment.user_id)
            if user:
                user.balance = (user.balance or 0) + payment.amount
                app.logger.info(f"Balance updated: user={user.id}, +{payment.amount}, new_balance={user.balance}")
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Payment verified: +{payment.amount}đ'
            })
        else:
            payment.status = 'CANCELLED'
            db.session.commit()
            return jsonify({'success': True, 'message': 'Payment cancelled'})
        
    except Exception as e:
        app.logger.error(f"PayOS webhook error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/payment/success', methods=['GET'])
def payment_success():
    """Payment success redirect page"""
    user_id = request.args.get('user_id', '')
    
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Thanh toán thành công</title>
        <style>
            body { background: #1a1a2e; color: white; font-family: Arial; text-align: center; padding: 50px; }
            .success { color: #22c55e; font-size: 48px; }
            h1 { color: #22c55e; }
            p { color: #888; }
        </style>
    </head>
    <body>
        <div class="success">✅</div>
        <h1>Thanh toán thành công!</h1>
        <p>Số dư của bạn đã được cập nhật.</p>
        <p>Bạn có thể đóng trang này và quay lại ứng dụng.</p>
    </body>
    </html>
    ''')

@app.route('/payment/cancel', methods=['GET'])
def payment_cancel():
    """Payment cancel redirect page"""
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Thanh toán bị hủy</title>
        <style>
            body { background: #1a1a2e; color: white; font-family: Arial; text-align: center; padding: 50px; }
            .cancel { color: #ef4444; font-size: 48px; }
            h1 { color: #ef4444; }
            p { color: #888; }
        </style>
    </head>
    <body>
        <div class="cancel">❌</div>
        <h1>Thanh toán bị hủy</h1>
        <p>Bạn đã hủy giao dịch hoặc hết thời gian thanh toán.</p>
        <p>Quay lại ứng dụng để thử lại.</p>
    </body>
    </html>
    ''')


@app.route('/api/get_accounts', methods=['GET'])
@login_required
def get_accounts():
    """Get all Onluyen accounts for current user"""
    accounts = OnluyenAccount.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        'success': True,
        'accounts': [{
            'id': acc.id,
            'username': acc.username,
            'api_key': acc.api_key[:10] + '...' if acc.api_key else None
        } for acc in accounts]
    })

@app.route('/api/start_solver', methods=['POST'])
@login_required
def start_solver():
    """Start the solver process"""
    account_id = request.json.get('account_id')
    account = OnluyenAccount.query.get(account_id)
    
    if not account or account.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Invalid account'}), 403
        
    # Check Balance (Free for Admin)
    is_admin = getattr(current_user, 'is_admin', False)
    if not is_admin and current_user.balance < 2000:
        return jsonify({'success': False, 'message': 'Insufficient balance (Need 2000 VND)'}), 402
    
    # Deduct balance if not admin
    if not is_admin:
        current_user.balance -= 2000
    
    db.session.commit()
    
    # Create Session Record
    new_session = SolverSession(user_id=current_user.id, account_id=account.id, status='RUNNING')
    db.session.add(new_session)
    db.session.commit()
    
    # Get config from request
    config_data = request.json
    
    account_data = {
        'username': account.username,
        'password': account.password,
        'proxy_key': account.proxy_key,
        'api_key': account.api_key,
        # Settings
        'auto_detect': config_data.get('auto_detect', True),
        'save_answers': config_data.get('save_answers', True),
        'continue_on_timeout': config_data.get('continue_on_timeout', True),
        'quiz_time': config_data.get('quiz_time', 45),
        'target_score': config_data.get('target_score', 8.0),
        'delay_min': config_data.get('delay_min', 3),
        'delay_max': config_data.get('delay_max', 8),
        'wait_for_assignment': config_data.get('wait_for_assignment', False)  # Don't auto-start solving if True
    }
    
    WebSolverManager.start_session(app, new_session.id, account_data)
    return jsonify({'success': True, 'session_id': new_session.id})

@app.route('/api/get_assignments/<int:session_id>', methods=['GET'])
@login_required
def get_assignments(session_id):
    """Get list of incomplete assignments from a running session"""
    session = WebSolverManager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    # Check if session is ready - allow multiple states
    allowed_states = ['LOGGED_IN', 'RUNNING', 'IDLE', 'WAITING', 'SOLVING']
    if session.state not in allowed_states:
        return jsonify({'error': f'Session not ready (state: {session.state})'}), 400
    
    # Get assignments using the instance method
    try:
        assignments = session.get_assignments()
        return jsonify({'assignments': assignments, 'state': session.state})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/select_assignment', methods=['POST'])
@login_required
def select_assignment():
    """Select a specific assignment to solve"""
    session_id = request.json.get('session_id')
    assignment_index = request.json.get('assignment_index')
    
    session = WebSolverManager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    try:
        success = session.select_and_solve(assignment_index)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Cannot start solving'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/session_status/<int:session_id>', methods=['GET'])
@login_required
def session_status(session_id):
    """Get current session status and logs"""
    session = WebSolverManager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'state': session.state,
        'logs': session.logs[-20:],
        'running': session.running,
        'vnc_port': session.get_websocket_port()  # noVNC websocket port
    })

@app.route('/stream/<int:session_id>')
def stream_feed(session_id):
    """Stream screenshots from headless Chrome"""
    def generate():
        while True:
            session = WebSolverManager.get_session(session_id)
            if not session or not session.running:
                break
            
            frame = session.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')
            time.sleep(1)  # 1 FPS for screenshots
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ================= Admin Routes =================
@app.route('/admin')
@login_required
def admin_panel():
    if not getattr(current_user, 'is_admin', False):
        return redirect(url_for('dashboard'))
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/api/admin/update_balance', methods=['POST'])
@login_required
def admin_update_balance():
    if not getattr(current_user, 'is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    user = User.query.get(int(data.get('user_id')))
    if user:
        user.balance = int(data.get('amount'))
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'User not found'}), 404

# CLI to create admin
@app.cli.command("create-admin")
def create_admin():
    import click
    username = click.prompt("Username")
    password = click.prompt("Password", hide_input=True)
    
    user = User.query.filter_by(username=username).first()
    if user:
        user.is_admin = True
        user.password_hash = generate_password_hash(password)
        print(f"Updated {username} to Admin.")
    else:
        user = User(username=username, password_hash=generate_password_hash(password), is_admin=True)
        db.session.add(user)
        print(f"Created new Admin {username}.")
    
    db.session.commit()
    

    








from payos import PayOS
from payos.types import ItemData, CreatePaymentLinkRequest

# Initialize PayOS
# Initialize PayOS
# Ensure .env is loaded
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

payos = PayOS(
    client_id=os.getenv("PAYOS_CLIENT_ID"), 
    api_key=os.getenv("PAYOS_API_KEY"), 
    checksum_key=os.getenv("PAYOS_CHECKSUM_KEY")
)

@app.route('/api/payos/create_payment', methods=['POST'])
@login_required
def create_payment():
    try:
        data = request.json
        amount = int(data.get('amount', 10000))
        if amount < 2000:
            return jsonify({'error': 'Minimum 2000 VND'}), 400
        
        # Create unique order code
        order_code = int(time.time() * 1000) # Simple unique ID
        
        # Use CreatePaymentLinkRequest instead of PaymentData
        # Each payment has unique description with order code
        payment_data = CreatePaymentLinkRequest(
            orderCode=order_code,
            amount=amount,
            description=f"QS{order_code % 1000000}",  # Unique code for each payment
            items=[ItemData(name=f"Topup {current_user.username}", quantity=1, price=amount)],
            returnUrl=url_for('dashboard', _external=True),
            cancelUrl=url_for('dashboard', _external=True)
        )
        
        payment_link_data = payos.payment_requests.create(payment_data)
        
        # Save pending payment to DB
        payment = Payment(
            user_id=current_user.id,
            order_code=str(order_code),
            amount=amount,
            status='PENDING'
        )
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({'checkoutUrl': payment_link_data.checkout_url})
        
    except Exception as e:
        print(f"PayOS Error: {e}")
        return jsonify({'error': str(e)}), 500

# ================= Answer Storage API =================
@app.route('/api/get-answer-file', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def get_answer_file():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json
    quiz_hash = data.get('quiz_hash')
    
    if not quiz_hash:
        return jsonify({'success': False, 'message': 'Missing hash'}), 400
        
    answer = AnswerFile.query.filter_by(quiz_hash=quiz_hash).first()
    if answer:
        return jsonify({'success': True, 'answers': json.loads(answer.content)})
    return jsonify({'success': False, 'message': 'Not found'}), 404

@app.route('/api/save-answer-file', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def save_answer_file():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.json
    quiz_name = data.get('quiz_name')
    quiz_hash = data.get('quiz_hash')
    answers = data.get('answers')
    
    if not quiz_name or not quiz_hash or not answers:
        return jsonify({'success': False, 'message': 'Invalid data'}), 400
        
    # Upsert
    answer = AnswerFile.query.filter_by(quiz_hash=quiz_hash).first()
    if not answer:
        answer = AnswerFile(quiz_name=quiz_name, quiz_hash=quiz_hash)
        db.session.add(answer)
    
    answer.content = json.dumps(answers)
    db.session.commit()
    return jsonify({'success': True})

# ================= Chrome Extension API =================
from flask_cors import cross_origin

@app.route('/api/ext/login', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_login():
    """Extension login endpoint"""
    if request.method == 'OPTIONS':
        return '', 200
        
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'balance': user.balance
            }
        })
    return jsonify({'success': False, 'message': 'Sai tên đăng nhập hoặc mật khẩu'}), 401

@app.route('/api/ext/register', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_register():
    """Extension register endpoint"""
    if request.method == 'OPTIONS':
        return '', 200
        
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Tên đăng nhập đã tồn tại'}), 400
    
    user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/ext/accounts', methods=['GET', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_get_accounts():
    """Get accounts for extension"""
    if request.method == 'OPTIONS':
        return '', 200
        
    # Get user_id from header (since extension can't use cookies easily)
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    accounts = OnluyenAccount.query.filter_by(user_id=int(user_id)).all()
    return jsonify({
        'success': True,
        'accounts': [{'id': a.id, 'username': a.username} for a in accounts]
    })

@app.route('/api/ext/add_account', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_add_account():
    """Add Onluyen account from extension"""
    if request.method == 'OPTIONS':
        return '', 200
        
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    account = OnluyenAccount(
        user_id=int(user_id),
        username=data['username'],
        password=data['password'],
        api_key=data.get('api_key', '')
    )
    db.session.add(account)
    db.session.commit()
    return jsonify({'success': True, 'account_id': account.id})

@app.route('/api/ext/start_solver', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_start_solver():
    """Start solver from extension"""
    if request.method == 'OPTIONS':
        return '', 200
        
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    account_id = data.get('account_id')
    
    account = OnluyenAccount.query.get(account_id)
    if not account or account.user_id != int(user_id):
        return jsonify({'success': False, 'message': 'Account not found'}), 404
    
    # Create session
    new_session = SolverSession(user_id=int(user_id), account_id=int(account_id), status='RUNNING')
    db.session.add(new_session)
    db.session.commit()
    
    # Prepare account data
    account_data = {
        'username': account.username,
        'password': account.password,
        'api_key': account.api_key
    }
    
    # Start solver
    WebSolverManager.start_session(app, new_session.id, account_data, {})
    
    return jsonify({'success': True, 'session_id': new_session.id})

@app.route('/api/ext/session_status/<int:session_id>', methods=['GET', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_session_status(session_id):
    """Get session status for extension"""
    if request.method == 'OPTIONS':
        return '', 200
        
    session = WebSolverManager.get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'state': session.state,
        'logs': session.logs[-20:],
        'running': session.running
    })


# ================= AI Solve via gpt4free (PollinationsAI) =================
import base64

@app.route('/api/ext/gemini-solve', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def ext_gemini_solve():
    """Solve quiz using gpt4free PollinationsAI (free, no auth needed)"""
    if request.method == 'OPTIONS':
        return '', 200
    
    data = request.json
    prompt = data.get('prompt', '')
    image_base64 = data.get('image')  # Base64 encoded image (optional)
    
    if not prompt:
        return jsonify({'success': False, 'message': 'Missing prompt'}), 400
    
    try:
        print(f"[AI Solve] Prompt: {prompt[:50]}...")
        
        # Build messages for gpt4free API
        messages = []
        
        if image_base64:
            # Vision model with image
            print(f"[AI Solve] Image size: {len(image_base64)} bytes")
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            })
        else:
            messages.append({"role": "user", "content": prompt})
        
        # Call gpt4free server (running on localhost:6969)
        response = requests.post(
            'http://localhost:6969/v1/chat/completions',
            json={
                "model": "PollinationsAI",
                "messages": messages
            },
            timeout=60
        )
        
        result = response.json()
        
        if 'error' in result:
            print(f"[AI Solve] Error: {result['error']}")
            return jsonify({'success': False, 'message': result['error'].get('message', 'Unknown error')})
        
        # Extract response text
        text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f"[AI Solve] Response: {text[:100]}...")
        
        return jsonify({'success': True, 'response': text})
        
    except Exception as e:
        print(f"[AI Solve] Exception: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Extension Version Check API
@app.route('/api/ext/version', methods=['GET', 'OPTIONS'])
@cross_origin()
def ext_version_check():
    """Get latest extension version info"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        return jsonify({
            'version': '1.2.0',  # Update this when releasing new version
            'download_url': 'https://tool.1amsleep.xyz/ext/quiz-solver-latest.zip',
            'changelog': 'Fixed Gemini Web image upload with resumable protocol'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/log-file', methods=['POST'])
@cross_origin()
def debug_log_file():
    """Save content to a debug file"""
    try:
        data = request.json
        content = data.get('content', '')
        filename = data.get('filename', 'gemini_debug.txt')
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"[Debug] Saved {len(content)} bytes to {filename}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

