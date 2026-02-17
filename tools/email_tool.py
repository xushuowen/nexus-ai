"""Email sending tool via SMTP."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class EmailTool(BaseTool):
    name = "email"
    description = "Send an email via SMTP"
    category = "communication"
    requires_confirmation = True
    parameters = [
        ToolParameter("to", "string", "Recipient email address"),
        ToolParameter("subject", "string", "Email subject"),
        ToolParameter("body", "string", "Email body text"),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        to_addr = kwargs["to"]
        subject = kwargs["subject"]
        body = kwargs["body"]

        smtp_host = os.getenv("SMTP_HOST", "")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_pass = os.getenv("SMTP_PASS", "")

        if not smtp_host or not smtp_user:
            return ToolResult(
                success=False, output="",
                error="SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASS env vars."
            )

        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = to_addr
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            return ToolResult(success=True, output=f"Email sent to {to_addr}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to send: {e}")
