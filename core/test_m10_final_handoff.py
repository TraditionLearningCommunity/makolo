from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class M10FinalWebAuthContractTests(TestCase):
    def test_global_login_and_logout_use_canonical_core_login(self):
        self.assertEqual(settings.LOGIN_URL, "core:login")
        self.assertEqual(settings.LOGOUT_REDIRECT_URL, "core:login")

    def test_anonymous_library_redirects_instead_of_erroring(self):
        response = self.client.get(reverse("personal_assets:list"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f'{reverse("core:login")}?next='))

    def test_anonymous_operations_redirects_instead_of_erroring(self):
        response = self.client.get(reverse("operations:organizations"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f'{reverse("core:login")}?next='))
