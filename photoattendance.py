import os
import sys
import datetime
import logging
import json
import numpy as np
from scipy.spatial.distance import cosine, euclidean

import django
from django.utils import timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Set up Django environment (adjust path as needed)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
django.setup()

from deepface import DeepFace
from portal.models import (
    CustomUser, GroupPhotoAttendance, Attendance
)


def calculate_user_embedding(user, detector_backend="retinaface", align=True):
    """
    Calculate and store a composite embedding for a user's profile photos.
    This sets user.embedding (JSON) and saves the user.

    Parameters:
        user (CustomUser): The user whose embeddings are to be (re)calculated.
        detector_backend (str): The face detection backend for DeepFace.
        align (bool): Whether to align faces before embedding generation.
    """
    logging.info(f"Calculating embeddings for user: {user}")
    photos = user.profile_photos.all()
    user_embeddings = []

    if not photos.exists():
        logging.warning(f"No profile photos for user {user}. Skipping embedding calculation.")
        user.modified_profile_photo = False
        user.save()
        return

    for photo in photos:
        try:
            image_path = photo.file.path
            # Generate embeddings from the photo
            embeddings_list = DeepFace.represent(
                img_path=image_path,
                model_name="Facenet512",
                enforce_detection=True,
                detector_backend=detector_backend,
                align=align
            )
            if embeddings_list:
                # DeepFace returns a list of dicts; get the first embedding
                user_embeddings.append(np.array(embeddings_list[0]['embedding']))
        except Exception as e:
            logging.error(f"Error generating embedding for photo {photo} of user {user}: {e}")

    if user_embeddings:
        # Average across all valid embeddings
        composite_embedding = np.mean(user_embeddings, axis=0).tolist()
        # Store as JSON in the 'embedding' field
        user.embedding = composite_embedding
        user.modified_profile_photo = False  # Reset since we've updated now
        user.save()
        logging.info(f"Successfully stored embeddings for user {user}")
    else:
        logging.warning(f"No valid embeddings found for user {user}")


def update_embeddings_for_all_students(detector_backend="retinaface", align=True):
    logging.info("Updating embeddings for all student profiles that need recalculation...")
    # Filter only Student type
    students = CustomUser.objects.filter(user_type="Student")

    for user in students:
        # If the user’s embedding is missing or user.modified_profile_photo == True,
        # we recalc and store it.
        if user.modified_profile_photo or not user.embedding:
            calculate_user_embedding(user, detector_backend, align)

    logging.info("All necessary student embeddings have been updated.")


def get_stored_embeddings():
    """
    Retrieve (User, embedding_vector) for all Students who have a stored embedding.
    Returns a list of tuples: (user_obj, np.array_of_embedding).
    """
    logging.info("Fetching stored embeddings for students...")
    students_with_embeddings = CustomUser.objects.filter(
        user_type="Student",
        embedding__isnull=False
    )

    stored_embeddings = []
    for user in students_with_embeddings:
        try:
            embedding_list = (
                json.loads(user.embedding)
                if isinstance(user.embedding, str)
                else user.embedding
            )
            embedding_array = np.array(embedding_list)
            stored_embeddings.append((user, embedding_array))
        except Exception as e:
            logging.error(f"Error loading embedding from user {user}: {e}")

    logging.info(f"Fetched embeddings for {len(stored_embeddings)} students.")
    return stored_embeddings


def compare_with_group_photo(group_photo_path, stored_embeddings, 
                             metric="cosine", detector_backend="retinaface",
                             align=True, distance_threshold=0.5):
    """
    Compare faces in a group photo to the provided stored embeddings.

    Parameters:
        group_photo_path (str): Path to the group photo.
        stored_embeddings (list of tuples): [(user, np.array_of_embedding), ...].
        metric (str): The distance metric to use for comparison.
        detector_backend (str): The face detection backend for DeepFace.
        align (bool): Align faces before embedding generation.
        distance_threshold (float): Below this distance => match found.

    Returns:
        list of (user, "Present") for each matched user.
    """
    logging.info(f"Comparing group photo: {group_photo_path} with stored embeddings. Metric: {metric}")

    attendance = []
    try:
        # Represent all faces found in the group photo
        group_faces = DeepFace.represent(
            img_path=group_photo_path,
            model_name="Facenet512",
            enforce_detection=True,
            detector_backend=detector_backend,
            align=align
        )

        if not group_faces:
            logging.warning("No faces detected in group photo.")
            return attendance

        # Compare each face in the group photo with each user's stored embedding
        for face_dict in group_faces:
            group_embedding = np.array(face_dict['embedding'])

            for user, user_embedding in stored_embeddings:
                # Calculate distance
                if metric == "cosine":
                    distance = cosine(group_embedding, user_embedding)
                elif metric == "euclidean":
                    distance = euclidean(group_embedding, user_embedding)
                elif metric == "euclidean_l2":
                    distance = np.linalg.norm(group_embedding - user_embedding)
                else:
                    logging.error(f"Unsupported metric: {metric}")
                    continue

                if distance < distance_threshold:
                    # We consider this face a match for the user
                    attendance.append((user, "Present"))
                    logging.debug(f"User {user.username} matched with distance {distance} using {metric}")
                    # Move on to the next face once we have a match
                    break

        logging.info(f"Group photo comparison completed. Found {len(attendance)} matches.")
        return attendance

    except Exception as e:
        logging.error(f"Error comparing group photo: {e}")
        return attendance


def scan_group_photos():
    """
    Update user embeddings (if needed), then go through all GroupPhotoAttendance
    entries, do face comparisons, create or update Attendance records, and
    clean up the processed group photos.
    """
    logging.info("Scanning group photos...")

    # Step 1: Update embeddings for all students if needed
    update_embeddings_for_all_students()

    # Step 2: Get stored embeddings
    stored_embeddings = get_stored_embeddings()

    # Step 3: Compare each group photo with the stored embeddings
    for group_photo in GroupPhotoAttendance.objects.all():
        group_photo_path = group_photo.file.path
        attendance_list = compare_with_group_photo(group_photo_path, stored_embeddings)
        attendance_date = timezone.localdate()

        # Step 4: Mark attendance
        for user, status in attendance_list:
            if (
                group_photo.course_id
                and not group_photo.course.people.filter(pk=user.pk).exists()
            ):
                continue
            Attendance.objects.update_or_create(
                student=user,
                course=group_photo.course,
                day=attendance_date.day,
                month=attendance_date.month,
                year=attendance_date.year,
                defaults={'status': status},
            )

        # Remove processed file & delete DB record
        file_name = group_photo.file.name
        storage = group_photo.file.storage
        group_photo.delete()
        if file_name:
            storage.delete(file_name)

    logging.info("Finished scanning all group photos.")


if __name__ == "__main__":
    scan_group_photos()
