import time
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import django
import os
import sys
import csv
import datetime
# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from portal.models import Announcement, Courses, UploadedAttendance, Attendance, CustomUser

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

def main():
    while True:
        send_email_task()
        scanAttendance()
        userFix()
        time.sleep(60)  # Sleep for 60 seconds before checking for new tasks

if __name__ == "__main__":
    main()
