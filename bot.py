import time
import os
import random
import re
import requests
import json
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from gemini_web_api import GeminiWebClient
import konmeo

# File lưu thông tin đăng nhập
CONFIG_FILE = "config.json"

def log(msg, type="INFO"):
    print(f"[{time.strftime('%H:%M:%S')}] [{type}] {msg}")

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def load_config():
    """Đọc config từ file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config):
    """Lưu config vào file"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_credentials():
    """Lấy thông tin đăng nhập (từ file hoặc nhập mới)"""
    config = load_config()
    
    if config.get("account") and config.get("password"):
        print(f"\n📌 Tài khoản đã lưu: {config['account']}")
        choice = input("Sử dụng tài khoản này? (Y/n): ").strip().lower()
        if choice != 'n':
            return config["account"], config["password"]
    
    # Nhập mới
    print("\n🔐 NHẬP THÔNG TIN ĐĂNG NHẬP KIEMMONEY")
    account = input("Email hoặc SĐT: ").strip()
    password = input("Mật khẩu: ").strip()
    
    # Hỏi lưu
    save_choice = input("Lưu thông tin đăng nhập? (Y/n): ").strip().lower()
    if save_choice != 'n':
        config["account"] = account
        config["password"] = password
        save_config(config)
        print("✅ Đã lưu thông tin đăng nhập!")
    
    return account, password

def solve_captcha_with_gemini(driver, google_cookies):
    """Chụp ảnh captcha và gửi lên Gemini để giải"""
    log("Đang giải CAPTCHA bằng Gemini...", "INFO")
    captcha_path = "captcha_temp.png"
    
    try:
        # Chụp ảnh captcha
        captcha_img = driver.find_element(By.ID, "captchaImg")
        captcha_img.screenshot(captcha_path)
        log("-> Đã chụp ảnh CAPTCHA", "SUCCESS")
        
        if not google_cookies:
            return None
            
        ua = driver.execute_script("return navigator.userAgent;")
        gemini = GeminiWebClient(google_cookies, user_agent=ua)
        
        prompt = """
        Look at this CAPTCHA image and tell me EXACTLY what text/characters are shown.
        OUTPUT ONLY the characters you see, nothing else. No explanation needed.
        Example output: ABC123 or xYz789
        """
        
        result = gemini.send_prompt(prompt, captcha_path, model='flash')
        
        if result:
            # Làm sạch kết quả
            captcha_text = result.strip().replace(" ", "")
            # Chỉ giữ lại ký tự alphanumeric
            captcha_text = re.sub(r'[^a-zA-Z0-9]', '', captcha_text)
            log(f"-> CAPTCHA: {captcha_text}", "SUCCESS")
            return captcha_text
        return None
    except Exception as e:
        log(f"Lỗi giải CAPTCHA: {e}", "ERROR")
        return None

