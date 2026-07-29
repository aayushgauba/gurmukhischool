from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from .mailbox import send_admin_email
from .models import MailDraft, MailboxMessage
from .tasks import process_email_pipeline, send_two_factor_code_email


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

    def test_two_factor_email_is_sent_by_django_task(self):
        self.user.email = "admin@example.com"
        self.user.save(update_fields=["email"])
        result = send_two_factor_code_email.call(self.user.pk, "123456", 10)
        self.assertEqual(result["sent"], 1)
        self.assertIn("123456", mail.outbox[0].body)

    @override_settings(EMAIL_IMAP_HOST="")
    def test_pipeline_processes_stages_in_required_order(self):
        draft = MailDraft.objects.create(
            recipient="visitor@example.com",
            subject="Response",
            body="Hello",
            status=MailDraft.QUEUED,
            created_by=self.user,
            created_by_name="Aman Singh",
        )
        result = process_email_pipeline.call()
        draft.refresh_from_db()
        self.assertEqual(
            list(result),
            ["two_factor", "responses", "sync"],
        )
        self.assertTrue(result["two_factor"]["checked"])
        self.assertEqual(result["responses"]["sent"], 1)
        self.assertEqual(draft.status, MailDraft.SENT)
        self.assertFalse(result["sync"]["configured"])
