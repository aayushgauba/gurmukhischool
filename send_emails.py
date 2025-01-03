import time
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import django
import os
import sys
import csv
import datetime
import face_recognition
import numpy as np
from PIL import Image
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
from portal.models import Announcement, Courses, UploadedAttendance, Attendance, CustomUser, GroupPhotoAttendance

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
def userFix():
    logging.info("Fixing user permissions...")
    users = CustomUser.objects.all()
    for user in users:
        is_superuser = user.usertype in ('Teacher', 'Admin')
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            user.save()
    logging.info("User permissions updated.")

def read_attendance_csv(file_path):
    with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
        csvreader = csv.reader(csvfile)
        date_strings = next(csvreader)
        attendance = next(csvreader)
        dates = [datetime.datetime.strptime(date, "%d-%m-%Y").date() for date in date_strings]
        attendance_data = dict(zip(dates, attendance))
        return attendance_data

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
        file_path = attendance.file.path
        attendance.delete()
        if os.path.exists(file_path):
            os.remove(file_path)
    logging.info("Attendance scan completed.")

def send_email_task():
    logging.info("Sending announcement emails...")
    announcements = Announcement.objects.filter(sent=False)
    for announcement in announcements:
        html_content = render_to_string('email/announcementNotification.html', {"announcement": announcement})
        courses = announcement.recipients.all()
        for course in courses:
            people = course.People.all()
            for person in people:
                email = EmailMultiAlternatives(
                    subject="A new announcement has been made",
                    body=announcement.content,
                    to=[person.email],
                )
                email.attach_alternative(html_content, "text/html")
                email.send()
        announcement.sent = True
        announcement.save()
    logging.info("Emails sent successfully.")

def resize_image(image_path):
    with Image.open(image_path) as img:
        width, height = img.size
        img = img.resize((width // 2, height // 2))  # Reduce image size by half
        img.save(image_path)
        logging.info(f"Resized image to {img.size}.")

def generate_embeddings_for_profiles():
    logging.info("Generating embeddings for profile photos...")
    users = CustomUser.objects.filter(usertype="Student")
    embeddings = []
    for user in users:
        if user.profile_photo:
            image_path = user.profile_photo.path
            if not os.path.exists(image_path):
                logging.warning(f"Profile photo not found for user {user.email}.")
                continue
            resize_image(image_path)
            image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(image)
            if encoding:
                embeddings.append((user, encoding[0]))
            else:
                logging.warning(f"No encoding generated for user {user.email}.")
    logging.info("Embeddings generation completed.")
    return embeddings

def compare_with_group_photo(group_photo_path, stored_embeddings):
    logging.info(f"Processing group photo: {group_photo_path}")
    resize_image(group_photo_path)
    group_image = face_recognition.load_image_file(group_photo_path)
    group_face_encodings = face_recognition.face_encodings(group_image)
    attendance = []

    for group_encoding in group_face_encodings:
        matched = False
        for user, stored_encoding in stored_embeddings:
            distance = np.linalg.norm(group_encoding - stored_encoding)
            if distance < 0.6:
                attendance.append((user, 'Present'))
                matched = True
                break
        if not matched:
            logging.warning("No match found for a face in the group photo.")

    logging.info(f"Completed processing for group photo: {group_photo_path}")
    return attendance

def scan_group_photos():
    logging.info("Scanning group photos...")
    stored_embeddings = generate_embeddings_for_profiles()
    group_photos = GroupPhotoAttendance.objects.all()

    for group_photo in group_photos:
        attendance_list = compare_with_group_photo(group_photo.file.path, stored_embeddings)
        for user, status in attendance_list:
            if user.profile_photo:
                Attendance.objects.update_or_create(
                    student=user,
                    day=datetime.datetime.today().day,
                    month=datetime.datetime.today().month,
                    year=datetime.datetime.today().year,
                    defaults={'status': status},
                )
        file_path = group_photo.file.path
        group_photo.delete()
        if os.path.exists(file_path):
            os.remove(file_path)
    logging.info("Group photo scanning completed.")

def main():
    while True:
        logging.info("Starting main process...")
        send_email_task()
        scanAttendance()
        userFix()
        scan_group_photos()
        logging.info("Main process iteration completed.")
        time.sleep(60)  # Wait 60 seconds before the next iteration

if __name__ == "__main__":
    main()