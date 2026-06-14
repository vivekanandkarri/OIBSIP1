"""Email handler module for PyVoice Assistant.

Composes and sends emails via smtplib and SSL, requiring user voice/text confirmation
before dispatching. Supports a clean mock mode for testing/demo.
"""

import os
import smtplib
import logging
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Callable, Dict, Optional
from handlers.base_handler import BaseHandler, HandlerError

logger = logging.getLogger("PyVoice.Handlers.Email")


class EmailHandler(BaseHandler):
    """Composes, drafts, and sends emails with interactive user confirmation."""

    # Predefined contact list for demo mapping of names to addresses
    DEMO_CONTACTS = {
        "Rahul": "rahul.demo@gmail.com",
        "Priya": "priya.demo@gmail.com",
        "John": "john.doe@demo.com",
        "Boss": "manager.work@company.com"
    }

    def execute(self, 
                entities: Dict[str, Any], 
                speak_fn: Optional[Callable[[str], None]] = None, 
                listen_fn: Optional[Callable[[], str]] = None) -> str:
        """Composes and dispatches an email using extracted entities.

        Args:
            entities: Extracted parameters (recipient_name, subject, body).
            speak_fn: Callback to speak text to user.
            listen_fn: Callback to listen to user voice/text response.

        Returns:
            Status message to speak to user.
        """
        # Resolve recipient
        name = entities.get("recipient_name")
        email_address = None

        if name:
            email_address = self.DEMO_CONTACTS.get(name)
            # If name is an email itself, parse it
            if not email_address and "@" in name:
                email_address = name.replace(" ", "")  # clean spaces

        # If no recipient resolved, ask user
        if not email_address:
            if speak_fn and listen_fn:
                speak_fn("Who would you like to send the email to?")
                try:
                    ans = listen_fn()
                    name = ans.title()
                    email_address = self.DEMO_CONTACTS.get(name)
                    if not email_address and "@" in ans:
                        email_address = ans.replace(" ", "")
                except Exception:
                    raise HandlerError("Failed to obtain recipient name.")
            
            if not email_address:
                raise HandlerError("Recipient email address or contact name is unknown.")

        # Resolve Subject and Body
        subject = entities.get("subject", "No Subject (Sent via PyVoice Assistant)")
        body = entities.get("body")

        if not body:
            if speak_fn and listen_fn:
                speak_fn("What is the body of the email?")
                try:
                    body = listen_fn()
                except Exception:
                    raise HandlerError("Failed to obtain email body.")
            
            if not body:
                body = "Draft sent from PyVoice Assistant."

        # Masking email address for logging privacy
        masked_email = self._mask_email(email_address)
        logger.info(f"Drafting email to {masked_email} with subject: '{subject}'")

        # Voice Confirmation Loop
        confirmed = False
        confirmation_prompt = f"I have drafted an email for {name or email_address} with subject '{subject}'. Should I send it?"
        
        if speak_fn and listen_fn:
            # Repeat up to 3 times for confirmation if unclear
            for attempt in range(3):
                speak_fn(confirmation_prompt)
                try:
                    response = listen_fn().lower()
                    if "yes" in response or "send" in response or "sure" in response or "okay" in response or "do it" in response:
                        confirmed = True
                        break
                    elif "no" in response or "cancel" in response or "don't" in response:
                        confirmed = False
                        break
                    else:
                        speak_fn("I didn't catch that. Please say yes to send, or no to cancel.")
                except Exception:
                    break
        else:
            # Fallback to auto-confirm if no callbacks (e.g. testing) or print to stdout
            print(f"\n[EMAIL DRAFT] To: {email_address} | Subject: {subject}\nBody: {body}\n")
            # Auto-confirm for command-line/testing unless specified otherwise
            confirmed = True

        if not confirmed:
            return "Email sending cancelled."

        # Send Email
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port_str = os.getenv("SMTP_PORT", "465")
        sender_email = os.getenv("SENDER_EMAIL")
        sender_password = os.getenv("SENDER_PASSWORD")

        # Port parsing with safety
        try:
            smtp_port = int(smtp_port_str)
        except ValueError:
            smtp_port = 465

        # If credentials are not set, run mock mode
        if not sender_email or not sender_password or sender_email.startswith("your_"):
            logger.info("SMTP Credentials missing or default. Mocking email delivery.")
            return f"Mock mode active. I have simulated sending the email to {name or email_address} successfully."

        try:
            # Create message structure
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email_address
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            # Send via SMTP SSL
            logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port} via SSL...")
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10.0) as server:
                server.login(sender_email, sender_password)
                server.send_mail(sender_email, email_address, msg.as_string())
            
            logger.info(f"Email successfully sent to {masked_email}")
            return f"The email has been sent to {name or email_address}."
        except Exception as e:
            logger.error(f"Failed to send email to {masked_email}: {e}")
            raise HandlerError(f"I was unable to send the email due to a network connection error: {e}")

    def _mask_email(self, email: str) -> str:
        """Utility to mask email address to protect privacy in logs.

        e.g., 'rahul.demo@gmail.com' -> 'r*********o@gmail.com'
        """
        if not email or "@" not in email:
            return email
        try:
            local, domain = email.split("@", 1)
            if len(local) <= 2:
                return f"{local[0]}*@{domain}"
            return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"
        except Exception:
            return "redacted@email.com"
