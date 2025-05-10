import os
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

class EmailConfig:
    """Configuration class for email service settings from environment variables."""
    def __init__(self):
        # Get all configuration from environment variables
        self.host = os.getenv("EMAIL_HOST", "smtp.gmail.com")
        self.port = int(os.getenv("EMAIL_PORT", "587"))
        self.username = os.getenv("EMAIL_USER", "")
        self.password = os.getenv("EMAIL_PASSWORD", "")
        self.use_tls = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
        self.from_email = self.username
        self.from_name = os.getenv("EMAIL_FROM_NAME", "Email Verification")

# Create a default email configuration from environment variables
email_config = EmailConfig()

def generate_verification_code(length=6):
    """Generate a random verification code."""
    return ''.join(random.choices(string.digits, k=length))

def get_code_expiry(minutes=10):
    """Set code expiry to specified minutes from now."""
    return datetime.now() + timedelta(minutes=minutes)

def send_verification_email(to_email, verification_code, config=None):
    """
    Send verification email with the provided code.
    
    Args:
        to_email: Recipient's email address
        verification_code: The verification code to send
        config: Optional EmailConfig instance. If not provided, uses the default.
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    # Use provided config or default
    cfg = config or email_config
    
    try:
        # Create message
        msg = MIMEMultipart()
        from_display = f"{cfg.from_name} <{cfg.from_email}>" if cfg.from_name else cfg.from_email
        msg['From'] = from_display
        msg['To'] = to_email
        msg['Subject'] = "Your Verification Code"
        
        # Email body
        body = f"""
        <html>
        <body>
            <h2>Email Verification</h2>
            <p>Your verification code is: <strong>{verification_code}</strong></p>
            <p>This code will expire in 10 minutes.</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        
        # Connect to server and send email - use TLS by default for port 587
        server = smtplib.SMTP(cfg.host, cfg.port)
        if cfg.use_tls:
            server.starttls()
        
        # Login with credentials
        server.login(cfg.username, cfg.password)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False