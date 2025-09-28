import json
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

def get_secret(secret_name: str, region_name: str = 'ap-southeast-1') -> Dict[str, Any]:
    """
    Lấy secret từ AWS Secrets Manager
    
    Args:
        secret_name: Tên của secret
        region_name: AWS region
        
    Returns:
        Dict chứa secret data
        
    Raises:
        ClientError: Nếu không thể lấy secret
    """
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
        return json.loads(secret)
    except ClientError as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        raise e

def publish_sns_message(
    topic_arn: str, 
    message: Dict[str, Any], 
    message_attributes: Optional[Dict[str, Dict[str, str]]] = None,
    region_name: str = 'ap-southeast-1'
) -> str:
    """
    Publish message tới SNS topic
    
    Args:
        topic_arn: ARN của SNS topic
        message: Message data
        message_attributes: SNS message attributes
        region_name: AWS region
        
    Returns:
        Message ID từ SNS
        
    Raises:
        ClientError: Nếu không thể publish message
    """
    sns_client = boto3.client('sns', region_name=region_name)
    
    try:
        kwargs = {
            'TopicArn': topic_arn,
            'Message': json.dumps(message)
        }
        
        if message_attributes:
            kwargs['MessageAttributes'] = message_attributes
            
        response = sns_client.publish(**kwargs)
        return response['MessageId']
        
    except ClientError as e:
        print(f"Error publishing to SNS topic {topic_arn}: {str(e)}")
        raise e

def send_sqs_message(
    queue_url: str,
    message_body: Dict[str, Any],
    message_attributes: Optional[Dict[str, Dict[str, str]]] = None,
    delay_seconds: int = 0,
    region_name: str = 'ap-southeast-1'
) -> str:
    """
    Gửi message tới SQS queue
    
    Args:
        queue_url: URL của SQS queue
        message_body: Message data
        message_attributes: SQS message attributes
        delay_seconds: Delay trước khi message available
        region_name: AWS region
        
    Returns:
        Message ID từ SQS
        
    Raises:
        ClientError: Nếu không thể gửi message
    """
    sqs_client = boto3.client('sqs', region_name=region_name)
    
    try:
        kwargs = {
            'QueueUrl': queue_url,
            'MessageBody': json.dumps(message_body)
        }
        
        if message_attributes:
            kwargs['MessageAttributes'] = message_attributes
            
        if delay_seconds > 0:
            kwargs['DelaySeconds'] = delay_seconds
            
        response = sqs_client.send_message(**kwargs)
        return response['MessageId']
        
    except ClientError as e:
        print(f"Error sending message to SQS queue {queue_url}: {str(e)}")
        raise e

def put_dynamodb_item(
    table_name: str,
    item: Dict[str, Any],
    region_name: str = 'ap-southeast-1'
) -> bool:
    """
    Lưu item vào DynamoDB table
    
    Args:
        table_name: Tên DynamoDB table
        item: Item data
        region_name: AWS region
        
    Returns:
        True nếu thành công
        
    Raises:
        ClientError: Nếu không thể lưu item
    """
    dynamodb = boto3.resource('dynamodb', region_name=region_name)
    table = dynamodb.Table(table_name)
    
    try:
        table.put_item(Item=item)
        return True
        
    except ClientError as e:
        print(f"Error putting item to DynamoDB table {table_name}: {str(e)}")
        raise e

def send_email_ses(
    source_email: str,
    destination_emails: list,
    subject: str,
    html_body: str,
    text_body: str,
    region_name: str = 'ap-southeast-1'
) -> str:
    """
    Gửi email qua Amazon SES
    
    Args:
        source_email: Email người gửi
        destination_emails: List email người nhận
        subject: Tiêu đề email
        html_body: Nội dung HTML
        text_body: Nội dung text
        region_name: AWS region
        
    Returns:
        Message ID từ SES
        
    Raises:
        ClientError: Nếu không thể gửi email
    """
    ses_client = boto3.client('ses', region_name=region_name)
    
    try:
        response = ses_client.send_email(
            Source=source_email,
            Destination={'ToAddresses': destination_emails},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                    'Html': {'Data': html_body, 'Charset': 'UTF-8'}
                }
            }
        )
        return response['MessageId']
        
    except ClientError as e:
        print(f"Error sending email via SES: {str(e)}")
        raise e

def put_cloudwatch_metric(
    namespace: str,
    metric_name: str,
    value: float,
    unit: str = 'Count',
    dimensions: Optional[Dict[str, str]] = None,
    region_name: str = 'ap-southeast-1'
) -> bool:
    """
    Gửi custom metric tới CloudWatch
    
    Args:
        namespace: CloudWatch namespace
        metric_name: Tên metric
        value: Giá trị metric
        unit: Đơn vị metric
        dimensions: Dimensions cho metric
        region_name: AWS region
        
    Returns:
        True nếu thành công
        
    Raises:
        ClientError: Nếu không thể gửi metric
    """
    cloudwatch_client = boto3.client('cloudwatch', region_name=region_name)
    
    try:
        metric_data = {
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit
        }
        
        if dimensions:
            metric_data['Dimensions'] = [
                {'Name': k, 'Value': v} for k, v in dimensions.items()
            ]
            
        cloudwatch_client.put_metric_data(
            Namespace=namespace,
            MetricData=[metric_data]
        )
        return True
        
    except ClientError as e:
        print(f"Error putting CloudWatch metric: {str(e)}")
        raise e