def login_kiemmoney(driver, account, password, google_cookies):
    """Đăng nhập vào kiemmoney.com"""
    log("Đang mở trang đăng nhập KiemMoney...", "INFO")
    
    # Set timeout cho page load
    driver.set_page_load_timeout(30)
    
    try:
        driver.get("https://kiemmoney.com/account/login")
    except Exception as e:
        log(f"Timeout khi load trang, thử refresh...: {e}", "WARN")
        try:
            driver.refresh()
        except:
            pass
    
    log("-> Trang đã load xong", "INFO")
    time.sleep(2)
    
    # Kiểm tra nếu đã đăng nhập rồi (redirect sang dashboard)
    current_url = driver.current_url
    log(f"-> URL hiện tại: {current_url}", "INFO")
    
    if "login" not in current_url.lower():
        log("🎉 Đã đăng nhập sẵn rồi!", "SUCCESS")
        return True
    
    try:
        # Nhập tài khoản
        account_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "account"))
        )
        account_input.clear()
        account_input.send_keys(account)
        log(f"-> Đã nhập tài khoản: {account}", "SUCCESS")
        
        # Nhập mật khẩu
        password_input = driver.find_element(By.ID, "password")
        password_input.clear()
        password_input.send_keys(password)
        log("-> Đã nhập mật khẩu", "SUCCESS")
        
        # Giải CAPTCHA
        max_attempts = 3
        for attempt in range(max_attempts):
            log(f"Thử giải CAPTCHA lần {attempt + 1}...", "INFO")
            
            # Click vào captcha để refresh nếu không phải lần đầu
            if attempt > 0:
                try:
                    captcha_img = driver.find_element(By.ID, "captchaImg")
                    captcha_img.click()
                    time.sleep(2)
                except:
                    pass
            
            captcha_text = solve_captcha_with_gemini(driver, google_cookies)
            
            if captcha_text:
                captcha_input = driver.find_element(By.ID, "captcha")
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)
                
                # Click đăng nhập
                submit_btn = driver.find_element(By.ID, "submitBtn")
                submit_btn.click()
                log("-> Đã click nút đăng nhập, chờ phản hồi...", "INFO")
                time.sleep(5)  # Tăng thời gian chờ
                
                # Kiểm tra đăng nhập thành công
                current_url = driver.current_url
                log(f"-> URL sau đăng nhập: {current_url}", "INFO")
                
                if "login" not in current_url.lower():
                    log("🎉 Đăng nhập thành công!", "SUCCESS")
                    # Chờ thêm để trang dashboard load hoàn toàn
                    time.sleep(3)
                    log(f"-> Trang hiện tại: {driver.current_url}", "INFO")
                    return True
                else:
                    # Kiểm tra xem có thông báo lỗi không
                    try:
                        error_msg = driver.find_element(By.CSS_SELECTOR, ".alert, .error, .message").text
                        log(f"-> Lỗi từ server: {error_msg}", "WARN")
                    except:
                        pass
                    log("CAPTCHA sai hoặc lỗi khác, thử lại...", "WARN")
            else:
                log("Không giải được CAPTCHA", "ERROR")
        
        return False
    except Exception as e:
        log(f"Lỗi đăng nhập: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False

# ============== MAPPING CÁC TASK TRÊN KIEMMONEY ==============
TASK_CONFIG = {
    "nhapma": {"name": "Nhapma", "data_id": "79", "bypass_func": "nhapma", "reward": 350},
    "4mmo": {"name": "4mmo", "data_id": "78", "bypass_func": "4mmo", "reward": 350},
    "uptolink2": {"name": "Uptolink 2", "data_id": "77", "bypass_func": "uptolink", "reward": 350},
    "uptolink3": {"name": "Uptolink 3", "data_id": "76", "bypass_func": "uptolink", "reward": 300},
    "linktop": {"name": "LinkTop", "data_id": "75", "bypass_func": "linktop", "reward": 300},
    "linkngon": {"name": "LinkNgon", "data_id": "74", "bypass_func": "linkngon", "reward": 300},
    "linktot": {"name": "Linktot", "data_id": "68", "bypass_func": "linktot", "reward": 350},
    "bbmkts": {"name": "Bbmkts", "data_id": "63", "bypass_func": "bbmkts", "reward": 450},
}

def show_task_menu():
    """Hiển thị menu chọn task trên KiemMoney"""
    print("\n📋 CHỌN NHIỆM VỤ TRÊN KIEMMONEY:")
    tasks = list(TASK_CONFIG.keys())
    for i, key in enumerate(tasks, 1):
        cfg = TASK_CONFIG[key]
        print(f"  {i}. {cfg['name']} ({cfg['reward']} ⭐)")
    print("  0. Quay lại")
    
    choice = input("\nChọn: ").strip()
    if choice == "0":
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(tasks):
            return tasks[idx]
    except:
        pass
    return None

def bypass_task_auto(task_url, bypass_type):
    """Auto bypass một task dựa vào loại bypass (không cần Gemini)"""
    try:
        if bypass_type == "nhapma":
            return None  # Dùng Gemini cho Nhapma
        elif bypass_type == "4mmo":
            return konmeo.get_code_4mmo()
        elif bypass_type == "linktop":
            url = konmeo.normalize_https_url(task_url)
            if url:
                code, err = konmeo.get_code_linktopngon(url, "linktop.one")
                return code if code else f"Lỗi: {err}"
            return None
        elif bypass_type == "linktot":
            return konmeo.get_code_linktot_normal(task_url)
        elif bypass_type == "bbmkts":
            return konmeo.get_code_bbmkts(task_url)
        elif bypass_type == "uptolink":
            return None  # Dùng Gemini cho Uptolink
        else:
            return None
    except Exception as e:
        log(f"Lỗi bypass {bypass_type}: {e}", "ERROR")
        return None

def detect_nhapma_page_type(driver):
    """Phát hiện loại trang Nhapma: type1 (có ảnh hướng dẫn) hoặc type2 (có link + keyword)"""
    try:
        # Kiểm tra type2: có "Bước 1: Sao chép link" và keyword cần tìm
        has_step_copy = driver.execute_script("""
            var text = document.body.innerText;
            return text.includes('Bước 1') && text.includes('Sao chép link');
        """)
        
        has_keyword_section = driver.execute_script("""
            var orangeBox = document.querySelector('.border-orange-500, .border-orange-400');
            return orangeBox !== null;
        """)
        
        if has_step_copy and has_keyword_section:
            return "type2"
        
        # Kiểm tra type1: có ảnh hướng dẫn
        has_instruction_image = driver.execute_script("""
            var img = document.querySelector('.shortify-reviewcontent img') ||
                     document.querySelector('[data-v-9b370738] img') ||
                     document.querySelector('form img');
            return img !== null;
        """)
        
        if has_instruction_image:
            return "type1"
        
        return "unknown"
    except:
        return "unknown"

def extract_nhapma_type2_data(driver):
    """Trích xuất link và keyword từ trang Nhapma type2"""
    log("Trích xuất dữ liệu từ Nhapma type2...", "INFO")
    
    try:
        # Lấy link cần sao chép (nằm trong blue box đầu tiên)
        target_link = driver.execute_script("""
            var blueBox = document.querySelector('.border-blue-500');
            if (blueBox) {
                var linkSpan = blueBox.querySelector('span.truncate');
                if (linkSpan) return linkSpan.innerText.trim();
            }
            // Fallback: tìm link có chứa http
            var spans = document.querySelectorAll('span');
            for (var s of spans) {
                if (s.innerText.includes('http') && s.innerText.length > 20) {
                    return s.innerText.trim();
                }
            }
            return null;
        """)
        
        # Lấy keyword cần tìm (nằm trong orange box)
        target_keyword = driver.execute_script("""
            var orangeBox = document.querySelector('.border-orange-500, .border-orange-400');
            if (orangeBox) {
                var keywordSpan = orangeBox.querySelector('span.font-medium');
                if (keywordSpan) return keywordSpan.innerText.trim();
            }
            // Fallback: tìm text sau "click vào là"
            var text = document.body.innerText;
            var match = text.match(/click vào là\\s*([\\w]+)/i);
            if (match) return match[1];
            return null;
        """)
        
        log(f"-> Link: {target_link[:50] if target_link else 'None'}...", "INFO")
        log(f"-> Keyword: {target_keyword}", "INFO")
        
        return target_link, target_keyword
    except Exception as e:
        log(f"Lỗi trích xuất: {e}", "ERROR")
        return None, None

def handle_nhapma_type2(driver, google_cookies, target_link, target_keyword):
    """Xử lý Nhapma type2: mở link, tìm keyword, click, lấy code"""
    log(f"=== XỬ LÝ NHAPMA TYPE2 ===", "WARN")
    log(f"Link: {target_link}", "INFO")
    log(f"Keyword: {target_keyword}", "INFO")
    
    try:
        # 1. Mở link trong tab mới
        original_window = driver.current_window_handle
        driver.execute_script(f"window.open('{target_link}', '_blank');")
        time.sleep(3)
        
        # Chuyển sang tab mới
        for handle in driver.window_handles:
            if handle != original_window:
                driver.switch_to.window(handle)
                break
        
        log(f"-> Đã mở link: {driver.current_url}", "SUCCESS")
        time.sleep(5)  # Chờ trang load
        
        # 2. Scroll và tìm keyword
        log(f"Đang tìm keyword '{target_keyword}'...", "INFO")
        
        # Scroll xuống dần và tìm
        found_element = None
        for scroll_pos in range(0, 5000, 500):
            driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
            time.sleep(1)
            
            # Tìm element chứa keyword
            found_element = driver.execute_script(f"""
                var keyword = '{target_keyword}';
                var allElements = document.querySelectorAll('a, button, span, div');
                for (var el of allElements) {{
                    if (el.innerText && el.innerText.toLowerCase().includes(keyword.toLowerCase())) {{
                        // Không phải element ẩn
                        if (el.offsetWidth > 0 && el.offsetHeight > 0) {{
                            el.scrollIntoView({{block: 'center'}});
                            return el.outerHTML.substring(0, 200);
                        }}
                    }}
                }}
                return null;
            """)
            
            if found_element:
                log(f"-> Tìm thấy element chứa '{target_keyword}'", "SUCCESS")
                break
        
        if not found_element:
            log(f"Không tìm thấy '{target_keyword}' trong trang!", "ERROR")
            driver.close()
            driver.switch_to.window(original_window)
            return None
        
        # 3. Click vào element chứa keyword
        clicked = driver.execute_script(f"""
            var keyword = '{target_keyword}';
            var links = document.querySelectorAll('a');
            for (var el of links) {{
                if (el.innerText && el.innerText.toLowerCase().includes(keyword.toLowerCase())) {{
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) {{
                        el.click();
                        return 'Clicked link: ' + el.href;
                    }}
                }}
            }}
            // Fallback: tìm bất kỳ element nào
            var allElements = document.querySelectorAll('*');
            for (var el of allElements) {{
                if (el.innerText === keyword || el.innerText.includes(keyword)) {{
                    if (el.offsetWidth > 0 && el.offsetHeight > 0 && el.click) {{
                        el.click();
                        return 'Clicked element';
                    }}
                }}
            }}
            return 'No clickable element found';
        """)
        
        log(f"-> {clicked}", "INFO")
        time.sleep(3)
        
        # 4. QUAN TRỌNG: Kiểm tra có tab mới mở không
        log("Kiểm tra tabs sau khi click...", "INFO")
        all_tabs = driver.window_handles
        log(f"-> Số tabs: {len(all_tabs)}", "INFO")
        
        target_url_for_konmeo = None
        nhapma_tab = original_window
        
        # Tìm tab mới (không phải tab gốc và không phải tab đã mở link)
        for handle in all_tabs:
            if handle == original_window:
                continue
            driver.switch_to.window(handle)
            time.sleep(2)
            current_url = driver.current_url
            log(f"-> Tab URL: {current_url}", "INFO")
            
            # Nếu đây là tab mới từ click keyword (không phải trang photosnow ban đầu)
            if "nhapma" not in current_url and current_url != target_link:
                target_url_for_konmeo = current_url
                log(f"-> Tìm thấy target URL: {target_url_for_konmeo}", "SUCCESS")
                # Đóng tab này
                driver.close()
                break
        
        # Nếu không tìm được trong tab mới, thử lấy từ redirect
        if not target_url_for_konmeo:
            # Có thể click đã redirect trong cùng tab
            current_tab_url = driver.current_url
            if "nhapma" not in current_tab_url and current_tab_url != target_link:
                target_url_for_konmeo = current_tab_url
                log(f"-> Target URL từ redirect: {target_url_for_konmeo}", "SUCCESS")
        
        if not target_url_for_konmeo:
            log("Không tìm được target URL!", "ERROR")
            driver.switch_to.window(original_window)
            return None
        
        # 5. Gọi konmeo để lấy code
        log(f"Gọi konmeo bypass với URL: {target_url_for_konmeo}", "INFO")
        code = None
        try:
            code = konmeo.get_code_nhapma(target_url_for_konmeo)
            if code:
                log(f"🎉 CODE TỪ KONMEO: {code}", "SUCCESS")
        except Exception as e:
            log(f"Lỗi konmeo: {e}", "ERROR")
        
        if not code:
            code = input("Konmeo lỗi. Nhập code bằng tay: ").strip()
        
        if not code:
            log("Không có code!", "ERROR")
            driver.switch_to.window(original_window)
            return None
        
        # 6. Quay lại trang Nhapma gốc
        driver.switch_to.window(original_window)
        time.sleep(2)
        
        # Reload hoặc navigate về trang nhapma nếu cần
        current_url = driver.current_url
        log(f"-> Quay lại trang: {current_url}", "INFO")
        
        # 7. Trong trang nhapma - tìm nút "Tiếp tục" và click
        log("Tìm và click nút Tiếp tục...", "INFO")
        
        for _ in range(10):
            time.sleep(2)
            clicked_continue = driver.execute_script("""
                // Tìm nút Tiếp tục
                var btns = document.querySelectorAll('button, a');
                for (var btn of btns) {
                    var text = btn.innerText.toLowerCase();
                    if (text.includes('tiếp tục') || text.includes('continue') || 
                        text.includes('xác nhận') || text.includes('submit')) {
                        if (btn.offsetWidth > 0 && btn.offsetHeight > 0) {
                            btn.scrollIntoView({block: 'center'});
                            btn.click();
                            return 'Clicked: ' + btn.innerText;
                        }
                    }
                }
                
                // Tìm nút có icon angular
                var iconBtn = document.querySelector('img[src*="angular_icon"]');
                if (iconBtn) {
                    var parent = iconBtn.closest('a, button, span');
                    if (parent) {
                        parent.click();
                        return 'Clicked icon button';
                    }
                }
                
                return null;
            """)
            
            if clicked_continue:
                log(f"-> {clicked_continue}", "SUCCESS")
                break
            
            # Scroll xuống tìm tiếp
            driver.execute_script("window.scrollBy(0, 300);")
        
        time.sleep(3)
        
        # 8. Kiểm tra có chuyển sang trang KiemMoney captcha không
        current_url = driver.current_url
        log(f"-> URL sau click continue: {current_url}", "INFO")
        
        if "kiemmoney" in current_url:
            # Đã chuyển sang trang captcha KiemMoney
            log("Đã đến trang captcha KiemMoney!", "SUCCESS")
            return code  # Trả về code để hàm gọi xử lý captcha
        
        return code
        
    except Exception as e:
        log(f"Lỗi xử lý Nhapma type2: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return None

def get_nhapma_image_and_domain(driver, google_cookies):
    """Lấy ảnh từ trang Nhapma và gửi Gemini để tìm domain"""
    log("Đang tìm ảnh hướng dẫn Nhapma...", "INFO")
    img_path = "nhapma_instruction.png"
    
    try:
        # Tìm ảnh trong div chứa hướng dẫn
        img_element = None
        
        # Thử các selector khác nhau cho ảnh Nhapma
        selectors = [
            'div.rounded-xl img[alt="Hướng dẫn"]',
            'div[data-v-9b370738] img',
            'img[alt="Hướng dẫn"]',
            '.rounded-xl.border-orange-200 img',
            'div.text-center img.rounded-lg'
        ]
        
        for selector in selectors:
            try:
                img_element = driver.find_element(By.CSS_SELECTOR, selector)
                if img_element:
                    log(f"-> Tìm thấy ảnh với selector: {selector}", "SUCCESS")
                    break
            except:
                continue
        
        if img_element:
            # Scroll đến ảnh và chụp
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img_element)
            time.sleep(1)
            img_element.screenshot(img_path)
            log("-> Đã chụp ảnh hướng dẫn Nhapma", "SUCCESS")
        else:
            # Fallback: chụp toàn trang
            log("-> Không tìm thấy ảnh, chụp toàn trang...", "WARN")
            driver.save_screenshot(img_path)
        
        if not google_cookies:
            return None
        
        # Gửi Gemini để phân tích
        ua = driver.execute_script("return navigator.userAgent;")
        gemini = GeminiWebClient(google_cookies, user_agent=ua)
        
        prompt = """
        Look at this image. Find the target website domain shown.
        Ignore google.com, nhapma.com, upanhlaylink.com.
        OUTPUT ONLY THE DOMAIN NAME (example: website.com)
        """
        
        result = gemini.send_prompt(prompt, img_path, model='pro')
        log(f"-> Gemini raw response: {result[:100] if result else 'None'}...", "INFO")
        
        if result:
            # Tìm tất cả domain trong response
            candidates = re.findall(r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}', result)
            blacklist = ['google.com', 'nhapma.com', 'upanhlaylink.com', 'gemini.google.com', 'sf-static.upanhlaylink.com']
            
            log(f"-> Các domain tìm thấy: {candidates}", "INFO")
            
            final_domain = None
            for cand in candidates:
                cand_lower = cand.lower()
                if any(bl in cand_lower for bl in blacklist):
                    continue
                if len(cand) < 4:
                    continue
                if final_domain is None or len(cand) > len(final_domain):
                    final_domain = cand
            
            if final_domain:
                final_domain = final_domain.rstrip('.')
                log(f"-> CHỐT DOMAIN: {final_domain}", "SUCCESS")
                return final_domain
        
        return None
    except Exception as e:
        log(f"Lỗi lấy ảnh Nhapma: {e}", "ERROR")
        return None

def solve_kiemmoney_captcha(driver, google_cookies):
    """Giải captcha trên trang KiemMoney sau khi nhập code"""
    log("Đang giải captcha KiemMoney...", "INFO")
    
    try:
        # Chờ trang captcha load
        time.sleep(3)
        
        # Tìm ảnh captcha
        captcha_img = None
        captcha_selectors = [
            'img[src*="captcha"]',
            '.captcha-card img',
            'form img',
            '#rewardForm img'
        ]
        
        for selector in captcha_selectors:
            try:
                captcha_img = driver.find_element(By.CSS_SELECTOR, selector)
                if captcha_img:
                    log(f"-> Tìm thấy captcha với selector: {selector}", "SUCCESS")
                    break
            except:
                continue
        
        if not captcha_img:
            log("Không tìm thấy ảnh captcha!", "ERROR")
            return False
        
        # Chụp ảnh captcha
        captcha_path = "kiemmoney_captcha.png"
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", captcha_img)
        time.sleep(1)
        captcha_img.screenshot(captcha_path)
        log("-> Đã chụp ảnh captcha", "SUCCESS")
        
        # Gửi Gemini để giải
        if not google_cookies:
            log("Không có cookies Gemini!", "ERROR")
            return False
        
        ua = driver.execute_script("return navigator.userAgent;")
        gemini = GeminiWebClient(google_cookies, user_agent=ua)
        
        prompt = "Read the captcha text in this image. Output ONLY the captcha text, nothing else."
        result = gemini.send_prompt(prompt, captcha_path, model='pro')
        
        captcha_text = None
        if result:
            # Lấy captcha text từ Gemini response
            captcha_text = result.strip().split('\n')[0].strip()
            # Loại bỏ các ký tự không phải alphanumeric
            captcha_text = ''.join(c for c in captcha_text if c.isalnum())
            if captcha_text:
                log(f"-> Captcha từ Gemini: {captcha_text}", "SUCCESS")
        
        # Fallback: Yêu cầu nhập thủ công nếu Gemini lỗi
        if not captcha_text:
            log("Gemini không trả về kết quả! Yêu cầu nhập thủ công.", "WARN")
            # Hiển thị đường dẫn ảnh để user xem
            abs_path = os.path.abspath(captcha_path)
            log(f"-> Xem captcha tại: {abs_path}", "INFO")
            
            # Thử mở ảnh captcha
            try:
                os.startfile(abs_path)  # Windows
            except:
                pass
            
            captcha_text = input("Nhập captcha bằng tay: ").strip()
        
        if not captcha_text:
            log("Không có captcha text!", "ERROR")
            return False
        
        # Điền captcha vào input
        captcha_input = None
        input_selectors = ['#captchaInput', 'input[name="captcha"]', 'input[placeholder*="captcha"]']
        
        for selector in input_selectors:
            try:
                captcha_input = driver.find_element(By.CSS_SELECTOR, selector)
                if captcha_input:
                    break
            except:
                continue
        
        if not captcha_input:
            log("Không tìm thấy input captcha!", "ERROR")
            return False
        
        captcha_input.clear()
        # Nhập từng ký tự với delay ngẫu nhiên
        for char in captcha_text:
            captcha_input.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))  # Delay 100-300ms mỗi ký tự
        log(f"-> Đã nhập captcha: {captcha_text}", "SUCCESS")
        
        time.sleep(1)
        
        # Click nút Tiếp Tục
        submit_btn = None
        btn_selectors = ['#submitBtn', 'button[type="button"]', '.btn-primary-custom', 'button:contains("Tiếp Tục")']
        
        for selector in btn_selectors:
            try:
                submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
                if submit_btn and submit_btn.is_displayed():
                    break
            except:
                continue
        
        if submit_btn:
            submit_btn.click()
            log("-> Đã click Tiếp Tục", "SUCCESS")
        else:
            # Thử JavaScript
            driver.execute_script("""
                var btn = document.querySelector('#submitBtn') || 
                          document.querySelector('button.btn-primary-custom');
                if (btn) btn.click();
            """)
            log("-> Đã click Tiếp Tục (JS)", "SUCCESS")
        
        time.sleep(3)
        
        # Đợi SweetAlert2 popup và click OK
        log("Đợi popup OK...", "INFO")
        for _ in range(10):
            try:
                # Tìm nút OK của SweetAlert2
                ok_btn = driver.execute_script("""
                    var btn = document.querySelector('.swal2-confirm') ||
                              document.querySelector('.swal2-actions button') ||
                              document.querySelector('button.swal2-styled');
                    if (btn) { btn.click(); return true; }
                    return false;
                """)
                if ok_btn:
                    log("-> Đã click OK", "SUCCESS")
                    break
            except:
                pass
            time.sleep(1)
        
        time.sleep(2)
        return True
        
    except Exception as e:
        log(f"Lỗi giải captcha: {e}", "ERROR")
        return False

