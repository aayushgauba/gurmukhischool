import os
import sys
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import django

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
from portal.models import Announcement, Courses, UploadedAttendance, Attendance, CustomUser, GroupPhotoAttendance

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def send_email_task():
    logging.info("Sending announcement emails...")
    announcements = Announcement.objects.filter(sent=False)
    for announcement in announcements:
        html_content = render_to_string('email/announcementNotification.html', {"announcement": announcement})
        for course in announcement.recipients.all():
            for person in course.People.all():
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


def main():
    send_email_task()

if __name__ == "__main__":
    main()
