#!/bin/bash

# Script kiểm tra chi phí AWS hiện tại
# Sử dụng: ./scripts/check-costs.sh [region]

set -e

REGION=${1:-ap-southeast-1}

echo "💰 AWS Cost Analysis"
echo "Region: $REGION"
echo "Time: $(date)"
echo ""

# Kiểm tra AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI first."
    exit 1
fi

# Kiểm tra AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run 'aws configure' first."
    exit 1
fi

echo "🔍 Checking current AWS resources and estimated costs..."
echo ""

# Kiểm tra CloudFormation stacks
echo "📊 CloudFormation Stacks:"
STACKS=$(aws cloudformation list-stacks --region $REGION --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[?contains(StackName, `order-processing`)].{Name:StackName,Status:StackStatus,Created:CreationTime}' --output table 2>/dev/null)

if [ $? -eq 0 ] && [ ! -z "$STACKS" ]; then
    echo "$STACKS"
else
    echo "  ✅ No order-processing stacks found"
fi

echo ""

# Kiểm tra Lambda functions
echo "⚡ Lambda Functions:"
LAMBDA_COUNT=$(aws lambda list-functions --region $REGION --query "length(Functions[?contains(FunctionName, 'order-processing')])" --output text 2>/dev/null || echo "0")
if [ "$LAMBDA_COUNT" -gt 0 ]; then
    aws lambda list-functions --region $REGION --query "Functions[?contains(FunctionName, 'order-processing')].{Name:FunctionName,Runtime:Runtime,Size:CodeSize,LastModified:LastModified}" --output table
    echo "  💰 Estimated cost: \$0.00 - \$5.00/month (depending on usage)"
else
    echo "  ✅ No Lambda functions found"
fi

echo ""

# Kiểm tra API Gateway
echo "🌐 API Gateway:"
API_COUNT=$(aws apigateway get-rest-apis --region $REGION --query "length(items[?contains(name, 'order-processing')])" --output text 2>/dev/null || echo "0")
if [ "$API_COUNT" -gt 0 ]; then
    aws apigateway get-rest-apis --region $REGION --query "items[?contains(name, 'order-processing')].{Name:name,Id:id,CreatedDate:createdDate}" --output table
    echo "  💰 Estimated cost: \$0.00 - \$10.00/month (depending on requests)"
else
    echo "  ✅ No API Gateways found"
fi

echo ""

# Kiểm tra DynamoDB tables
echo "🗄️  DynamoDB Tables:"
DYNAMO_TABLES=$(aws dynamodb list-tables --region $REGION --query "TableNames[?contains(@, 'order-processing')]" --output text 2>/dev/null || echo "")
if [ ! -z "$DYNAMO_TABLES" ]; then
    for table in $DYNAMO_TABLES; do
        aws dynamodb describe-table --table-name "$table" --region $REGION --query 'Table.{Name:TableName,Status:TableStatus,ItemCount:ItemCount,SizeBytes:TableSizeBytes,BillingMode:BillingModeSummary.BillingMode}' --output table
    done
    echo "  💰 Estimated cost: \$0.00 - \$25.00/month (Pay-per-request)"
else
    echo "  ✅ No DynamoDB tables found"
fi

echo ""

# Kiểm tra SQS queues
echo "📨 SQS Queues:"
SQS_QUEUES=$(aws sqs list-queues --region $REGION --queue-name-prefix "order-processing" --query 'QueueUrls' --output text 2>/dev/null || echo "")
if [ ! -z "$SQS_QUEUES" ]; then
    echo "  Found queues:"
    for queue_url in $SQS_QUEUES; do
        queue_name=$(basename "$queue_url")
        message_count=$(aws sqs get-queue-attributes --queue-url "$queue_url" --attribute-names ApproximateNumberOfMessages --region $REGION --query 'Attributes.ApproximateNumberOfMessages' --output text 2>/dev/null || echo "0")
        echo "    - $queue_name (Messages: $message_count)"
    done
    echo "  💰 Estimated cost: \$0.00 - \$1.00/month (first 1M requests free)"
else
    echo "  ✅ No SQS queues found"
fi

echo ""

# Kiểm tra SNS topics
echo "📢 SNS Topics:"
SNS_TOPICS=$(aws sns list-topics --region $REGION --query "Topics[?contains(TopicArn, 'order-processing')].TopicArn" --output text 2>/dev/null || echo "")
if [ ! -z "$SNS_TOPICS" ]; then
    for topic in $SNS_TOPICS; do
        topic_name=$(basename "$topic")
        echo "    - $topic_name"
    done
    echo "  💰 Estimated cost: \$0.00 - \$2.00/month (first 1M publishes free)"
else
    echo "  ✅ No SNS topics found"
fi

echo ""

# Kiểm tra CloudWatch Logs
echo "📋 CloudWatch Log Groups:"
LOG_GROUPS=$(aws logs describe-log-groups --region $REGION --log-group-name-prefix "/aws/lambda/order-processing" --query 'logGroups[].{Name:logGroupName,Size:storedBytes,Retention:retentionInDays}' --output table 2>/dev/null)
if [ $? -eq 0 ] && [ ! -z "$LOG_GROUPS" ]; then
    echo "$LOG_GROUPS"
    echo "  💰 Estimated cost: \$0.00 - \$5.00/month (depending on log volume)"
else
    echo "  ✅ No CloudWatch log groups found"
fi

echo ""

# Tổng kết chi phí ước tính
echo "💰 TOTAL ESTIMATED MONTHLY COST: \$0.00 - \$50.00"
echo ""
echo "📊 Cost Breakdown:"
echo "  - Lambda Functions: \$0.00 - \$5.00"
echo "  - API Gateway: \$0.00 - \$10.00"
echo "  - DynamoDB: \$0.00 - \$25.00"
echo "  - SQS: \$0.00 - \$1.00"
echo "  - SNS: \$0.00 - \$2.00"
echo "  - CloudWatch Logs: \$0.00 - \$5.00"
echo "  - Other services: \$0.00 - \$2.00"
echo ""
echo "💡 Cost Optimization Tips:"
echo "  1. 🗑️  Delete unused resources: ./scripts/cleanup.sh"
echo "  2. 📊 Set up billing alerts in AWS Console"
echo "  3. 🔄 Use AWS Free Tier when possible"
echo "  4. ⏰ Schedule resources to run only when needed"
echo "  5. 📈 Monitor usage with AWS Cost Explorer"
echo ""
echo "🚨 To avoid ALL charges, run: ./scripts/cleanup.sh"
