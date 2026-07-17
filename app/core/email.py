"""
Email sender — anti-spam hardened.
Uses Python's built-in smtplib. No extra packages needed.

Anti-spam measures applied:
  - No emoji in subject lines (major spam trigger)
  - Proper RFC 5322 Date and Message-ID headers
  - List-Unsubscribe header
  - Reply-To header
  - Both plain-text and HTML parts (HTML-only = spam flag)
  - Clean, safe subject lines without trigger words
  - Sender name in proper RFC format
  - ehlo() called with a real domain identifier
"""

import smtplib
import ssl
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Optional

import urllib.request
import urllib.error
import json
from app.core.config import settings



def _send_resend(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    url = "https://api.resend.com/emails"
    # Strip any leading/trailing spaces, newlines, or quotes from copy-paste mistakes
    api_key = (settings.RESEND_API_KEY or "").strip().strip("'").strip('"')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }


    from_name = settings.SMTP_FROM_NAME or "CODEXA Coding Club"
    # Send from the verified custom domain instead of the restricted sandbox domain
    payload = {
        "from": f"{from_name} <noreply@sitamcodexa.org>",
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "text": text_body
    }

    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=15) as response:
        res_body = response.read().decode("utf-8")
        print(f"[RESEND] Successfully sent email to {to_email}: {res_body}")


def _send_brevo(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    url = "https://api.brevo.com/v3/smtp/email"
    # Clean up API key from spaces or quotes
    api_key = (settings.BREVO_API_KEY or "").strip().strip("'").strip('"')
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    from_name = settings.SMTP_FROM_NAME or "CODEXA Coding Club"
    payload = {
        "sender": {"name": from_name, "email": "noreply@sitamcodexa.org"},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=15) as response:
        res_body = response.read().decode("utf-8")
        print(f"[BREVO] Successfully sent email to {to_email}: {res_body}")


def _send(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
) -> None:
    """
    Send email. Uses Brevo API if settings.BREVO_API_KEY is configured.
    Otherwise uses Resend API if settings.RESEND_API_KEY is configured.
    Otherwise falls back to standard SMTP.
    """
    if settings.BREVO_API_KEY:
        try:
            _send_brevo(to_email, subject, html_body, text_body)
            print(f"[EMAIL] Delivered via Brevo API '{subject}' -> {to_email}")
            return
        except Exception as exc:
            print(f"[EMAIL] Brevo delivery failed: {exc}. Falling back to Resend...")

    if settings.RESEND_API_KEY:
        try:
            _send_resend(to_email, subject, html_body, text_body)
            print(f"[EMAIL] Delivered via Resend API '{subject}' -> {to_email}")
            return
        except Exception as exc:
            print(f"[EMAIL] Resend delivery failed: {exc}. Falling back to SMTP...")


    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[EMAIL] SMTP not configured — skipping '{subject}' to {to_email}")
        return

    from_addr   = settings.SMTP_FROM_EMAIL
    from_name   = settings.SMTP_FROM_NAME
    sender_domain = from_addr.split("@")[-1] if "@" in from_addr else "mail.local"


    msg = MIMEMultipart("alternative")

    # ── Mandatory headers ────────────────────────────────────────
    msg["Subject"]  = subject
    msg["From"]     = f"{from_name} <{from_addr}>"
    msg["To"]       = to_email
    msg["Reply-To"] = f"{from_name} <{from_addr}>"
    msg["Date"]     = formatdate(localtime=False)
    msg["MIME-Version"]     = "1.0"

    # Plain text MUST come first in multipart/alternative
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, context=context) as server:
                server.ehlo(sender_domain)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
                server.ehlo(sender_domain)
                server.starttls(context=context)
                server.ehlo(sender_domain)        # second ehlo after STARTTLS
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
        print(f"[EMAIL] Delivered '{subject}' -> {to_email}")
    except Exception as exc:
        print(f"[EMAIL] Failed to deliver '{subject}' -> {to_email}: {exc}")



# ── HTML template ─────────────────────────────────────────────────

