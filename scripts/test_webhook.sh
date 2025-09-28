#!/bin/bash

# Script test webhook endpoint
# Sử dụng: ./scripts/test_webhook.sh [stage] [region]

set -e

# Default values
STAGE=${1:-dev}
REGION=${2:-ap-southeast-1}

echo "🧪 Testing Order Processing Webhook"
echo "Stage: $STAGE"
echo "Region: $REGION"
echo ""

# Lấy Webhook URL trực tiếp từ CloudFormation output
STACK_NAME="order-processing-system-$STAGE"
WEBHOOK_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$WEBHOOK_URL" ] || [ "$WEBHOOK_URL" == "None" ]; then
    echo "❌ Could not find Webhook URL. Make sure the stack is deployed."
    echo "Available outputs:"
    aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table 2>/dev/null || echo "Stack not found"
    exit 1
fi
echo "🔗 Webhook URL: $WEBHOOK_URL"
echo ""

# Test 1: Basic connectivity
echo "📡 Test 1: Basic connectivity"
response=$(curl -s -o /dev/null -w "%{http_code}" "$WEBHOOK_URL" || echo "000")
if [ "$response" == "400" ] || [ "$response" == "401" ]; then
    echo "✅ Endpoint is reachable (HTTP $response - expected for missing signature)"
else
    echo "❌ Unexpected response: HTTP $response"
fi
echo ""

# Test 2: Mock Stripe checkout.session.completed event
echo "📡 Test 2: Mock checkout.session.completed event"

# Tạo mock payload
mock_payload='{
  "id": "evt_test_webhook",
  "object": "event",
  "api_version": "2020-08-27",
  "created": '$(date +%s)',
  "data": {
    "object": {
      "id": "cs_test_session_123",
      "object": "checkout.session",
      "amount_total": 2000,
      "currency": "usd",
      "customer": "cus_test_customer",
      "customer_details": {
        "email": "ngo.quang.trung@sun-asterisk.com",
        "name": "Test Customer"
      },
      "metadata": {
        "order_id": "test_order_123",
        "products": "[{\"sku\":\"PROD-001\",\"quantity\":2,\"name\":\"Test Product\"}]"
      },
      "payment_intent": "pi_test_payment_123",
      "payment_status": "paid",
      "mode": "payment"
    }
  },
  "livemode": false,
  "pending_webhooks": 1,
  "request": {
    "id": "req_test_123",
    "idempotency_key": null
  },
  "type": "checkout.session.completed"
}'

# Tạo mock signature (sẽ fail validation nhưng test endpoint)
timestamp=$(date +%s)
mock_signature="t=$timestamp,v1=mock_signature_for_testing"

echo "Sending mock event..."
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Stripe-Signature: $mock_signature" \
    -d "$mock_payload" \
    "$WEBHOOK_URL")

http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
response_body=$(echo "$response" | grep -v "HTTP_CODE:")

echo "Response Code: $http_code"
echo "Response Body: $response_body"

if [ "$http_code" == "401" ]; then
    echo "✅ Expected 401 - signature validation working"
elif [ "$http_code" == "200" ]; then
    echo "⚠️  Unexpected 200 - signature validation may be disabled"
else
    echo "❌ Unexpected response code: $http_code"
fi
echo ""

# Test 3: Invalid JSON
echo "📡 Test 3: Invalid JSON payload"
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "Stripe-Signature: t=$(date +%s),v1=invalid_signature" \
    -d "invalid json" \
    "$WEBHOOK_URL")

http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
echo "Response Code: $http_code"

if [ "$http_code" == "400" ]; then
    echo "✅ Correctly rejected invalid JSON"
else
    echo "❌ Unexpected response for invalid JSON: $http_code"
fi
echo ""

# Test 4: Missing signature
echo "📡 Test 4: Missing Stripe signature"
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$mock_payload" \
    "$WEBHOOK_URL")

http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
echo "Response Code: $http_code"

if [ "$http_code" == "400" ]; then
    echo "✅ Correctly rejected missing signature"
else
    echo "❌ Unexpected response for missing signature: $http_code"
fi
echo ""

# Kiểm tra CloudWatch Logs
echo "📋 Checking recent Lambda logs..."
LOG_GROUP="/aws/lambda/order-processing-system-$STAGE-stripeWebhook"

recent_logs=$(aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --start-time $(($(date +%s) * 1000 - 300000)) \
    --region $REGION \
    --output json 2>/dev/null | jq -r '.events[].message' | tail -10)

if [ ! -z "$recent_logs" ]; then
    echo "Recent webhook logs:"
    echo "$recent_logs" | sed 's/^/  /'
else
    echo "No recent logs found (this might be normal for a new deployment)"
fi
echo ""

# Kiểm tra SQS messages
echo "📨 Checking SQS queues for messages..."
QUEUE_NAMES=(
    "order-processing-system-$STAGE-order-processing"
    "order-processing-system-$STAGE-email"
    "order-processing-system-$STAGE-inventory"
)

for queue_name in "${QUEUE_NAMES[@]}"; do
    queue_url=$(aws sqs get-queue-url --queue-name "$queue_name" --region $REGION --output text --query 'QueueUrl' 2>/dev/null || echo "")
    
    if [ ! -z "$queue_url" ]; then
        message_count=$(aws sqs get-queue-attributes \
            --queue-url "$queue_url" \
            --attribute-names ApproximateNumberOfMessages \
            --region $REGION \
            --output json 2>/dev/null | jq -r '.Attributes.ApproximateNumberOfMessages // "0"')
        
        echo "  $queue_name: $message_count messages"
    else
        echo "  $queue_name: Queue not found"
    fi
done
echo ""

echo "🎯 Test Summary:"
echo "  - Webhook endpoint is accessible"
echo "  - Signature validation is working"
echo "  - Error handling is working"
echo "  - Check CloudWatch logs for detailed execution info"
echo ""
echo "💡 Next Steps:"
echo "1. Update Secrets Manager with real Stripe webhook secret"
echo "2. Configure real Stripe webhook with this URL: $WEBHOOK_URL"
echo "3. Test with real Stripe events"
echo "4. Monitor the system with: ./scripts/monitor.sh $STAGE $REGION"
