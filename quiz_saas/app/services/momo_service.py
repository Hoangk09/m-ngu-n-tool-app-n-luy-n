import json
import uuid
import hmac
import hashlib
import requests
import os
import time

class MomoService:
    @staticmethod
    def create_payment_link(order_code: str, amount: int, order_info: str, return_url: str, notify_url: str):
        # Config
        endpoint = os.environ.get("MOMO_ENDPOINT", "https://payment.momo.vn/v2/gateway/api/create")
        partner_code = os.environ.get("MOMO_PARTNER_CODE", "YOUR_PARTNER_CODE")
        access_key = os.environ.get("MOMO_ACCESS_KEY", "YOUR_ACCESS_KEY")
        secret_key = os.environ.get("MOMO_SECRET_KEY", "YOUR_SECRET_KEY")
        
        request_id = str(uuid.uuid4())
        order_id = str(order_code)
        request_type = "captureWallet"
        extra_data = ""  # Base64 encode if needed
        
        # Signature format: accessKey=$accessKey&amount=$amount&extraData=$extraData&ipnUrl=$ipnUrl&orderId=$orderId&orderInfo=$orderInfo&partnerCode=$partnerCode&redirectUrl=$redirectUrl&requestId=$requestId&requestType=$requestType
        raw_signature = f"accessKey={access_key}&amount={amount}&extraData={extra_data}&ipnUrl={notify_url}&orderId={order_id}&orderInfo={order_info}&partnerCode={partner_code}&redirectUrl={return_url}&requestId={request_id}&requestType={request_type}"
        
        signature = hmac.new(
            secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        payload = {
            "partnerCode": partner_code,
            "partnerName": "Quiz Solver Tool",
            "storeId": "MomoTestStore",
            "requestId": request_id,
            "amount": amount,
            "orderId": order_id,
            "orderInfo": order_info,
            "redirectUrl": return_url,
            "ipnUrl": notify_url,
            "lang": "vi",
            "extraData": extra_data,
            "requestType": request_type,
            "signature": signature
        }
        
        try:
            response = requests.post(endpoint, json=payload)
            data = response.json()
            
            if data.get("resultCode") == 0:
                return data.get("payUrl")
            else:
                print(f"MoMo Error: {data.get('message')} (Code: {data.get('resultCode')})")
                return None
        except Exception as e:
            print(f"MoMo Exception: {e}")
            return None
