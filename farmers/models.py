from django.db import models
from django.contrib.auth.models import User

class Farmer(models.Model):
    user = models.OneToOneField(
    User,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    village = models.CharField(max_length=100)
    district = models.CharField(max_length=100)

    def __str__(self):
        return self.name