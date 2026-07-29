import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AdminMessageNotification, Contact, MailboxMessage
from .spam_classifier import is_likely_spam


logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Contact, dispatch_uid="pages.classify_contact_spam")
def classify_contact_spam(sender, instance, **kwargs):
    if instance.pk or instance.is_spam or instance.spam_reviewed:
        return
    spam_messages = list(Contact.objects.filter(
        is_spam=True,
        spam_reviewed=True,
    ).values_list(
        "message",
        flat=True,
    ))
    spam_messages.extend(
        "\n".join(part for part in [message.subject, message.body] if part)
        for message in MailboxMessage.objects.filter(
            is_spam=True,
            spam_reviewed=True,
        ).only("subject", "body")
    )
    legitimate_messages = list(Contact.objects.filter(
        is_spam=False,
        spam_reviewed=True,
    ).values_list(
        "message",
        flat=True,
    ))
    legitimate_messages.extend(
        "\n".join(part for part in [message.subject, message.body] if part)
        for message in MailboxMessage.objects.filter(
            is_spam=False,
            spam_reviewed=True,
        ).only(
            "subject",
            "body",
        )
    )
    likely_spam, matched_terms = is_likely_spam(
        instance.message,
        spam_messages,
        legitimate_messages,
    )
    if likely_spam:
        instance.is_spam = True
        logger.info(
            "Contact submission automatically classified as spam using %d learned terms.",
            len(matched_terms),
        )


@receiver(post_save, sender=Contact, dispatch_uid="pages.notify_contact_recipients")
def notify_contact_recipients(sender, instance, created, **kwargs):
    if created and not instance.is_spam:
        transaction.on_commit(
            lambda contact_id=instance.pk: AdminMessageNotification.objects.get_or_create(
                contact_id=contact_id
            )
        )


@receiver(
    post_save,
    sender=MailboxMessage,
    dispatch_uid="pages.notify_mailbox_recipients",
)
def notify_mailbox_recipients(sender, instance, created, **kwargs):
    configured_senders = {
        address.strip().lower()
        for address in [
            settings.DEFAULT_FROM_EMAIL,
            settings.EMAIL_HOST_USER,
        ]
        if address
    }
    if (
        created
        and not instance.is_spam
        and instance.sender_email.strip().lower() not in configured_senders
    ):
        transaction.on_commit(
            lambda message_id=instance.pk: AdminMessageNotification.objects.get_or_create(
                mailbox_message_id=message_id
            )
        )
