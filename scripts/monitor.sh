#!/bin/bash

# Script monitoring hệ thống order processing
# Sử dụng: ./scripts/monitor.sh [stage] [region]

set -e

# Default values
STAGE=${1:-dev}
REGION=${2:-ap-southeast-1}

echo "📊 Order Processing System Monitoring"
echo "Stage: $STAGE"
echo "Region: $REGION"
echo "Time: $(date)"
echo ""

# Function để lấy queue metrics
get_queue_metrics() {
    local queue_name=$1
    local queue_url=$(aws sqs get-queue-url --queue-name "$queue_name" --region $REGION --output text --query 'QueueUrl' 2>/dev/null || echo "")
    
    if [ -z "$queue_url" ]; then
        echo "  ❌ Queue not found: $queue_name"
        return
    fi
    
    local attributes=$(aws sqs get-queue-attributes \
        --queue-url "$queue_url" \
        --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible,ApproximateNumberOfMessagesDelayed \
        --region $REGION \
        --output json 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        local visible=$(echo $attributes | jq -r '.Attributes.ApproximateNumberOfMessages // "0"')
        local not_visible=$(echo $attributes | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible // "0"')
        local delayed=$(echo $attributes | jq -r '.Attributes.ApproximateNumberOfMessagesDelayed // "0"')
        
        echo "  📨 $queue_name:"
        echo "    Visible: $visible"
        echo "    Processing: $not_visible"
        echo "    Delayed: $delayed"
        
        # Cảnh báo nếu có quá nhiều messages
        if [ "$visible" -gt 50 ]; then
            echo "    ⚠️  WARNING: High message count!"
        fi
    else
        echo "  ❌ Failed to get metrics for: $queue_name"
    fi
}

# Function để lấy Lambda metrics
get_lambda_metrics() {
    local function_name=$1
    local full_name="order-processing-system-$STAGE-$function_name"
    
    echo "  🔧 $function_name:"
    
    # Lấy invocation count trong 1 giờ qua
    local end_time=$(date -u +"%Y-%m-%dT%H:%M:%S")
    local start_time=$(date -u -d '1 hour ago' +"%Y-%m-%dT%H:%M:%S")
    
    local invocations=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Invocations \
        --dimensions Name=FunctionName,Value=$full_name \
        --start-time $start_time \
        --end-time $end_time \
        --period 3600 \
        --statistics Sum \
        --region $REGION \
        --output json 2>/dev/null | jq -r '.Datapoints[0].Sum // "0"')
    
    local errors=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Errors \
        --dimensions Name=FunctionName,Value=$full_name \
        --start-time $start_time \
        --end-time $end_time \
        --period 3600 \
        --statistics Sum \
        --region $REGION \
        --output json 2>/dev/null | jq -r '.Datapoints[0].Sum // "0"')
    
    local duration=$(aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Duration \
        --dimensions Name=FunctionName,Value=$full_name \
        --start-time $start_time \
        --end-time $end_time \
        --period 3600 \
        --statistics Average \
        --region $REGION \
        --output json 2>/dev/null | jq -r '.Datapoints[0].Average // "0"')
    
    echo "    Invocations (1h): $invocations"
    echo "    Errors (1h): $errors"
    echo "    Avg Duration: ${duration}ms"
    
    # Cảnh báo nếu có lỗi
    if [ "$errors" != "0" ] && [ "$errors" != "null" ]; then
        echo "    ⚠️  WARNING: Function has errors!"
    fi
}

# Function để kiểm tra CloudWatch Alarms
check_alarms() {
    echo "🚨 CloudWatch Alarms Status:"
    
    local alarms=$(aws cloudwatch describe-alarms \
        --alarm-name-prefix "order-processing-system-$STAGE" \
        --region $REGION \
        --output json 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo $alarms | jq -r '.MetricAlarms[] | "  \(.AlarmName): \(.StateValue) - \(.StateReason)"'
        
        # Đếm số alarms đang ALARM
        local alarm_count=$(echo $alarms | jq -r '.MetricAlarms[] | select(.StateValue=="ALARM") | .AlarmName' | wc -l)
        if [ "$alarm_count" -gt 0 ]; then
            echo "  ⚠️  WARNING: $alarm_count alarm(s) in ALARM state!"
        fi
    else
        echo "  ❌ Failed to get alarm status"
    fi
}

# Function để lấy DynamoDB metrics
get_dynamodb_metrics() {
    local table_name="order-processing-system-$STAGE-orders"
    
    echo "🗄️  DynamoDB Table: $table_name"
    
    # Lấy item count
    local item_count=$(aws dynamodb describe-table \
        --table-name $table_name \
        --region $REGION \
        --output json 2>/dev/null | jq -r '.Table.ItemCount // "0"')
    
    local table_size=$(aws dynamodb describe-table \
        --table-name $table_name \
        --region $REGION \
        --output json 2>/dev/null | jq -r '.Table.TableSizeBytes // "0"')
    
    echo "  Items: $item_count"
    echo "  Size: $table_size bytes"
}

# Main monitoring
echo "🔍 SQS Queues Status:"
get_queue_metrics "order-processing-system-$STAGE-order-processing"
get_queue_metrics "order-processing-system-$STAGE-email"
get_queue_metrics "order-processing-system-$STAGE-inventory"
echo ""

echo "🔍 SQS Dead Letter Queues:"
get_queue_metrics "order-processing-system-$STAGE-order-processing-dlq"
get_queue_metrics "order-processing-system-$STAGE-email-dlq"
get_queue_metrics "order-processing-system-$STAGE-inventory-dlq"
echo ""

echo "🔍 Lambda Functions Status:"
get_lambda_metrics "stripeWebhook"
get_lambda_metrics "orderProcessor"
get_lambda_metrics "emailProcessor"
get_lambda_metrics "inventoryProcessor"
echo ""

check_alarms
echo ""

get_dynamodb_metrics
echo ""

# Lấy recent logs nếu có lỗi
echo "📋 Recent Error Logs (last 10 minutes):"
local log_groups=$(aws logs describe-log-groups \
    --log-group-name-prefix "/aws/lambda/order-processing-system-$STAGE" \
    --region $REGION \
    --output json 2>/dev/null | jq -r '.logGroups[].logGroupName')

for log_group in $log_groups; do
    local errors=$(aws logs filter-log-events \
        --log-group-name "$log_group" \
        --start-time $(($(date +%s) * 1000 - 600000)) \
        --filter-pattern "ERROR" \
        --region $REGION \
        --output json 2>/dev/null | jq -r '.events[].message' | head -3)
    
    if [ ! -z "$errors" ]; then
        echo "  ❌ Errors in $log_group:"
        echo "$errors" | sed 's/^/    /'
    fi
done

echo ""
echo "✅ Monitoring completed at $(date)"
echo ""
echo "💡 Tips:"
echo "  - Run this script regularly to monitor system health"
echo "  - Set up CloudWatch dashboards for real-time monitoring"
echo "  - Configure SNS notifications for critical alarms"
echo "  - Use './scripts/logs.sh [function-name] [stage]' to view detailed logs"
