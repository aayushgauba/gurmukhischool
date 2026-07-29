from contextlib import nullcontext

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from database_table_backup import (
    acquire_lock,
    create_backups,
    delete_backups,
    list_backups,
    release_lock,
    require_supported_database,
)


class Command(BaseCommand):
    help = "Create, list, or delete managed PostgreSQL/MySQL table copies."

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            nargs="?",
            default="create",
            choices=("create", "list", "delete"),
        )

    def handle(self, *args, **options):
        action = options["action"]
        require_supported_database(connection)
        database_context = (
            transaction.atomic()
            if connection.vendor == "postgresql"
            else nullcontext()
        )
        lock_acquired = False
        try:
            with database_context:
                if connection.vendor == "postgresql":
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
                        )
                acquire_lock(connection)
                lock_acquired = True
                if action == "create":
                    create_backups(connection)
                elif action == "list":
                    list_backups(connection)
                else:
                    delete_backups(connection)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        finally:
            if lock_acquired:
                try:
                    release_lock(connection)
                except Exception as exc:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Could not release the database lock: {exc}"
                        )
                    )
        self.stdout.write(self.style.SUCCESS(f"Table backup action {action!r} completed."))
