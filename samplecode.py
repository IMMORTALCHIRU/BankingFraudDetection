#!/usr/bin/env python3
import os
import smtplib
from email.message import EmailMessage


def send_email(smtp_user, app_password, to_email, subject=None, body=None):
	subject = subject or "Test email from samplecode.py"
	body = body or "This is a test email sent via Gmail SMTP using an app password."

	msg = EmailMessage()
	msg["Subject"] = subject
	msg["From"] = smtp_user
	msg["To"] = to_email
	msg.set_content(body)

	try:
		with smtplib.SMTP("smtp.gmail.com", 587) as server:
			server.ehlo()
			server.starttls()
			server.ehlo()
			server.login(smtp_user, app_password)
			server.send_message(msg)
		return True, "Email sent successfully"
	except Exception as e:
		return False, str(e)


def main():
	# WARNING: hardcoding secrets is unsafe. Prefer environment variables.
	smtp_user = os.environ.get("SMTP_USER", "bhavanimutagar7@gmail.com")
	app_password = os.environ.get("SMTP_APP_PASSWORD", "natqxjssmkwyfyxx")
	to_email = os.environ.get("TO_EMAIL", "chiru38038@gmail.com")

	ok, info = send_email(smtp_user, app_password, to_email)
	if ok:
		print(f"Email successfully sent to {to_email}")
		print(info)
	else:
		print(f"Failed to send email: {info}")


if __name__ == "__main__":
	main()

