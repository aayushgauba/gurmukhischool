from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from .mailbox import send_admin_email
from .models import MailDraft, MailboxMessage


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="configured@example.com",
)
class AdminMailboxTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin@example.com",
            first_name="Aman",
            last_name="Singh",
        )

    def test_outbound_email_uses_configured_sender_and_user_signature(self):
        draft = MailDraft.objects.create(
            recipient="visitor@example.com",
            subject="Welcome",
            body="Thank you for contacting us.",
            created_by=self.user,
        )
        send_admin_email(draft, self.user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "configured@example.com")
        self.assertEqual(mail.outbox[0].to, ["visitor@example.com"])
        self.assertIn("Aman Singh", mail.outbox[0].body)
        self.assertIn("Sikh Study Circle of St. Louis", mail.outbox[0].body)

    def test_mailbox_uid_is_unique_within_folder(self):
        MailboxMessage.objects.create(folder="INBOX", uid="42")
        message, created = MailboxMessage.objects.update_or_create(
            folder="INBOX",
            uid="42",
            defaults={"subject": "Updated"},
        )
        self.assertFalse(created)
        self.assertEqual(message.subject, "Updated")
