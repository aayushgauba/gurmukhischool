from django.conf import settings
from django.db import models


class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    date = models.DateField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_spam = models.BooleanField(default=False)
    spam_reviewed = models.BooleanField(default=False)


class MailboxMessage(models.Model):
    folder = models.CharField(max_length=100, default="INBOX")
    uid = models.CharField(max_length=255)
    message_id = models.CharField(max_length=998, blank=True)
    sender_name = models.CharField(max_length=255, blank=True)
    sender_email = models.EmailField(blank=True)
    recipients = models.TextField(blank=True)
    subject = models.CharField(max_length=998, blank=True)
    body = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(auto_now=True)
    is_spam = models.BooleanField(default=False)
    spam_reviewed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-received_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["folder", "uid"],
                name="unique_mailbox_folder_uid",
            ),
        ]

    def __str__(self):
        return self.subject or "(No subject)"


class MailDraft(models.Model):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (QUEUED, "Queued"),
        (SENT, "Sent"),
    ]

    recipient = models.EmailField()
    subject = models.CharField(max_length=998)
    body = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=DRAFT,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="mail_drafts",
    )
    created_by_name = models.CharField(max_length=255, blank=True)
    contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_drafts",
    )
    reply_to_message = models.ForeignKey(
        MailboxMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.subject


class TwoFactorEmailDelivery(models.Model):
    QUEUED = "queued"
    SENT = "sent"
    STATUS_CHOICES = [
        (QUEUED, "Queued"),
        (SENT, "Sent"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor_email_deliveries",
    )
    nonce = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=QUEUED,
    )
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]


class AdminMessageNotification(models.Model):
    QUEUED = "queued"
    SENT = "sent"
    SKIPPED = "skipped"
    STATUS_CHOICES = [
        (QUEUED, "Queued"),
        (SENT, "Sent"),
        (SKIPPED, "Skipped"),
    ]

    contact = models.OneToOneField(
        Contact,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="admin_notification",
    )
    mailbox_message = models.OneToOneField(
        MailboxMessage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="admin_notification",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=QUEUED,
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
