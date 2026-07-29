#!/usr/bin/env python
"""Compatibility launcher for scheduled portal email tasks."""

from portal.standalone import run_task_script


if __name__ == "__main__":
    run_task_script("emails")
