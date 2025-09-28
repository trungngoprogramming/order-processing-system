import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional

def verify_stripe_webhook_signature(
    payload: str,
    signature_header: str,
    webhook_secret: str,
    tolerance: int = 300
) -> bool:
    """
    Xác thực chữ ký Stripe webhook
    
    Args:
        payload: Raw request body từ Stripe
        signature_header: Giá trị của header 'Stripe-Signature'
        webhook_secret: Webhook endpoint secret từ Stripe
        tolerance: Thời gian tolerance (giây) cho timestamp
        
    Returns:
        True nếu signature hợp lệ
        
    Raises:
        ValueError: Nếu signature header không đúng format
    """
    try:
        # Parse signature header
        # Format: t=1492774577,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd
        elements = signature_header.split(',')
        
        timestamp = None
        signatures = []
        
        for element in elements:
            key, value = element.split('=', 1)
            if key == 't':
                timestamp = int(value)
            elif key.startswith('v'):
                signatures.append(value)
        
        if timestamp is None:
            raise ValueError("No timestamp found in signature header")
        
        if not signatures:
            raise ValueError("No signatures found in signature header")
        
        # Kiểm tra timestamp tolerance
        current_time = int(time.time())
        if abs(current_time - timestamp) > tolerance:
            print(f"Timestamp outside tolerance. Current: {current_time}, Webhook: {timestamp}")
            return False
        
        # Tạo signed payload
        signed_payload = f"{timestamp}.{payload}"
        
        # Tính expected signature
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # So sánh với các signatures trong header
        for signature in signatures:
            if hmac.compare_digest(expected_signature, signature):
                return True
        
        print("No matching signature found")
        return False
        
    except Exception as e:
        print(f"Error verifying Stripe signature: {str(e)}")
        return False

def parse_stripe_event(payload: str) -> Optional[Dict[str, Any]]:
    """
    Parse Stripe event từ JSON payload
    
    Args:
        payload: JSON string từ Stripe webhook
        
    Returns:
        Dict chứa event data hoặc None nếu invalid
    """
    try:
        event = json.loads(payload)
        
        # Validate basic structure
        required_fields = ['id', 'type', 'data', 'created']
        for field in required_fields:
            if field not in event:
                print(f"Missing required field: {field}")
                return None
        
        return event
        
    except json.JSONDecodeError as e:
        print(f"Invalid JSON payload: {str(e)}")
        return None

def extract_order_info_from_checkout_session(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trích xuất thông tin đơn hàng từ Stripe Checkout Session
    
    Args:
        session_data: Data object từ checkout.session.completed event
        
    Returns:
        Dict chứa thông tin đơn hàng đã được chuẩn hóa
    """
    session = session_data.get('object', {})
    
    return {
        'session_id': session.get('id'),
        'payment_intent_id': session.get('payment_intent'),
        'customer_id': session.get('customer'),
        'customer_email': session.get('customer_details', {}).get('email'),
        'customer_name': session.get('customer_details', {}).get('name'),
        'amount_total': session.get('amount_total', 0),
        'amount_subtotal': session.get('amount_subtotal', 0),
        'currency': session.get('currency', 'usd'),
        'payment_status': session.get('payment_status'),
        'mode': session.get('mode'),
        'metadata': session.get('metadata', {}),
        'line_items_url': session.get('url'),  # URL to retrieve line items
        'success_url': session.get('success_url'),
        'cancel_url': session.get('cancel_url')
    }

def extract_payment_info_from_payment_intent(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trích xuất thông tin thanh toán từ Stripe Payment Intent
    
    Args:
        payment_data: Data object từ payment_intent.* event
        
    Returns:
        Dict chứa thông tin thanh toán đã được chuẩn hóa
    """
    payment_intent = payment_data.get('object', {})
    
    return {
        'payment_intent_id': payment_intent.get('id'),
        'amount': payment_intent.get('amount', 0),
        'amount_received': payment_intent.get('amount_received', 0),
        'currency': payment_intent.get('currency', 'usd'),
        'status': payment_intent.get('status'),
        'customer_id': payment_intent.get('customer'),
        'payment_method_id': payment_intent.get('payment_method'),
        'receipt_email': payment_intent.get('receipt_email'),
        'description': payment_intent.get('description'),
        'metadata': payment_intent.get('metadata', {}),
        'charges': payment_intent.get('charges', {}).get('data', [])
    }

def extract_invoice_info_from_invoice(invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trích xuất thông tin hóa đơn từ Stripe Invoice
    
    Args:
        invoice_data: Data object từ invoice.* event
        
    Returns:
        Dict chứa thông tin hóa đơn đã được chuẩn hóa
    """
    invoice = invoice_data.get('object', {})
    
    return {
        'invoice_id': invoice.get('id'),
        'customer_id': invoice.get('customer'),
        'subscription_id': invoice.get('subscription'),
        'amount_due': invoice.get('amount_due', 0),
        'amount_paid': invoice.get('amount_paid', 0),
        'amount_remaining': invoice.get('amount_remaining', 0),
        'currency': invoice.get('currency', 'usd'),
        'status': invoice.get('status'),
        'payment_intent_id': invoice.get('payment_intent'),
        'hosted_invoice_url': invoice.get('hosted_invoice_url'),
        'invoice_pdf': invoice.get('invoice_pdf'),
        'metadata': invoice.get('metadata', {}),
        'period_start': invoice.get('period_start'),
        'period_end': invoice.get('period_end'),
        'lines': invoice.get('lines', {}).get('data', [])
    }

def format_amount_for_display(amount_cents: int, currency: str = 'USD') -> str:
    """
    Format amount từ cents sang display format
    
    Args:
        amount_cents: Số tiền tính bằng cents (Stripe format)
        currency: Mã tiền tệ
        
    Returns:
        String đã format cho display
    """
    # Stripe amounts are in cents for most currencies
    # Một số currencies như JPY không có decimal places
    zero_decimal_currencies = ['jpy', 'krw', 'vnd', 'clp', 'pyg', 'rwf', 'ugx', 'xaf', 'xof']
    
    if currency.lower() in zero_decimal_currencies:
        amount = amount_cents
        return f"{amount:,} {currency.upper()}"
    else:
        amount = amount_cents / 100
        return f"{amount:,.2f} {currency.upper()}"

def is_test_event(event_data: Dict[str, Any]) -> bool:
    """
    Kiểm tra xem event có phải từ test mode không
    
    Args:
        event_data: Stripe event data
        
    Returns:
        True nếu là test event
    """
    # Stripe test events có livemode = false
    return not event_data.get('livemode', True)