def bypass_4mmo_with_gemini(driver, google_cookies):
    """Bypass 4mmo: lấy code từ konmeo → nhập code → captcha → OK"""
    log("=== BẮT ĐẦU BYPASS 4MMO ===", "WARN")
    
    # 1. Lấy code từ konmeo
    code = None
    try:
        code = konmeo.get_code_4mmo()
        if code:
            log(f"🎉 CODE 4MMO: {code}", "SUCCESS")
    except Exception as e:
        log(f"Lỗi konmeo.get_code_4mmo: {e}", "ERROR")
    
    if not code:
        code = input("Không lấy được code tự động. Nhập code bằng tay: ").strip()
    
    if not code:
        log("Không có code, hủy...", "ERROR")
        return None
    
    # 2. Chờ chuyển hướng đến trang 4mmo
    log("Chờ chuyển hướng đến 4mmo.net...", "INFO")
    try:
        # Chờ tối đa 30 giây để URL chứa "4mmo"
        WebDriverWait(driver, 30).until(
            lambda d: "4mmo" in d.current_url.lower()
        )
        log(f"-> Đã đến trang 4mmo: {driver.current_url}", "SUCCESS")
    except:
        log(f"Không thể chờ 4mmo, URL hiện tại: {driver.current_url}", "WARN")
    
    time.sleep(3)  # Chờ thêm để trang load hoàn toàn
    log(f"URL hiện tại: {driver.current_url}", "INFO")
    
    # 3. Nhập code vào form 4mmo và submit
    log("Nhập code vào form 4mmo...", "INFO")
    try:
        # Chờ input xuất hiện với WebDriverWait
        code_input = None
        input_selectors = [
            '#code',
            'input[name="code_"]',
            'input.code-input',
            'input[placeholder*="code"]',
            'input[placeholder*="mã"]',
            'input[placeholder*="Dán"]'
        ]
        
        # Thử chờ với WebDriverWait
        for selector in input_selectors:
            try:
                code_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if code_input:
                    log(f"-> Tìm thấy input: {selector}", "SUCCESS")
                    break
            except:
                continue
        
        # Nếu không tìm được, thử scroll và tìm lại
        if not code_input:
            log("Thử scroll và tìm lại...", "INFO")
            driver.execute_script("window.scrollTo(0, 300);")
            time.sleep(2)
            
            for selector in input_selectors:
                try:
                    code_input = driver.find_element(By.CSS_SELECTOR, selector)
                    if code_input and code_input.is_displayed():
                        log(f"-> Tìm thấy input sau scroll: {selector}", "SUCCESS")
                        break
                except:
                    continue
        
        if code_input:
            # Scroll đến input
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", code_input)
            time.sleep(1)
            
            code_input.clear()
            code_input.send_keys(code)
            log(f"-> Đã nhập code: {code}", "SUCCESS")
            time.sleep(2)
            
            # Click nút "Xác Nhận & Tiếp Tục"
            clicked = driver.execute_script("""
                var btn = document.querySelector('#invisibleCaptchaShortlink') ||
                          document.querySelector('.traffic-submit-btn') ||
                          document.querySelector('.btn-captcha') ||
                          document.querySelector('button[type="submit"]') ||
                          document.querySelector('form button');
                if (btn) {
                    btn.scrollIntoView({block: 'center'});
                    btn.click();
                    return 'Clicked: ' + btn.innerText;
                }
                return 'No button found';
            """)
            log(f"-> {clicked}", "SUCCESS" if "Clicked" in clicked else "ERROR")
            time.sleep(5)
        else:
            log("Không tìm thấy input code! Kiểm tra lại trang...", "WARN")
            # In ra HTML để debug
            log(f"Page title: {driver.title}", "INFO")
            return None
            
    except Exception as e:
        log(f"Lỗi nhập code: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return None
    
    # 3. Giải captcha KiemMoney
    result = solve_kiemmoney_captcha(driver, google_cookies)
    
    if result:
        log("✅ HOÀN TẤT BYPASS 4MMO!", "SUCCESS")
        return code
    else:
        log("Có lỗi trong quá trình giải captcha", "WARN")
        return code  # Vẫn trả về code dù captcha thất bại

def bypass_linktop_linkngon(driver, google_cookies, bypass_type="linktop"):
    """Bypass LinkTop/LinkNgon: chờ redirect → lấy code từ konmeo → nhập code → captcha → OK"""
    domain_map = {
        "linktop": "linktop.one",
        "linkngon": "linkngon.me"
    }
    domain = domain_map.get(bypass_type, "linktop.one")
    display_name = "LinkTop" if bypass_type == "linktop" else "LinkNgon"
    
    log(f"=== BẮT ĐẦU BYPASS {display_name.upper()} ===", "WARN")
    
    # 1. Chờ chuyển hướng đến trang linktop/linkngon
    log(f"Chờ chuyển hướng đến {domain}...", "INFO")
    try:
        WebDriverWait(driver, 30).until(
            lambda d: domain.split('.')[0] in d.current_url.lower()
        )
        log(f"-> Đã đến trang: {driver.current_url}", "SUCCESS")
    except:
        log(f"Không thể chờ {domain}, URL hiện tại: {driver.current_url}", "WARN")
    
    time.sleep(3)
    current_url = driver.current_url
    log(f"URL hiện tại: {current_url}", "INFO")
    
    # 2. Lấy code từ konmeo
    code = None
    try:
        # Normalize URL trước
        target_url = konmeo.normalize_https_url(current_url)
        if target_url:
            log(f"Target URL (normalized): {target_url}", "INFO")
            code, err = konmeo.get_code_linktopngon(target_url, domain)
            if code:
                log(f"🎉 CODE {display_name}: {code}", "SUCCESS")
            elif err:
                log(f"Konmeo lỗi: {err}", "ERROR")
        else:
            log("Không thể normalize URL!", "ERROR")
    except Exception as e:
        log(f"Lỗi konmeo: {e}", "ERROR")
    
    if not code:
        code = input(f"Không lấy được code {display_name} tự động. Nhập code bằng tay: ").strip()
    
    if not code:
        log("Không có code, hủy...", "ERROR")
        return None
    
    # 3. Nhập code vào form và submit
    log(f"Nhập code vào form {display_name}...", "INFO")
    try:
        # Chờ input xuất hiện
        code_input = None
        input_selectors = [
            '#code',
            'input[name="code"]',
            'input[name="code_"]',
            'input.code-input',
            'input[placeholder*="code"]',
            'input[placeholder*="mã"]',
            'input[placeholder*="Dán"]'
        ]
        
        for selector in input_selectors:
            try:
                code_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if code_input:
                    log(f"-> Tìm thấy input: {selector}", "SUCCESS")
                    break
            except:
                continue
        
        if not code_input:
            # Scroll và tìm lại
            log("Thử scroll và tìm lại...", "INFO")
            driver.execute_script("window.scrollTo(0, 300);")
            time.sleep(2)
            for selector in input_selectors:
                try:
                    code_input = driver.find_element(By.CSS_SELECTOR, selector)
                    if code_input and code_input.is_displayed():
                        log(f"-> Tìm thấy input sau scroll: {selector}", "SUCCESS")
                        break
                except:
                    continue
        
        if code_input:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", code_input)
            time.sleep(1)
            
            code_input.clear()
            # Nhập từng ký tự
            for char in code:
                code_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            log(f"-> Đã nhập code: {code}", "SUCCESS")
            time.sleep(2)
            
            # Click nút submit
            clicked = driver.execute_script("""
                var btn = document.querySelector('#invisibleCaptchaShortlink') ||
                          document.querySelector('.traffic-submit-btn') ||
                          document.querySelector('.btn-captcha') ||
                          document.querySelector('button[type="submit"]') ||
                          document.querySelector('form button');
                if (btn) {
                    btn.scrollIntoView({block: 'center'});
                    btn.click();
                    return 'Clicked: ' + btn.innerText;
                }
                return 'No button found';
            """)
            log(f"-> {clicked}", "SUCCESS" if "Clicked" in clicked else "ERROR")
            time.sleep(5)
        else:
            log("Không tìm thấy input code!", "WARN")
            return None
            
    except Exception as e:
        log(f"Lỗi nhập code: {e}", "ERROR")
        return None
    
    # 4. Giải captcha KiemMoney
    result = solve_kiemmoney_captcha(driver, google_cookies)
    
    if result:
        log(f"✅ HOÀN TẤT BYPASS {display_name.upper()}!", "SUCCESS")
        return code
    else:
        log("Có lỗi trong quá trình giải captcha", "WARN")
        return code

def bypass_nhapma_with_gemini(driver, google_cookies):
    """Bypass Nhapma hoàn chỉnh - hỗ trợ cả type1 (ảnh) và type2 (link + keyword)"""
    log("=== BẮT ĐẦU BYPASS NHAPMA ===", "WARN")
    
    # 1. Detect loại page Nhapma
    page_type = detect_nhapma_page_type(driver)
    log(f"-> Loại page Nhapma: {page_type}", "INFO")
    
    # 2. Xử lý theo loại page
    if page_type == "type2":
        # Type2: Có link + keyword cần tìm
        target_link, target_keyword = extract_nhapma_type2_data(driver)
        
        if not target_link or not target_keyword:
            log("Không trích xuất được link/keyword từ type2!", "ERROR")
            return None
        
        # Xử lý type2: mở link, tìm keyword, click, lấy code
        code = handle_nhapma_type2(driver, google_cookies, target_link, target_keyword)
        
        if not code:
            log("Không lấy được code từ type2", "WARN")
            code = input("Nhập code bằng tay: ").strip()
        
        if not code:
            log("Không có code, hủy...", "ERROR")
            return None
        
        log(f"🎉 CODE NHAPMA (Type2): {code}", "SUCCESS")
        
        # Giải captcha KiemMoney (nếu đã chuyển đến trang captcha)
        current_url = driver.current_url
        if "kiemmoney" in current_url:
            log("Giải captcha KiemMoney...", "INFO")
            result = solve_kiemmoney_captcha(driver, google_cookies)
            if result:
                log("✅ HOÀN TẤT BYPASS NHAPMA TYPE2!", "SUCCESS")
            else:
                log("Có lỗi trong quá trình giải captcha", "WARN")
        
        return code
    
    # Type1 hoặc Unknown: Sử dụng flow cũ (ảnh hướng dẫn + Gemini)
    log("Sử dụng flow Type1 (ảnh + Gemini)...", "INFO")
    
    # Lấy domain từ Gemini
    target_domain = get_nhapma_image_and_domain(driver, google_cookies)
    if not target_domain:
        target_domain = input("Gemini lỗi. Nhập domain đích bằng tay: ").strip()
    
    if not target_domain:
        log("Không có domain, hủy...", "ERROR")
        return None
    
    # 2. Tạo URL và lấy code từ konmeo
    if not target_domain.startswith("http"):
        target_url = "https://" + target_domain
    else:
        target_url = target_domain
    
    log(f"URL target: {target_url}", "INFO")
    
    code = None
    try:
        code = konmeo.get_code_nhapma(target_url)
        if code:
            log(f"🎉 CODE NHAPMA: {code}", "SUCCESS")
    except Exception as e:
        log(f"Lỗi konmeo.get_code_nhapma: {e}", "ERROR")
    
    if not code:
        code = input("Không lấy được code tự động. Nhập code bằng tay: ").strip()
    
    if not code:
        log("Không có code, hủy...", "ERROR")
        return None
    
    # 3. Nhập code vào form Nhapma và submit
    log("Nhập code vào form Nhapma...", "INFO")
    try:
        # Tìm input nhập code
        code_input = None
        input_selectors = [
            'input[name="code"]',
            'input[placeholder*="mã"]',
            'input[placeholder*="code"]',
            '.from-brand-500 input'
        ]
        
        for selector in input_selectors:
            try:
                code_input = driver.find_element(By.CSS_SELECTOR, selector)
                if code_input:
                    break
            except:
                continue
        
        if code_input:
            code_input.clear()
            code_input.send_keys(code)
            log(f"-> Đã nhập code: {code}", "SUCCESS")
            time.sleep(1)
            
            # Click nút "Xác Nhận Và Tiếp Tục"
            driver.execute_script("""
                var btn = document.querySelector('button[type="submit"]') ||
                          document.querySelector('form button');
                if (btn) btn.click();
            """)
            log("-> Đã click Xác Nhận Và Tiếp Tục", "SUCCESS")
            time.sleep(5)
        else:
            log("Không tìm thấy input code!", "WARN")
            
    except Exception as e:
        log(f"Lỗi nhập code: {e}", "ERROR")
    
    # 4. Giải captcha KiemMoney
    result = solve_kiemmoney_captcha(driver, google_cookies)
    
    if result:
        log("✅ HOÀN TẤT BYPASS NHAPMA!", "SUCCESS")
        return code
    else:
        log("Có lỗi trong quá trình giải captcha", "WARN")
        return code  # Vẫn trả về code dù captcha thất bại

def navigate_to_uptolink_task(driver, task_key=None):
    """Điều hướng đến task Uptolink 2"""
    
    try:
        # Bước 1: Click nút "Không hiển thị lại trong 2 giờ" (nếu có popup)
        log("Kiểm tra popup...", "INFO")
        try:
            hide_btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-hide-2h"))
            )
            hide_btn.click()
            log("-> Đã click 'Không hiển thị lại trong 2 giờ'", "SUCCESS")
            time.sleep(1)
        except:
            log("-> Không có popup, tiếp tục...", "INFO")
        
        # Bước 2: Mở sidebar menu (click hamburger trên mobile)
        log("Mở sidebar menu...", "INFO")
        try:
            # Dùng JavaScript để click hamburger menu
            driver.execute_script("""
                var toggle = document.querySelector('#kt_aside_mobile_toggle');
                if (toggle) {
                    toggle.click();
                    return true;
                }
                return false;
            """)
            log("-> Đã click nút hamburger menu", "SUCCESS")
            time.sleep(1)
        except:
            log("-> Không tìm thấy nút hamburger", "INFO")
        
        # Bước 3: Click menu "Vượt link rút gọn" bằng JavaScript
        log("Đang chọn menu 'Vượt link rút gọn'...", "INFO")
        time.sleep(1)  # Chờ sidebar animation
        
        # Dùng JavaScript để tìm và click menu
        result = driver.execute_script("""
            // Tìm menu link bằng nhiều cách
            var menuLink = document.querySelector('a.menu-link[data-link="tasks"]') ||
                           document.querySelector('a[data-link="tasks"]') ||
                           Array.from(document.querySelectorAll('a.menu-link')).find(el => el.innerText.includes('Vượt link'));
            
            if (menuLink) {
                menuLink.click();
                return 'Đã click menu: ' + menuLink.innerText;
            }
            return 'Không tìm thấy menu';
        """)
        log(f"-> {result}", "SUCCESS" if "Đã click" in result else "ERROR")
        
        if "Không tìm thấy" in result:
            raise Exception(result)
        
        time.sleep(2)
        log("-> Đã chọn menu 'Vượt link rút gọn'", "SUCCESS")
        
        # Bước 4: Đóng drawer overlay và sidebar (để không bị che nút)
        log("Đóng sidebar overlay...", "INFO")
        driver.execute_script("""
            // Đóng drawer overlay nếu có
            var overlay = document.querySelector('.drawer-overlay');
            if (overlay) overlay.click();
            
            // Đóng sidebar (click lại hamburger hoặc ẩn đi)
            var toggle = document.querySelector('#kt_aside_mobile_toggle');
            var aside = document.querySelector('#kt_aside');
            if (aside && aside.classList.contains('drawer-on')) {
                if (toggle) toggle.click();
            }
            
            // Ẩn overlay bằng CSS nếu vẫn còn
            var allOverlays = document.querySelectorAll('.drawer-overlay');
            allOverlays.forEach(function(o) { o.style.display = 'none'; });
        """)
        time.sleep(1)
        
        # Bước 5: Xác định task cần click
        if task_key and task_key in TASK_CONFIG:
            cfg = TASK_CONFIG[task_key]
            data_id = cfg["data_id"]
            task_name = cfg["name"]
        else:
            data_id = "77"  # Mặc định Uptolink 2
            task_name = "Uptolink 2"
        
        log(f"Đang tìm task '{task_name}'...", "INFO")
        
        # Kiểm tra xem task có khả dụng không (không bị "Hết lượt")
        is_available = driver.execute_script(f"""
            var taskBtn = document.querySelector('button.taskCallLink[data-id="{data_id}"]');
            if (taskBtn) {{
                // Kiểm tra nếu button bị disabled hoặc có text "Hết lượt"
                if (taskBtn.disabled || taskBtn.innerText.includes('Hết lượt')) {{
                    return 'HET_LUOT';
                }}
                return 'AVAILABLE';
            }}
            return 'NOT_FOUND';
        """)
        
        if is_available == "HET_LUOT":
            log(f"⚠ Task '{task_name}' đã HẾT LƯỢT! Bỏ qua...", "WARN")
            return False, "HET_LUOT"
        
        if is_available == "NOT_FOUND":
            log(f"Không tìm thấy task '{task_name}'", "ERROR")
            return False, None
        
        # Dùng JavaScript để click để tránh bị overlay che
        result = driver.execute_script(f"""
            var taskBtn = document.querySelector('button.taskCallLink[data-id="{data_id}"]');
            if (taskBtn) {{
                taskBtn.click();
                return 'Đã click task: ' + taskBtn.getAttribute('data-id');
            }}
            return 'Không tìm thấy task';
        """)
        log(f"-> {result}", "SUCCESS" if "Đã click" in result else "ERROR")
        
        if "Không tìm thấy" in result:
            raise Exception(result)
        
        time.sleep(3)
        
        return True, task_key if task_key else "uptolink2"
    except Exception as e:
        log(f"Lỗi điều hướng: {e}", "ERROR")
        # Thử cách khác - dùng JavaScript trực tiếp
        try:
            driver.execute_script(f"""
                var btn = document.querySelector('button.taskCallLink[data-id="{data_id}"]');
                if (btn) btn.click();
            """)
            time.sleep(3)
            return True, task_key if task_key else "uptolink2"
        except:
            pass
        return False

