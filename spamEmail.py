import os
import django

# 🛠️ Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gurmukhischool.settings")
django.setup()

from pages.models import Contact
from main.models import BlacklistedIP
from transformers import pipeline

def clean_spam_messages():
    print("🔍 Running daily spam cleanup...")

    # 🧠 Load lightweight spam classifier
    spam_classifier = pipeline("text-classification", model="mrm8488/bert-tiny-finetuned-sms-spam-detection")

    total_scanned = 0
    total_spam = 0

    for msg in Contact.objects.all():
        if not msg.message or len(msg.message.strip()) < 5:
            continue  # Skip empty or too-short messages

        try:
            result = spam_classifier(msg.message, truncation=True)[0]
            label = result['label'].lower()
            score = result['score']
            total_scanned += 1

            if label == 'spam' and score > 0.85:
                ip = msg.ip_address
                if ip:
                    BlacklistedIP.objects.get_or_create(
                        ip_address=ip,
                        reason = 'Spam detected in daily scan',
                    )
                msg.delete()
                total_spam += 1

        except Exception as e:
            print(f"⚠️ Error processing message ID {msg.id}: {e}")

    print(f"✅ Done. Scanned: {total_scanned}, Deleted Spam: {total_spam}")

if __name__ == "__main__":
    clean_spam_messages()
