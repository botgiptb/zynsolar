from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Customer


class CustomerModelAndViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="customer_test_user",
            password="testpassword123",
            is_staff=True
        )
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name="Alice Walker",
            phone="+1 555-111-2233",
            email="alice@walker.com",
            customer_type='INDIVIDUAL',
            house_building="12B",
            street="Highland Ave",
            city="Phoenix",
            state="AZ",
            postal_code="85001"
        )

    def test_customer_creation_and_auto_id(self):
        self.assertTrue(self.customer.customer_id.startswith("CUST-"))
        self.assertEqual(self.customer.full_address, "12B, Highland Ave, Phoenix, AZ, 85001")
        self.assertEqual(self.customer.total_bookings, 0)

    def test_customer_list_view(self):
        response = self.client.get(reverse('customers:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Walker")
        self.assertContains(response, self.customer.customer_id)

    def test_customer_detail_view(self):
        response = self.client.get(self.customer.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Walker")
        self.assertContains(response, "Phoenix")

    def test_customer_quick_create_ajax(self):
        response = self.client.post(reverse('customers:quick_create'), {
            'name': 'Bob Ross',
            'phone': '+1 555-888-9999',
            'city': 'Scottsdale',
            'street': 'Painter Way'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['customer']['name'], 'Bob Ross')
        self.assertTrue(Customer.objects.filter(phone='+1 555-888-9999').exists())

    def test_unauthenticated_access_redirects_to_login(self):
        unauth_client = Client()
        response = unauth_client.get(reverse('customers:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('core:login'), response.url)

    def test_customer_attachment_upload_and_delete(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from customers.models import CustomerAttachment

        test_file = SimpleUploadedFile("bill.pdf", b"%PDF-1.4 fake pdf", content_type="application/pdf")
        upload_url = reverse('customers:attachment_upload', kwargs={'pk': self.customer.pk})
        resp = self.client.post(upload_url, {
            'category': 'ELECTRICITY_BILL',
            'title': 'KSEB Nov Bill',
            'file': test_file
        })
        self.assertEqual(resp.status_code, 302)
        att = CustomerAttachment.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.title, 'KSEB Nov Bill')
        self.assertTrue(att.is_pdf)

        # Delete
        del_url = reverse('customers:attachment_delete', kwargs={'pk': self.customer.pk, 'attachment_pk': att.pk})
        del_resp = self.client.post(del_url)
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(CustomerAttachment.objects.filter(pk=att.pk).exists())

