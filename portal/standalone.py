import os
import sys


def run_task_script(task_name):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gurmukhischool.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(
        [sys.argv[0], "run_portal_task", task_name, *sys.argv[1:]]
    )
