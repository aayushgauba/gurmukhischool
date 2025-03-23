import os
import sys
import logging
import django

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
from portal.models import Announcement, Courses, UploadedAttendance, Attendance, CustomUser, GroupPhotoAttendance

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Utility: Fix user permissions
def userFix():
    logging.info("Fixing user permissions...")
    users = CustomUser.objects.all()
    for user in users:
        is_superuser = user.usertype in ('Teacher', 'Admin', 'EmailSender')
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            user.save()
    logging.info("User permissions updated.")

# Main process
def main():
    userFix()

if __name__ == "__main__":
    main()