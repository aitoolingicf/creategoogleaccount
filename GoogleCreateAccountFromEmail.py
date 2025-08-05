#!/usr/bin/env python3
"""
Simple Google Workspace Account Automation for Non-Profits
Monitors email for account creation requests from authorized volunteers
"""

import os
import sys
import json
import logging
import smtplib
import imaplib
import email
import re
import secrets
import string
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

from googleapiclient.discovery import build
from google.oauth2 import service_account


# Simple configuration
class Config:
    def __init__(self):
        # Required environment variables (set in GitHub Secrets or deployment)
        self.GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', '/tmp/service-account.json')
        self.DOMAIN = os.getenv('DOMAIN')  # e.g., 'mynonprofit.org'
        self.EMAIL_HOST = os.getenv('EMAIL_HOST', 'imap.gmail.com')
        self.EMAIL_PORT = int(os.getenv('EMAIL_PORT', '993'))
        self.EMAIL_USER = os.getenv('EMAIL_USER')  # e.g., 'accounts@mynonprofit.org'
        self.EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')  # Gmail app password
        self.SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))

        # Simple authorization - comma-separated list of authorized emails
        self.AUTHORIZED_EMAILS = set([
            email.strip().lower()
            for email in os.getenv('AUTHORIZED_EMAILS', '').split(',')
            if email.strip()
        ])

        # Admin settings
        self.ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
        self.DEFAULT_ORG_UNIT = os.getenv('DEFAULT_ORG_UNIT', '/')
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

        # Validate required settings
        self._validate_config()

    def _validate_config(self):
        """Validate that required configuration is present"""
        required = ['DOMAIN', 'EMAIL_USER', 'EMAIL_PASSWORD', 'ADMIN_EMAIL']
        missing = [key for key in required if not getattr(self, key)]

        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")

        if not self.AUTHORIZED_EMAILS:
            raise ValueError("AUTHORIZED_EMAILS must be set")


config = Config()

# Set up logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SimpleAuth:
    """Simple email-based authorization for small non-profits"""

    def __init__(self, authorized_emails: set):
        self.authorized_emails = authorized_emails
        logger.info(f"Initialized with {len(authorized_emails)} authorized emails")

    def is_authorized(self, email: str) -> bool:
        """Check if email is authorized to create accounts"""
        # Clean up email address (remove display name if present)
        email_match = re.search(r'<([^>]+)>', email)
        if email_match:
            email = email_match.group(1)

        email = email.lower().strip()
        is_auth = email in self.authorized_emails

        if is_auth:
            logger.info(f"Authorized request from: {email}")
        else:
            logger.warning(f"Unauthorized request from: {email}")

        return is_auth


class GoogleWorkspaceManager:
    def __init__(self):
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Initialize Google Admin SDK service"""
        try:
            # Handle both file path and JSON string
            if os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE):
                credentials = service_account.Credentials.from_service_account_file(
                    config.GOOGLE_SERVICE_ACCOUNT_FILE,
                    scopes=['https://www.googleapis.com/auth/admin.directory.user']
                )
            else:
                # For Cloud Run - service account key as JSON string
                service_account_info = json.loads(os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '{}'))
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=['https://www.googleapis.com/auth/admin.directory.user']
                )

            self.service = build('admin', 'directory_v1', credentials=credentials)
            logger.info("Google Admin SDK service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Admin SDK: {e}")
            raise

    def create_user(self, user_data: Dict) -> Dict:
        """Create a new user account"""
        try:
            temp_password = self._generate_password()

            user = {
                'name': {
                    'givenName': user_data['first_name'],
                    'familyName': user_data['last_name']
                },
                'primaryEmail': f"{user_data['username']}@{config.DOMAIN}",
                'password': temp_password,
                'orgUnitPath': config.DEFAULT_ORG_UNIT,
                'changePasswordAtNextLogin': True,
                'suspended': False
            }

            # Add optional fields
            if user_data.get('department'):
                user['organizations'] = [{
                    'department': user_data['department'],
                    'primary': True
                }]

            result = self.service.users().insert(body=user).execute()
            result['temp_password'] = temp_password

            logger.info(f"Created user: {user['primaryEmail']}")
            return result

        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise

    def user_exists(self, email: str) -> bool:
        """Check if user already exists"""
        try:
            self.service.users().get(userKey=email).execute()
            return True
        except Exception:
            return False

    def _generate_password(self) -> str:
        """Generate secure temporary password"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(12))