def get_target_from_gemini(driver, google_cookies):
    log("Đang tìm ảnh hướng dẫn...", "INFO")
    img_path = "instruction.png"
    try:
        try:
            img_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.separator img, .entry-content img"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img_element)
            time.sleep(2)
            img_element.screenshot(img_path)
            log("-> Đã chụp ảnh hướng dẫn", "SUCCESS")
        except:
            driver.save_screenshot(img_path)

        if not google_cookies: return None
        ua = driver.execute_script("return navigator.userAgent;")
        gemini = GeminiWebClient(google_cookies, user_agent=ua)
        
        # Prompt đơn giản hơn
        prompt = """
        Look at this image. Find the target website domain shown.
        Ignore google.com, totreview.com, uptolink.one.
        OUTPUT ONLY THE DOMAIN NAME (example: website.com)
        """
        
        # Thử model Pro trước, nếu lỗi sẽ tự fallback sang Auto
        result = gemini.send_prompt(prompt, img_path, model='pro')
        
        log(f"-> Gemini raw response: {result[:100] if result else 'None'}...", "INFO")
        
        if result:
            # Tìm tất cả domain trong response (dù response dài)
            candidates = re.findall(r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}', result)
            blacklist = ['google.com', 'totreview.com', 'uptolink.one', 'gemini.google.com']
            
            log(f"-> Các domain tìm thấy: {candidates}", "INFO")
            
            final_domain = None
            for cand in candidates:
                cand_lower = cand.lower()
                # Bỏ qua blacklist
                if any(bl in cand_lower for bl in blacklist): 
                    continue
                # Bỏ qua các domain quá ngắn (ít hơn 4 ký tự)
                if len(cand) < 4:
                    continue
                # Chọn domain dài nhất (thường là domain đầy đủ)
                if final_domain is None or len(cand) > len(final_domain):
                    final_domain = cand
            
            if final_domain:
                final_domain = final_domain.rstrip('.')
                log(f"-> CHỐT DOMAIN: {final_domain}", "SUCCESS")
                return final_domain
            
            # Nếu không tìm thấy domain hợp lệ, thử lấy dòng cuối
            lines = result.strip().split('\n')
            for line in reversed(lines):
                clean_line = line.strip().lower()
                if clean_line and 'google' not in clean_line and '.' in clean_line:
                    # Kiểm tra có phải domain không
                    if re.match(r'^[a-z0-9][a-z0-9\.-]+\.[a-z]{2,}$', clean_line):
                        log(f"-> CHỐT DOMAIN (từ dòng cuối): {clean_line}", "SUCCESS")
                        return clean_line
                        
        return None
    except Exception as e:
        log(f"Lỗi Vision: {e}", "ERROR")
        return None

