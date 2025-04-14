from django.db import models

class CarouselImage(models.Model):
    title = models.CharField(max_length=100)
    image = models.FileField(upload_to='carousel_images/')
    order = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField()
    def __str__(self):
        return self.title
    
class BlacklistedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.TextField(blank=True, null=True)
    added_on = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.ip_address} - {self.reason or 'No reason provided'}"
