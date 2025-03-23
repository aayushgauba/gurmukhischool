import os
import sys
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import django
from datetime import date, timedelta
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
from portal.models import Announcement, EmailSubscriber, WeeklyEmail, Courses, UploadedAttendance, Attendance, CustomUser, GroupPhotoAttendance

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def send_community_email_task():
    logging.info("Sending weekly emails...")
    # Only process announcements created 7 or more days ago
    threshold_date = date.today() + timedelta(days=7)
    emails = WeeklyEmail.objects.filter(sent=False, date_scheduled = threshold_date)
    print(emails)
    for email in emails:
        html_content = render_to_string('email/weekly-kirtan-email.html', {"email": email})
        subscribers = EmailSubscriber.objects.all()
        for subscriber in subscribers:
            emailTemp = EmailMultiAlternatives(
                    subject="Weekly Kirtan",
                    body=email.organizer,
                    to=[subscriber.email],
                )
            emailTemp.attach_alternative(html_content, "text/html")
            emailTemp.send()
        email.sent = True
        email.save()
    
    logging.info("Emails sent successfully.")

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
    send_community_email_task()

if __name__ == "__main__":
    main()
