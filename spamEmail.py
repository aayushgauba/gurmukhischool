import os
import django

# 🛠️ Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gurmukhischool.settings")
django.setup()

from pages.models import Contact
from transformers import BertTokenizerFast, BertForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
import torch
import pandas as pd

# 🧩 Custom Dataset
class ContactSpamDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=512):
        self.encodings = tokenizer(texts, truncation=True, padding=True, max_length=max_length)
        self.labels = labels

    def __getitem__(self, idx):
        return {
            **{k: torch.tensor(v[idx]) for k, v in self.encodings.items()},
            "labels": torch.tensor(self.labels[idx], dtype=torch.long)
        }

    def __len__(self):
        return len(self.labels)

messages = Contact.objects.exclude(message__isnull=True).exclude(message__exact='').all()
data = [(m.message.strip(), int(m.is_spam)) for m in messages if len(m.message.strip()) > 5]
df = pd.DataFrame(data, columns=["text", "label"])
train_texts, val_texts, train_labels, val_labels = train_test_split(df["text"], df["label"], test_size=0.2, random_state=42)
tokenizer = BertTokenizerFast.from_pretrained("prajjwal1/bert-tiny")
train_dataset = ContactSpamDataset(train_texts.tolist(), train_labels.tolist(), tokenizer)
val_dataset = ContactSpamDataset(val_texts.tolist(), val_labels.tolist(), tokenizer)
model = BertForSequenceClassification.from_pretrained("prajjwal1/bert-tiny", num_labels=2)
training_args = TrainingArguments(
    output_dir="./spam_model",
    evaluation_strategy="epoch",
    save_strategy="epoch",
    num_train_epochs=3,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    logging_dir="./logs",
    logging_steps=10,
    save_total_limit=1,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss"
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset
)
trainer.train()
model.save_pretrained("spam_model")
tokenizer.save_pretrained("spam_model")

print("✅ Model retrained with full 512-token context and saved.")
