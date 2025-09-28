# 🚀 Simple CI/CD Pipeline

Pipeline đơn giản cho Order Processing System với 3 bước chính: Build → Security Scan → Deploy.

## 📋 Pipeline Overview

### Workflow: `simple-cicd.yml`
**Trigger**: Push to `main`/`develop`, Pull Request, Manual dispatch

**Jobs:**
1. 📦 **Build** - Build và package Lambda functions
2. 🔒 **Security Scan** - Trivy vulnerability scanning  
3. 🚀 **Deploy** - Deploy lên AWS (dev/prod)

## 🔄 Pipeline Flow

```
Push Code → Build Packages → Security Scan → Deploy to AWS
```

### 📦 Build Job:
- Setup Python 3.9
- Install dependencies
- Package Lambda functions thành zip files
- Upload artifacts

### 🔒 Security Scan Job:
- Trivy filesystem scan
- Upload SARIF results to GitHub Security
- Generate security report

### 🚀 Deploy Job:
- Configure AWS credentials
- Deploy CloudFormation infrastructure
- Update Lambda function code
- Verify deployment

## 🔧 Setup Instructions

### 1. GitHub Secrets
Cần cấu hình secrets trong GitHub repository:

```
AWS_ACCESS_KEY_ID      # AWS Access Key
AWS_SECRET_ACCESS_KEY  # AWS Secret Key
```

### 2. GitHub Environments
Tạo environments (optional):

- **development** - Auto-deploy từ `develop` branch
- **production** - Auto-deploy từ `main` branch

### 3. Branch Strategy
- `develop` → Deploy to dev environment
- `main` → Deploy to production environment

## 🚀 Deployment

### Development:
```bash
git push origin develop
# → Triggers: Build → Security Scan → Deploy to Dev
```

### Production:
```bash
git push origin main  
# → Triggers: Build → Security Scan → Deploy to Prod
```

### Manual Deploy:
```bash
# Go to GitHub Actions → Simple CI/CD → Run workflow
```

## 🔒 Security Features

### Trivy Scanning:
- ✅ Filesystem vulnerability scan
- ✅ Configuration security check
- ✅ SARIF report to GitHub Security tab
- ✅ Fail pipeline on critical vulnerabilities

### AWS Security:
- ✅ IAM credentials via GitHub Secrets
- ✅ Least privilege access
- ✅ Encrypted resources

## 📊 Pipeline Status

### Success Flow:
```
✅ Build → ✅ Security Scan → ✅ Deploy → 🎉 Complete
```

### Failure Scenarios:
```
❌ Build Failed → Stop pipeline
❌ Security Issues → Stop pipeline  
❌ Deploy Failed → Rollback available
```

## 🛠️ Local Development

### Test Build Locally:
```bash
# Install dependencies
pip install -r requirements.txt

# Build packages
mkdir -p dist
for handler in stripe_webhook order_processor email_processor inventory_processor; do
  mkdir -p "dist/$handler"
  cp "src/handlers/${handler}.py" "dist/$handler/"
  cp -r src/utils "dist/$handler/"
  touch "dist/$handler/__init__.py"
  touch "dist/$handler/utils/__init__.py"
  (cd "dist/$handler" && zip -r "../${handler}.zip" .)
done
```

### Run Security Scan:
```bash
# Install Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# Run scan
trivy fs .
```

### Deploy Manually:
```bash
# Deploy infrastructure
./scripts/deploy.sh dev ap-southeast-1

# Update Lambda code
aws lambda update-function-code \
  --function-name order-processing-system-dev-stripe-webhook \
  --zip-file fileb://dist/stripe_webhook.zip
```

## 🧹 Cleanup Resources

### Delete All AWS Resources:
```bash
./scripts/cleanup.sh dev ap-southeast-1
```

### Check Current Costs:
```bash
./scripts/check-costs.sh ap-southeast-1
```

## 🚨 Troubleshooting

### Common Issues:

#### Build Failed:
```bash
Error: No module named 'boto3'
```
**Solution**: Check requirements.txt và Python version

#### Security Scan Failed:
```bash
Error: Critical vulnerabilities found
```
**Solution**: Update dependencies hoặc fix security issues

#### Deploy Failed:
```bash
Error: Access Denied
```
**Solution**: Check AWS credentials và IAM permissions

#### Lambda Update Failed:
```bash
Error: Function not found
```
**Solution**: Deploy infrastructure trước khi update code

## 📈 Monitoring

### GitHub Actions:
- Build duration tracking
- Security scan results
- Deployment status
- Failure notifications

### AWS Monitoring:
- CloudWatch logs
- Lambda metrics
- API Gateway metrics
- Cost tracking

## 💡 Best Practices

### Code Quality:
- ✅ Keep functions small và focused
- ✅ Use proper error handling
- ✅ Add logging for debugging

### Security:
- 🔒 Never commit secrets
- 🔍 Regular security scans
- 🛡️ Update dependencies regularly

### Deployment:
- 🚀 Test in dev before prod
- 📋 Use infrastructure as code
- 🔄 Enable rollback capabilities

## 📚 Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Trivy Security Scanner](https://trivy.dev/)
- [AWS Lambda Guide](https://docs.aws.amazon.com/lambda/)
- [AWS CloudFormation](https://docs.aws.amazon.com/cloudformation/)
