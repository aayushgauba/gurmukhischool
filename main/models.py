from django.db import models

class CarouselImage(models.Model):
    title = models.CharField(max_length=100)
    image = models.FileField(upload_to='carousel_images/')
    order = models.PositiveIntegerField(blank=True, null=True)
    description = models.TextField()
    def __str__(self):
        return self.title
