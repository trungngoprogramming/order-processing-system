#!/bin/bash

# Script xem logs của Lambda functions
# Sử dụng: ./scripts/logs.sh [function-name] [stage] [region] [minutes]

set -e

# Parameters
FUNCTION_NAME=${1:-stripeWebhook}
STAGE=${2:-dev}
REGION=${3:-ap-southeast-1}
MINUTES=${4:-30}

FULL_FUNCTION_NAME="order-processing-system-$STAGE-$FUNCTION_NAME"
LOG_GROUP="/aws/lambda/$FULL_FUNCTION_NAME"

echo "📋 Lambda Function Logs"
echo "Function: $FULL_FUNCTION_NAME"
echo "Region: $REGION"
echo "Time Range: Last $MINUTES minutes"
echo "Log Group: $LOG_GROUP"
echo ""

# Kiểm tra log group có tồn tại không
if ! aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region $REGION --output text --query 'logGroups[0].logGroupName' 2>/dev/null | grep -q "$LOG_GROUP"; then
    echo "❌ Log group not found: $LOG_GROUP"
    echo ""
    echo "Available Lambda functions:"
    aws logs describe-log-groups \
        --log-group-name-prefix "/aws/lambda/order-processing-system-$STAGE" \
        --region $REGION \
        --output table \
        --query 'logGroups[].logGroupName' 2>/dev/null || echo "No log groups found"
    exit 1
fi

# Tính start time
START_TIME=$(($(date +%s) * 1000 - $MINUTES * 60 * 1000))

echo "🔍 Fetching logs..."

# Lấy logs
aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --start-time $START_TIME \
    --region $REGION \
    --output json | jq -r '.events[] | "\(.timestamp | strftime("%Y-%m-%d %H:%M:%S")) [\(.logStreamName | split("/") | .[2])] \(.message)"' | while IFS= read -r line; do
    
    # Color coding cho different log levels
    if echo "$line" | grep -q "ERROR\|Exception\|Traceback"; then
        echo -e "\033[31m$line\033[0m"  # Red for errors
    elif echo "$line" | grep -q "WARNING\|WARN"; then
        echo -e "\033[33m$line\033[0m"  # Yellow for warnings
    elif echo "$line" | grep -q "INFO"; then
        echo -e "\033[32m$line\033[0m"  # Green for info
    elif echo "$line" | grep -q "DEBUG"; then
        echo -e "\033[36m$line\033[0m"  # Cyan for debug
    else
        echo "$line"  # Default color
    fi
done

echo ""
echo "✅ Log fetch completed"
echo ""
echo "💡 Usage tips:"
echo "  - Use different function names: stripeWebhook, orderProcessor, emailProcessor, inventoryProcessor"
echo "  - Adjust time range: ./scripts/logs.sh $FUNCTION_NAME $STAGE $REGION 60  # Last 60 minutes"
echo "  - Follow logs in real-time: ./scripts/logs.sh $FUNCTION_NAME $STAGE $REGION 5 && watch -n 5 './scripts/logs.sh $FUNCTION_NAME $STAGE $REGION 5'"
echo "  - Filter for errors only: ./scripts/logs.sh $FUNCTION_NAME $STAGE $REGION 30 | grep -E 'ERROR|Exception'"
