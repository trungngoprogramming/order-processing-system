import json
import os
import boto3
import hashlib
import hmac
from typing import Dict, Any

# Khởi tạo AWS clients
sns_client = boto3.client('sns')
secrets_client = boto3.client('secretsmanager')

def get_secret(secret_name: str) -> Dict[str, Any]:
    """Lấy secret từ AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error getting secret: {str(e)}")
        raise

def verify_stripe_signature(payload: str, signature: str, webhook_secret: str) -> bool:
    """
    Xác thực chữ ký Stripe webhook
    
    Trong thực tế, đây sẽ là logic xác thực thực sự:
    1. Lấy timestamp từ header
    2. Tạo signed payload = timestamp + '.' + payload
    3. Tính HMAC-SHA256 với webhook secret
    4. So sánh với signature từ Stripe
    
    Hiện tại return True để pass qua bước xác thực
    """
    # TODO: Implement actual Stripe signature verification
    # expected_signature = hmac.new(
    #     webhook_secret.encode('utf-8'),
    #     signed_payload.encode('utf-8'),
    #     hashlib.sha256
    # ).hexdigest()
    
    # Tạm thời return True để pass qua xác thực
    print(f"Verifying Stripe signature for payload length: {len(payload)}")
    print(f"Signature received: {signature[:20]}...")  # Log một phần signature
    
    # Logic xác thực thực tế sẽ được implement ở đây
    return True

def publish_to_sns(topic_arn: str, message: Dict[str, Any], event_type: str) -> bool:
    """Publish message to SNS với message attributes"""
    try:
        response = sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            MessageAttributes={
                'event_type': {
                    'DataType': 'String',
                    'StringValue': event_type
                },
                'source': {
                    'DataType': 'String',
                    'StringValue': 'stripe_webhook'
                }
            }
        )
        print(f"Published message to SNS: {response['MessageId']}")
        return True
    except Exception as e:
        print(f"Error publishing to SNS: {str(e)}")
        return False

def handler(event, context):
    """
    Lambda handler cho Stripe webhook
    
    Luồng xử lý:
    1. Lấy payload và signature từ request
    2. Xác thực signature với Stripe webhook secret
    3. Parse event data từ Stripe
    4. Publish event tới SNS topic tương ứng
    """
    try:
        # Lấy body và headers từ API Gateway event
        body = event.get('body', '')
        headers = event.get('headers', {})
        
        # Lấy Stripe signature từ header
        stripe_signature = headers.get('stripe-signature', '')
        
        if not stripe_signature:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing Stripe signature'})
            }
        
        # Lấy webhook secret từ Secrets Manager
        secrets = get_secret(os.environ['SECRETS_MANAGER_ARN'])
        webhook_secret = secrets['stripe_webhook_secret']
        
        # Xác thực Stripe signature
        if not verify_stripe_signature(body, stripe_signature, webhook_secret):
            print("Invalid Stripe signature")
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Invalid signature'})
            }
        
        # Parse Stripe event
        try:
            stripe_event = json.loads(body)
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid JSON payload'})
            }
        
        event_type = stripe_event.get('type', '')
        event_data = stripe_event.get('data', {})
        
        print(f"Processing Stripe event: {event_type}")
        
        # Xử lý các loại event khác nhau
        sns_topic_arn = os.environ['SNS_TOPIC_ARN']
        
        if event_type == 'payment_intent.succeeded':
            # Thanh toán thành công
            message = {
                'event_type': 'payment_confirmed',
                'payment_intent_id': event_data.get('object', {}).get('id'),
                'amount': event_data.get('object', {}).get('amount'),
                'currency': event_data.get('object', {}).get('currency'),
                'customer_id': event_data.get('object', {}).get('customer'),
                'metadata': event_data.get('object', {}).get('metadata', {}),
                'timestamp': stripe_event.get('created')
            }
            
            success = publish_to_sns(sns_topic_arn, message, 'payment_confirmed')
            
        elif event_type == 'checkout.session.completed':
            # Checkout session hoàn thành
            session = event_data.get('object', {})
            message = {
                'event_type': 'order_created',
                'session_id': session.get('id'),
                'payment_intent_id': session.get('payment_intent'),
                'customer_email': session.get('customer_details', {}).get('email'),
                'customer_id': session.get('customer'),
                'amount_total': session.get('amount_total'),
                'currency': session.get('currency'),
                'metadata': session.get('metadata', {}),
                'timestamp': stripe_event.get('created')
            }
            
            success = publish_to_sns(sns_topic_arn, message, 'order_created')
            
        elif event_type == 'invoice.payment_succeeded':
            # Thanh toán hóa đơn thành công
            invoice = event_data.get('object', {})
            message = {
                'event_type': 'order_updated',
                'invoice_id': invoice.get('id'),
                'customer_id': invoice.get('customer'),
                'subscription_id': invoice.get('subscription'),
                'amount_paid': invoice.get('amount_paid'),
                'currency': invoice.get('currency'),
                'timestamp': stripe_event.get('created')
            }
            
            success = publish_to_sns(sns_topic_arn, message, 'order_updated')
            
        else:
            # Event type không được hỗ trợ
            print(f"Unhandled event type: {event_type}")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': f'Event type {event_type} not handled'})
            }
        
        if success:
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Event processed successfully'})
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to process event'})
            }
            
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }
