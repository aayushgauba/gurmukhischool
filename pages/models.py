from django.db import models

class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    date = models.DateField(auto_now=True)
    ip_address=models.GenericIPAddressField(null=True, blank=True)
    is_spam = models.BooleanField(default=False)