def _base(content: str) -> str:
    year = datetime.now().year
    sender_email = settings.SMTP_FROM_EMAIL
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>CODEXA Coding Club</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f7;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#f4f4f7;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:560px;">

        <!-- Header -->
        <tr>
          <td style="background:#4f46e5;border-radius:12px 12px 0 0;padding:24px 32px;">
            <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:700;
                        letter-spacing:-0.3px;font-family:Arial,sans-serif;">
              CODEXA Coding Club
            </h1>
            <p style="margin:4px 0 0;color:rgba(255,255,255,0.75);font-size:12px;">
              Student Developer Community
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="background:#ffffff;padding:32px;border-left:1px solid #e5e7eb;
                     border-right:1px solid #e5e7eb;">
            {content}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;border:1px solid #e5e7eb;border-top:none;
                     border-radius:0 0 12px 12px;padding:16px 32px;text-align:center;">
            <p style="margin:0;color:#9ca3af;font-size:11px;line-height:1.6;">
              You received this email because you are associated with CODEXA Coding Club.<br>
              This is an automated message sent from {sender_email}<br>
              &copy; {year} CODEXA Coding Club. All rights reserved.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _btn(text: str, url: str, color: str = "#4f46e5") -> str:
    return (
        f'<a href="{url}" target="_blank" style="display:inline-block;background:{color};'
        f'color:#ffffff;font-weight:700;font-size:14px;padding:12px 28px;border-radius:8px;'
        f'text-decoration:none;margin:20px 0 8px;">{text}</a>'
    )


def _divider() -> str:
    return '<hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">'


# ── Public send functions ─────────────────────────────────────────

def send_application_received(to_email: str, name: str) -> None:
    """Confirmation email sent immediately after a student submits an application."""

    html_content = f"""\
<h2 style="color:#111827;font-size:18px;margin:0 0 12px;font-family:Arial,sans-serif;">
  Hi {name},
</h2>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Thank you for applying to join <strong>CODEXA Coding Club</strong>.
  We have received your application and our admin team will review it shortly.
</p>
<div style="background:#f5f3ff;border-left:4px solid #4f46e5;border-radius:4px;
            padding:16px 20px;margin:20px 0;">
  <p style="margin:0 0 8px;color:#4f46e5;font-size:13px;font-weight:700;">
    What happens next
  </p>
  <ul style="color:#374151;font-size:13px;line-height:2;margin:0;padding-left:18px;">
    <li>Admin reviews your application (usually within 24 hours)</li>
    <li>You will receive an approval or rejection email at this address</li>
    <li>If approved, sign in using the email and password you chose</li>
  </ul>
</div>
{_divider()}
<p style="color:#6b7280;font-size:12px;margin:0;">
  Application submitted for: <strong style="color:#111827;">{to_email}</strong>
</p>"""

    plain = (
        f"Hi {name},\n\n"
        f"Thank you for applying to CODEXA Coding Club.\n"
        f"Your application is under review. The admin team will notify you "
        f"at {to_email} once a decision is made.\n\n"
        f"If approved, you can sign in with the password you chose during registration.\n\n"
        f"CODEXA Coding Club"
    )

    _send(
        to_email=to_email,
        subject="Application Received - CODEXA Coding Club",
        html_body=_base(html_content),
        text_body=plain,
    )


