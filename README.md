# 🛒 Order Processing System
Hệ thống xử lý đơn hàng serverless hoàn chỉnh sử dụng AWS Lambda, SNS, SQS, DynamoDB và SES để xử lý webhook từ Stripe một cách tự động và có khả năng mở rộng cao.

## ✨ Tính năng chính

- 🔄 **Xử lý webhook Stripe tự động** với signature verification
- 📧 **Gửi email xác nhận** cho khách hàng qua Amazon SES  
- 📦 **Quản lý inventory** và thông báo kho hàng
- 🔒 **Bảo mật cao** với AWS Secrets Manager và IAM roles
- 📊 **Monitoring đầy đủ** với CloudWatch và alarms
- ⚡ **Serverless** - auto-scaling và pay-per-use
- 🏗️ **Infrastructure as Code** với CloudFormation

## 🏗️ Kiến trúc hệ thống

```
API Gateway → Lambda (Stripe Webhook) → SNS Topic
                                           ↓
                    ┌─────────────────────────────────────┐
                    ↓                     ↓               ↓
            Order Processing SQS    Email SQS    Inventory SQS
                    ↓                     ↓               ↓
            Order Processor     Email Processor  Inventory Processor
                    ↓                     ↓               ↓
                DynamoDB              Amazon SES    Warehouse System
```

### Thành phần chính:

- **API Gateway**: Nhận webhook từ Stripe
- **Lambda Functions**: 
  - `stripeWebhook`: Xác thực Stripe webhook và publish tới SNS
  - `orderProcessor`: Xử lý đơn hàng và lưu vào DynamoDB
  - `emailProcessor`: Gửi email xác nhận qua SES
  - `inventoryProcessor`: Thông báo cho hệ thống kho
- **SNS Topic**: Phân phối message tới các SQS queues
- **SQS Queues**: Hàng đợi message với Dead Letter Queues (DLQ)
- **DynamoDB**: Lưu trữ thông tin đơn hàng
- **SES**: Gửi email
- **Secrets Manager**: Quản lý API keys và secrets
- **CloudWatch**: Monitoring và alerting

## 🚀 Cài đặt và Deploy

### Yêu cầu hệ thống:

- **Node.js** 18+ và npm
- **Python** 3.9+
- **AWS CLI** đã cấu hình với appropriate permissions
- **AWS Account** với quyền tạo CloudFormation stacks
- **Stripe Account** để lấy API keys và webhook secrets

### Bước 1: Cài đặt dependencies

```bash
# Clone repository
git clone https://github.com/your-org/order-processing-system.git
cd order-processing-system

# Cài đặt project dependencies
npm install

# Tạo Python virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Bước 2: Cấu hình AWS

```bash
# Cấu hình AWS credentials
aws configure

# Verify SES email (thay your@email.com bằng email thực)
aws ses verify-email-identity --email-address your@email.com --region ap-southeast-1
```

### Bước 3: Deploy hệ thống

```bash
# Deploy development environment (basic)
./scripts/deploy.sh dev ap-southeast-1

# Deploy development environment (secure với VPC)
./scripts/deploy.sh dev ap-southeast-1 secure

# Deploy production environment (secure - khuyến nghị)
./scripts/deploy.sh prod ap-southeast-1 secure

# Hoặc sử dụng npm scripts:
npm run deploy          # dev basic
npm run deploy:prod     # prod basic
```

### Bước 4: Cấu hình Secrets

```bash
# Cập nhật Stripe credentials trong Secrets Manager
aws secretsmanager update-secret \
  --secret-id order-processing-system-dev-secrets \
  --secret-string '{
    "stripe_webhook_secret": "whsec_your_stripe_webhook_secret",
    "stripe_api_key": "sk_test_your_stripe_api_key", 
    "ses_from_email": "your@email.com"
  }' \
  --region ap-southeast-1
```

### Bước 5: Cấu hình Stripe Webhook

1. Đăng nhập vào Stripe Dashboard
2. Vào **Developers > Webhooks**
3. Tạo endpoint mới với URL từ deployment output
4. Chọn events: `checkout.session.completed`, `payment_intent.succeeded`, `invoice.payment_succeeded`
5. Copy webhook signing secret và cập nhật vào Secrets Manager

## 🧪 Testing

```bash
# Test webhook endpoint
npm run test

# Xem logs của function cụ thể
npm run logs stripeWebhook

# Monitor hệ thống
npm run monitor
```

## 📊 Monitoring

### CloudWatch Alarms được cấu hình:

- **SQS Queue Messages**: Cảnh báo khi có quá nhiều message chờ xử lý
- **DLQ Messages**: Cảnh báo khi có message trong Dead Letter Queue
- **Lambda Errors**: Theo dõi lỗi trong các Lambda functions

### Scripts monitoring:

```bash
# Xem tổng quan hệ thống
./scripts/monitor.sh [stage] [region]

# Xem logs chi tiết
./scripts/logs.sh [function-name] [stage] [region] [minutes]

# Test webhook
./scripts/test_webhook.sh [stage] [region]
```

## 🔧 Cấu hình

### Environment Variables:

- `STAGE`: Environment (dev/prod)
- `SNS_TOPIC_ARN`: ARN của SNS topic
- `ORDERS_TABLE`: Tên DynamoDB table
- `SECRETS_MANAGER_ARN`: ARN của Secrets Manager

### Secrets Manager:

```json
{
  "stripe_webhook_secret": "whsec_...",
  "stripe_api_key": "sk_...",
  "ses_from_email": "noreply@yourdomain.com"
}
```

## 📝 Luồng xử lý

### 1. Webhook từ Stripe:
```
POST /webhook/stripe
├── Xác thực signature
├── Parse event data  
└── Publish tới SNS topic
```

### 2. Xử lý đơn hàng:
```
SNS → Order Processing SQS → Lambda
├── Lưu order vào DynamoDB
├── Cập nhật status
└── Gửi metrics tới CloudWatch
```

### 3. Gửi email:
```
SNS → Email SQS → Lambda  
├── Tạo email content
├── Gửi qua SES
└── Log kết quả
```

### 4. Thông báo kho:
```
SNS → Inventory SQS → Lambda
├── Parse product info
├── Reserve inventory
└── Notify warehouse system
```

## 🚨 Error Handling

- **Dead Letter Queues**: Messages thất bại sẽ được chuyển tới DLQ sau 3 lần retry
- **CloudWatch Alarms**: Cảnh báo khi có lỗi hoặc message tích tụ
- **Structured Logging**: Tất cả logs được format để dễ search và debug

## 📈 Scaling

- **Lambda**: Auto-scaling theo traffic
- **SQS**: Unlimited throughput
- **DynamoDB**: On-demand billing mode
- **SNS**: Tự động scale theo subscribers

## 🛠️ Development

### Cấu trúc project:

```
├── src/
│   ├── handlers/          # Lambda function handlers
│   └── utils/            # Utility functions
├── scripts/              # Deployment và monitoring scripts
├── serverless.yml        # Serverless configuration
├── requirements.txt      # Python dependencies
└── package.json         # Node.js dependencies
```

### Local development:

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests (if available)
pytest tests/
```

### Debug Commands:
```bash
# Kiểm tra logs của function cụ thể
./scripts/logs.sh stripe-webhook dev ap-southeast-1

# Monitor tổng quan hệ thống
./scripts/monitor.sh dev ap-southeast-1

# Test webhook endpoint
./scripts/test_webhook.sh dev ap-southeast-1

# Kiểm tra chi phí AWS
./scripts/check-costs.sh
```
