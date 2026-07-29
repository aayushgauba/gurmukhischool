import json

from django.core.management.base import BaseCommand, CommandError

from pages.tasks import send_queued_admin_notifications


class Command(BaseCommand):
    help = (
        "Send queued administrator notifications for new contact-form "
        "submissions and newly synchronized mailbox email."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--enqueue",
            action="store_true",
            help="Submit notification delivery to Django's configured task backend.",
        )

    def handle(self, *args, **options):
        if options["enqueue"]:
            result = send_queued_admin_notifications.enqueue()
            if result.errors:
                raise CommandError(result.errors[0].traceback)
            self.stdout.write(
                self.style.SUCCESS(
                    "Administrator notifications submitted with status "
                    f"{result.status}."
                )
            )
            return

        result = send_queued_admin_notifications.call()
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        self.stdout.write(
            self.style.SUCCESS("Administrator notification task completed.")
        )
