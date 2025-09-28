import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any

# Khởi tạo AWS clients
ses_client = boto3.client('ses')
secrets_client = boto3.client('secretsmanager')
cloudwatch = boto3.client('cloudwatch')

def get_secret(secret_name: str) -> Dict[str, Any]:
    """Lấy secret từ AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error getting secret: {str(e)}")
        raise

def put_cloudwatch_metric(metric_name: str, value: float, unit: str = 'Count'):
    """Gửi custom metric lên CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace='EmailProcessing',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': unit,
                    'Timestamp': datetime.utcnow()
                }
            ]
        )
    except Exception as e:
        print(f"Error sending CloudWatch metric: {str(e)}")

def send_order_confirmation_email(message_data: Dict[str, Any], from_email: str) -> bool:
    """Gửi email xác nhận đơn hàng"""
    try:
        customer_email = message_data.get('customer_email')
        if not customer_email:
            print("No customer email provided")
            return False
        
        order_id = message_data.get('session_id') or message_data.get('payment_intent_id', 'N/A')
        amount = message_data.get('amount_total', 0)
        currency = message_data.get('currency', 'USD').upper()
        
        # Format amount (Stripe amounts are in cents)
        formatted_amount = f"{amount / 100:.2f} {currency}"
        
        subject = f"Xác nhận đơn hàng #{order_id}"
        
        html_body = f"""
        <html>
        <head></head>
        <body>
            <h2>Cảm ơn bạn đã đặt hàng!</h2>
            <p>Chúng tôi đã nhận được đơn hàng của bạn và đang xử lý.</p>
            
            <h3>Chi tiết đơn hàng:</h3>
            <ul>
                <li><strong>Mã đơn hàng:</strong> {order_id}</li>
                <li><strong>Tổng tiền:</strong> {formatted_amount}</li>
                <li><strong>Thời gian đặt:</strong> {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC</li>
            </ul>
            
            <p>Chúng tôi sẽ gửi thông báo cập nhật khi đơn hàng được xử lý và giao hàng.</p>
            
            <p>Trân trọng,<br>
            Đội ngũ hỗ trợ khách hàng</p>
        </body>
        </html>
        """
        
        text_body = f"""
        Cảm ơn bạn đã đặt hàng!
        
        Chúng tôi đã nhận được đơn hàng của bạn và đang xử lý.
        
        Chi tiết đơn hàng:
        - Mã đơn hàng: {order_id}
        - Tổng tiền: {formatted_amount}
        - Thời gian đặt: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC
        
        Chúng tôi sẽ gửi thông báo cập nhật khi đơn hàng được xử lý và giao hàng.
        
        Trân trọng,
        Đội ngũ hỗ trợ khách hàng
        """
        
        response = ses_client.send_email(
            Source=from_email,
            Destination={'ToAddresses': [customer_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'}
                }
            }
        )
        
        print(f"Order confirmation email sent to {customer_email}, MessageId: {response['MessageId']}")
        return True
        
    except Exception as e:
        print(f"Error sending order confirmation email: {str(e)}")
        return False

