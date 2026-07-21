from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import AuditLog


class RoleAndDashboardTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_user(
            username='admin-role', password='test-pass', is_staff=True,
            role=users.Role.ADMINISTRATOR,
        )
        self.editor = users.objects.create_user(
            username='editor-role', password='test-pass', is_staff=True,
            role=users.Role.EDITOR,
        )

    def test_editor_can_view_statistics_but_not_audience_or_audit(self):
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse('core:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('core:statistics')).status_code, 200)
        self.assertEqual(self.client.get(reverse('subscribers:list')).status_code, 302)
        self.assertEqual(self.client.get(reverse('core:audit_log')).status_code, 302)

    def test_administrator_can_view_audit_log(self):
        AuditLog.objects.create(user=self.admin, action='test.action', description='Test')
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:audit_log'))
        self.assertContains(response, 'test.action')