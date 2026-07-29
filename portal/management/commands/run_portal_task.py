import json

from django.core.management.base import BaseCommand, CommandError

from portal.tasks import (
    normalize_user_permissions,
    process_attendance_uploads,
    process_group_photos,
    send_pending_emails,
    spam_classifier_report,
    transfer_legacy_profile_photos,
)


TASKS = {
    "attendance": process_attendance_uploads,
    "emails": send_pending_emails,
    "group-photos": process_group_photos,
    "profile-photos": transfer_legacy_profile_photos,
    "spam-classifier": spam_classifier_report,
    "user-permissions": normalize_user_permissions,
}


class Command(BaseCommand):
    help = "Run or enqueue a reusable portal maintenance task."

    def add_arguments(self, parser):
        parser.add_argument("task_name", choices=sorted(TASKS))
        parser.add_argument(
            "--enqueue",
            action="store_true",
            help="Enqueue through Django's configured task backend.",
        )

    def handle(self, *args, **options):
        selected_task = TASKS[options["task_name"]]
        if options["enqueue"]:
            result = selected_task.enqueue()
            if result.errors:
                raise CommandError(result.errors[0].traceback)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Task {options['task_name']} submitted with status {result.status}."
                )
            )
            return
        result = selected_task.call()
        self.stdout.write(json.dumps(result, indent=2, sort_keys=True))
        self.stdout.write(
            self.style.SUCCESS(f"Task {options['task_name']} completed.")
        )
