import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gurmukhischool.settings")
django.setup()
from pages.models import Contact
from main.models import BlacklistedIP
from transformers import pipeline

def clean_spam_messages():
    print("🔍 Running daily spam cleanup...")

    spam_classifier = pipeline("text-classification", model="mrm8488/bert-tiny-finetuned-sms-spam-detection")

    total_scanned = 0
    total_spam = 0

    for msg in Contact.objects.all():
        result = spam_classifier(msg.message)[0]
        label = result['label'].lower()
        score = result['score']
        total_scanned += 1

        if label == 'spam' and score > 0.85:
            if msg.ip_address:
                BlacklistedIP.objects.get_or_create(
                    ip_address=msg.ip_address,
                    defaults={'reason': 'Spam detected in daily scan'}
                )
            BlacklistedIP.objects.get_or_create(
                ip_address=msg.ip_address,
                defaults={'reason': 'Spam detected in daily scan'}
            )
            msg.delete()
            total_spam += 1

    print(f"✅ Done. Scanned: {total_scanned}, Deleted Spam: {total_spam}")

if __name__ == "__main__":
    clean_spam_messages()