def setup_profile():
    user_data_dir = os.path.join(os.getcwd(), "konmeo_data")
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    driver = uc.Chrome(options=options, version_main=144)
    driver.get("https://gemini.google.com")
    print("\n[SETUP] Đăng nhập xong nhấn Enter...")
    input()
    driver.quit()

# --- HÀM API - LOGIC MỚI ---
def run_api_background(token, ua, cookies, referer, task_url, driver):
    log("🚀 Bắt đầu quy trình xử lý API Uptolink...", "WARN")
    
    s = requests.Session()
    for c in cookies:
        s.cookies.set(c['name'], c['value'], domain=c['domain'])
    
    headers = {
        "User-Agent": ua,
        "Referer": referer,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://uptolink.one",
        "content-value-random": token
    }
    
    payload = {
        "screen": "1920x1080",
        "browser[name]": "Chrome",
        "cookies": "true"
    }

    try:
        step = 1
        max_steps = 10  # Giới hạn số bước để tránh loop vô hạn
        
        while step <= max_steps:
            log(f"===== BƯỚC {step} =====", "WARN")
            
            # 1. Gọi Check Job
            log("-> Gọi /check/job...", "INFO")
            r_job = s.post("https://uptolink.one/check/job", data=payload, headers=headers)
            try:
                job_data = r_job.json()
                log(f"-> Job response: {job_data}", "INFO")
                wait_time = int(job_data.get("wait", 0))
            except Exception as e:
                log(f"-> Lỗi parse job: {e}", "ERROR")
                wait_time = 15  # Mặc định 15 giây nếu lỗi
            
            # 2. Gọi Countdown
            log("-> Gọi /check/countdown...", "INFO")
            s.post("https://uptolink.one/check/countdown", data=payload, headers=headers)
            
            # 3. Đếm ngược
            if wait_time > 0:
                log(f"-> Đếm ngược {wait_time} giây...", "WARN")
                for i in range(wait_time, 0, -1):
                    if i % 5 == 0 or i <= 5:
                        print(f"⏳ {i}s", end=" ", flush=True)
                    time.sleep(1)
                print()  # Xuống dòng
                
                # Thêm 2 giây buffer
                time.sleep(2)
            
            # 4. Gọi Continue
            log("-> Gọi /check/continue...", "INFO")
            r_continue = s.post("https://uptolink.one/check/continue", data=payload, headers=headers)
            
            try:
                res = r_continue.json()
                log(f"-> Continue response: {res}", "INFO")
                
                # Kiểm tra có URL không
                if res.get("url"):
                    final_link = res.get("url")
                    log(f"🎉 THÀNH CÔNG! Link: {final_link}", "SUCCESS")
                    
                    # Mở link trong tab mới
                    driver.execute_script(f"window.open('{final_link}', '_blank');")
                    log("-> Đã mở link trong tab mới!", "SUCCESS")
                    break
                
                # Kiểm tra có Code không
                elif res.get("code"):
                    code = res.get("code")
                    log(f"🎉 THÀNH CÔNG! Code: {code}", "SUCCESS")
                    driver.execute_script(f"alert('CODE: {code}');")
                    break
                
                # Kiểm tra status finish
                elif res.get("status") == "finish":
                    if res.get("url"):
                        final_link = res.get("url")
                        log(f"🎉 THÀNH CÔNG! Link: {final_link}", "SUCCESS")
                        driver.execute_script(f"window.open('{final_link}', '_blank');")
                        break
                    else:
                        log("-> Status finish nhưng không có URL, reload trang...", "WARN")
                        driver.refresh()
                        break
                
                # Còn bước tiếp theo
                elif res.get("status") == "success":
                    log(f"-> Bước {step} xong, tiếp tục bước tiếp...", "INFO")
                    step += 1
                    continue
                
                else:
                    log(f"-> Response không xác định: {res}", "WARN")
                    step += 1
                    continue
                    
            except json.JSONDecodeError:
                log(f"-> Lỗi JSON: {r_continue.text[:200]}", "ERROR")
                break
        
        if step > max_steps:
            log("⚠ Đã vượt quá số bước tối đa!", "ERROR")

    except Exception as e:
        log(f"Lỗi API Loop: {e}", "ERROR")
        import traceback
        traceback.print_exc()

    log("Đã kết thúc xử lý.", "INFO")
    input("Nhấn Enter để tiếp tục...")

