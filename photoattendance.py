import os
import sys
import datetime
import logging
import numpy as np
from deepface import DeepFace  # Import DeepFace for face recognition
import django
import time
from scipy.spatial.distance import cosine, euclidean

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()
from portal.models import Announcement, Courses, UploadedAttendance, Attendance, CustomUser, GroupPhotoAttendance

# Add the directory containing the 'pages' module to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_for_group_photos():
    return GroupPhotoAttendance.objects.exists()
# Task: Generate embeddings for student profiles
def generate_embeddings_for_profiles(detector_backend="retinaface", align=True):
    logging.info("Generating embeddings for profiles...")
    users = CustomUser.objects.filter(usertype="Student")
    embeddings = []

    for user in users:
        # Collect embeddings for all of the user's photos
        user_embeddings = []
        photos = user.profile_photos.all()  # Access multiple profile photos

        if photos.exists():
            for photo in photos:
                try:
                    image_path = photo.file.path
                    print(image_path)
                    embeddings_list = DeepFace.represent(
                        img_path=image_path,
                        model_name="Facenet512",
                        enforce_detection=True,
                        detector_backend=detector_backend,
                        align=align
                    )
                    if embeddings_list:
                        # Store the embedding from this photo
                        user_embeddings.append(np.array(embeddings_list[0]['embedding']))
                    else:
                        logging.warning(f"No face detected in photo {photo} for user {user}")
                except Exception as e:
                    logging.error(f"Error generating embedding for photo {photo} of user {user}: {e}")

            if user_embeddings:
                # Compute a composite embedding (average) from all photos
                composite_embedding = np.mean(user_embeddings, axis=0)
                embeddings.append((user, composite_embedding))
            else:
                logging.warning(f"No valid embeddings found for user {user} despite having photos.")
        else:
            logging.warning(f"No profile photos for user {user}")
    
    logging.info("Embeddings generated for profiles.")
    return embeddings

# Task: Compare group photo with stored embeddings using DeepFace.verify
def compare_with_group_photo(group_photo_path, stored_embeddings, metric="cosine", 
                             detector_backend="retinaface", align=True, distance_threshold=0.5):
    """
    Compare faces in a group photo against stored composite embeddings of users.

    Parameters:
        group_photo_path (str): Path to the group photo.
        stored_embeddings (list): List of tuples (user, composite_embedding).
        metric (str): Distance metric ('cosine', 'euclidean', 'euclidean_l2').
        detector_backend (str): Face detector backend.
        align (bool): Whether to align faces before embedding generation.
        distance_threshold (float): Threshold for considering a match.

    Returns:
        list: List of tuples (user, status) for matches found.
    """
    logging.info(f"Comparing group photo: {group_photo_path} using metric: {metric}")
    try:
        # Generate embeddings for all faces in the group photo
        group_embeddings_list = DeepFace.represent(
            img_path=group_photo_path,
            model_name="Facenet512",
            enforce_detection=True,
            detector_backend=detector_backend,
            align=align
        )

        if not group_embeddings_list:
            logging.warning("No faces detected in the group photo.")
            return []

        attendance = []

        # Compare each detected face's embedding from the group photo with stored embeddings
        for group_face in group_embeddings_list:
            group_embedding = np.array(group_face['embedding'])

            for user, stored_embedding in stored_embeddings:
                # Compute distance based on selected metric
                if metric == "cosine":
                    distance = cosine(group_embedding, stored_embedding)
                elif metric == "euclidean":
                    distance = euclidean(group_embedding, stored_embedding)
                elif metric == "euclidean_l2":
                    distance = np.linalg.norm(group_embedding - stored_embedding)
                else:
                    logging.error(f"Unsupported metric: {metric}")
                    continue

                # If distance below threshold, mark user as present
                if distance < distance_threshold:
                    attendance.append((user, "Present"))
                    logging.debug(f"User {user.username} matched with distance {distance} using {metric}")
                    # Break out of inner loop: move to next face after a match
                    break

        logging.info(f"Group photo comparison completed with {len(attendance)} matches.")
        return attendance

    except Exception as e:
        logging.error(f"Error comparing group photo: {e}")
        return []

# Task: Scan group photos
def scan_group_photos():
    logging.info("Scanning group photos...")
    stored_embeddings = generate_embeddings_for_profiles()
    for group_photo in GroupPhotoAttendance.objects.all():
        attendance_list = compare_with_group_photo(group_photo.file.path, stored_embeddings)
        for user, status in attendance_list:
            Attendance.objects.update_or_create(
                student=user,
                day=datetime.datetime.today().day,
                month=datetime.datetime.today().month,
                year=datetime.datetime.today().year,
                defaults={'status': status},
            )
        os.remove(group_photo.file.path)
        group_photo.delete()
    logging.info("Group photo scanning completed.")

# Main process
def main():
    while True:
        if check_for_group_photos():  # Only proceed if there are group photos
            logging.info("Group photos detected. Starting processing...")
            scan_group_photos()
        else:
            logging.info("No group photos detected. Sleeping for 5 minutes.")
            time.sleep(300)  # Wait for 5 minutes before checking again

if __name__ == "__main__":
    main()
