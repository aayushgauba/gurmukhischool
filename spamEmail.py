#!/usr/bin/env python
"""Compatibility launcher for the adaptive spam-classifier report."""

from portal.standalone import run_task_script


if __name__ == "__main__":
    run_task_script("spam-classifier")
