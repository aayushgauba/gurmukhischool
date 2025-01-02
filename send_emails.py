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

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
from portal.models import Announcement, Courses, UploadedAttendance, Attendance, CustomUser, GroupPhotoAttendance

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def userFix():
    users = CustomUser.objects.all()
    for user in users:
        if user.usertype == 'Student':
            user.is_superuser = False
            user.save()
        elif user.usertype == 'Teacher':
            user.is_superuser = True
            user.save()
        elif user.usertype == 'Admin':
            user.is_superuser = True
            user.save()

def read_attendance_csv(file_path):
    with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
        csvreader = csv.reader(csvfile)
        date_strings = next(csvreader)
        attendance = next(csvreader)
        dates = [datetime.datetime.strptime(date, "%d-%m-%Y").date() for date in date_strings]
        attendance_data = dict(zip(dates, attendance))
        return attendance_data

def scanAttendance():
    attendances = UploadedAttendance.objects.all()
    for attendance in attendances:
        user = attendance.student
        attendance_data = read_attendance_csv(attendance.file.path)
        for date, status in attendance_data.items():
            status = "Present" if status == 'P' else "Absent"
            try:
                attendance_temp = Attendance.objects.get(student=user, day=date.day, month=date.month, year=date.year)
                attendance_temp.delete()
            except Exception as e:
                attendance_temp = None
            Attendance.objects.create(student=user, day=date.day, month=date.month, year=date.year, status=status)
        file_path = attendance.file.path
        attendance.delete()
        if os.path.exists(file_path):
            os.remove(file_path)

def send_email_task():
    announcements = Announcement.objects.filter(sent=False)
    for announcement in announcements:
        html_content = render_to_string('email/announcementNotification.html', {"announcement": announcement})
        courses = announcement.recipients.all()
        for course in courses:
            people = course.People.all()
            for person in people:
                email = EmailMultiAlternatives(
                    subject=f"A new announcement has been made",
                    body=announcement.content,
                    to=[person.email],
                )
                email.attach_alternative(html_content, "text/html")
                email.send()
        announcement.sent = True
        announcement.save()

def generate_embeddings_for_profiles():
    users = CustomUser.objects.filter(usertype ="Student")
    embeddings = []
    for user in users:
        if user.profile_photo:  # Only process users with a profile photo
            image_path = user.profile_photo.path
            image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(image)
            if encoding:
                embeddings.append((user, encoding[0]))  # Store user and their embedding
    return embeddings

def compare_with_group_photo(group_photo_path, stored_embeddings):
    group_image = face_recognition.load_image_file(group_photo_path)
    group_face_encodings = face_recognition.face_encodings(group_image)
    attendance = []

    for group_encoding in group_face_encodings:
        matched = False
        # Compare with each stored user embedding
        for user, stored_encoding in stored_embeddings:
            distance = np.linalg.norm(group_encoding - stored_encoding)
            if distance < 0.6:  # You can tweak the threshold
                # Mark attendance for the user if a match is found and they have a profile photo
                attendance.append((user, 'Present'))
                matched = True
                break

        if not matched:
            continue

    return attendance

def scan_group_photos():
    stored_embeddings = generate_embeddings_for_profiles()

    # Get group photos that haven't been processed yet
    group_photos = GroupPhotoAttendance.objects.all()
    
    # Process each group photo
    for group_photo in group_photos:
        attendance_list = compare_with_group_photo(group_photo.file.path, stored_embeddings)
        for user, status in attendance_list:
            if user.profile_photo:
                try:
                    attendance_temp = Attendance.objects.get(student=user, day=datetime.datetime.today().day, month=datetime.datetime.today().month, year=datetime.datetime.today().year)
                    attendance_temp.delete()
                except Exception as e:
                    attendance_temp = None
                Attendance.objects.create(
                    student=user,
                    day=datetime.datetime.today().day,
                    month=datetime.datetime.today().month,
                    year=datetime.datetime.today().year,
                    status=status
                )
        file_path = group_photo.file.path
        group_photo.delete()
        os.remove(file_path)


def main():
    while True:
        send_email_task()
        scanAttendance()
        userFix()
        scan_group_photos()  # Added group photo scanning

if __name__ == "__main__":
    main()
