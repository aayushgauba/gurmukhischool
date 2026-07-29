import email
import imaplib
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import MailboxMessage


def mailbox_is_configured():
    return bool(
        settings.EMAIL_IMAP_HOST
        and settings.EMAIL_IMAP_USER
        and settings.EMAIL_IMAP_PASSWORD
    )


def _decoded_header(message, name):
    value = message.get(name, "")
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeError):
        return value


def _plain_body(message):
    candidates = message.walk() if message.is_multipart() else [message]
    for part in candidates:
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_content_type() != "text/plain":
            continue
        if "attachment" in (part.get("Content-Disposition") or "").lower():
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace").strip()
    return ""


def sync_inbox():
    if not mailbox_is_configured():
        raise ImproperlyConfigured("Incoming email is not configured.")

    connection_class = (
        imaplib.IMAP4_SSL if settings.EMAIL_IMAP_USE_SSL else imaplib.IMAP4
    )
    connection = connection_class(
        settings.EMAIL_IMAP_HOST,
        settings.EMAIL_IMAP_PORT,
        timeout=settings.EMAIL_TIMEOUT,
    )
    try:
        if settings.EMAIL_IMAP_USE_TLS:
            connection.starttls()
        connection.login(settings.EMAIL_IMAP_USER, settings.EMAIL_IMAP_PASSWORD)
        status, _ = connection.select(settings.EMAIL_IMAP_FOLDER, readonly=True)
        if status != "OK":
            raise RuntimeError("The configured mailbox folder could not be opened.")
        status, data = connection.uid("search", None, "ALL")
        if status != "OK":
            raise RuntimeError("The mailbox could not be searched.")
        uids = data[0].split()[-settings.EMAIL_IMAP_SYNC_LIMIT :]
        synced = 0
        for raw_uid in uids:
            uid = raw_uid.decode("ascii")
            status, payload = connection.uid("fetch", raw_uid, "(RFC822)")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            message = email.message_from_bytes(payload[0][1])
            sender = getaddresses([_decoded_header(message, "From")])
            recipients = getaddresses(
                [_decoded_header(message, "To"), _decoded_header(message, "Cc")]
            )
            try:
                received_at = parsedate_to_datetime(message.get("Date"))
                if received_at and timezone.is_naive(received_at):
                    received_at = timezone.make_aware(received_at)
            except (TypeError, ValueError, OverflowError):
                received_at = None
            MailboxMessage.objects.update_or_create(
                folder=settings.EMAIL_IMAP_FOLDER,
                uid=uid,
                defaults={
                    "message_id": message.get("Message-ID", "").strip(),
                    "sender_name": sender[0][0] if sender else "",
                    "sender_email": sender[0][1] if sender else "",
                    "recipients": ", ".join(
                        address for _name, address in recipients if address
                    ),
                    "subject": _decoded_header(message, "Subject"),
                    "body": _plain_body(message),
                    "received_at": received_at,
                },
            )
            synced += 1
        return synced
    finally:
        try:
            connection.logout()
        except imaplib.IMAP4.error:
            pass


def send_admin_email(mail_record, user=None):
    sender_name = mail_record.created_by_name
    if user is not None:
        sender_name = user.get_full_name() or user.username
    sender_name = sender_name or "Sikh Study Circle Administrator"
    signature = f"—\n{sender_name}\nSikh Study Circle of St. Louis"
    body = f"{mail_record.body.rstrip()}\n\n{signature}"
    email_message = EmailMultiAlternatives(
        subject=mail_record.subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[mail_record.recipient],
    )
    email_message.attach_alternative(
        render_to_string(
            "email/adminMailboxMessage.html",
            {
                "body": mail_record.body,
                "sender_name": sender_name,
            },
        ),
        "text/html",
    )
    return email_message.send(fail_silently=False)