class EmailProcessor:
    def __init__(self):
        self.mail = None

    def connect(self):
        """Connect to email server"""
        try:
            self.mail = imaplib.IMAP4_SSL(config.EMAIL_HOST, config.EMAIL_PORT)
            self.mail.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
            logger.info("Connected to email server")
        except Exception as e:
            logger.error(f"Email connection failed: {e}")
            raise

    def disconnect(self):
        """Disconnect from email server"""
        if self.mail:
            self.mail.close()
            self.mail.logout()

    def get_unread_messages(self) -> List[Dict]:
        """Get unread messages"""
        try:
            self.mail.select('INBOX')
            _, message_numbers = self.mail.search(None, 'UNSEEN')

            messages = []
            for num in message_numbers[0].split():
                _, msg_data = self.mail.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)

                messages.append({
                    'number': num,
                    'message': email_message,
                    'subject': email_message['subject'] or '',
                    'from': email_message['from'] or '',
                    'body': self._get_email_body(email_message)
                })

            return messages
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []

    def _get_email_body(self, email_message) -> str:
        """Extract text body from email"""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            return email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
        return ""

    def mark_as_read(self, message_number):
        """Mark email as read"""
        self.mail.store(message_number, '+FLAGS', '\\Seen')

    def send_notification(self, to_email: str, subject: str, body: str):
        """Send notification email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = config.EMAIL_USER
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
            server.starttls()
            server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)

            server.sendmail(config.EMAIL_USER, to_email, msg.as_string())
            server.quit()

            logger.info(f"Sent notification to {to_email}")
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")


class RequestParser:
    @staticmethod
    def parse_account_request(email_body: str, sender: str) -> Optional[Dict]:
        """Parse account creation request from email"""
        try:
            # Simple patterns for parsing
            patterns = {
                'first_name': r'(?:first[_\s]?name|fname)[:\s]+([a-zA-Z\s\-\.]+)',
                'last_name': r'(?:last[_\s]?name|lname|surname)[:\s]+([a-zA-Z\s\-\.]+)',
                'username': r'(?:username|user|email)[:\s]+([a-zA-Z0-9._-]+)',
                'department': r'(?:department|dept|team)[:\s]+([a-zA-Z\s\-]+)',
                'title': r'(?:title|position|role)[:\s]+([a-zA-Z\s\-]+)'
            }

            parsed_data = {'requester': sender}

            for field, pattern in patterns.items():
                match = re.search(pattern, email_body, re.IGNORECASE)
                if match:
                    parsed_data[field] = match.group(1).strip()

            # Validate required fields
            required = ['first_name', 'last_name', 'username']
            if all(field in parsed_data for field in required):
                logger.info(f"Parsed request for: {parsed_data['username']}")
                return parsed_data
            else:
                missing = [f for f in required if f not in parsed_data]
                logger.warning(f"Missing required fields: {missing}")
                return None

        except Exception as e:
            logger.error(f"Failed to parse request: {e}")
            return None


class NonProfitAccountAutomation:
    """Simple automation for non-profit organizations"""

    def __init__(self):
        self.gws_manager = GoogleWorkspaceManager()
        self.email_processor = EmailProcessor()
        self.auth = SimpleAuth(config.AUTHORIZED_EMAILS)
        self.parser = RequestParser()

    def process_requests(self):
        """Main processing method"""
        try:
            logger.info("Starting account creation check")

            self.email_processor.connect()
            messages = self.email_processor.get_unread_messages()

            if not messages:
                logger.info("No unread messages")
                return

            logger.info(f"Processing {len(messages)} messages")

            for msg in messages:
                self._process_single_request(msg)

        except Exception as e:
            logger.error(f"Error in main process: {e}")
            self._send_admin_alert(f"Automation error: {e}")
        finally:
            self.email_processor.disconnect()

    def _process_single_request(self, message: Dict):
        """Process a single email request"""
        try:
            sender = message['from']
            logger.info(f"Processing message from: {sender}")

            # Check authorization
            if not self.auth.is_authorized(sender):
                self._send_unauthorized_notification(sender)
                self.email_processor.mark_as_read(message['number'])
                return

            # Parse request
            user_data = self.parser.parse_account_request(message['body'], sender)
            if not user_data:
                self._send_invalid_format_notification(sender)
                self.email_processor.mark_as_read(message['number'])
                return

            # Check if user exists
            email_address = f"{user_data['username']}@{config.DOMAIN}"
            if self.gws_manager.user_exists(email_address):
                self._send_user_exists_notification(sender, email_address)
                self.email_processor.mark_as_read(message['number'])
                return

            # Create the account
            result = self.gws_manager.create_user(user_data)
            self._send_success_notification(user_data, result)

            # Mark as processed
            self.email_processor.mark_as_read(message['number'])

            logger.info(f"Successfully created account: {email_address}")

        except Exception as e:
            logger.error(f"Error processing request from {message['from']}: {e}")
            self._send_error_notification(message['from'], str(e))

    def _send_success_notification(self, user_data: Dict, result: Dict):
        """Send success notification"""
        subject = f"✅ Account Created: {user_data['username']}@{config.DOMAIN}"
        body = f"""Hello!

