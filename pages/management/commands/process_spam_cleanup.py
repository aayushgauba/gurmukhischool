import json

from django.core.management.base import BaseCommand, CommandError

from pages.tasks import purge_old_spam_messages


class Command(BaseCommand):
    help = (
        "Preview or delete spam contact messages and mailbox email older "
        "than the configured retention period."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Delete spam older than this many days (default: 90).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Perform deletion. Without this option, only preview counts.",
        )
        parser.add_argument(
            "--enqueue",
            action="store_true",
            help="Submit cleanup to Django's configured task backend.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days must be at least 1.")

        if options["enqueue"]:
            result = purge_old_spam_messages.enqueue(
                days=days,
                apply=options["apply"],
            )
            if result.errors:
                raise CommandError(result.errors[0].traceback)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Spam cleanup submitted with status {result.status}."
                )
            )
            return

        result = purge_old_spam_messages.call(
            days=days,
            apply=options["apply"],
        )
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        if options["apply"]:
            self.stdout.write(self.style.SUCCESS("Old spam was deleted."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Preview only; rerun with --apply to delete matched spam."
                )
            )
