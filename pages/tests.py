from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .mailbox import send_admin_email
from .models import (
    Contact,
    MailDraft,
    MailboxMessage,
    TwoFactorEmailDelivery,
)
from .tasks import (
    classify_spam_messages,
    process_email_pipeline,
    send_two_factor_code_email,
    two_factor_code_for_nonce,
)


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
        self.user.email = "admin@example.com"
        self.user.save(update_fields=["email"])
        delivery = TwoFactorEmailDelivery.objects.create(
            user=self.user,
            nonce="queued-test-nonce",
            expires_at=timezone.now() + timedelta(minutes=10),
        )
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
        delivery.refresh_from_db()
        self.assertEqual(result["two_factor"]["sent"], 1)
        self.assertEqual(delivery.status, TwoFactorEmailDelivery.SENT)
        self.assertIn(two_factor_code_for_nonce(delivery.nonce), mail.outbox[0].body)
        self.assertEqual(result["responses"]["sent"], 1)
        self.assertEqual(draft.status, MailDraft.SENT)
        self.assertFalse(result["sync"]["configured"])


class CombinedSpamClassifierTests(TestCase):
    def setUp(self):
        Contact.objects.create(
            name="Spam One",
            email="one@example.com",
            message="crypto jackpot investment",
            is_spam=True,
            spam_reviewed=True,
        )
        Contact.objects.create(
            name="Spam Two",
            email="two@example.com",
            message="crypto jackpot offer",
            is_spam=True,
            spam_reviewed=True,
        )
        MailboxMessage.objects.create(
            folder="INBOX",
            uid="spam-3",
            subject="crypto jackpot winner",
            is_spam=True,
            spam_reviewed=True,
        )
        Contact.objects.create(
            name="Parent",
            email="parent@example.com",
            message="Question about the school class schedule",
            spam_reviewed=True,
        )

    def test_task_classifies_contact_forms_and_mailbox_email(self):
        contact = Contact.objects.create(
            name="Candidate",
            email="candidate@example.com",
            message="Pending classification",
        )
        Contact.objects.filter(pk=contact.pk).update(
            message="Claim your crypto jackpot now",
        )
        email = MailboxMessage.objects.create(
            folder="INBOX",
            uid="candidate-email",
            subject="Crypto jackpot opportunity",
        )

        result = classify_spam_messages.call()

        contact.refresh_from_db()
        email.refresh_from_db()
        self.assertTrue(contact.is_spam)
        self.assertFalse(contact.spam_reviewed)
        self.assertTrue(email.is_spam)
        self.assertFalse(email.spam_reviewed)
        self.assertEqual(result["contacts_classified_as_spam"], 1)
        self.assertEqual(result["emails_classified_as_spam"], 1)

    def test_reviewed_legitimate_message_is_not_reclassified(self):
        contact = Contact.objects.create(
            name="Reviewed",
            email="reviewed@example.com",
            message="crypto jackpot question",
            spam_reviewed=True,
        )

        classify_spam_messages.call()

        contact.refresh_from_db()
        self.assertFalse(contact.is_spam)
