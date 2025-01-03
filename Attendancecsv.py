import time
import os
import sys
import csv
import datetime
import logging
import numpy as np
import cv2
from PIL import Image
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from photoattendance import DeepFace  # Import DeepFace for face recognition
import django

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
from portal.models import Announcement, Courses, UploadedAttendance, Attendance, CustomUser, GroupPhotoAttendance

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def read_attendance_csv(file_path):
    with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
        csvreader = csv.reader(csvfile)
        date_strings = next(csvreader)
        attendance = next(csvreader)
        dates = [datetime.datetime.strptime(date, "%d-%m-%Y").date() for date in date_strings]
        attendance_data = dict(zip(dates, attendance))
        return attendance_data

# Task: Scan uploaded attendance
def scanAttendance():
    logging.info("Scanning uploaded attendance...")
    attendances = UploadedAttendance.objects.all()
    for attendance in attendances:
        user = attendance.student
        attendance_data = read_attendance_csv(attendance.file.path)
        for date, status in attendance_data.items():
            status = "Present" if status == 'P' else "Absent"
            Attendance.objects.update_or_create(
                student=user,
                day=date.day,
                month=date.month,
                year=date.year,
                defaults={'status': status},
            )
        os.remove(attendance.file.path)
        attendance.delete()
    logging.info("Attendance scan completed.")


# Main process
def main():
    while True:
        logging.info("Starting main process...")
        scanAttendance()
if __name__ == "__main__":
    main()
