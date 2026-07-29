#!/usr/bin/env python
"""Compatibility launcher for the user-permission normalization task."""

from portal.standalone import run_task_script


if __name__ == "__main__":
    run_task_script("user-permissions")