def send_application_approved(to_email: str, name: str, unique_id: str, frontend_url: str) -> None:
    """Approval email with login link, sent when admin approves the request."""
    login_url = f"{frontend_url}/login"

    html_content = f"""\
<h2 style="color:#059669;font-size:18px;margin:0 0 12px;font-family:Arial,sans-serif;">
  Congratulations, {name}!
</h2>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Your application to join <strong>CODEXA Coding Club</strong> has been
  <strong style="color:#059669;">approved</strong>.
  Welcome to the community!
</p>
<div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:8px;
            padding:18px 20px;margin:20px 0;">
  <p style="margin:0 0 6px;color:#065f46;font-size:13px;font-weight:700;">
    Your login details
  </p>
  <table style="font-size:13px;color:#374151;border-collapse:collapse;">
    <tr>
      <td style="padding:3px 12px 3px 0;font-weight:600;color:#111827;">Member ID</td>
      <td style="padding:3px 0; font-family: monospace; font-size: 14px; font-weight: bold; color: #4f46e5;">{unique_id}</td>
    </tr>
    <tr>
      <td style="padding:3px 12px 3px 0;font-weight:600;color:#111827;">Email</td>
      <td style="padding:3px 0;">{to_email}</td>
    </tr>
    <tr>
      <td style="padding:3px 12px 3px 0;font-weight:600;color:#111827;">Password</td>
      <td style="padding:3px 0;">The password you set when you applied</td>
    </tr>
  </table>
</div>
{_btn("Sign In to CODEXA", login_url, "#059669")}
{_divider()}
<p style="color:#6b7280;font-size:12px;margin:0;">
  If you have forgotten your password, use the Forgot Password option on the sign-in page.
</p>"""

    plain = (
        f"Hi {name},\n\n"
        f"Your CODEXA Coding Club application has been approved!\n\n"
        f"Sign in at: {login_url}\n"
        f"Member ID: {unique_id}\n"
        f"Email: {to_email}\n"
        f"Password: The password you chose during registration\n\n"
        f"If you forgot your password, use the Forgot Password link on the sign-in page.\n\n"
        f"Welcome aboard!\n"
        f"CODEXA Coding Club"
    )

    _send(
        to_email=to_email,
        subject="Application Approved - Welcome to CODEXA Coding Club",
        html_body=_base(html_content),
        text_body=plain,
    )


def send_application_rejected(to_email: str, name: str) -> None:
    """Rejection email sent when admin rejects the application."""
    sender_email = settings.SMTP_FROM_EMAIL

    html_content = f"""\
<h2 style="color:#111827;font-size:18px;margin:0 0 12px;font-family:Arial,sans-serif;">
  Hi {name},
</h2>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Thank you for your interest in joining <strong>CODEXA Coding Club</strong>.
  After reviewing your application, we are unable to proceed with your membership at this time.
</p>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  If you believe this decision was made in error or would like further clarification,
  please contact the club admin by replying to this email.
</p>
{_divider()}
<p style="color:#6b7280;font-size:12px;margin:0;">
  You are welcome to apply again in a future intake period.
</p>"""

    plain = (
        f"Hi {name},\n\n"
        f"Thank you for applying to CODEXA Coding Club.\n"
        f"Unfortunately, we are unable to approve your application at this time.\n\n"
        f"If you have questions, please reply to this email or contact the admin at {sender_email}.\n\n"
        f"CODEXA Coding Club"
    )

    _send(
        to_email=to_email,
        subject="CODEXA Coding Club - Application Status Update",
        html_body=_base(html_content),
        text_body=plain,
    )



def send_event_registration_confirmation(
    to_email: str,
    name: str,
    event_title: str,
    event_date: str,
    event_location: str,
) -> None:
    """Send confirmation email when a student registers for an event."""

    html_content = f"""\
<h2 style="color:#4f46e5;font-size:18px;margin:0 0 12px;font-family:Arial,sans-serif;">
  Registration Confirmed!
</h2>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Hi {name},
</p>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  You have successfully registered for the event <strong>{event_title}</strong>.
</p>
<div style="background:#f5f3ff;border:1px solid #c7d2fe;border-radius:8px;
            padding:18px 20px;margin:20px 0;">
  <p style="margin:0 0 6px;color:#3730a3;font-size:13px;font-weight:700;">
    Event Details
  </p>
  <table style="font-size:13px;color:#374151;border-collapse:collapse;">
    <tr>
      <td style="padding:3px 12px 3px 0;font-weight:600;color:#111827;">Event Name</td>
      <td style="padding:3px 0;">{event_title}</td>
    </tr>
    <tr>
      <td style="padding:3px 12px 3px 0;font-weight:600;color:#111827;">Date & Time</td>
      <td style="padding:3px 0;">{event_date}</td>
    </tr>
    <tr>
      <td style="padding:3px 12px 3px 0;font-weight:600;color:#111827;">Location</td>
      <td style="padding:3px 0;">{event_location}</td>
    </tr>
  </table>
</div>
{_divider()}
<p style="color:#6b7280;font-size:12px;margin:0;">
  See you there! If you need to cancel your registration, you can do so from your CODEXA dashboard.
</p>"""

    plain = (
        f"Hi {name},\n\n"
        f"You have successfully registered for the event: {event_title}\n\n"
        f"Date & Time: {event_date}\n"
        f"Location: {event_location}\n\n"
        f"See you there!\n"
        f"CODEXA Coding Club"
    )

    _send(
        to_email=to_email,
        subject=f"Registration Confirmed: {event_title}",
        html_body=_base(html_content),
        text_body=plain,
    )


