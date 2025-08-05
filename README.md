# Google Workspace Account Automation for Non-Profits

A simple, secure email-based automation system for creating Google Workspace accounts. Perfect for small non-profit organizations with volunteer staff.

## Features

- ✅ **Email-based requests** - Create accounts by sending formatted emails
- 🔐 **Simple authorization** - Only authorized emails can create accounts  
- 🚀 **Cloud-ready** - Runs on Google Cloud Run with minimal cost
- 📧 **Automatic notifications** - Success/error notifications via email
- 🔍 **Audit logging** - All activities are logged for security
- 💰 **Cost-effective** - Likely free under Cloud Run's generous free tier

## How It Works

1. **Authorized volunteer** sends formatted email request
2. **System validates** the request and authorization
3. **Account is created** in Google Workspace
4. **Notifications sent** to requester and admin
5. **New user** receives login credentials

## Email Request Format

Send an email to your configured accounts address:

```
Subject: New Account Request

First Name: Jane
Last Name: Smith
Username: jane.smith
Department: Volunteers
Title: Event Coordinator
```

## Quick Setup

### 1. Google Cloud Setup

[![Deploy to Cloud Run](https://deploy.cloud.run/button.svg)](https://deploy.cloud.run)

Or manually:

```bash
# Clone the repository
git clone https://github.com/yourusername/gws-account-automation.git
cd gws-account-automation

# Deploy to Cloud Run
gcloud run deploy gws-automation \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### 2. Environment Variables

Set these in your Cloud Run service or deployment environment:

| Variable | Description | Example |
|----------|-------------|---------|
| `DOMAIN` | Your Google Workspace domain | `mynonprofit.org` |
| `EMAIL_USER` | Email address to monitor | `accounts@mynonprofit.org` |
| `EMAIL_PASSWORD` | Gmail app password | `abcd efgh ijkl mnop` |
| `AUTHORIZED_EMAILS` | Comma-separated authorized emails | `admin@mynonprofit.org,hr@mynonprofit.org` |
| `ADMIN_EMAIL` | Admin notification email | `admin@mynonprofit.org` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account credentials (JSON string) | `{"type": "service_account"...}` |

### 3. Google Workspace Setup

1. **Create Service Account:**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new service account
   - Download the JSON key file

2. **Enable Domain-Wide Delegation:**
   - In Google Admin Console, go to Security > API Controls
   - Add the service account with scope: `https://www.googleapis.com/auth/admin.directory.user`

3. **Gmail App Password:**
   - Enable 2FA on your Gmail account
   - Generate an app password for the automation

### 4. Schedule with Cloud Scheduler

```bash
# Run every 5 minutes
gcloud scheduler jobs create http gws-automation-trigger \
  --schedule="*/5 * * * *" \
  --uri="YOUR_CLOUD_RUN_URL" \
  --http-method=POST
```

## Configuration

### Authorized Emails

Only emails in the `AUTHORIZED_EMAILS` list can create accounts:

```bash
AUTHORIZED_EMAILS=director@mynonprofit.org,admin@mynonprofit.org,hr@mynonprofit.org
```

### Email Setup

The system monitors a Gmail inbox for requests. Use a dedicated email like `accounts@mynonprofit.org`.

**Gmail Setup:**
1. Create/use a Gmail account
2. Enable 2-Factor Authentication  
3. Generate an App Password
4. Use the app password in `EMAIL_PASSWORD`

## Security

- **Authorization-only**: Only pre-approved emails can create accounts
- **Audit trail**: All activities logged with timestamps
- **Secure credentials**: Temporary passwords with forced password change
- **Error notifications**: Failed attempts alert administrators
- **No persistent storage**: No database or file storage of sensitive data

## Cost Estimate

For a typical small non-profit:
- **Cloud Run**: $0/month (within free tier)
- **Cloud Scheduler**: $0.10/month (1 job)
- **Gmail**: Free
- **Total**: ~$0.10/month

## Monitoring

Check logs in Google Cloud Console:

```bash
# View logs
gcloud logs tail "resource.type=cloud_run_revision"

# Check service status  
gcloud run services describe gws-automation --region=us-central1
```

## Troubleshooting

### Common Issues

**"Not authorized" errors:**
- Check if sender email is in `AUTHORIZED_EMAILS`
- Verify email addresses are exact matches (case-insensitive)

**"Service account" errors:**
- Verify domain-wide delegation is enabled
- Check service account has correct permissions
- Ensure JSON credentials are valid

**"Email connection" errors:**
- Verify Gmail app password is correct
- Check Gmail account has 2FA enabled
- Confirm email settings (IMAP enabled)

### Debug Mode

Set `LOG_LEVEL=DEBUG` to see detailed logs:

```bash
gcloud run services update gws-automation \
  --set-env-vars LOG_LEVEL=DEBUG
```

## Development

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DOMAIN="mynonprofit.org"
export EMAIL_USER="accounts@mynonprofit.org"
# ... other variables

# Run locally
python main.py
```

### Testing Requests

Send test emails to your configured email address using the format above.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues and questions:
- Check the [troubleshooting guide](#troubleshooting)
- Review logs in Google Cloud Console
- Open an issue on GitHub

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Made with ❤️ for non-profit organizations**