import os
import sys
import csv
import datetime
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def setup_django_environment():
    """Set up Django environment only when needed."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
    import django
    django.setup()
    global UploadedAttendance, Attendance
    from portal.models import UploadedAttendance, Attendance

def check_for_uploaded_attendance():
    """Check if there are any uploaded attendance files."""
    setup_django_environment()
    from portal.models import UploadedAttendance
    return UploadedAttendance.objects.exists()

def read_attendance_csv(file_path):
    """Read attendance data from a CSV file."""
    def parse_date(date_str):
        for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Date '{date_str}' is not in a recognized format.")

    with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
        csvreader = csv.reader(csvfile)
        date_strings = next(csvreader)
        attendance = next(csvreader)
        dates = [parse_date(date) for date in date_strings]
        attendance_data = dict(zip(dates, attendance))
        return attendance_data

def scan_attendance():
    """Scan and process uploaded attendance files."""
    setup_django_environment()
    from portal.models import UploadedAttendance, Attendance
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

def main():
    scan_attendance()

if __name__ == "__main__":
    main()