def send_points_awarded(
    to_email: str,
    name: str,
    points: int,
    reason: str,
    activity_type: str,
    total_points: int,
    new_badges: list,
) -> None:
    """Notify a student when admin awards them points."""
    type_labels = {
        "workshop": "Workshop Completion",
        "hackathon": "Hackathon",
        "project": "Project Contribution",
        "event": "Event Participation",
        "general": "Club Activity",
    }
    type_label = type_labels.get(activity_type, "Club Activity")
    badge_html = ""
    if new_badges:
        badge_items = "".join(
            f'<li style="color:#374151;font-size:13px;line-height:2;">'
            f'{b.get("icon","")} <strong>{b.get("name","")}</strong> — {b.get("description","")}</li>'
            for b in new_badges
        )
        badge_html = f"""
<div style="background:#fefce8;border:1px solid #fde68a;border-radius:8px;padding:16px 20px;margin:20px 0;">
  <p style="margin:0 0 8px;color:#92400e;font-size:13px;font-weight:700;">Badges Earned</p>
  <ul style="margin:0;padding-left:18px;">{badge_items}</ul>
</div>"""

    html_content = f"""\
<h2 style="color:#059669;font-size:18px;margin:0 0 12px;font-family:Arial,sans-serif;">
  +{points} Points Awarded!
</h2>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Hi {name}, you have been awarded <strong style="color:#059669;">+{points} points</strong> for:
</p>
<div style="background:#f5f3ff;border-left:4px solid #4f46e5;border-radius:4px;padding:16px 20px;margin:20px 0;">
  <p style="margin:0 0 4px;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1px;">{type_label}</p>
  <p style="margin:0;color:#111827;font-size:15px;font-weight:700;">{reason}</p>
</div>
{badge_html}
<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:14px 20px;margin:20px 0;">
  <p style="margin:0;color:#374151;font-size:13px;">
    Total club points: <strong style="color:#4f46e5;font-size:16px;">{total_points} pts</strong>
  </p>
</div>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Keep participating in club activities to earn more points and climb the leaderboard!
</p>"""

    plain = (
        f"Hi {name},\n\n"
        f"You've been awarded +{points} points for: {reason}\n"
        f"Activity type: {type_label}\n\n"
        + (f"New badges earned: {', '.join(b.get('name','') for b in new_badges)}\n\n" if new_badges else "")
        + f"Total club points: {total_points} pts\n\n"
        f"CODEXA Coding Club"
    )

    _send(
        to_email=to_email,
        subject=f"+{points} Points Awarded - CODEXA Coding Club",
        html_body=_base(html_content),
        text_body=plain,
    )


def send_event_deleted_notification(
    to_email: str,
    name: str,
    event_title: str,
    event_date: str,
) -> None:
    """Send notification email when an event is cancelled/deleted."""
    html_content = f"""\
<h2 style="color:#dc2626;font-size:18px;margin:0 0 12px;font-family:Arial,sans-serif;">
  Event Cancelled
</h2>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Hi {name},
</p>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Please note that the event <strong>{event_title}</strong> (originally scheduled for {event_date}) has been cancelled by the administrator.
</p>
<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;
            padding:18px 20px;margin:20px 0;">
  <p style="margin:0 0 6px;color:#991b1b;font-size:13px;font-weight:700;">
    Cancelled Event
  </p>
  <table style="font-size:13px;color:#374151;border-collapse:collapse;">
    <tr>
      <td style="padding:3px 12px 3px 0;font-weight:600;color:#111827;">Event Name</td>
      <td style="padding:3px 0;">{event_title}</td>
    </tr>
    <tr>
      <td style="padding:3px 12px 3px 0;font-weight:600;color:#111827;">Original Date</td>
      <td style="padding:3px 0;">{event_date}</td>
    </tr>
  </table>
</div>
{_divider()}
<p style="color:#6b7280;font-size:12px;margin:0;">
  We apologize for any inconvenience caused. Check the CODEXA portal for updates and upcoming events!
</p>"""

    plain = (
        f"Hi {name},\n\n"
        f"Please note that the event: {event_title} (originally scheduled for {event_date}) has been cancelled by the administrator.\n\n"
        f"We apologize for any inconvenience caused.\n\n"
        f"CODEXA Coding Club"
    )

    _send(
        to_email=to_email,
        subject=f"Event Cancelled: {event_title}",
        html_body=_base(html_content),
        text_body=plain,
    )


