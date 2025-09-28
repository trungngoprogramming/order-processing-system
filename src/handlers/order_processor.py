import json
import os
import boto3
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List

# Khởi tạo AWS clients
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

def get_orders_table():
    """Lấy DynamoDB table cho orders"""
    table_name = os.environ['ORDERS_TABLE']
    return dynamodb.Table(table_name)

def put_cloudwatch_metric(metric_name: str, value: float, unit: str = 'Count'):
    """Gửi custom metric lên CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace='OrderProcessing',
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

def process_order_created(message_data: Dict[str, Any]) -> bool:
    """Xử lý event tạo đơn hàng mới"""
    try:
        table = get_orders_table()
        
        # Tạo order_id từ session_id hoặc payment_intent_id
        order_id = message_data.get('session_id') or message_data.get('payment_intent_id')
        
        if not order_id:
            print("Missing order identifier")
            return False
        
        # Chuẩn bị dữ liệu order
        order_item = {
            'order_id': order_id,
            'customer_id': message_data.get('customer_id', 'unknown'),
            'customer_email': message_data.get('customer_email', ''),
            'amount_total': Decimal(str(message_data.get('amount_total', 0))),
            'currency': message_data.get('currency', 'usd'),
            'payment_intent_id': message_data.get('payment_intent_id', ''),
            'session_id': message_data.get('session_id', ''),
            'status': 'created',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'metadata': message_data.get('metadata', {}),
            'stripe_timestamp': message_data.get('timestamp', 0)
        }
        
        # Lưu vào DynamoDB
        table.put_item(Item=order_item)
        
        print(f"Created order: {order_id}")
        put_cloudwatch_metric('OrdersCreated', 1)
        
        return True
        
    except Exception as e:
        print(f"Error processing order created: {str(e)}")
        put_cloudwatch_metric('OrderProcessingErrors', 1)
        return False

def process_payment_confirmed(message_data: Dict[str, Any]) -> bool:
    """Xử lý event xác nhận thanh toán"""
    try:
        table = get_orders_table()
        
        payment_intent_id = message_data.get('payment_intent_id')
        if not payment_intent_id:
            print("Missing payment_intent_id")
            return False
        
        # Cập nhật status của order
        response = table.update_item(
            Key={'order_id': payment_intent_id},
            UpdateExpression='SET #status = :status, updated_at = :updated_at, payment_confirmed_at = :confirmed_at',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'payment_confirmed',
                ':updated_at': datetime.utcnow().isoformat(),
                ':confirmed_at': datetime.utcnow().isoformat()
            },
            ReturnValues='UPDATED_NEW'
        )
        
        print(f"Payment confirmed for order: {payment_intent_id}")
        put_cloudwatch_metric('PaymentsConfirmed', 1)
        
        return True
        
    except Exception as e:
        print(f"Error processing payment confirmation: {str(e)}")
        put_cloudwatch_metric('OrderProcessingErrors', 1)
        return False

def process_order_updated(message_data: Dict[str, Any]) -> bool:
    """Xử lý event cập nhật đơn hàng"""
    try:
        table = get_orders_table()
        
        # Sử dụng invoice_id làm order_id cho subscription orders
        order_id = message_data.get('invoice_id')
        if not order_id:
            print("Missing order identifier for update")
            return False
        
        # Cập nhật thông tin order
        update_expression = 'SET updated_at = :updated_at'
        expression_values = {':updated_at': datetime.utcnow().isoformat()}
        
        if message_data.get('subscription_id'):
            update_expression += ', subscription_id = :sub_id'
            expression_values[':sub_id'] = message_data['subscription_id']
        
        if message_data.get('amount_paid'):
            update_expression += ', amount_paid = :amount_paid'
            expression_values[':amount_paid'] = Decimal(str(message_data['amount_paid']))
        
        table.update_item(
            Key={'order_id': order_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        print(f"Updated order: {order_id}")
        put_cloudwatch_metric('OrdersUpdated', 1)
        
        return True
        
    except Exception as e:
        print(f"Error processing order update: {str(e)}")
        put_cloudwatch_metric('OrderProcessingErrors', 1)
        return False

def handler(event, context):
    """
    Lambda handler cho xử lý đơn hàng từ SQS
    
    Nhận messages từ SQS và xử lý theo loại event:
    - order_created: Tạo record mới trong DynamoDB
    - payment_confirmed: Cập nhật status thanh toán
    - order_updated: Cập nhật thông tin đơn hàng
    """
    
    processed_count = 0
    failed_count = 0
    
    try:
        # Xử lý từng message trong batch
        for record in event.get('Records', []):
            try:
                # Parse message từ SQS
                message_body = json.loads(record['body'])
                
                # Nếu message đến từ SNS, cần parse thêm một lần
                if 'Message' in message_body:
                    actual_message = json.loads(message_body['Message'])
                else:
                    actual_message = message_body
                
                event_type = actual_message.get('event_type')
                
                print(f"Processing event: {event_type}")
                
                # Xử lý theo loại event
                success = False
                
                if event_type == 'order_created':
                    success = process_order_created(actual_message)
                elif event_type == 'payment_confirmed':
                    success = process_payment_confirmed(actual_message)
                elif event_type == 'order_updated':
                    success = process_order_updated(actual_message)
                else:
                    print(f"Unknown event type: {event_type}")
                    success = True  # Không fail cho unknown events
                
                if success:
                    processed_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                print(f"Error processing individual record: {str(e)}")
                failed_count += 1
        
        # Gửi metrics tổng hợp
        put_cloudwatch_metric('MessagesProcessed', processed_count)
        if failed_count > 0:
            put_cloudwatch_metric('MessageProcessingFailures', failed_count)
        
        print(f"Batch processing completed. Processed: {processed_count}, Failed: {failed_count}")
        
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
        print(f"Error in order processor handler: {str(e)}")
        put_cloudwatch_metric('HandlerErrors', 1)
        
        # Trả về tất cả messages là failed
        return {
            'batchItemFailures': [
                {'itemIdentifier': record['messageId']} 
                for record in event.get('Records', [])
            ]
        }
