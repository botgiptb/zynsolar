from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile, CompanySetting


class UserRegistrationAndApprovalTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='adminpassword123'
        )
        self.admin_profile = UserProfile.objects.filter(user=self.admin).first()
        if not self.admin_profile:
            self.admin_profile = UserProfile.objects.create(
                user=self.admin,
                status=UserProfile.STATUS_APPROVED,
                role='ADMIN'
            )

    def test_user_registration_creates_inactive_user_with_pending_profile(self):
        url = reverse('core:register')
        resp = self.client.post(url, {
            'first_name': 'John',
            'last_name': 'Doe',
            'username': 'johndoe',
            'email': 'john@solarcrm.com',
            'phone': '+1 555-1234',
            'role': 'SALES',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('core:login'))

        user = User.objects.filter(username='johndoe').first()
        self.assertIsNotNone(user)
        self.assertFalse(user.is_active)  # Inactive until approved
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')

        profile = getattr(user, 'profile', None)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.status, UserProfile.STATUS_PENDING)
        self.assertEqual(profile.role, 'SALES')

    def test_login_blocked_while_pending_approval(self):
        # Register user
        self.client.post(reverse('core:register'), {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'username': 'janesmith',
            'email': 'jane@solarcrm.com',
            'phone': '+1 555-5678',
            'role': 'SURVEYOR',
            'password': 'password123',
            'confirm_password': 'password123'
        })

        # Attempt login before approval
        login_resp = self.client.post(reverse('core:login'), {
            'username': 'janesmith',
            'password': 'password123'
        })
        self.assertEqual(login_resp.status_code, 200)
        self.assertTrue(login_resp.context['is_pending_approval'])
        # User is NOT logged in
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_admin_approval_activates_user_and_allows_login(self):
        # Register user
        self.client.post(reverse('core:register'), {
            'first_name': 'Alex',
            'last_name': 'Rivera',
            'username': 'alexrivera',
            'email': 'alex@solarcrm.com',
            'role': 'INSTALLER',
            'password': 'password123',
            'confirm_password': 'password123'
        })

        user = User.objects.get(username='alexrivera')
        profile = user.profile
        self.assertEqual(profile.status, UserProfile.STATUS_PENDING)

        # Login as Admin
        self.client.login(username='admin_test', password='adminpassword123')

        # Admin approves user
        approve_url = reverse('core:user_approve', kwargs={'pk': profile.pk})
        resp = self.client.post(approve_url, {
            'role': 'INSTALLER',
            'grant_staff': '0'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('core:user_approvals'))

        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(profile.status, UserProfile.STATUS_APPROVED)
        self.assertEqual(profile.approved_by, self.admin)
        self.assertIsNotNone(profile.approved_at)

        # Logout admin and login as Alex
        self.client.logout()
        alex_login_resp = self.client.post(reverse('core:login'), {
            'username': 'alexrivera',
            'password': 'password123'
        })
        self.assertEqual(alex_login_resp.status_code, 302)
        self.assertRedirects(alex_login_resp, reverse('core:dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)

    def test_admin_reject_workflow(self):
        # Register user
        self.client.post(reverse('core:register'), {
            'first_name': 'Bob',
            'last_name': 'Reject',
            'username': 'bobreject',
            'email': 'bob@solarcrm.com',
            'role': 'DRIVER',
            'password': 'password123',
            'confirm_password': 'password123'
        })

        user = User.objects.get(username='bobreject')
        profile = user.profile

        # Admin rejects
        self.client.login(username='admin_test', password='adminpassword123')
        reject_url = reverse('core:user_reject', kwargs={'pk': profile.pk})
        resp = self.client.post(reject_url, {
            'reason': 'Not an authorized technician.'
        })
        self.assertEqual(resp.status_code, 302)

        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(profile.status, UserProfile.STATUS_REJECTED)
        self.assertEqual(profile.rejection_reason, 'Not an authorized technician.')

        # Attempt to login
        self.client.logout()
        bob_resp = self.client.post(reverse('core:login'), {
            'username': 'bobreject',
            'password': 'password123'
        })
        self.assertEqual(bob_resp.status_code, 200)
        self.assertTrue(bob_resp.context['is_rejected'])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_unauthenticated_access_redirects_to_login(self):
        # Client not logged in
        resp = self.client.get(reverse('core:dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('core:login'), resp.url)

        resp_bookings = self.client.get(reverse('bookings:list'))
        self.assertEqual(resp_bookings.status_code, 302)
        self.assertIn(reverse('core:login'), resp_bookings.url)

    def test_logout_redirects_to_login(self):
        self.client.login(username='admin_test', password='adminpassword123')
        resp = self.client.post(reverse('core:logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('core:login'))
        self.assertNotIn('_auth_user_id', self.client.session)


class TeamManagementAndPerformanceTestCase(TestCase):
    def setUp(self):
        from decimal import Decimal
        from core.models import TeamMember
        from customers.models import Customer
        from bookings.models import SolarBooking

        self.client = Client()
        self.user = User.objects.create_user(
            username="team_test_admin",
            password="adminpassword123",
            first_name="Team",
            last_name="Manager",
            is_staff=True
        )
        self.profile = getattr(self.user, 'profile', None)
        if not self.profile:
            self.profile = UserProfile.objects.create(
                user=self.user,
                status=UserProfile.STATUS_APPROVED,
                role='ADMIN'
            )
        else:
            self.profile.status = UserProfile.STATUS_APPROVED
            self.profile.role = 'ADMIN'
            self.profile.save()
        self.client.force_login(self.user)

        self.sales_rep = TeamMember.objects.create(
            name="John Solar",
            role="SALES",
            phone="+1 555-0101",
            monthly_target_kw=Decimal('20.00'),
            is_active=True
        )
        self.installer = TeamMember.objects.create(
            name="Crew Alpha",
            role="INSTALLER",
            phone="+1 555-0102",
            is_active=True
        )

        self.customer = Customer.objects.create(
            name="Team Client",
            phone="+1 555-9988",
            house_building="Bldg 1",
            street="Solar Way",
            city="Phoenix",
            state="AZ",
            postal_code="85001"
        )
        self.booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('10.00'),
            booking_amount=Decimal('12000.00'),
            advance_payment=Decimal('4000.00'),
            assigned_salesperson="John Solar",
            installation_team="Crew Alpha",
            stage=SolarBooking.STAGE_INSTALLATION,
            installation_progress=70
        )

    def test_team_list_view(self):
        resp = self.client.get(reverse('core:team_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "John Solar")
        self.assertContains(resp, "Crew Alpha")
        self.assertContains(resp, "Operations Team Management")

    def test_team_detail_view_and_performance(self):
        resp = self.client.get(reverse('core:team_detail', kwargs={'pk': self.sales_rep.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "John Solar")
        self.assertContains(resp, "12,000")  # Revenue
        self.assertContains(resp, self.booking.booking_ref)

    def test_team_member_create_and_toggle(self):
        from core.models import TeamMember
        # Create
        create_url = reverse('core:team_create')
        resp = self.client.post(create_url, {
            'name': 'Surveyor Dave',
            'designation': 'Site Engineer',
            'phone': '+1 555-7777',
            'is_active': 'on'
        })
        self.assertEqual(resp.status_code, 302)
        dave = TeamMember.objects.filter(name='Surveyor Dave').first()
        self.assertIsNotNone(dave)
        self.assertTrue(dave.is_active)

        # Toggle Active
        toggle_url = reverse('core:team_toggle_active', kwargs={'pk': dave.pk})
        self.client.post(toggle_url)
        dave.refresh_from_db()
        self.assertFalse(dave.is_active)

    def test_sync_users_to_team(self):
        from core.models import TeamMember
        # Sync users action
        sync_url = reverse('core:team_sync_users')
        resp = self.client.post(sync_url)
        self.assertEqual(resp.status_code, 302)
        # Verify self.user was synced
        synced_member = TeamMember.objects.filter(user=self.user).first()
        self.assertIsNotNone(synced_member)
        self.assertEqual(synced_member.name, "Team Manager")


from django.test import override_settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware
import json


class ErrorManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='err_user', password='password123')
        self.profile = UserProfile.objects.filter(user=self.user).first()
        if self.profile:
            self.profile.status = UserProfile.STATUS_APPROVED
            self.profile.role = 'SALES'
            self.profile.save()
        self.client.force_login(self.user)

    def _prepare_request(self, request):
        request.user = self.user
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        request.session.save()
        return request

    @override_settings(DEBUG=False)
    def test_custom_404_html_view(self):
        resp = self.client.get('/nonexistent-path-12345/')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, 'Page Not Found', status_code=404)
        self.assertContains(resp, 'HTTP ERROR 404', status_code=404)

    @override_settings(DEBUG=False)
    def test_custom_404_ajax_json_view(self):
        resp = self.client.get('/api/nonexistent/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['code'], 404)
        self.assertEqual(data['error'], 'NotFound')

    def test_custom_500_html_and_ajax_views(self):
        from core.views import custom_server_error_view
        from django.test import RequestFactory
        factory = RequestFactory()

        # HTML
        req_html = self._prepare_request(factory.get('/some-failing-route/'))
        resp_html = custom_server_error_view(req_html)
        self.assertEqual(resp_html.status_code, 500)
        self.assertIn(b'Unexpected System Error', resp_html.content)

        # AJAX
        req_ajax = factory.get('/some-failing-route/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        resp_ajax = custom_server_error_view(req_ajax)
        self.assertEqual(resp_ajax.status_code, 500)
        data = json.loads(resp_ajax.content.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['code'], 500)
        self.assertEqual(data['error'], 'InternalServerError')

    def test_custom_403_html_and_ajax_views(self):
        from core.views import custom_permission_denied_view
        from django.test import RequestFactory
        factory = RequestFactory()

        # HTML
        req_html = self._prepare_request(factory.get('/restricted/'))
        resp_html = custom_permission_denied_view(req_html)
        self.assertEqual(resp_html.status_code, 403)
        self.assertIn(b'Access Restricted', resp_html.content)

        # AJAX
        req_ajax = factory.get('/restricted/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        resp_ajax = custom_permission_denied_view(req_ajax)
        self.assertEqual(resp_ajax.status_code, 403)
        data = json.loads(resp_ajax.content.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['code'], 403)
        self.assertEqual(data['error'], 'PermissionDenied')

    def test_custom_400_html_and_ajax_views(self):
        from core.views import custom_bad_request_view
        from django.test import RequestFactory
        factory = RequestFactory()

        # HTML
        req_html = self._prepare_request(factory.get('/bad-params/'))
        resp_html = custom_bad_request_view(req_html)
        self.assertEqual(resp_html.status_code, 400)
        self.assertIn(b'Invalid Request', resp_html.content)

        # AJAX
        req_ajax = factory.get('/bad-params/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        resp_ajax = custom_bad_request_view(req_ajax)
        self.assertEqual(resp_ajax.status_code, 400)
        data = json.loads(resp_ajax.content.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['code'], 400)

    def test_custom_csrf_failure_view(self):
        from core.views import custom_csrf_failure_view
        from django.test import RequestFactory
        factory = RequestFactory()

        # HTML
        req_html = self._prepare_request(factory.post('/form-submit/'))
        resp_html = custom_csrf_failure_view(req_html, reason="Token missing")
        self.assertEqual(resp_html.status_code, 403)
        self.assertIn(b'Session Token Expired', resp_html.content)

        # AJAX
        req_ajax = factory.post('/form-submit/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        resp_ajax = custom_csrf_failure_view(req_ajax, reason="Token missing")
        self.assertEqual(resp_ajax.status_code, 403)
        data = json.loads(resp_ajax.content.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['error'], 'CSRFTokenExpired')

    def test_global_exception_middleware_ajax_exception(self):
        from core.middleware import GlobalExceptionMiddleware
        from django.test import RequestFactory

        factory = RequestFactory()
        req = factory.get('/api/test-error/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        req.user = self.user

        def get_response(r):
            raise ValueError("Test database failure")

        middleware = GlobalExceptionMiddleware(get_response)
        resp = middleware.process_exception(req, ValueError("Test database failure"))
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 500)
        data = json.loads(resp.content.decode('utf-8'))
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['code'], 500)
        self.assertIn('unexpected error', data['message'].lower())


class CatalogManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='catalog_admin', password='password123')
        self.profile = UserProfile.objects.filter(user=self.user).first()
        if self.profile:
            self.profile.status = UserProfile.STATUS_APPROVED
            self.profile.role = 'ADMIN'
            self.profile.save()
        self.client.force_login(self.user)

    def test_catalog_ensure_defaults(self):
        from core.models import CatalogItem
        CatalogItem.objects.all().delete()
        CatalogItem.ensure_defaults()
        self.assertTrue(CatalogItem.objects.filter(category=CatalogItem.CATEGORY_PANEL).exists())
        self.assertTrue(CatalogItem.objects.filter(category=CatalogItem.CATEGORY_INVERTER).exists())
        self.assertTrue(CatalogItem.objects.filter(category=CatalogItem.CATEGORY_MOUNTING).exists())
        self.assertTrue(CatalogItem.objects.filter(category=CatalogItem.CATEGORY_ACCESSORY).exists())
        self.assertTrue(CatalogItem.objects.filter(category=CatalogItem.CATEGORY_LEAD_SOURCE).exists())
        self.assertTrue(CatalogItem.objects.filter(category=CatalogItem.CATEGORY_ASSIGNED_ROLE).exists())

    def test_settings_view_add_toggle_and_delete_catalog_item(self):
        from core.models import CatalogItem
        settings_url = reverse('core:settings')

        # 1. Add new solar panel model
        resp = self.client.post(settings_url, {
            'action': 'add_catalog_item',
            'category': CatalogItem.CATEGORY_PANEL,
            'name': 'Waaree 545W Mono PERC Half-Cut',
            'description': 'High efficiency tier 1 module',
            'active_tab': 'catalog'
        })
        self.assertEqual(resp.status_code, 302)
        item = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_PANEL, name='Waaree 545W Mono PERC Half-Cut').first()
        self.assertIsNotNone(item)
        self.assertTrue(item.is_active)
        self.assertEqual(item.description, 'High efficiency tier 1 module')

        # 2. Toggle active
        resp_toggle = self.client.post(settings_url, {
            'action': 'toggle_catalog_item',
            'item_id': item.pk,
            'cat': CatalogItem.CATEGORY_PANEL,
            'active_tab': 'catalog'
        })
        self.assertEqual(resp_toggle.status_code, 302)
        item.refresh_from_db()
        self.assertFalse(item.is_active)

        # 3. Delete option
        resp_delete = self.client.post(settings_url, {
            'action': 'delete_catalog_item',
            'item_id': item.pk,
            'cat': CatalogItem.CATEGORY_PANEL,
            'active_tab': 'catalog'
        })
        self.assertEqual(resp_delete.status_code, 302)
        self.assertFalse(CatalogItem.objects.filter(pk=item.pk).exists())

    def test_catalog_ajax_api(self):
        from core.models import CatalogItem

        # 1. GET active items
        get_url = f"{reverse('core:catalog_ajax')}?category={CatalogItem.CATEGORY_INVERTER}"
        resp_get = self.client.get(get_url)
        self.assertEqual(resp_get.status_code, 200)
        data_get = resp_get.json()
        self.assertEqual(data_get['status'], 'success')
        self.assertIn('On-Grid Smart Inverter 5kW', data_get['items'])

        # 2. POST add new inverter
        post_url = reverse('core:catalog_ajax')
        resp_post = self.client.post(post_url, {
            'category': CatalogItem.CATEGORY_INVERTER,
            'name': 'Sungrow 10kW Commercial 3-Phase',
            'description': 'Dual MPPT'
        })
        self.assertEqual(resp_post.status_code, 200)
        data_post = resp_post.json()
        self.assertEqual(data_post['status'], 'success')
        item_id = data_post['item']['id']
        self.assertTrue(CatalogItem.objects.filter(pk=item_id).exists())

        # 3. DELETE inverter via AJAX
        del_url = reverse('core:catalog_delete_ajax', kwargs={'pk': item_id})
        resp_del = self.client.post(del_url)
        self.assertEqual(resp_del.status_code, 200)
        self.assertEqual(resp_del.json()['status'], 'success')
        self.assertFalse(CatalogItem.objects.filter(pk=item_id).exists())

    def test_booking_form_reflects_catalog_items(self):
        from core.models import CatalogItem
        from bookings.forms import SolarBookingForm

        # Create new unique panel in catalog
        panel_name = 'Adani Solar 540W Bifacial Ultra'
        CatalogItem.objects.create(
            category=CatalogItem.CATEGORY_PANEL,
            name=panel_name,
            is_active=True
        )

        form = SolarBookingForm()
        choice_values = [c[0] for c in form.fields['panel_type'].choices]
        self.assertIn(panel_name, choice_values)

        # Deactivate panel in catalog
        item = CatalogItem.objects.get(category=CatalogItem.CATEGORY_PANEL, name=panel_name)
        item.is_active = False
        item.save()

        form2 = SolarBookingForm()
        choice_values2 = [c[0] for c in form2.fields['panel_type'].choices]
        self.assertNotIn(panel_name, choice_values2)

