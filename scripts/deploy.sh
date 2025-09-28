#!/bin/bash

# Script deploy hệ thống order processing
# Sử dụng: ./scripts/deploy.sh [stage] [region] [secure]
# Ví dụ: ./scripts/deploy.sh dev ap-southeast-1 secure

set -e  # Exit on any error

# Default values
STAGE=${1:-dev}
REGION=${2:-ap-southeast-1}
SECURE=${3:-basic}

if [ "$SECURE" = "secure" ]; then
    STACK_NAME="order-processing-system-secure-$STAGE"
    TEMPLATE_FILE="cloudformation-secure.yaml"
    echo "🔒 Deploying SECURE Order Processing System"
else
    STACK_NAME="order-processing-system-$STAGE"
    TEMPLATE_FILE="cloudformation-template.yaml"
    echo "🚀 Deploying Order Processing System (Basic)"
fi

echo "Stack Name: $STACK_NAME"
echo "Stage: $STAGE"
echo "Region: $REGION"
echo "Template: $TEMPLATE_FILE"

# Kiểm tra dependencies
echo "📋 Checking dependencies..."

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

# Kiểm tra template file tồn tại
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "❌ Template file not found: $TEMPLATE_FILE"
    exit 1
fi

if [ "$SECURE" = "secure" ]; then
    echo "🏗️ Deploying secure infrastructure với CloudFormation..."
    echo "  ✅ VPC với Public/Private Subnets"
    echo "  ✅ NAT Gateway cho Private Subnets"
    echo "  ✅ VPC Endpoints cho AWS services"
    echo "  ✅ Security Groups với Least Privilege"
    echo "  ✅ IAM Roles với Least Privilege"
    echo "  ✅ Encrypted SQS, SNS, DynamoDB, Secrets"
    echo ""
    
    # Deploy secure CloudFormation stack
    aws cloudformation deploy \
        --template-file $TEMPLATE_FILE \
        --stack-name $STACK_NAME \
        --region $REGION \
        --capabilities CAPABILITY_NAMED_IAM \
        --parameter-overrides Stage=$STAGE VpcCidr=10.0.0.0/16
else
    echo "🏗️ Deploying basic infrastructure với CloudFormation..."
    
    # Deploy basic CloudFormation stack
    aws cloudformation deploy \
        --template-file $TEMPLATE_FILE \
        --stack-name $STACK_NAME \
        --region $REGION \
        --capabilities CAPABILITY_NAMED_IAM \
        --parameter-overrides Stage=$STAGE
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment completed successfully!"
    echo ""
    
    # Lấy thông tin outputs
    echo "📊 Stack Information:"
    aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table 2>/dev/null || echo "No outputs available"
    
    echo ""
    echo "📋 Deployment Summary:"
    echo "  Stack Name: $STACK_NAME"
    echo "  Stage: $STAGE"
    echo "  Region: $REGION"
    echo "  Template: $TEMPLATE_FILE"
    
    if [ "$SECURE" = "secure" ]; then
        echo "  Security: 🔒 SECURE (VPC + Least Privilege + Encryption)"
        echo ""
        echo "🔐 Security Features Implemented:"
        echo "  ✅ VPC với Public (10.0.1.0/24, 10.0.2.0/24) và Private Subnets (10.0.10.0/24, 10.0.11.0/24)"
        echo "  ✅ NAT Gateway cho outbound traffic từ Private Subnets"
        echo "  ✅ VPC Endpoints cho DynamoDB, S3, SNS, SQS, Secrets Manager"
        echo "  ✅ Security Groups chỉ cho phép traffic cần thiết"
        echo "  ✅ IAM Roles với Least Privilege cho từng Lambda function"
        echo "  ✅ Encryption at rest cho DynamoDB, SQS, SNS, Secrets Manager"
        echo "  ✅ CloudWatch monitoring và alarms"
    else
        echo "  Security: ⚠️  BASIC (No VPC, Basic IAM)"
    fi
    
    echo ""
    # Lấy Webhook URL từ outputs
    WEBHOOK_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
        --output text 2>/dev/null || echo "Not available")
    
    if [ "$WEBHOOK_URL" != "Not available" ] && [ "$WEBHOOK_URL" != "None" ]; then
        echo ""
        echo "🔗 Stripe Webhook URL: $WEBHOOK_URL"
    fi
    
    echo ""
    echo "🔧 Next Steps:"
    echo "1. Cập nhật Secrets Manager với Stripe credentials:"
    echo "   aws secretsmanager update-secret \\"
    echo "     --secret-id $STACK_NAME-secrets \\"
    echo "     --secret-string '{\"stripe_webhook_secret\":\"whsec_your_secret\",\"stripe_api_key\":\"sk_your_key\",\"ses_from_email\":\"your@email.com\"}' \\"
    echo "     --region $REGION"
    echo ""
    echo "2. Verify SES email address:"
    echo "   aws ses verify-email-identity --email-address your@email.com --region $REGION"
    echo ""
    
    if [ "$WEBHOOK_URL" != "Not available" ] && [ "$WEBHOOK_URL" != "None" ]; then
        echo "3. Configure Stripe webhook endpoint:"
        echo "   Webhook URL: $WEBHOOK_URL"
        echo "   Events: checkout.session.completed, payment_intent.succeeded, invoice.payment_succeeded"
        echo ""
        echo "4. Update Lambda function code (hiện tại chỉ là placeholder):"
        echo "   aws lambda update-function-code --function-name $STACK_NAME-stripe-webhook --zip-file fileb://lambda-code.zip --region $REGION"
        echo ""
    fi
    
    if [ "$SECURE" = "secure" ]; then
        echo "3. Deploy Lambda functions vào Private Subnets (cần thêm bước này)"
        echo ""
        echo "4. Test security với penetration testing"
        echo ""
        echo "🛡️ Security Checklist:"
        echo "  ✅ VPC với Public/Private Subnets"
        echo "  ✅ Least Privilege IAM Roles"
        echo "  ✅ No hardcoded secrets (sử dụng Secrets Manager)"
        echo "  ✅ Encryption at rest và in transit"
        echo "  ✅ Network isolation với Security Groups"
        echo "  ✅ VPC Endpoints để tránh Internet traffic"
        echo "  ✅ CloudWatch monitoring và alerting"
        echo "  ✅ Dead Letter Queues cho error handling"
    else
        echo "3. Configure Stripe webhook endpoint (cần API Gateway)"
        echo ""
        echo "4. Test the system:"
        echo "   ./scripts/test_webhook.sh $STAGE $REGION"
        echo ""
        echo "💡 Để deploy phiên bản secure:"
        echo "   ./scripts/deploy.sh $STAGE $REGION secure"
    fi
    
    echo ""
    
else
    echo "❌ Deployment failed!"
    exit 1
fi
