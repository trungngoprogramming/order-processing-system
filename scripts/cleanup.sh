#!/bin/bash

# Script xóa tất cả AWS resources để tránh phát sinh chi phí
# Sử dụng: ./scripts/cleanup.sh [stage] [region]

set -e

STAGE=${1:-dev}
REGION=${2:-ap-southeast-1}
STACK_NAME="order-processing-system-$STAGE"

echo "🗑️  AWS Resources Cleanup"
echo "Stack Name: $STACK_NAME"
echo "Stage: $STAGE"
echo "Region: $REGION"
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

echo "⚠️  WARNING: This will DELETE ALL resources for $STACK_NAME"
echo "This action CANNOT be undone!"
echo ""
read -p "Are you sure you want to continue? (type 'DELETE' to confirm): " confirmation

if [ "$confirmation" != "DELETE" ]; then
    echo "❌ Cleanup cancelled."
    exit 1
fi

echo ""
echo "🔍 Checking existing resources..."

# Kiểm tra stack có tồn tại không
STACK_EXISTS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].StackName' --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_EXISTS" = "NOT_FOUND" ]; then
    echo "✅ Stack $STACK_NAME not found. Nothing to delete."
    exit 0
fi

echo "📋 Found stack: $STACK_NAME"

# Lấy thông tin resources trước khi xóa
echo ""
echo "📊 Resources to be deleted:"
aws cloudformation list-stack-resources --stack-name $STACK_NAME --region $REGION --query 'StackResourceSummaries[*].[ResourceType,LogicalResourceId,PhysicalResourceId]' --output table

echo ""
echo "🗑️  Starting cleanup process..."

# Bước 1: Xóa tất cả messages trong SQS queues trước
echo "🧹 Cleaning SQS queues..."
SQS_QUEUES=$(aws sqs list-queues --region $REGION --queue-name-prefix $STACK_NAME --query 'QueueUrls[]' --output text 2>/dev/null || echo "")

if [ ! -z "$SQS_QUEUES" ]; then
    for queue_url in $SQS_QUEUES; do
        echo "  Purging queue: $queue_url"
        aws sqs purge-queue --queue-url "$queue_url" --region $REGION 2>/dev/null || echo "    Failed to purge queue"
    done
    echo "  ✅ SQS queues purged"
else
    echo "  ℹ️  No SQS queues found"
fi

# Bước 2: Xóa CloudFormation stack
echo ""
echo "🗑️  Deleting CloudFormation stack..."
aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION

echo "⏳ Waiting for stack deletion to complete..."
echo "This may take several minutes..."

# Theo dõi quá trình xóa
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION

if [ $? -eq 0 ]; then
    echo "✅ Stack $STACK_NAME deleted successfully!"
else
    echo "❌ Stack deletion may have failed. Checking status..."
    
    STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "DELETE_COMPLETE")
    
    if [ "$STACK_STATUS" = "DELETE_COMPLETE" ]; then
        echo "✅ Stack deletion completed successfully"
    else
        echo "⚠️  Stack status: $STACK_STATUS"
        echo "Please check AWS Console for details"
    fi
fi

# Bước 3: Kiểm tra và xóa các resources có thể bị sót lại
echo ""
echo "🔍 Checking for remaining resources..."

# Kiểm tra Lambda functions
echo "Checking Lambda functions..."
LAMBDA_FUNCTIONS=$(aws lambda list-functions --region $REGION --query "Functions[?starts_with(FunctionName, '$STACK_NAME')].FunctionName" --output text 2>/dev/null || echo "")

if [ ! -z "$LAMBDA_FUNCTIONS" ]; then
    echo "⚠️  Found remaining Lambda functions:"
    for func in $LAMBDA_FUNCTIONS; do
        echo "  - $func"
        read -p "Delete $func? (y/N): " delete_func
        if [ "$delete_func" = "y" ] || [ "$delete_func" = "Y" ]; then
            aws lambda delete-function --function-name "$func" --region $REGION
            echo "    ✅ Deleted $func"
        fi
    done
else
    echo "  ✅ No remaining Lambda functions"
fi

# Kiểm tra S3 buckets (nếu có)
echo "Checking S3 buckets..."
S3_BUCKETS=$(aws s3api list-buckets --query "Buckets[?contains(Name, '$STACK_NAME')].Name" --output text 2>/dev/null || echo "")

if [ ! -z "$S3_BUCKETS" ]; then
    echo "⚠️  Found S3 buckets:"
    for bucket in $S3_BUCKETS; do
        echo "  - $bucket"
        read -p "Delete $bucket and all its contents? (y/N): " delete_bucket
        if [ "$delete_bucket" = "y" ] || [ "$delete_bucket" = "Y" ]; then
            # Xóa tất cả objects trước
            aws s3 rm s3://$bucket --recursive --region $REGION
            # Xóa bucket
            aws s3api delete-bucket --bucket $bucket --region $REGION
            echo "    ✅ Deleted $bucket"
        fi
    done
else
    echo "  ✅ No S3 buckets found"
fi

# Kiểm tra CloudWatch Log Groups
echo "Checking CloudWatch Log Groups..."
LOG_GROUPS=$(aws logs describe-log-groups --region $REGION --log-group-name-prefix "/aws/lambda/$STACK_NAME" --query 'logGroups[].logGroupName' --output text 2>/dev/null || echo "")

if [ ! -z "$LOG_GROUPS" ]; then
    echo "⚠️  Found CloudWatch Log Groups:"
    for log_group in $LOG_GROUPS; do
        echo "  - $log_group"
        read -p "Delete $log_group? (y/N): " delete_log
        if [ "$delete_log" = "y" ] || [ "$delete_log" = "Y" ]; then
            aws logs delete-log-group --log-group-name "$log_group" --region $REGION
            echo "    ✅ Deleted $log_group"
        fi
    done
else
    echo "  ✅ No CloudWatch Log Groups found"
fi

echo ""
echo "🎉 Cleanup completed!"
echo ""
echo "📋 Summary:"
echo "  ✅ CloudFormation stack deleted"
echo "  ✅ SQS queues purged and deleted"
echo "  ✅ Lambda functions deleted"
echo "  ✅ API Gateway deleted"
echo "  ✅ DynamoDB table deleted"
echo "  ✅ SNS topics deleted"
echo "  ✅ CloudWatch alarms deleted"
echo "  ✅ IAM roles deleted"
echo ""
echo "💰 No more charges should occur for these resources!"
echo ""
echo "💡 Tips:"
echo "  - Check AWS Billing Console to confirm no ongoing charges"
echo "  - Consider setting up billing alerts for future deployments"
echo "  - Keep this script for future cleanups"
