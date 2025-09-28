import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any, List

# Khởi tạo AWS clients
cloudwatch = boto3.client('cloudwatch')
# Trong thực tế có thể cần thêm clients khác như:
# - SNS để gửi thông báo tới hệ thống kho
# - SQS để gửi message tới external inventory system
# - Lambda để invoke inventory management functions

def put_cloudwatch_metric(metric_name: str, value: float, unit: str = 'Count'):
    """Gửi custom metric lên CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace='InventoryProcessing',
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

def process_order_created_inventory(message_data: Dict[str, Any]) -> bool:
    """
    Xử lý thông báo kho khi có đơn hàng mới
    
    Trong thực tế sẽ:
    1. Parse thông tin sản phẩm từ order
    2. Kiểm tra tồn kho
    3. Reserve sản phẩm
    4. Gửi thông báo tới warehouse management system
    5. Cập nhật inventory database
    """
    try:
        order_id = message_data.get('session_id') or message_data.get('payment_intent_id')
        customer_id = message_data.get('customer_id')
        amount_total = message_data.get('amount_total', 0)
        
        print(f"Processing inventory for new order: {order_id}")
        
        # TODO: Implement actual inventory logic
        # 1. Extract product information from order metadata
        metadata = message_data.get('metadata', {})
        
        # Giả lập xử lý inventory
        inventory_items = []
        
        # Trong thực tế, sẽ parse từ metadata hoặc query từ order details
        # Ví dụ metadata có thể chứa:
        # {
        #   "products": [
        #     {"sku": "PROD-001", "quantity": 2, "name": "Product 1"},
        #     {"sku": "PROD-002", "quantity": 1, "name": "Product 2"}
        #   ]
        # }
        
        if 'products' in metadata:
            try:
                products = json.loads(metadata['products']) if isinstance(metadata['products'], str) else metadata['products']
                for product in products:
                    inventory_item = {
                        'order_id': order_id,
                        'sku': product.get('sku'),
                        'quantity': product.get('quantity', 1),
                        'product_name': product.get('name', 'Unknown'),
                        'action': 'reserve',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    inventory_items.append(inventory_item)
                    
                    # Giả lập gửi thông báo tới warehouse system
                    print(f"Reserving inventory - SKU: {product.get('sku')}, Quantity: {product.get('quantity')}")
                    
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error parsing products from metadata: {str(e)}")
                # Fallback: tạo generic inventory notification
                inventory_items.append({
                    'order_id': order_id,
                    'sku': 'UNKNOWN',
                    'quantity': 1,
                    'product_name': 'Generic Order Item',
                    'action': 'reserve',
                    'timestamp': datetime.utcnow().isoformat()
                })
        else:
            # Không có thông tin sản phẩm chi tiết, tạo generic notification
            inventory_items.append({
                'order_id': order_id,
                'sku': 'GENERIC',
                'quantity': 1,
                'product_name': f'Order {order_id}',
                'action': 'reserve',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # TODO: Gửi thông báo tới warehouse management system
        # Có thể sử dụng:
        # - SNS để publish tới warehouse topic
        # - SQS để gửi message tới warehouse queue
        # - HTTP API call tới external inventory system
        # - Database update cho internal inventory system
        
        # Giả lập thành công
        for item in inventory_items:
            print(f"Inventory notification sent: {json.dumps(item)}")
        
        put_cloudwatch_metric('InventoryReservations', len(inventory_items))
        put_cloudwatch_metric('OrdersProcessedForInventory', 1)
        
        return True
        
    except Exception as e:
        print(f"Error processing inventory for order creation: {str(e)}")
        put_cloudwatch_metric('InventoryProcessingErrors', 1)
        return False

def process_inventory_update(message_data: Dict[str, Any]) -> bool:
    """
    Xử lý cập nhật inventory
    
    Có thể được trigger bởi:
    1. Inventory adjustment từ warehouse
    2. Product restock notification
    3. Inventory audit results
    """
    try:
        print("Processing inventory update notification")
        
        # TODO: Implement inventory update logic
        # Ví dụ message_data có thể chứa:
        # {
        #   "event_type": "inventory_update",
        #   "sku": "PROD-001",
        #   "quantity_change": 100,
        #   "new_quantity": 500,
        #   "reason": "restock",
        #   "warehouse_id": "WH-001"
        # }
        
        sku = message_data.get('sku', 'UNKNOWN')
        quantity_change = message_data.get('quantity_change', 0)
        new_quantity = message_data.get('new_quantity', 0)
        reason = message_data.get('reason', 'unknown')
        
        print(f"Inventory update - SKU: {sku}, Change: {quantity_change}, New Quantity: {new_quantity}, Reason: {reason}")
        
        # TODO: Update inventory database
        # TODO: Send notifications if low stock
        # TODO: Update product availability status
        
        put_cloudwatch_metric('InventoryUpdates', 1)
        
        if quantity_change > 0:
            put_cloudwatch_metric('InventoryRestocks', 1)
        elif quantity_change < 0:
            put_cloudwatch_metric('InventoryDeductions', 1)
        
        return True
        
    except Exception as e:
        print(f"Error processing inventory update: {str(e)}")
        put_cloudwatch_metric('InventoryProcessingErrors', 1)
        return False

def handler(event, context):
    """
    Lambda handler cho xử lý thông báo kho từ SQS
    
    Nhận messages từ SQS và xử lý theo loại event:
    - order_created: Reserve inventory cho đơn hàng mới
    - inventory_update: Cập nhật thông tin tồn kho
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
                    # Lấy message attributes từ SNS
                    message_attributes = message_body.get('MessageAttributes', {})
                else:
                    actual_message = message_body
                    message_attributes = {}
                
                event_type = actual_message.get('event_type')
                
                print(f"Processing inventory event: {event_type}")
                
                # Xử lý theo loại event
                success = False
                
                if event_type == 'order_created':
                    success = process_order_created_inventory(actual_message)
                elif event_type == 'inventory_update':
                    success = process_inventory_update(actual_message)
                else:
                    print(f"No inventory handler for event type: {event_type}")
                    success = True  # Không fail cho unknown events
                
                if success:
                    processed_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                print(f"Error processing individual inventory record: {str(e)}")
                failed_count += 1
        
        # Gửi metrics tổng hợp
        put_cloudwatch_metric('InventoryBatchesProcessed', 1)
        put_cloudwatch_metric('InventoryMessagesProcessed', processed_count)
        
        if failed_count > 0:
            put_cloudwatch_metric('InventoryMessageFailures', failed_count)
        
        print(f"Inventory batch processing completed. Processed: {processed_count}, Failed: {failed_count}")
        
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
        print(f"Error in inventory processor handler: {str(e)}")
        put_cloudwatch_metric('InventoryHandlerErrors', 1)
        
        # Trả về tất cả messages là failed
        return {
            'batchItemFailures': [
                {'itemIdentifier': record['messageId']} 
                for record in event.get('Records', [])
            ]
        }
