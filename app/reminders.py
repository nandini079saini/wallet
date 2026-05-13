from datetime import date, datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Bill, User
from .config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
    REMINDER_DAYS_BEFORE,
)

def send_email(to_email: str, subject: str, body: str):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        print("Email config not set; skipping email")
        return

    print("==== SENDING EMAIL ====")
    print("SMTP_HOST:", SMTP_HOST)
    print("SMTP_USER:", SMTP_USER)
    print("TO:", to_email)

    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"✅ Sent reminder email to {to_email}")
    except Exception as e:
        print("❌ Error sending email:", repr(e))



def check_and_send_bill_reminders():
    today = date.today()
    db: Session = SessionLocal()
    try:
        bills = db.query(Bill).join(User).filter(Bill.is_active == True).all()

        for bill in bills:
            # Due date this month
            year = today.year
            month = today.month

            # If due_day > last day of month, clamp (e.g., 31st in Feb -> 28)
            # Simple version: ignore clamp, assume 1-28 used by user

            due_date = date(year, month, bill.due_day)
            reminder_date = due_date - timedelta(days=REMINDER_DAYS_BEFORE)

            if today == reminder_date:
                # Avoid sending twice if job runs multiple times
                if bill.last_notified == today:
                    continue

                user = db.query(User).filter(User.id == bill.user_id).first()
                if not user:
                    continue

                subject = f"Reminder: {bill.name} bill due on {due_date.strftime('%d %b')}"
                body = (
                    f"Hi {user.name},\n\n"
                    f"This is a reminder that your bill '{bill.name}' of amount {bill.amount} "
                    f"is due on {due_date.strftime('%d %b %Y')}.\n\n"
                    f"- Wallet App"
                )
                send_email(user.email, subject, body)

                bill.last_notified = today
                db.add(bill)

        db.commit()
    except Exception as e:
        print("Error in reminder job:", e)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")

    # Run once every day at 06:00 server time
    scheduler.add_job(
        check_and_send_bill_reminders,
        "cron",
        hour=6,
        minute=0,
        id="bill_reminders",
        replace_existing=True,
    )
    scheduler.start()
    print("Bill reminder scheduler started")
    return scheduler
