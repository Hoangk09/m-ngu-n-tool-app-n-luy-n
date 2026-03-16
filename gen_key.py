import requests
import json

SERVER_URL = " http://127.0.0.1:8000"

def generate_key():
    print("=== Tool Tạo Key Bản Quyền ===")
    hwid = input("Nhập HWID của khách: ").strip()
    if not hwid:
        print("❌ HWID không được để trống!")
        return

    try:
        response = requests.post(
            f"{SERVER_URL}/gen_key",
            json={"hwid": hwid, "admin_secret": "admin123"},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ TẠO KEY THÀNH CÔNG!")
            print(f"HWID: {data['hwid']}")
            print(f"KEY : {data['key']}")
            print("-" * 30)
        else:
            print(f"\n❌ Lỗi: {response.text}")
            
    except Exception as e:
        print(f"\n❌ Lỗi kết nối: {e}")
        print("Hãy chắc chắn rằng server.py đang chạy!")

if __name__ == "__main__":
    generate_key()
    input("\nNhấn Enter để thoát...")
