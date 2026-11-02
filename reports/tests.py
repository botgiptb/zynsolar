from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from customers.models import Customer
from bookings.models import SolarBooking


class ReportsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="report_test_user",
            password="testpassword123",
            is_staff=True
        )
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name="Report Customer",
            phone="+1 555-444-5555",
            city="Scottsdale",
            house_building="Bldg 3",
            street="Scottsdale Rd",
            state="AZ",
            postal_code="85251"
        )
        self.booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('10.00'),
            booking_amount=Decimal('12000.00'),
            advance_payment=Decimal('4000.00'),
            stage=SolarBooking.STAGE_NEW,
            assigned_salesperson="Sarah Jenkins"
        )

    def test_report_dashboard_view(self):
        response = self.client.get(reverse('reports:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Executive Solar Intelligence")
        self.assertContains(response, self.booking.booking_ref)

    def test_export_csv(self):
        response = self.client.get(reverse('reports:export_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn(self.booking.booking_ref.encode(), response.content)

    def test_export_excel(self):
        response = self.client.get(reverse('reports:export_excel'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue('spreadsheetml' in response['Content-Type'])

    def test_printable_report(self):
        response = self.client.get(reverse('reports:printable'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.booking.booking_ref)