def run_auto(use_kiemmoney=False):
    user_data_dir = os.path.join(os.getcwd(), "konmeo_data")
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-popup-blocking")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    
    driver = uc.Chrome(options=options, version_main=144)
    google_cookies = None
    
    # Lấy thông tin đăng nhập nếu cần
    account, password = None, None
    if use_kiemmoney:
        account, password = get_credentials()
    
    try:
        # 1. Lấy Cookie Gemini (mở tab riêng)
        log("Mở Gemini lấy cookie...", "INFO")
        driver.get("https://gemini.google.com")
        time.sleep(5)
        google_cookies = driver.get_cookies()
        if not any(c['name']=='__Secure-1PSID' for c in google_cookies):
            log("Chưa đăng nhập Gemini! Vui lòng chạy Setup Profile trước.", "ERROR")
            input("Nhấn Enter để thoát...")
            driver.quit()
            return
        log("-> Đã lấy cookie Gemini", "SUCCESS")

        # 2. Đăng nhập KiemMoney (nếu chọn)
        if use_kiemmoney:
            log("Bắt đầu đăng nhập KiemMoney...", "INFO")
            login_result = login_kiemmoney(driver, account, password, google_cookies)
            
            if not login_result:
                log("Đăng nhập KiemMoney thất bại!", "ERROR")
                input("Nhấn Enter để thoát...")
                driver.quit()
                return
            
            # Chờ trang load xong sau khi đăng nhập
            log("Đăng nhập thành công! Chờ trang dashboard load...", "SUCCESS")
            time.sleep(5)
            
            # Hiển thị menu chọn task
            selected_task = show_task_menu()
            if not selected_task:
                log("Không chọn task, thoát...", "INFO")
                driver.quit()
                return
            
            # Điều hướng đến task được chọn
            log(f"Bắt đầu điều hướng đến task: {TASK_CONFIG[selected_task]['name']}...", "INFO")
            nav_result = navigate_to_uptolink_task(driver, selected_task)
            
            if not nav_result:
                log("Không tìm thấy task!", "ERROR")
                log("URL hiện tại: " + driver.current_url, "INFO")
                input("Nhấn Enter để thoát...")
                driver.quit()
                return
            
            nav_success, selected_task = nav_result if isinstance(nav_result, tuple) else (nav_result, "uptolink2")
            
            # Chờ redirect  
            log("Đợi chuyển hướng...", "INFO")
            time.sleep(5)
            
            # Kiểm tra và chuyển sang tab mới nếu có
            log(f"Số tab hiện tại: {len(driver.window_handles)}", "INFO")
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                log(f"Đã chuyển sang tab mới: {driver.current_url}", "INFO")
        else:
            # Nhập link thủ công
            task_url = input("Link Task: ").strip()
            if not task_url.startswith("http"):
                task_url = "https://" + task_url
            log(f"Vào Link: {task_url}", "INFO")
            driver.get(task_url)
        
        time.sleep(5)
        log(f"URL hiện tại: {driver.current_url}", "INFO")
        
        # ========== THỬ AUTO-BYPASS TRƯỚC ==========
        bypass_type = TASK_CONFIG.get(selected_task, {}).get("bypass_func", "uptolink") if use_kiemmoney else None
        
        # Xử lý riêng cho Nhapma (cần Gemini)
        if bypass_type == "nhapma":
            log("Sử dụng flow Nhapma với Gemini...", "WARN")
            code = bypass_nhapma_with_gemini(driver, google_cookies)
            if code:
                log(f"🎉 THÀNH CÔNG! CODE: {code}", "SUCCESS")
                try:
                    import pyperclip
                    pyperclip.copy(code)
                    log("-> Đã copy code vào clipboard!", "SUCCESS")
                except:
                    pass
                input("\nNhấn Enter để tiếp tục hoặc chạy task khác...")
                driver.quit()
                return
            else:
                log("Bypass Nhapma thất bại!", "ERROR")
                input("\nNhấn Enter để thoát...")
                driver.quit()
                return
        
        # Xử lý riêng cho 4mmo
        elif bypass_type == "4mmo":
            log("Sử dụng flow 4mmo...", "WARN")
            code = bypass_4mmo_with_gemini(driver, google_cookies)
            if code:
                log(f"🎉 THÀNH CÔNG! CODE: {code}", "SUCCESS")
                try:
                    import pyperclip
                    pyperclip.copy(code)
                    log("-> Đã copy code vào clipboard!", "SUCCESS")
                except:
                    pass
                input("\nNhấn Enter để tiếp tục hoặc chạy task khác...")
                driver.quit()
                return
            else:
                log("Bypass 4mmo thất bại!", "ERROR")
                input("\nNhấn Enter để thoát...")
                driver.quit()
                return
        
        # Xử lý riêng cho LinkTop / LinkNgon
        elif bypass_type in ("linktop", "linkngon"):
            display_name = "LinkTop" if bypass_type == "linktop" else "LinkNgon"
            log(f"Sử dụng flow {display_name}...", "WARN")
            code = bypass_linktop_linkngon(driver, google_cookies, bypass_type)
            if code:
                log(f"🎉 THÀNH CÔNG! CODE: {code}", "SUCCESS")
                try:
                    import pyperclip
                    pyperclip.copy(code)
                    log("-> Đã copy code vào clipboard!", "SUCCESS")
                except:
                    pass
                input("\nNhấn Enter để tiếp tục hoặc chạy task khác...")
                driver.quit()
                return
            else:
                log(f"Bypass {display_name} thất bại!", "ERROR")
                input("\nNhấn Enter để thoát...")
                driver.quit()
                return
        
        # Các bypass khác (không cần Gemini)
        elif bypass_type and bypass_type != "uptolink":
            log(f"Thử auto-bypass bằng: {bypass_type}", "WARN")
            try:
                current_url = driver.current_url
                code = bypass_task_auto(current_url, bypass_type)
                
                if code:
                    log(f"🎉 THÀNH CÔNG! CODE: {code}", "SUCCESS")
                    
                    # Copy code vào clipboard (nếu có thể)
                    try:
                        import pyperclip
                        pyperclip.copy(code)
                        log("-> Đã copy code vào clipboard!", "SUCCESS")
                    except:
                        pass
                    
                    input("\nNhấn Enter để tiếp tục hoặc chạy task khác...")
                    driver.quit()
                    return
                else:
                    log("Auto-bypass không thành công, thử phương pháp Gemini...", "WARN")
            except Exception as e:
                log(f"Lỗi auto-bypass: {e}, thử phương pháp Gemini...", "WARN")
        
        # ========== FLOW GEMINI (cho Uptolink và fallback) ==========
        # Click verify/continue nếu có
        try:
            driver.execute_script("document.querySelectorAll('button, a.btn').forEach(b=>{if(b.innerText.match(/verify|continue|click/i)) b.click()})")
        except:
            pass
        
        # Chờ chuyển sang totreview
        log("Chờ chuyển hướng đến totreview...", "INFO")
        WebDriverWait(driver, 120).until(EC.url_contains("totreview"))
        
        # 3. Soi ảnh
        target_domain = get_target_from_gemini(driver, google_cookies)
        if not target_domain: 
            target_domain = input("Gemini lỗi. Nhập Link Đích bằng tay: ").strip()

        # 4. Search & Access
        log(f"Google Search: {target_domain}", "INFO")
        driver.execute_script("window.open('https://google.com','_blank')")
        driver.switch_to.window(driver.window_handles[-1])
        
        driver.get("https://www.google.com")
        try:
            search_box = driver.find_element(By.NAME, "q")
            search_box.send_keys(target_domain)
            search_box.send_keys(Keys.ENTER)
        except:
            pass
        time.sleep(3)
        
        log("Đang tìm link...", "WARN")
        found = driver.execute_script(f"""
            var links = document.querySelectorAll('#search a');
            for(var i=0; i<links.length; i++) {{
                if(links[i].href.includes('{target_domain}')) {{
                    links[i].click();
                    return true;
                }}
            }}
            return false;
        """)
        
        if not found:
            log("-> Không tìm thấy. Vào thẳng...", "WARN")
            if not target_domain.startswith("http"):
                target_url = "https://" + target_domain
            else:
                target_url = target_domain
            driver.get(target_url)
        else:
            log("-> Đã click link.", "SUCCESS")

        # 5. Token
        log("Đang chờ Token...", "INFO")
        token = None
        for i in range(40):
            driver.execute_script(f"window.scrollTo(0, {random.randint(100, 800)});")
            try:
                raw = driver.execute_script("return (typeof rd !== 'undefined') ? rd : null;")
                if raw and len(raw) > 20:
                    token = raw
                    break
            except:
                pass
            time.sleep(1)
            
        if token:
            log(f"Token OK: {token[:15]}...", "SUCCESS")
            # Gọi API Multi-Step Mới
            task_url = driver.current_url
            run_api_background(token, driver.execute_script("return navigator.userAgent;"), driver.get_cookies(), driver.current_url, task_url, driver)
        else:
            log("Không thấy Token.", "ERROR")

    except Exception as e:
        log(f"Lỗi: {e}", "ERROR")

