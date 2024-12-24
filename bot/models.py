from django.db import models

# Create your models here.

from django.contrib.auth.models import User

# class Booking(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     source = models.CharField(max_length=100)
#     destination = models.CharField(max_length=100)
#     created_at = models.DateTimeField(auto_now_add=True)
# models.py
from django.db import models
from django.contrib.auth.models import User
# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser 
# from phonenumber_field.modelfields import PhoneNumberField  # Optional, for better phone number handling

# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser , Group, Permission

# class User(AbstractUser ):
#     whatsapp_number = models.CharField(max_length=15, blank=True, null=True)  # Example field

#     # Specify related_name to avoid clashes
#     groups = models.ManyToManyField(
#         Group,
#         related_name='custom_user_set',  # Change this to a unique name
#         blank=True,
#         help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
#         verbose_name='groups',
#     )
    
#     user_permissions = models.ManyToManyField(
#         Permission,
#         related_name='custom_user_set',  # Change this to a unique name
#         blank=True,
#         help_text='Specific permissions for this user.',
#         verbose_name='user permissions',
#     )

#     def __str__(self):
#         return self.username
# models.py
from django.db import models
from django.contrib.auth.models import User

class Route(models.Model):
    source = models.CharField(max_length=100,null=True)
    destination = models.CharField(max_length=100,null=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2 ,null=True)

    def __str__(self):
        return f"{self.source} to {self.destination}"

class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    route = models.ForeignKey(Route, on_delete=models.CASCADE,null=True)
    ticket_count = models.PositiveIntegerField(null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    whatsapp_number = models.CharField(max_length=15, blank=True, null=True)
    def save(self, *args, **kwargs):
        # Calculate total price based on ticket count and route price
        self.total_price = self.route.base_price * self.ticket_count
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking by {self.user.username} for {self.ticket_count} tickets"