from datetime import datetime, timezone

import click

from models import Transaction
from mailer import send_email

DUE_SOON_DAYS = 5  # start warning 2 days before the 7-day grace period ends
GRACE_DAYS = 7


@click.command('send-due-reminders')
def send_due_reminders_command():
    """Email members whose loans are approaching or past the grace period.

    Intended to run daily via an external scheduler (cron, systemd timer, etc.) —
    this app has no in-process job scheduler.
    """
    now = datetime.now(timezone.utc)
    active = Transaction.query.filter_by(return_date=None).all()
    sent = 0
    skipped = 0
    for tr in active:
        issue_dt = tr.issue_date if tr.issue_date.tzinfo else tr.issue_date.replace(tzinfo=timezone.utc)
        days = (now - issue_dt).days
        if days < DUE_SOON_DAYS:
            continue
        member, book = tr.member, tr.book
        if not member or not member.email:
            skipped += 1
            continue
        title = book.title if book else 'a book'
        if days >= GRACE_DAYS:
            subject = f'Overdue: "{title}"'
            body = (f'Hi {member.name},\n\n"{title}" is now {days - GRACE_DAYS} day(s) overdue. '
                     'Please return it as soon as possible to avoid further fines.\n')
        else:
            subject = f'Reminder: "{title}" is due soon'
            body = f'Hi {member.name},\n\nJust a reminder that "{title}" is due in {GRACE_DAYS - days} day(s).\n'
        send_email(member.email, subject, body)
        sent += 1
    click.echo(f'Sent {sent} reminder(s). Skipped {skipped} loan(s) with no member email on file.')


def init_app(app):
    app.cli.add_command(send_due_reminders_command)