def shortlink_menu():
    """Menu get code từ shortlink"""
    while True:
        clear_screen()
        print("=" * 50)
        print("      GET CODE TỪ SHORTLINK")
        print("=" * 50)
        print("\n📋 CHỌN NỀN TẢNG:")
        print("  1. BBMKTS.COM")
        print("  2. YEULINK.COM")
        print("  3. XLINK.CO")
        print("  4. 4MMO.NET")
        print("  5. LINKTOT.NET (Backlink)")
        print("  6. LINKTOT.NET (Normal)")
        print("  7. LINKTOP.ONE")
        print("  8. LINKNGON.IO")
        print("  9. LINKNGON.ME")
        print("  10. KIEMTIENNGAY.COM")
        print("  11. NHAPMA.COM")
        print("  0. Quay lại")
        print()
        
        c = input("Chọn (0-11): ").strip()
        
        try:
            if c == "0":
                break
            elif c == "1":
                link = input("Nhập link lấy code: ").strip()
                print("\nCODE:", konmeo.get_code_bbmkts(link))
            elif c == "2":
                link = input("Nhập link lấy code: ").strip()
                cfg = konmeo.YEULINK_LIKE["yeulink"]
                short = konmeo.get_yeulink_like_short_code(link, cfg["domain"])
                code = konmeo.get_yeulink_like_code(cfg["base"], short)
                print("\nCODE:", code)
            elif c == "3":
                link = input("Nhập link lấy code: ").strip()
                cfg = konmeo.YEULINK_LIKE["xlink"]
                short = konmeo.get_yeulink_like_short_code(link, cfg["domain"])
                code = konmeo.get_yeulink_like_code(cfg["base"], short)
                print("\nCODE:", code)
            elif c == "4":
                print("\nCODE:", konmeo.get_code_4mmo())
            elif c == "5":
                link = input("Nhập link lấy code: ").strip()
                print("\nCODE:", konmeo.get_code_linktot_backlink(link))
            elif c == "6":
                link = input("Nhập link lấy code: ").strip()
                print("\nCODE:", konmeo.get_code_linktot_normal(link))
            elif c == "7":
                link = input("Nhập link lấy code: ").strip()
                link = konmeo.normalize_https_url(link)
                if not link:
                    print("Link không hợp lệ")
                else:
                    code, err = konmeo.get_code_linktopngon(link, "linktop.one")
                    print("\nCODE:", code if code else err)
            elif c == "8":
                link = input("Nhập link lấy code: ").strip()
                link = konmeo.normalize_https_url(link)
                if not link:
                    print("Link không hợp lệ")
                else:
                    code, err = konmeo.get_code_linktopngon(link, "linkngon.io")
                    print("\nCODE:", code if code else err)
            elif c == "9":
                link = input("Nhập link lấy code: ").strip()
                link = konmeo.normalize_https_url(link)
                if not link:
                    print("Link không hợp lệ")
                else:
                    code, err = konmeo.get_code_linktopngon(link, "linkngon.me")
                    print("\nCODE:", code if code else err)
            elif c == "10":
                link = input("Nhập link lấy code: ").strip()
                print("\nCODE:", konmeo.get_code_kiemtienngay(link))
            elif c == "11":
                link = input("Nhập link lấy code: ").strip()
                print("\nCODE:", konmeo.get_code_nhapma(link))
        except Exception as e:
            print(f"\nLỖI: {e}")
        
        input("\nNhấn Enter để tiếp tục...")

def is_golden_hour():
    """Kiểm tra có đang trong khung giờ vàng không (4:00 - 7:30 sáng)"""
    now = time.localtime()
    hour = now.tm_hour
    minute = now.tm_min
    
    # 4:00 - 7:30 sáng
    if hour >= 4 and (hour < 7 or (hour == 7 and minute <= 30)):
        return True
    return False