The Google Workspace account has been successfully created:

👤 Name: {user_data['first_name']} {user_data['last_name']}
📧 Email: {user_data['username']}@{config.DOMAIN}
🔐 Temporary Password: {result['temp_password']}
🏢 Department: {user_data.get('department', 'Not specified')}
💼 Title: {user_data.get('title', 'Not specified')}

⚠️ Important:
- The user must change their password on first login
- Please share these credentials securely with the new user
- The account may take a few minutes to become fully active

Best regards,
{config.DOMAIN} Account System
        """

        self.email_processor.send_notification(user_data['requester'], subject, body)

        # Notify admin
        admin_subject = f"New Account Created: {user_data['username']}@{config.DOMAIN}"
        admin_body = f"Account created for {user_data['first_name']} {user_data['last_name']} requested by {user_data['requester']}"
        self.email_processor.send_notification(config.ADMIN_EMAIL, admin_subject, admin_body)

    def _send_unauthorized_notification(self, sender: str):
        """Send unauthorized notification"""
        subject = "❌ Account Creation Request - Not Authorized"
        body = f"""Hello,

Your request to create a Google Workspace account could not be processed because your email address is not authorized to create accounts.

If you believe this is an error, please contact the administrator at {config.ADMIN_EMAIL}.

Best regards,
{config.DOMAIN} Account System
        """

        self.email_processor.send_notification(sender, subject, body)

        # Alert admin
        admin_subject = f"🚨 Unauthorized Account Request from {sender}"
        self.email_processor.send_notification(config.ADMIN_EMAIL, admin_subject,
                                               f"Unauthorized account creation attempt from {sender}")

    def _send_invalid_format_notification(self, sender: str):
        """Send invalid format notification"""
        subject = "❌ Account Creation Request - Invalid Format"
        body = f"""Hello,

Your account creation request could not be processed due to missing or invalid information.

Please use this format:

Subject: New Account Request

First Name: John
Last Name: Doe  
Username: john.doe
Department: Volunteers (optional)
Title: Volunteer Coordinator (optional)

Best regards,
{config.DOMAIN} Account System
        """

        self.email_processor.send_notification(sender, subject, body)

    def _send_user_exists_notification(self, sender: str, email_address: str):
        """Send user exists notification"""
        subject = "❌ Account Already Exists"
        body = f"""Hello,

The user {email_address} already exists in the system.

If you need to reset their password or modify their account, please contact the administrator at {config.ADMIN_EMAIL}.

Best regards,
{config.DOMAIN} Account System
        """

        self.email_processor.send_notification(sender, subject, body)

    def _send_error_notification(self, sender: str, error: str):
        """Send error notification"""
        subject = "❌ Account Creation Error"
        body = f"""Hello,

An error occurred while processing your account creation request:

Error: {error}

Please contact the administrator at {config.ADMIN_EMAIL} for assistance.

Best regards,
{config.DOMAIN} Account System
        """

        self.email_processor.send_notification(sender, subject, body)

    def _send_admin_alert(self, message: str):
        """Send admin alert"""
        subject = "🚨 Google Workspace Automation Alert"
        self.email_processor.send_notification(config.ADMIN_EMAIL, subject, message)


def main():
    """Main entry point"""
    try:
        automation = NonProfitAccountAutomation()
        automation.process_requests()
        logger.info("✅ Account automation completed successfully")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()