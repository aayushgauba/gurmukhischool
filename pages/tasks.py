import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.tasks import task
from django.template.loader import render_to_string
from django.utils import timezone

from portal.models import CustomUser

from .mailbox import mailbox_is_configured, send_admin_email, sync_inbox
from .models import MailDraft


logger = logging.getLogger(__name__)


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
    # Verification-code tasks run immediately during login so users are never
    # left waiting for a scheduled worker. This stage intentionally runs first
    # in the general mail pipeline to preserve that ordering.
    return {"checked": True, "delivery": "event-driven"}


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
