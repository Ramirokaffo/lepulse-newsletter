from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Utilisateur interne, extensible sans modifier les comptes Django."""

    class Role(models.TextChoices):
        ADMINISTRATOR = 'administrator', 'Administrateur'
        EDITOR = 'editor', 'Rédacteur'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ADMINISTRATOR)

    @property
    def is_administrator(self):
        return self.is_superuser or self.role == self.Role.ADMINISTRATOR

    class Meta:
        verbose_name = 'utilisateur'
        verbose_name_plural = 'utilisateurs'