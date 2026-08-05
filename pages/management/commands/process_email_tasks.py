import json

from django.core.management.base import BaseCommand, CommandError

from pages.tasks import process_email_pipeline


class Command(BaseCommand):
    help = (
        "Process email operations in order: verify the two-factor delivery "
        "stage, send account activations, send queued responses, then "
        "synchronize incoming email and send administrator notifications."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--enqueue",
            action="store_true",
            help="Submit the ordered pipeline to Django's configured task backend.",
        )

    def handle(self, *args, **options):
        if options["enqueue"]:
            result = process_email_pipeline.enqueue()
            if result.errors:
                raise CommandError(result.errors[0].traceback)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Email pipeline submitted with status {result.status}."
                )
            )
            return
        result = process_email_pipeline.call()
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        self.stdout.write(self.style.SUCCESS("Email pipeline completed."))