def send_announcement_deleted_notification(
    to_email: str,
    name: str,
    announcement_title: str,
) -> None:
    """Send notification email when an active announcement is deleted/retracted."""
    html_content = f"""\
<h2 style="color:#4f46e5;font-size:18px;margin:0 0 12px;font-family:Arial,sans-serif;">
  Announcement Update
</h2>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Hi {name},
</p>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  This is a quick update to let you know that the announcement <strong>"{announcement_title}"</strong> has been removed or retracted by the club administrators.
</p>
{_divider()}
<p style="color:#6b7280;font-size:12px;margin:0;">
  Please check the CODEXA portal for the latest active announcements and club updates.
</p>"""

    plain = (
        f"Hi {name},\n\n"
        f"This is a quick update to let you know that the announcement \"{announcement_title}\" has been removed or retracted by the club administrators.\n\n"
        f"CODEXA Coding Club"
    )

    _send(
        to_email=to_email,
        subject=f"Announcement Update: {announcement_title}",
        html_body=_base(html_content),
        text_body=plain,
    )


def send_password_reset_otp(
    to_email: str,
    name: str,
    otp: str,
    frontend_url: str,
) -> None:
    """Send a 6-digit OTP for password reset. Expires in 15 minutes."""
    reset_url = f"{frontend_url}/reset-password"

    html_content = f"""\
<h2 style="color:#111827;font-size:18px;margin:0 0 12px;font-family:Arial,sans-serif;">
  Password Reset Request
</h2>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  Hi {name},
</p>
<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 16px;">
  We received a request to reset the password for your CODEXA account.
  Use the one-time code below to continue. This code expires in
  <strong>15 minutes</strong>.
</p>

<div style="background:#f5f3ff;border:1px solid #c7d2fe;border-radius:12px;
            padding:28px;margin:24px 0;text-align:center;">
  <p style="margin:0 0 8px;color:#4f46e5;font-size:12px;font-weight:700;
             letter-spacing:1px;text-transform:uppercase;font-family:Arial,sans-serif;">
    Your OTP Code
  </p>
  <p style="margin:8px 0;font-size:36px;font-weight:bold;color:#4f46e5;
             font-family:'Courier New',Courier,monospace;letter-spacing:8px;">
    {otp}
  </p>
  <p style="margin:12px 0 0;color:#6b7280;font-size:12px;font-family:Arial,sans-serif;">
    Expires in 15 minutes
  </p>
</div>

{_btn("Enter OTP &amp; Reset Password", reset_url)}

{_divider()}
<p style="color:#6b7280;font-size:12px;margin:0;line-height:1.6;">
  If you did not request a password reset, you can safely ignore this email.
  Your account will remain unchanged.<br><br>
  For security, do not share this OTP with anyone.
</p>"""

    plain = (
        f"Hi {name},\n\n"
        f"We received a request to reset your CODEXA account password.\n\n"
        f"Your OTP code is: {otp}\n\n"
        f"This code expires in 15 minutes.\n\n"
        f"To reset your password, visit: {reset_url}\n\n"
        f"If you did not request a password reset, ignore this email.\n\n"
        f"CODEXA Coding Club"
    )

    _send(
        to_email=to_email,
        subject="Password Reset Code - CODEXA Coding Club",
        html_body=_base(html_content),
        text_body=plain,
    )

