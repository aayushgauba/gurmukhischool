from django.test import TestCase
from django.urls import reverse


class LangarScheduleTests(TestCase):
    def test_home_page_displays_weekly_langar_schedule(self):
        response = self.client.get(reverse("indexMain"))

        self.assertContains(
            response,
            "Langar is held every Saturday and Sunday starting at 10:00 AM.",
        )

    def test_about_page_displays_weekly_langar_schedule(self):
        response = self.client.get(reverse("aboutMain"))

        self.assertContains(
            response,
            "every Saturday and Sunday starting at 10:00 AM",
        )
