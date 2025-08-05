# Quick Setup Guide for Non-Profits

This guide will get your Google Workspace account automation running in about 30 minutes.

## Prerequisites

- Google Workspace domain (e.g., `mynonprofit.org`)
- Gmail account for monitoring requests
- Google Cloud account (free tier is fine)
- GitHub account

## Step 1: Google Workspace Setup (10 minutes)

### 1.1 Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing one
3. Go to **IAM & Admin** → **Service Accounts**
4. Click **Create Service Account**:
   - Name: `gws-automation`
   - Description: `Google Workspace account automation`
5. Click **Create and Continue**
6. Skip role assignment for now
7. Click **Done**
8. Click on the created service account
9. Go to **Keys** tab → **Add Key** → **Create New Key**
10. Choose **JSON** and download the file
11. **Keep this file secure - never commit to GitHub!**

### 1.2 Enable Domain-Wide Delegation

1. In the service account details, click **Enable Domain-Wide Delegation**
2. Copy the **Client ID** (long number)
3. Go to [Google Admin Console](https://admin.google.com)
4. Navigate to **Security** → **API Controls** → **Domain-wide Delegation**
5. Click **Add new** and enter:
   - Client ID: (paste the copied Client ID)
   - OAuth Scopes: `https://www.googleapis.com/auth/admin.directory.user`
6. Click **Authorize**

### 1.3 Setup Gmail Account

1. Use existing Gmail or create new one (e.g., `accounts@mynonprofit.org`)
2. Enable 2-Factor Authentication
3. Generate App Password:
   - Go to Google Account settings
   - Security → App Passwords
   - Select app: Mail, device: Other
   - Name it "GWS Automation"
   - **Save the 16-character password**

## Step 2: GitHub Setup (5 minutes)

### 2.1 Fork Repository

1. Go to the GitHub repository
2. Click **Fork** to create your own copy
3. Clone your fork locally

### 2.2 Setup GitHub Secrets

In your GitHub repository, go to **Settings** → **Secrets and Variables** → **Actions**

Add these secrets:

| Secret Name | Value | Example |
|-------------|-------|---------|
| `GCP_PROJECT_ID` | Your Google Cloud project ID | `my-nonprofit-project` |
| `GCP_SA_KEY` | Contents of service account JSON file | `{"type": "service_account"...}` |
| `DOMAIN` | Your Google Workspace domain | `mynonprofit.org` |
| `EMAIL_USER` | Gmail address for monitoring | `accounts@mynonprofit.org` |
| `EMAIL_PASSWORD` | Gmail app password | `abcd efgh ijkl mnop` |
| `ADMIN_EMAIL` | Admin notification email | `admin@mynonprofit.org` |
| `AUTHORIZED_EMAILS` | Authorized requester emails | `director@mynonprofit.org,admin@mynonprofit.org` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account JSON as string | `{"type": "service_account"...}` |

**Important:** `GCP_SA_KEY` and `GOOGLE_SERVICE_ACCOUNT_JSON` should contain the exact same JSON content from your service account file.

## Step 3: Deploy to Cloud Run (10 minutes)

### 3.1 Enable APIs

In Google Cloud Console, enable these APIs:
- Cloud Run API
- Cloud Build API  
- Cloud Scheduler API

### 3.2 Deploy via GitHub Actions

1. Push any change to the `main` branch of your fork
2. GitHub Actions will automatically build and deploy
3. Check the **Actions** tab to monitor progress
4. Deployment takes about 5-10 minutes

### 3.3 Manual Deploy (Alternative)

If GitHub Actions doesn't work, deploy manually:

```bash
# Set your project
gcloud config set project YOUR-PROJECT-ID

# Deploy
gcloud run deploy gws-automation \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="DOMAIN=mynonprofit.org,EMAIL_USER=accounts@mynonprofit.org" \
  # ... add other env vars
```

## Step 4: Setup Scheduler (5 minutes)

Create a scheduled job to check for emails every 5 minutes:

```bash
# Get your service URL
SERVICE_URL=$(gcloud run services describe gws-automation --platform managed --region us-central1 --format 'value(status.url)')

# Create scheduler job
gcloud scheduler jobs create http gws-automation-trigger \
  --location=us-central1 \
  --schedule="*/5 * * * *" \
  --uri="$SERVICE_URL" \
  --http-method=POST
```

## Step 5: Test the System (5 minutes)

### 5.1 Send Test Email

From an authorized email address, send to your monitoring email:

```
To: accounts@mynonprofit.org
Subject: New Account Request

First Name: Test
Last Name: User
Username: test.user
Department: Volunteers
Title: Test Volunteer
```

### 5.2 Check Logs

```bash
# View Cloud Run logs
gcloud logs tail "resource.type=cloud_run_revision" --limit=50

# Or check in Cloud Console
# Logging → Logs Explorer → Filter by Cloud Run
```

### 5.3 Verify Account Creation

1. Check Google Admin Console for new user
2. Verify notification emails were sent
3. Test login with temporary password

## Troubleshooting

### Common Issues

**"Service account not found"**
- Verify service account JSON is correct in GitHub secrets
- Check domain-wide delegation is enabled

**"Not authorized" errors** 
- Verify sender email is in `AUTHORIZED_EMAILS`
- Check email format exactly matches

**"Email connection failed"**
- Verify Gmail app password is correct  
- Ensure 2FA is enabled on Gmail account
- Check IMAP is enabled in Gmail settings

**"No messages processed"**
- Verify scheduler is running (`gcloud scheduler jobs list`)
- Check if emails are marked as read
- Verify email format matches expected pattern

### Get Help

1. Check Cloud Run logs for detailed error messages
2. Verify all environment variables are set correctly
3. Test individual components (email connection, Google API, etc.)
4. Open GitHub issue with log details if stuck

## Security Notes

- **Never commit** service account files or credentials to GitHub
- Use GitHub Secrets for all sensitive configuration
- Regularly review authorized email list
- Monitor logs for unauthorized attempts
- Use strong, unique passwords for all accounts

## Cost Estimate

For typical small non-profit usage:
- **Cloud Run**: $0/month (free tier: 180,000 vCPU-seconds)
- **Cloud Scheduler**: $0.10/month
- **Gmail**: Free
- **Total**: ~$0.10/month

## Next Steps

- **Customize**: Modify code for your specific needs
- **Monitor**: Set up Cloud Monitoring alerts
- **Scale**: Add more authorized users as needed
- **Backup**: Export user data periodically

---

**🎉 You're all set!** Your volunteers can now create Google Workspace accounts by simply sending formatted emails.