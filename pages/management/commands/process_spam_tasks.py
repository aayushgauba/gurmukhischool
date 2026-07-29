import json

from django.core.management.base import BaseCommand, CommandError

from pages.tasks import classify_spam_messages


class Command(BaseCommand):
    help = (
        "Classify unreviewed mailbox emails and website contact messages "
        "using patterns learned from administrator-reviewed messages."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--enqueue",
            action="store_true",
            help="Submit spam classification to Django's configured task backend.",
        )

    def handle(self, *args, **options):
        if options["enqueue"]:
            result = classify_spam_messages.enqueue()
            if result.errors:
                raise CommandError(result.errors[0].traceback)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Spam classification submitted with status {result.status}."
                )
            )
            return

        result = classify_spam_messages.call()
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        self.stdout.write(self.style.SUCCESS("Spam classification completed."))
