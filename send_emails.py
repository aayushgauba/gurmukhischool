import time
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import django
import os
import sys

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from portal.models import Announcement, Courses

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
        time.sleep(60)  # Sleep for 60 seconds before checking for new tasks

if __name__ == "__main__":
    main()
