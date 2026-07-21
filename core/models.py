from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField('action', max_length=80)
    object_type = models.CharField('type d’objet', max_length=100, blank=True)
    object_id = models.CharField('identifiant', max_length=80, blank=True)
    description = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'entrée du journal'
        verbose_name_plural = 'journal des actions'

    def __str__(self):
        return f'{self.action} · {self.created_at:%d/%m/%Y %H:%M}'