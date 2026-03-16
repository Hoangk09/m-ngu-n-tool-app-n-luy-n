import os
from payos import PayOS
from fastapi import HTTPException

# Need actual keys
CLIENT_ID = "YOUR_CLIENT_ID"
API_KEY = "YOUR_API_KEY"
CHECKSUM_KEY = "YOUR_CHECKSUM_KEY"

payos = PayOS(CLIENT_ID, API_KEY, CHECKSUM_KEY)

class PayOSService:
    @staticmethod
    def create_payment_link(order_code: int, amount: int, description: str, return_url: str, cancel_url: str):
        payment_data = {
            "orderCode": order_code,
            "amount": amount,
            "description": description,
            "items": [
                {"name": description, "quantity": 1, "price": amount}
            ],
            "returnUrl": return_url,
            "cancelUrl": cancel_url
        }
        
        try:
            payment_link = payos.createPaymentLink(payment_data)
            return payment_link
        except Exception as e:
            print(f"PayOS Error: {e}")
            return None

    @staticmethod
    def get_payment_info(order_code: int):
        try:
            return payos.getPaymentLinkInformation(order_code)
        except Exception as e:
            return None
