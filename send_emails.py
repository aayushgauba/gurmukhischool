import time
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import django
import os
import sys
import csv
import datetime
from PIL import Image
import logging
from deepface import DeepFace  # Import DeepFace for face recognition
import cv2
import numpy as np
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
from portal.models import Announcement, Courses, UploadedAttendance, Attendance, CustomUser, GroupPhotoAttendance

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Use DeepFace's built-in face recognition functions

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

def generate_embeddings_for_profiles():
    logging.info("Generating embeddings for profiles...")
    users = CustomUser.objects.filter(usertype="Student")
    embeddings = []

    for user in users:
        if user.profile_photo:
            try:
                image = cv2.imread(user.profile_photo.path)
                if image is not None:
                    # Use DeepFace to extract embeddings
                    embedding = DeepFace.represent(img_path=user.profile_photo.path, model_name="VGG-Face", enforce_detection=False)
                    embeddings.append((user, embedding[0]['embedding']))  # Assuming 'embedding' is the key from DeepFace
            except Exception as e:
                logging.error(f"Error generating embedding for user {user}: {e}")

    logging.info("Embeddings generated for profiles.")
    return embeddings

def compare_with_group_photo(group_photo_path, stored_embeddings):
    logging.info(f"Comparing group photo: {group_photo_path}")
    try:
        # Use DeepFace for face comparison
        group_embedding = DeepFace.represent(img_path=group_photo_path, model_name="VGG-Face", enforce_detection=False)

        attendance = []
        for embedding_data in group_embedding:
            group_face_embedding = embedding_data['embedding']
            matched_user = None
            min_distance = float("inf")
            for user, stored_embedding in stored_embeddings:
                distance = np.linalg.norm(np.array(group_face_embedding) - np.array(stored_embedding))
                if distance < min_distance and distance < 0.8:  # Adjust threshold as needed
                    min_distance = distance
                    matched_user = user

            if matched_user:
                attendance.append((matched_user, "Present"))

        logging.info(f"Group photo comparison completed with {len(attendance)} matches.")
        return attendance
    except Exception as e:
        logging.error(f"Error comparing group photo: {e}")
        return []

def scan_group_photos():
    logging.info("Scanning group photos...")
    stored_embeddings = generate_embeddings_for_profiles()
    group_photos = GroupPhotoAttendance.objects.all()

    for group_photo in group_photos:
        attendance_list = compare_with_group_photo(group_photo.file.path, stored_embeddings)
        for user, status in attendance_list:
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