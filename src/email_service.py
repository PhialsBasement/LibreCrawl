"""
Email service for sending verification emails
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Tuple

# Load environment variables
def get_env(key: str, default: str = '') -> str:
    """Get environment variable with fallback"""
    return os.getenv(key, default)

# Email configuration
SMTP_HOST = get_env('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(get_env('SMTP_PORT', '587'))
SMTP_USER = get_env('SMTP_USER', '')
SMTP_PASSWORD = get_env('SMTP_PASSWORD', '')
SMTP_FROM = get_env('SMTP_FROM', 'noreply@librecrawl.com')
SMTP_FROM_NAME = get_env('SMTP_FROM_NAME', 'LibreCrawl')

# App URLs
MAIN_APP_URL = get_env('MAIN_APP_URL', 'https://crawl.librecrawl.com')
WORKSHOP_APP_URL = get_env('WORKSHOP_APP_URL', 'https://workshop.librecrawl.com')

def send_verification_email(to_email: str, username: str, token: str, app_source: str = 'main', is_resend: bool = False) -> Tuple[bool, str]:
    """
    Send verification email to user

    Args:
        to_email: Recipient email address
        username: Username of the user
        token: Verification token
        app_source: 'main' or 'workshop' - determines which app to redirect to

    Returns:
        (success, message)
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print("Warning: SMTP credentials not configured. Email not sent.")
        print(f"Verification link would be: {MAIN_APP_URL}/verify?token={token}")
        return False, "Email service not configured"

    try:
        # Determine which app to link to
        if app_source == 'workshop':
            app_name = "LibreCrawl Plugin Workshop"
            app_url = WORKSHOP_APP_URL
            verify_url = f"{WORKSHOP_APP_URL}/verify?token={token}"
        else:
            app_name = "LibreCrawl"
            app_url = MAIN_APP_URL
            verify_url = f"{MAIN_APP_URL}/verify?token={token}"

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Verify your {app_name} account'
        msg['From'] = f'{SMTP_FROM_NAME} <{SMTP_FROM}>'
        msg['To'] = to_email

        # Plain text version
        if is_resend:
            text = f"""
Hello {username},

We received a new registration request for {app_name} using this email address.

Since your previous registration was not verified, we've updated your account with the new username and password you provided, and we're sending you a new verification link.

Please verify your email address by clicking the link below:

{verify_url}

This link will expire in 24 hours.

If you did not request this, please ignore this email.

Best regards,
The LibreCrawl Team
"""
        else:
            text = f"""
Hello {username},

Thank you for registering with {app_name}!

Please verify your email address by clicking the link below:

{verify_url}

This link will expire in 24 hours.

If you did not create this account, please ignore this email.

Best regards,
The LibreCrawl Team
"""

        # HTML version
        if is_resend:
            resend_notice = f"""
        <div style="background: #fef3c7; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #f59e0b;">
            <strong>Note:</strong> We received a new registration request for this email address. Since your previous registration was not verified, we've updated your account with the new username and password you provided.
        </div>"""
        else:
            resend_notice = ""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .content {{
            background: #f9fafb;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            padding: 15px 30px;
            text-decoration: none !important;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            color: #6b7280;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{app_name}</h1>
    </div>
    <div class="content">
        <h2>Hello {username}!</h2>
        {resend_notice}
        <p>{'Thank you for registering' if not is_resend else 'Please verify your email address'} with {app_name}.</p>
        <p>Please verify your email address by clicking the button below:</p>
        <center>
            <a href="{verify_url}" class="button">Verify Email Address</a>
        </center>
        <p>Or copy and paste this link into your browser:</p>
        <p style="background: white; padding: 10px; border-radius: 5px; word-break: break-all;">
            {verify_url}
        </p>
        <div class="footer">
            <p>This link will expire in 24 hours.</p>
            <p>If you did not {'create this account' if not is_resend else 'request this'}, please ignore this email.</p>
        </div>
    </div>
</body>
</html>
"""

        # Attach both versions
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            # Only use TLS and login if credentials provided
            if SMTP_PORT != 25 and SMTP_USER and SMTP_PASSWORD:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        print(f"Verification email sent to {to_email}")
        return True, "Verification email sent successfully"

    except Exception as e:
        print(f"Error sending email: {e}")
        return False, f"Failed to send email: {str(e)}"

def send_welcome_email(to_email: str, username: str, app_source: str = 'main') -> Tuple[bool, str]:
    """
    Send welcome email after verification

    Args:
        to_email: Recipient email address
        username: Username of the user
        app_source: 'main' or 'workshop'

    Returns:
        (success, message)
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        return False, "Email service not configured"

    try:
        # Determine which app
        if app_source == 'workshop':
            app_name = "LibreCrawl Plugin Workshop"
            app_url = WORKSHOP_APP_URL
        else:
            app_name = "LibreCrawl"
            app_url = MAIN_APP_URL

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Welcome to {app_name}!'
        msg['From'] = f'{SMTP_FROM_NAME} <{SMTP_FROM}>'
        msg['To'] = to_email

        # Plain text version
        text = f"""
Hello {username},

Welcome to {app_name}!

Your account has been verified and you can now log in at:
{app_url}

Best regards,
The LibreCrawl Team
"""

        # HTML version
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .content {{
            background: #f9fafb;
            padding: 30px;
            border-radius: 0 0 10px 10px;
        }}
        .button {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            padding: 15px 30px;
            text-decoration: none !important;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Welcome to {app_name}!</h1>
    </div>
    <div class="content">
        <h2>Hello {username}!</h2>
        <p>Your account has been successfully verified.</p>
        <p>You can now log in and start using {app_name}:</p>
        <center>
            <a href="{app_url}" class="button">Go to {app_name}</a>
        </center>
    </div>
</body>
</html>
"""

        # Attach both versions
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)

        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            # Only use TLS and login if credentials provided
            if SMTP_PORT != 25 and SMTP_USER and SMTP_PASSWORD:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        return True, "Welcome email sent successfully"

    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False, f"Failed to send email: {str(e)}"
