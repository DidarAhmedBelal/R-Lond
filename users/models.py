from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from .enums import UserRole
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN.value)
        extra_fields.setdefault('agree_to_terms', True) 

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        if extra_fields.get('role') != UserRole.ADMIN.value:
            raise ValueError('Superuser must have role of admin.')
        if extra_fields.get('agree_to_terms') is not True:
            raise ValueError('Superuser must agree to the terms.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)

    profile_image = models.ImageField(upload_to="profiles/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    secondary_number = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    gender = models.CharField(max_length=10, blank=True, choices=[
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ])
    date_of_birth = models.DateField(blank=True, null=True)
    national_id = models.CharField(max_length=50, blank=True)

    role = models.CharField(max_length=20, choices=UserRole.choices(), default=UserRole.CUSTOMER.value)
    agree_to_terms = models.BooleanField(default=False)  

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)  

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def generate_otp(self):
        import random
        otp = ''.join(random.choices('0123456789', k=6))
        self.otp_code = otp
        self.otp_created_at = timezone.now()
        self.save(update_fields=['otp_code', 'otp_created_at'])
        return otp

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email
