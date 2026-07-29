import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.template.loader import render_to_string

from portal.models import CustomUser

from .models import Contact
from .spam_classifier import is_likely_spam


logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Contact, dispatch_uid="pages.classify_contact_spam")
def classify_contact_spam(sender, instance, **kwargs):
    if instance.pk or instance.is_spam:
        return
    spam_messages = Contact.objects.filter(is_spam=True).values_list(
        "message",
        flat=True,
    )
    legitimate_messages = Contact.objects.filter(is_spam=False).values_list(
        "message",
        flat=True,
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


def send_contact_notification(contact_id):
    try:
        contact = Contact.objects.get(pk=contact_id)
        recipients = list(
            CustomUser.objects.filter(
                approved=True,
                is_active=True,
            )
            .filter(
                Q(user_type=CustomUser.ADMIN)
                | Q(groups__name=CustomUser.ADMIN)
                | Q(contact_notifications_enabled=True)
            )
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )
        if not recipients:
            logger.warning(
                "Contact message %s was saved, but no notification recipients are configured.",
                contact_id,
            )
            return

        plain_text = (
            "A new message has been received through the website contact form.\n\n"
            f"From: {contact.name}\n"
            f"Email: {contact.email}\n"
            f"Date: {contact.date:%B %d, %Y}\n\n"
            f"{contact.message}"
        )
        html_message = render_to_string(
            "email/contactNotification.html",
            {"contact": contact},
        )
        email = EmailMultiAlternatives(
            subject="A new message has been received",
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[],
            bcc=recipients,
            reply_to=[contact.email],
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
    except Exception:
        logger.exception(
            "Contact message %s was saved, but its notification email failed.",
            contact_id,
        )


@receiver(post_save, sender=Contact, dispatch_uid="pages.notify_contact_recipients")
def notify_contact_recipients(sender, instance, created, **kwargs):
    if created and not instance.is_spam:
        transaction.on_commit(
            lambda contact_id=instance.pk: send_contact_notification(contact_id)
        )