def send_payment_confirmation_email(message_data: Dict[str, Any], from_email: str) -> bool:
    """Gửi email xác nhận thanh toán"""
    try:
        # Lấy customer email từ metadata hoặc customer_id
        customer_email = message_data.get('customer_email')
        if not customer_email:
            # Nếu không có email, có thể query từ customer_id
            # Ở đây tạm thời skip nếu không có email
            print("No customer email for payment confirmation")
            return True  # Return true để không retry
        
        payment_intent_id = message_data.get('payment_intent_id', 'N/A')
        amount = message_data.get('amount', 0)
        currency = message_data.get('currency', 'USD').upper()
        
        # Format amount (Stripe amounts are in cents)
        formatted_amount = f"{amount / 100:.2f} {currency}"
        
        subject = f"Xác nhận thanh toán - Đơn hàng #{payment_intent_id}"
        
        html_body = f"""
        <html>
        <head></head>
        <body>
            <h2>Thanh toán thành công!</h2>
            <p>Chúng tôi đã nhận được thanh toán cho đơn hàng của bạn.</p>
            
            <h3>Chi tiết thanh toán:</h3>
            <ul>
                <li><strong>Mã thanh toán:</strong> {payment_intent_id}</li>
                <li><strong>Số tiền:</strong> {formatted_amount}</li>
                <li><strong>Thời gian:</strong> {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC</li>
            </ul>
            
            <p>Đơn hàng của bạn sẽ được xử lý và giao trong thời gian sớm nhất.</p>
            
            <p>Trân trọng,<br>
            Đội ngũ hỗ trợ khách hàng</p>
        </body>
        </html>
        """
        
        text_body = f"""
        Thanh toán thành công!
        
        Chúng tôi đã nhận được thanh toán cho đơn hàng của bạn.
        
        Chi tiết thanh toán:
        - Mã thanh toán: {payment_intent_id}
        - Số tiền: {formatted_amount}
        - Thời gian: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC
        
        Đơn hàng của bạn sẽ được xử lý và giao trong thời gian sớm nhất.
        
        Trân trọng,
        Đội ngũ hỗ trợ khách hàng
        """
        
        response = ses_client.send_email(
            Source=from_email,
            Destination={'ToAddresses': [customer_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'}
                }
            }
        )
        
        print(f"Payment confirmation email sent to {customer_email}, MessageId: {response['MessageId']}")
        return True
        
    except Exception as e:
        print(f"Error sending payment confirmation email: {str(e)}")
        return False

def handler(event, context):
    """
    Lambda handler cho gửi email từ SQS
    
    Nhận messages từ SQS và gửi email tương ứng:
    - order_created: Gửi email xác nhận đơn hàng
    - payment_confirmed: Gửi email xác nhận thanh toán
    """
    
    processed_count = 0
    failed_count = 0
    
    try:
        # Lấy email cấu hình từ Secrets Manager
        secrets = get_secret(os.environ['SECRETS_MANAGER_ARN'])
        from_email = secrets['ses_from_email']
        
        # Xử lý từng message trong batch
        for record in event.get('Records', []):
            try:
                # Parse message từ SQS
                message_body = json.loads(record['body'])
                
                # Nếu message đến từ SNS, cần parse thêm một lần
                if 'Message' in message_body:
                    actual_message = json.loads(message_body['Message'])
                    # Lấy message attributes từ SNS
                    message_attributes = message_body.get('MessageAttributes', {})
                else:
                    actual_message = message_body
                    message_attributes = {}
                
                event_type = actual_message.get('event_type')
                
                print(f"Processing email for event: {event_type}")
                
                # Xử lý theo loại event
                success = False
                
                if event_type == 'order_created':
                    success = send_order_confirmation_email(actual_message, from_email)
                elif event_type == 'payment_confirmed':
                    success = send_payment_confirmation_email(actual_message, from_email)
                else:
                    print(f"No email handler for event type: {event_type}")
                    success = True  # Không fail cho unknown events
                
                if success:
                    processed_count += 1
                    put_cloudwatch_metric('EmailsSent', 1)
                else:
                    failed_count += 1
                    put_cloudwatch_metric('EmailSendFailures', 1)
                    
            except Exception as e:
                print(f"Error processing individual email record: {str(e)}")
                failed_count += 1
                put_cloudwatch_metric('EmailSendFailures', 1)
        
        # Gửi metrics tổng hợp
        put_cloudwatch_metric('EmailBatchesProcessed', 1)
        
        print(f"Email batch processing completed. Processed: {processed_count}, Failed: {failed_count}")
        
        # Trả về thông tin về các messages failed (để SQS có thể retry)
        if failed_count > 0:
            return {
                'batchItemFailures': [
                    {'itemIdentifier': record['messageId']} 
                    for record in event.get('Records', [])
                ][-failed_count:]  # Chỉ báo failed cho số messages thất bại
            }
        
        return {'statusCode': 200}
        
    except Exception as e:
        print(f"Error in email processor handler: {str(e)}")
        put_cloudwatch_metric('EmailHandlerErrors', 1)
        
        # Trả về tất cả messages là failed
        return {
            'batchItemFailures': [
                {'itemIdentifier': record['messageId']} 
                for record in event.get('Records', [])
            ]
        }
