"""Seitengerüst: Skiplink, Landmarken, Theme-Knopf mit Zustand, Logo je Thema, Sprachwahl mit Beschriftung."""

import re

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import UserProfile


class ShellTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("gerueststeller", password="pw")
        UserProfile.objects.update_or_create(user=self.user, defaults={"subscription_tier": "pro"})

    def page(self, name="core:landing", login=False):
        if login:
            self.client.force_login(self.user)
        return self.client.get(reverse(name)).content.decode()

    def test_skip_link_and_main_landmark(self):
        html = self.page("core:login")

        self.assertIn('class="skip-link"', html)
        self.assertEqual(html.count('id="main-content"'), 1)
        self.assertEqual(html.count("<main"), 1)

    def test_the_stylesheets_come_from_files_not_from_an_inline_block(self):
        html = self.page("core:login")

        for sheet in ("tokens.css", "base.css", "components.css", "shell.css"):
            self.assertIn(f"core/css/{sheet}", html)
        self.assertNotIn(
            "--brand-navy:", html, "die Token stehen in tokens.css, nicht mehr im HTML"
        )

    def test_the_theme_button_reports_its_state_and_has_a_name(self):
        html = self.page("core:login")

        self.assertRegex(
            html, r'<button[^>]*id="themeToggle"[^>]*aria-label="[^"]+"[^>]*aria-pressed="false"'
        )

    def test_both_logo_variants_are_present_and_only_one_has_a_text_alternative(self):
        html = self.page("core:login")

        self.assertIn("logo--on-light", html)
        self.assertIn("logo--on-dark", html)
        dark_img = re.search(r"<img[^>]*logo--on-dark[^>]*>", html).group(0)
        self.assertIn(
            'alt=""',
            dark_img,
            "die zweite Fassung ist Dekor, sonst läse der Screenreader den Namen doppelt",
        )

    def test_the_menu_uses_disclosure_buttons_not_aria_menus(self):
        html = self.page("core:dashboard", login=True)

        self.assertNotIn('role="menu"', html)
        self.assertNotIn('role="menuitem"', html)
        for target in ("navDropdownManage", "navDropdownBilling", "navDropdownFaq"):
            self.assertRegex(html, rf'aria-expanded="false" aria-controls="{target}"')
            self.assertIn(f'id="{target}"', html)

    def test_the_current_page_is_marked(self):
        html = self.page("core:dashboard", login=True)

        self.assertRegex(html, r'<a href="[^"]*dashboard/" aria-current="page">')

    def test_footer_labels_follow_the_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        html = self.client.get(reverse("core:login")).content.decode()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "de"
        with_de = self.client.get(reverse("core:login")).content.decode()

        self.assertNotIn("Seitenende", html)
        self.assertIn('aria-label="Site footer"', html)
        self.assertIn('aria-label="Rechtliche Hinweise"', with_de)

    def test_the_language_select_has_a_label(self):
        html = self.page("core:login")

        self.assertRegex(html, r'<select[^>]*name="language"[^>]*aria-label="[^"]+"')
