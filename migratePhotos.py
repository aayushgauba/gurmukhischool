#!/usr/bin/env python
import os
import django
from django.db import transaction

def setup_django():
    # Set the Django settings module environment variable
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gurmukhischool.settings')
    django.setup()

def transfer_photos():
    from portal.models import CustomUser, ProfilePhoto  # Import models after setup
    # Use a transaction to ensure atomicity of operations
    with transaction.atomic():
        users = CustomUser.objects.all()
        for user in users:
            if user.profile_photo:
                # Create or get a ProfilePhoto instance for the given file
                photo, created = ProfilePhoto.objects.get_or_create(
                    file=user.profile_photo.name
                )
                user.profile_photos.add(photo)
                print(f'Linked photo for user {user.username}')
    print('Photo transfer complete.')

def main():
    setup_django()
    transfer_photos()

if __name__ == '__main__':
    main()
