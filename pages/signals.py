import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string

from portal.models import CustomUser

from .models import Contact


logger = logging.getLogger(__name__)


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
    if created:
        transaction.on_commit(
            lambda contact_id=instance.pk: send_contact_notification(contact_id)
        )