def get_time_until_golden_hour():
    """Tính thời gian còn lại đến khung giờ vàng (giây)"""
    now = time.localtime()
    hour = now.tm_hour
    minute = now.tm_min
    second = now.tm_sec
    
    current_seconds = hour * 3600 + minute * 60 + second
    start_seconds = 4 * 3600  # 4:00 AM
    
    if hour >= 4 and (hour < 7 or (hour == 7 and minute <= 30)):
        return 0  # Đang trong giờ vàng
    elif hour >= 7 and minute > 30:
        # Đã qua giờ vàng, chờ đến ngày mai
        return (24 * 3600 - current_seconds) + start_seconds
    else:
        # Chưa đến giờ vàng
        return start_seconds - current_seconds

def golden_hour_scheduler():
    """Chế độ treo, tự động chạy trong khung giờ vàng 4:00 - 7:30"""
    clear_screen()
    print("=" * 50)
    print("    🌟 CHẾ ĐỘ KHUNG GIỜ VÀNG (4:00 - 7:30)")
    print("=" * 50)
    
    # Chọn các task muốn chạy
    print("\n📋 CHỌN CÁC TASK SẼ TỰ ĐỘNG CHẠY:")
    tasks = list(TASK_CONFIG.keys())
    selected_tasks = []
    
    for i, key in enumerate(tasks, 1):
        cfg = TASK_CONFIG[key]
        print(f"  {i}. {cfg['name']} ({cfg['reward']} ⭐)")
    
    print("\nNhập số các task muốn chạy, cách nhau bằng dấu phẩy")
    print("Ví dụ: 1,2,5 (hoặc 'all' để chọn tất cả)")
    
    choice = input("\nChọn: ").strip().lower()
    
    if choice == "all":
        selected_tasks = tasks
    else:
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected_tasks = [tasks[i] for i in indices if 0 <= i < len(tasks)]
        except:
            print("Lỗi nhập, mặc định chọn tất cả!")
            selected_tasks = tasks
    
    if not selected_tasks:
        print("Không có task nào được chọn!")
        input("\nNhấn Enter để quay lại...")
        return
    
    print(f"\n✅ Đã chọn: {', '.join([TASK_CONFIG[t]['name'] for t in selected_tasks])}")
    
    # Số lượt chạy mỗi task
    loop_count = input("\nSố lượt chạy mỗi task (mặc định 1): ").strip()
    try:
        loop_count = int(loop_count) if loop_count else 1
    except:
        loop_count = 1
    
    print(f"\n🔄 Mỗi task sẽ chạy {loop_count} lượt")
    print("\n" + "=" * 50)
    print("⏰ BẮT ĐẦU CHẾ ĐỘ TREO...")
    print("Nhấn Ctrl+C để dừng")
    print("=" * 50)
    
    # Lấy credentials trước
    account, password = get_credentials()
    
    try:
        while True:
            if is_golden_hour():
                log("🌟 KHUNG GIỜ VÀNG - BẮT ĐẦU CHẠY!", "SUCCESS")
                
                # Khởi tạo driver
                user_data_dir = os.path.join(os.getcwd(), "konmeo_data")
                options = uc.ChromeOptions()
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-popup-blocking")
                options.add_argument(f"--user-data-dir={user_data_dir}")
                
                driver = uc.Chrome(options=options, version_main=144)
                
                try:
                    # Lấy cookie Gemini
                    log("Mở Gemini lấy cookie...", "INFO")
                    driver.get("https://gemini.google.com")
                    time.sleep(5)
                    google_cookies = driver.get_cookies()
                    
                    if not any(c['name']=='__Secure-1PSID' for c in google_cookies):
                        log("Chưa đăng nhập Gemini!", "ERROR")
                        driver.quit()
                        time.sleep(60)
                        continue
                    
                    # Đăng nhập KiemMoney
                    log("Đăng nhập KiemMoney...", "INFO")
                    login_result = login_kiemmoney(driver, account, password, google_cookies)
                    
                    if not login_result:
                        log("Đăng nhập thất bại!", "ERROR")
                        driver.quit()
                        time.sleep(60)
                        continue
                    
                    time.sleep(5)
                    
                    # Chạy từng task
                    for task_key in selected_tasks:
                        if not is_golden_hour():
                            log("Đã hết khung giờ vàng!", "WARN")
                            break
                        
                        cfg = TASK_CONFIG[task_key]
                        log(f"=== CHẠY TASK: {cfg['name']} ===", "WARN")
                        
                        for lap in range(loop_count):
                            if not is_golden_hour():
                                break
                            
                            log(f"Lượt {lap + 1}/{loop_count}", "INFO")
                            
                            try:
                                # Navigate đến task
                                nav_result = navigate_to_uptolink_task(driver, task_key)
                                
                                # Kiểm tra nếu hết lượt
                                if isinstance(nav_result, tuple):
                                    nav_success, nav_status = nav_result
                                    if nav_status == "HET_LUOT":
                                        log(f"⏭ Bỏ qua {cfg['name']} - đã hết lượt!", "WARN")
                                        break  # Break khỏi vòng lặp lượt, chuyển sang task tiếp
                                else:
                                    nav_success = nav_result
                                
                                if not nav_success:
                                    log(f"Không thể navigate đến {cfg['name']}", "ERROR")
                                    continue
                                
                                time.sleep(5)
                                
                                # Chuyển tab nếu cần
                                if len(driver.window_handles) > 1:
                                    driver.switch_to.window(driver.window_handles[-1])
                                
                                bypass_type = cfg.get("bypass_func", "uptolink")
                                
                                # Xử lý theo loại bypass
                                if bypass_type == "nhapma":
                                    code = bypass_nhapma_with_gemini(driver, google_cookies)
                                elif bypass_type == "4mmo":
                                    code = bypass_4mmo_with_gemini(driver, google_cookies)
                                elif bypass_type in ("linktop", "linkngon"):
                                    code = bypass_linktop_linkngon(driver, google_cookies, bypass_type)
                                elif bypass_type != "uptolink":
                                    code = bypass_task_auto(driver.current_url, bypass_type)
                                else:
                                    # Uptolink flow - skip cho giờ vàng vì phức tạp
                                    log("Skip Uptolink trong chế độ tự động", "WARN")
                                    code = None
                                
                                if code:
                                    log(f"🎉 CODE: {code}", "SUCCESS")
                                
                                # Đóng tab thừa
                                while len(driver.window_handles) > 1:
                                    driver.switch_to.window(driver.window_handles[-1])
                                    driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                                
                                # Chờ giữa các lượt
                                time.sleep(10)
                                
                            except Exception as e:
                                log(f"Lỗi task {cfg['name']}: {e}", "ERROR")
                                continue
                    
                except Exception as e:
                    log(f"Lỗi trong phiên: {e}", "ERROR")
                finally:
                    try:
                        driver.quit()
                    except:
                        pass
                
                # Nếu vẫn còn trong giờ vàng, chờ 5 phút rồi chạy lại
                if is_golden_hour():
                    log("Chờ 5 phút trước khi chạy lại...", "INFO")
                    time.sleep(300)
                    
            else:
                # Chờ đến giờ vàng
                wait_seconds = get_time_until_golden_hour()
                wait_hours = wait_seconds // 3600
                wait_minutes = (wait_seconds % 3600) // 60
                
                now = time.strftime("%H:%M:%S")
                log(f"[{now}] Chờ đến khung giờ vàng: {wait_hours}h {wait_minutes}m", "INFO")
                
                # Sleep 1 phút rồi check lại
                time.sleep(60)
                
    except KeyboardInterrupt:
        log("\n⏹ Đã dừng chế độ treo!", "WARN")
        input("\nNhấn Enter để quay lại menu...")

def show_menu():
    """Hiển thị menu chính"""
    clear_screen()
    print("=" * 50)
    print("      KONMEO v13.0 - Auto Bypass Uptolink")
    print("=" * 50)
    print("\n📋 MENU:")
    print("  1. Chạy qua KiemMoney (Tự động đăng nhập)")
    print("  2. Chạy bằng Link thủ công")
    print("  3. Setup Profile (Đăng nhập Gemini)")
    print("  4. Cấu hình tài khoản KiemMoney")
    print("  5. Get Code từ Shortlink (11 nền tảng)")
    print("  6. 🌟 Chế độ Khung Giờ Vàng (4:00-7:30)")
    print("  0. Thoát")
    print()
    return input("Chọn: ").strip()

if __name__ == "__main__":
    while True:
        choice = show_menu()
        
        if choice == "1":
            run_auto(use_kiemmoney=True)
        elif choice == "2":
            run_auto(use_kiemmoney=False)
        elif choice == "3":
            setup_profile()
        elif choice == "4":
            # Xóa config cũ và nhập lại
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            get_credentials()
            input("\nNhấn Enter để quay lại menu...")
        elif choice == "5":
            shortlink_menu()
        elif choice == "6":
            golden_hour_scheduler()
        elif choice == "0":
            print("Tạm biệt!")
            break
        else:
            print("Lựa chọn không hợp lệ!")
            time.sleep(1)