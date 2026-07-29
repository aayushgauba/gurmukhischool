import logging
import hashlib
import hmac

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.tasks import task
from django.template.loader import render_to_string
from django.utils import timezone

from portal.models import CustomUser

from .mailbox import mailbox_is_configured, send_admin_email, sync_inbox
from .models import Contact, MailDraft, MailboxMessage, TwoFactorEmailDelivery
from .spam_classifier import is_likely_spam, learn_spam_terms


logger = logging.getLogger(__name__)


def two_factor_code_for_nonce(nonce):
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        nonce.encode(),
        hashlib.sha256,
    ).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def _mailbox_text(message):
    return "\n".join(part for part in [message.subject, message.body] if part)


@task
def classify_spam_messages():
    spam_messages = list(
        Contact.objects.filter(is_spam=True, spam_reviewed=True).values_list(
            "message",
            flat=True,
        )
    )
    spam_messages.extend(
        _mailbox_text(message)
        for message in MailboxMessage.objects.filter(
            is_spam=True,
            spam_reviewed=True,
        ).only("subject", "body")
    )
    legitimate_messages = list(
        Contact.objects.filter(
            is_spam=False,
            spam_reviewed=True,
        ).values_list("message", flat=True)
    )
    legitimate_messages.extend(
        _mailbox_text(message)
        for message in MailboxMessage.objects.filter(
            is_spam=False,
            spam_reviewed=True,
        ).only(
            "subject",
            "body",
        )
    )

    learned_terms = learn_spam_terms(spam_messages, legitimate_messages)
    contact_spam_ids = []
    for contact in Contact.objects.filter(
        is_spam=False,
        spam_reviewed=False,
    ).only("id", "message"):
        likely_spam, _ = is_likely_spam(
            contact.message,
            spam_messages,
            legitimate_messages,
        )
        if likely_spam:
            contact_spam_ids.append(contact.pk)

    email_spam_ids = []
    for message in MailboxMessage.objects.filter(
        is_spam=False,
        spam_reviewed=False,
    ).only("id", "subject", "body"):
        likely_spam, _ = is_likely_spam(
            _mailbox_text(message),
            spam_messages,
            legitimate_messages,
        )
        if likely_spam:
            email_spam_ids.append(message.pk)

    Contact.objects.filter(pk__in=contact_spam_ids).update(is_spam=True)
    MailboxMessage.objects.filter(pk__in=email_spam_ids).update(is_spam=True)
    return {
        "reviewed_spam_messages": len(spam_messages),
        "legitimate_messages": len(legitimate_messages),
        "contacts_classified_as_spam": len(contact_spam_ids),
        "emails_classified_as_spam": len(email_spam_ids),
        "learned_terms": [
            {"term": term, "score": round(score, 3)}
            for term, score in sorted(
                learned_terms.items(),
                key=lambda item: (-item[1], item[0]),
            )[:50]
        ],
    }


@task
def send_two_factor_code_email(user_id, code, expires_minutes):
    user = CustomUser.objects.get(pk=user_id)
    html_message = render_to_string(
        "email/twoFactorCode.html",
        {
            "user": user,
            "code": code,
            "expires_minutes": expires_minutes,
        },
    )
    email_message = EmailMultiAlternatives(
        subject="Your Gurmukhi School verification code",
        body=(
            f"Your Gurmukhi School verification code is {code}. "
            f"It expires in {expires_minutes} minutes."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    email_message.attach_alternative(html_message, "text/html")
    email_message.send(fail_silently=False)
    return {"sent": 1, "user_id": user_id}


@task
def check_two_factor_delivery_stage():
    sent = 0
    failed = 0
    expired = TwoFactorEmailDelivery.objects.filter(
        expires_at__lte=timezone.now(),
    ).delete()[0]
    delivery_ids = list(
        TwoFactorEmailDelivery.objects.filter(
            status=TwoFactorEmailDelivery.QUEUED,
            expires_at__gt=timezone.now(),
        ).values_list("id", flat=True)
    )
    for delivery_id in delivery_ids:
        try:
            with transaction.atomic():
                delivery = (
                    TwoFactorEmailDelivery.objects.select_for_update()
                    .select_related("user")
                    .get(pk=delivery_id)
                )
                if delivery.status != TwoFactorEmailDelivery.QUEUED:
                    continue
                send_two_factor_code_email.call(
                    delivery.user_id,
                    two_factor_code_for_nonce(delivery.nonce),
                    max(
                        1,
                        int(
                            (delivery.expires_at - timezone.now()).total_seconds()
                            // 60
                        ),
                    ),
                )
                delivery.status = TwoFactorEmailDelivery.SENT
                delivery.sent_at = timezone.now()
                delivery.save(update_fields=["status", "sent_at"])
        except Exception:
            logger.exception(
                "Queued two-factor email %s failed to send.",
                delivery_id,
            )
            failed += 1
        else:
            sent += 1
    return {"sent": sent, "failed": failed, "expired": expired}


@task
def send_queued_email_responses():
    sent = 0
    failed = 0
    queued_ids = list(
        MailDraft.objects.filter(status=MailDraft.QUEUED).values_list("id", flat=True)
    )
    for draft_id in queued_ids:
        try:
            with transaction.atomic():
                draft = (
                    MailDraft.objects.select_for_update()
                    .get(pk=draft_id)
                )
                if draft.status != MailDraft.QUEUED:
                    continue
                send_admin_email(draft, draft.created_by)
                draft.status = MailDraft.SENT
                draft.sent_at = timezone.now()
                draft.save(update_fields=["status", "sent_at", "updated_at"])
        except Exception:
            logger.exception("Queued admin email %s failed to send.", draft_id)
            failed += 1
        else:
            sent += 1
    return {"sent": sent, "failed": failed}


@task
def sync_incoming_email():
    if not mailbox_is_configured():
        return {"configured": False, "synced": 0}
    return {"configured": True, "synced": sync_inbox()}


@task
def process_email_pipeline():
    results = {
        "two_factor": check_two_factor_delivery_stage.call(),
        "responses": send_queued_email_responses.call(),
    }
    try:
        results["sync"] = sync_incoming_email.call()
    except Exception as exc:
        results["sync"] = {
            "configured": mailbox_is_configured(),
            "synced": 0,
            "error": str(exc),
        }
    return results
