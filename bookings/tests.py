from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from customers.models import Customer
from bookings.models import SolarBooking, BookingAuditLog, PipelineStage, BookingPayment, BookingNote, Task


class SolarBookingWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="booking_test_user",
            password="testpassword123",
            is_staff=True
        )
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone="+1 555-900-1122",
            city="Phoenix",
            house_building="Apt 1",
            street="Main St",
            state="AZ",
            postal_code="85002"
        )
        self.booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('6.00'),
            panel_type="Bifacial 550W",
            inverter_type="Growatt 6kW",
            booking_amount=Decimal('8000.00'),
            advance_payment=Decimal('2000.00'),
            assigned_salesperson="Sarah Jenkins",
            assigned_team_driver="Crew 1"
        )

    def test_auto_booking_ref_and_balance_calculation(self):
        self.assertTrue(self.booking.booking_ref.startswith("SB-"))
        self.assertEqual(self.booking.balance_amount, Decimal('6000.00'))
        self.assertEqual(self.booking.stage, SolarBooking.STAGE_NEW)
        self.assertEqual(self.booking.stage_step_number, 1)

    def test_four_stage_workflow_advancement(self):
        # 1. Advance to Stage 2: Site Survey
        url_advance = reverse('bookings:advance_stage', kwargs={'pk': self.booking.pk})
        resp = self.client.post(url_advance, {
            'target_stage': SolarBooking.STAGE_SURVEY,
            'survey_scheduled_date': '2026-11-01',
            'survey_team_driver': 'Surveyor Dave',
            'notes': 'Scheduled site visit'
        })
        self.assertEqual(resp.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.stage, SolarBooking.STAGE_SURVEY)
        self.assertEqual(self.booking.survey_status, 'SCHEDULED')
        self.assertEqual(self.booking.stage_step_number, 2)

        # 2. Advance to Stage 3: Installation
        resp = self.client.post(url_advance, {
            'target_stage': SolarBooking.STAGE_INSTALLATION,
            'survey_roof_measurements': '600 sq ft, 20 deg tilt',
            'installation_scheduled_date': '2026-11-05',
            'installation_team': 'Alpha Crew',
            'notes': 'Survey approved, starting install'
        })
        self.assertEqual(resp.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.stage, SolarBooking.STAGE_INSTALLATION)
        self.assertEqual(self.booking.stage_step_number, 3)

        # 3. Advance to Stage 4: Completed
        resp = self.client.post(url_advance, {
            'target_stage': SolarBooking.STAGE_COMPLETED,
            'actual_completion_date': '2026-11-10',
            'final_payment_received': '6000.00',
            'warranty_certificate_issued': 'on',
            'notes': 'Grid connected and tested'
        })
        self.assertEqual(resp.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.stage, SolarBooking.STAGE_COMPLETED)
        self.assertEqual(self.booking.stage_step_number, 4)
        self.assertEqual(self.booking.installation_progress, 100)
        self.assertEqual(self.booking.balance_amount, Decimal('0.00'))
        self.assertTrue(self.booking.warranty_certificate_issued)

        # Verify audit logs
        logs = BookingAuditLog.objects.filter(booking=self.booking)
        self.assertGreaterEqual(logs.count(), 3)

    def test_cancellation_and_reopen_workflow(self):
        # Cancel booking
        resp = self.client.post(reverse('bookings:cancel', kwargs={'pk': self.booking.pk}), {
            'cancellation_reason': 'Customer requested refund'
        })
        self.assertEqual(resp.status_code, 302)
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.is_cancelled)
        self.assertEqual(self.booking.cancellation_reason, 'Customer requested refund')

        # Reopen booking
        resp = self.client.post(reverse('bookings:reopen', kwargs={'pk': self.booking.pk}))
        self.assertEqual(resp.status_code, 302)
        self.booking.refresh_from_db()
        self.assertFalse(self.booking.is_cancelled)

    def test_custom_panel_creation_and_validation(self):
        url_create = reverse('bookings:create')
        # 1. Custom panel selected without custom name should fail validation
        resp_invalid = self.client.post(url_create, {
            'customer': self.customer.pk,
            'stage': SolarBooking.STAGE_NEW,
            'system_capacity_kw': '10.0',
            'panel_type': 'Custom Solar Module Spec',
            'custom_panel_name': '',
            'inverter_type': 'On-Grid Smart Inverter 5kW',
            'number_of_panels': '20',
            'installation_type': 'ROOFTOP_TIN',
            'booking_amount': '12000.00',
            'advance_payment': '3000.00',
            'booking_date': '2026-10-24',
            'assigned_salesperson': 'Unassigned',
            'assigned_team_driver': 'Unassigned'
        })
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertFormError(resp_invalid.context['form'], 'custom_panel_name', "Please enter the new solar panel model / wattage.")

        # 2. Custom panel selected with custom name should succeed and save custom name
        resp_valid = self.client.post(url_create, {
            'customer': self.customer.pk,
            'stage': SolarBooking.STAGE_NEW,
            'system_capacity_kw': '10.0',
            'panel_type': 'Custom Solar Module Spec',
            'custom_panel_name': 'Canadian Solar HiKu7 660W Bifacial',
            'inverter_type': 'On-Grid Smart Inverter 5kW',
            'number_of_panels': '20',
            'installation_type': 'ROOFTOP_TIN',
            'booking_amount': '12000.00',
            'advance_payment': '3000.00',
            'booking_date': '2026-10-24',
            'assigned_salesperson': 'Unassigned',
            'assigned_team_driver': 'Unassigned'
        })
        self.assertEqual(resp_valid.status_code, 302)
        new_booking = SolarBooking.objects.filter(customer=self.customer).order_by('-created_at').first()
        self.assertEqual(new_booking.panel_type, 'Canadian Solar HiKu7 660W Bifacial')

        # 3. Direct dynamically added option posted
        resp_direct = self.client.post(url_create, {
            'customer': self.customer.pk,
            'stage': SolarBooking.STAGE_NEW,
            'system_capacity_kw': '12.0',
            'panel_type': 'Trina Solar 670W Vertex',
            'inverter_type': 'On-Grid Smart Inverter 5kW',
            'number_of_panels': '24',
            'installation_type': 'ROOFTOP_TIN',
            'booking_amount': '15000.00',
            'advance_payment': '5000.00',
            'booking_date': '2026-10-24',
            'assigned_salesperson': 'Unassigned',
            'assigned_team_driver': 'Unassigned'
        })
        self.assertEqual(resp_direct.status_code, 302)
        new_booking2 = SolarBooking.objects.filter(customer=self.customer).order_by('-created_at').first()
        self.assertEqual(new_booking2.panel_type, 'Trina Solar 670W Vertex')

    def test_custom_installation_type_creation_and_validation(self):
        url_create = reverse('bookings:create')
        # 1. Custom mount selected without specifying custom mount should fail
        resp_invalid = self.client.post(url_create, {
            'customer': self.customer.pk,
            'stage': SolarBooking.STAGE_NEW,
            'system_capacity_kw': '10.0',
            'panel_type': 'Monocrystalline PERC 550W Half-Cut',
            'inverter_type': 'On-Grid Smart Inverter 5kW',
            'number_of_panels': '20',
            'installation_type': 'OTHER',
            'custom_installation_type': '',
            'booking_amount': '12000.00',
            'advance_payment': '3000.00',
            'booking_date': '2026-10-24',
            'assigned_salesperson': 'Unassigned',
            'assigned_team_driver': 'Unassigned'
        })
        self.assertEqual(resp_invalid.status_code, 200)
        self.assertFormError(resp_invalid.context['form'], 'custom_installation_type', "Please enter the custom mounting structure type.")

        # 2. Custom mount selected with custom name should succeed
        resp_valid = self.client.post(url_create, {
            'customer': self.customer.pk,
            'stage': SolarBooking.STAGE_NEW,
            'system_capacity_kw': '10.0',
            'panel_type': 'Monocrystalline PERC 550W Half-Cut',
            'inverter_type': 'On-Grid Smart Inverter 5kW',
            'number_of_panels': '20',
            'installation_type': 'OTHER',
            'custom_installation_type': 'Ballasted Commercial Flat Roof Mount',
            'booking_amount': '12000.00',
            'advance_payment': '3000.00',
            'booking_date': '2026-10-24',
            'assigned_salesperson': 'Unassigned',
            'assigned_team_driver': 'Unassigned'
        })
        self.assertEqual(resp_valid.status_code, 302)
        new_booking = SolarBooking.objects.filter(customer=self.customer).order_by('-created_at').first()
        self.assertEqual(new_booking.installation_type, 'Ballasted Commercial Flat Roof Mount')
        self.assertEqual(new_booking.get_installation_type_display(), 'Ballasted Commercial Flat Roof Mount')

        # 3. Direct dynamically added option posted
        resp_direct = self.client.post(url_create, {
            'customer': self.customer.pk,
            'stage': SolarBooking.STAGE_NEW,
            'system_capacity_kw': '10.0',
            'panel_type': 'Monocrystalline PERC 550W Half-Cut',
            'inverter_type': 'On-Grid Smart Inverter 5kW',
            'number_of_panels': '20',
            'installation_type': 'Pergola Canopy Mount',
            'booking_amount': '12000.00',
            'advance_payment': '3000.00',
            'booking_date': '2026-10-24',
            'assigned_salesperson': 'Unassigned',
            'assigned_team_driver': 'Unassigned'
        })
        self.assertEqual(resp_direct.status_code, 302)
        new_booking2 = SolarBooking.objects.filter(customer=self.customer).order_by('-created_at').first()
        self.assertEqual(new_booking2.installation_type, 'Pergola Canopy Mount')
        self.assertEqual(new_booking2.get_installation_type_display(), 'Pergola Canopy Mount')

    def test_assigned_staff_choices_populated_from_approved_staff(self):
        from core.models import UserProfile
        from bookings.forms import SolarBookingForm

        # Create an approved staff member
        approved_staff = User.objects.create_user(
            username="salmankm",
            first_name="Salman",
            last_name="KM",
            password="password123"
        )
        profile = getattr(approved_staff, 'profile', None)
        if not profile:
            profile = UserProfile.objects.create(user=approved_staff)
        profile.status = UserProfile.STATUS_APPROVED
        profile.role = 'SALES'
        profile.save()

        form = SolarBookingForm()
        staff_choice_values = [c[0] for c in form.fields['assigned_salesperson'].choices]
        self.assertIn('Salman KM', staff_choice_values)

    def test_booking_attachment_upload_and_delete(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from bookings.models import BookingAttachment

        test_file = SimpleUploadedFile("roof_photo.jpg", b"fake_image_bytes", content_type="image/jpeg")
        upload_url = reverse('bookings:attachment_upload', kwargs={'pk': self.booking.pk})
        resp = self.client.post(upload_url, {
            'category': 'SURVEY_ROOF',
            'title': 'South Roof Pitch',
            'file': test_file
        })
        self.assertEqual(resp.status_code, 302)
        att = BookingAttachment.objects.filter(booking=self.booking).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.title, 'South Roof Pitch')
        self.assertTrue(att.is_image)
        self.assertEqual(att.file_extension, '.jpg')

        # Test delete
        del_url = reverse('bookings:attachment_delete', kwargs={'pk': self.booking.pk, 'attachment_pk': att.pk})
        del_resp = self.client.post(del_url)
        self.assertEqual(del_resp.status_code, 302)
        self.assertFalse(BookingAttachment.objects.filter(pk=att.pk).exists())

    def test_pipeline_cards_view_default(self):
        url = reverse('bookings:list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'bookings/booking_list.html')
        self.assertIn('pipeline_columns', resp.context)
        cols = resp.context['pipeline_columns']
        self.assertEqual(len(cols), 4)
        new_col = cols[0]
        self.assertEqual(new_col['key'], SolarBooking.STAGE_NEW)
        self.assertEqual(new_col['count'], 1)
        self.assertEqual(new_col['bookings'][0], self.booking)
        self.assertContains(resp, 'Kanban')
        self.assertContains(resp, self.booking.booking_ref)

    def test_pipeline_search_filter(self):
        url = reverse('bookings:list') + '?q=Sarah'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.booking.booking_ref)

    def test_pipeline_filter_by_stage(self):
        url = reverse('bookings:list') + '?stage=NEW'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        cols = resp.context['pipeline_columns']
        self.assertEqual(len(cols), 1)
        self.assertEqual(cols[0]['key'], SolarBooking.STAGE_NEW)


class PipelineCustomizationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="pipeline_admin",
            password="testpassword123",
            is_staff=True,
            is_superuser=True
        )
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(name="Pipeline Customer", phone="+91 98888 11111", city="Calicut")
        PipelineStage.ensure_defaults()

    def test_default_seeded_stages(self):
        stages = list(PipelineStage.get_active_stages())
        self.assertEqual(len(stages), 4)
        self.assertEqual(stages[0].code, 'NEW')
        self.assertEqual(stages[1].code, 'SITE_SURVEY')
        self.assertEqual(stages[2].code, 'INSTALLATION')
        self.assertEqual(stages[3].code, 'COMPLETED')

    def test_add_custom_pipeline_stage(self):
        url = reverse('core:settings')
        resp = self.client.post(url, {
            'action': 'add_pipeline_stage',
            'name': 'Net Metering / DISCOM',
            'color': '#0891b2',
            'icon': 'bi-lightning-charge-fill',
            'position_after': 'SITE_SURVEY',
        })
        self.assertEqual(resp.status_code, 302)

        stage = PipelineStage.objects.filter(name='Net Metering / DISCOM').first()
        self.assertIsNotNone(stage)
        self.assertEqual(stage.color, '#0891b2')
        self.assertFalse(stage.is_system)

        # Verify Kanban board now has 5 columns
        board_url = reverse('bookings:list')
        board_resp = self.client.get(board_url)
        self.assertEqual(board_resp.status_code, 200)
        cols = board_resp.context['pipeline_columns']
        self.assertEqual(len(cols), 5)
        codes = [c['key'] for c in cols]
        self.assertIn(stage.code, codes)

    def test_reorder_and_toggle_stage(self):
        stage = PipelineStage.objects.create(
            name="Structural Check",
            code="STRUCT_CHECK",
            order=2,
            is_system=False,
            is_active=True
        )
        url = reverse('core:settings')

        # Toggle inactive
        self.client.post(url, {'action': 'toggle_pipeline_stage', 'stage_id': stage.pk})
        stage.refresh_from_db()
        self.assertFalse(stage.is_active)

        # Toggle active
        self.client.post(url, {'action': 'toggle_pipeline_stage', 'stage_id': stage.pk})
        stage.refresh_from_db()
        self.assertTrue(stage.is_active)

    def test_delete_custom_stage_with_safe_reassignment(self):
        stage = PipelineStage.objects.create(
            name="Procurement",
            code="PROCUREMENT",
            order=3,
            is_system=False,
            is_active=True
        )
        # Create a booking in this stage
        booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('5.00'),
            stage=stage.code,
            booking_amount=Decimal('100000')
        )
        url = reverse('core:settings')

        # Delete attempt without reassign should be blocked
        self.client.post(url, {
            'action': 'delete_pipeline_stage',
            'stage_id': stage.pk,
            'reassign_to': ''
        })
        self.assertTrue(PipelineStage.objects.filter(pk=stage.pk).exists())
        booking.refresh_from_db()
        self.assertEqual(booking.stage, stage.code)

        # Delete with valid reassignment to 'SITE_SURVEY'
        self.client.post(url, {
            'action': 'delete_pipeline_stage',
            'stage_id': stage.pk,
            'reassign_to': 'SITE_SURVEY'
        })
        self.assertFalse(PipelineStage.objects.filter(pk=stage.pk).exists())
        booking.refresh_from_db()
        self.assertEqual(booking.stage, 'SITE_SURVEY')

    def test_system_stage_cannot_be_deleted(self):
        new_stage = PipelineStage.objects.get(code='NEW')
        url = reverse('core:settings')
        self.client.post(url, {
            'action': 'delete_pipeline_stage',
            'stage_id': new_stage.pk,
        })
        self.assertTrue(PipelineStage.objects.filter(code='NEW').exists())


class PaymentAndCreditManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="accounts_officer", password="password123", is_staff=True)
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name="Rahul Sharma",
            phone="+91 9876543210",
            city="Jaipur",
            state="Rajasthan"
        )
        self.booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('5.00'),
            booking_amount=Decimal('200000.00'),
            advance_payment=Decimal('50000.00')
        )

    def test_booking_payment_creation_and_balance_recalculation(self):
        # Create an initial advance payment
        p1 = BookingPayment.objects.create(
            booking=self.booking,
            amount=Decimal('50000.00'),
            payment_method='UPI',
            milestone='BOOKING_ADVANCE',
            transaction_ref='UPI12345678'
        )
        self.assertTrue(p1.receipt_number.startswith("REC-"))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.total_paid, Decimal('50000.00'))
        self.assertEqual(self.booking.balance_amount, Decimal('150000.00'))
        self.assertEqual(self.booking.payment_percentage, 25)

        # Record second milestone payment (material dispatch)
        p2 = BookingPayment.objects.create(
            booking=self.booking,
            amount=Decimal('100000.00'),
            payment_method='NEFT_RTGS',
            milestone='MATERIAL_DISPATCH',
            transaction_ref='RTGS998877'
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.total_paid, Decimal('150000.00'))
        self.assertEqual(self.booking.balance_amount, Decimal('50000.00'))
        self.assertEqual(self.booking.payment_percentage, 75)

        # Delete second payment and verify balance rolls back
        p2.delete()
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.total_paid, Decimal('50000.00'))
        self.assertEqual(self.booking.balance_amount, Decimal('150000.00'))

    def test_record_payment_view_post(self):
        url = reverse('bookings:record_payment', kwargs={'pk': self.booking.pk})
        resp = self.client.post(url, {
            'amount': '30000.00',
            'payment_date': '2026-10-25',
            'payment_method': 'UPI',
            'milestone': 'FEASIBILITY_APPROVAL',
            'transaction_ref': 'UPI/TEST/001',
            'notes': 'Survey sign-off milestone payment'
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.total_paid, Decimal('80000.00'))
        self.assertEqual(self.booking.balance_amount, Decimal('120000.00'))

        # Verify audit log
        audit = BookingAuditLog.objects.filter(booking=self.booking, action='PAYMENT_UPDATED').first()
        self.assertIsNotNone(audit)
        self.assertIn("Payment received: ₹30,000.00", audit.notes)

    def test_payment_receipt_view_renders_correctly(self):
        payment = BookingPayment.objects.create(
            booking=self.booking,
            amount=Decimal('45000.00'),
            payment_method='NEFT_RTGS',
            milestone='INSTALLATION_PROGRESS',
            transaction_ref='UTR445566'
        )
        url = reverse('bookings:payment_receipt', kwargs={'payment_id': payment.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, payment.receipt_number)
        self.assertContains(resp, self.customer.name)
        self.assertContains(resp, "45,000.00")
        self.assertContains(resp, "Forty Five Thousand Rupees Only")

    def test_credit_management_view(self):
        url = reverse('bookings:credit_management')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Credit & Receivables Management")
        self.assertContains(resp, self.customer.name)
        self.assertIn('aging_summary', resp.context)
        self.assertIn('total_outstanding', resp.context)
        self.assertEqual(resp.context['total_outstanding'], self.booking.balance_amount)


class InternalNotesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="tech_engineer", password="password123", is_staff=True)
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name="Vikram Patel",
            phone="+91 9123456789",
            city="Ahmedabad"
        )
        self.booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('10.00'),
            booking_amount=Decimal('450000.00'),
            internal_notes="Customer requested installation only on weekends."
        )

    def test_booking_note_model_and_counts(self):
        self.assertEqual(self.booking.all_notes_count, 1)  # 1 from internal_notes
        note = BookingNote.objects.create(
            booking=self.booking,
            author=self.user,
            author_name="tech_engineer",
            category=BookingNote.CATEGORY_TECHNICAL,
            note_text="Roof parapet is 3 feet high; shadow clearance verified.",
            is_pinned=True
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.all_notes_count, 2)
        self.assertTrue(note.is_pinned)
        self.assertIn("tech_engineer", str(note))

    def test_add_internal_note_view(self):
        url = reverse('bookings:add_note', kwargs={'pk': self.booking.pk})
        resp = self.client.post(url, {
            'category': 'SITE_SURVEY',
            'note_text': 'Distribution box needs 16 sq mm copper cable extension.',
            'is_pinned': 'on'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        note = BookingNote.objects.filter(booking=self.booking, category='SITE_SURVEY').first()
        self.assertIsNotNone(note)
        self.assertEqual(note.author, self.user)
        self.assertTrue(note.is_pinned)

        # Verify audit log
        audit = BookingAuditLog.objects.filter(booking=self.booking, action='NOTE_ADDED').first()
        self.assertIsNotNone(audit)
        self.assertIn("Distribution box needs", audit.notes)

    def test_delete_internal_note_view(self):
        note = BookingNote.objects.create(
            booking=self.booking,
            author=self.user,
            author_name="tech_engineer",
            category=BookingNote.CATEGORY_GENERAL,
            note_text="Temporary reminder to call client."
        )
        url = reverse('bookings:delete_note', kwargs={'pk': self.booking.pk, 'note_id': note.pk})
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(BookingNote.objects.filter(pk=note.pk).exists())

        audit = BookingAuditLog.objects.filter(booking=self.booking, action='NOTE_DELETED').first()
        self.assertIsNotNone(audit)

    def test_update_primary_notes_view(self):
        url = reverse('bookings:update_primary_notes', kwargs={'pk': self.booking.pk})
        resp = self.client.post(url, {
            'internal_notes': 'Updated primary contractual instruction.'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.internal_notes, 'Updated primary contractual instruction.')


class SolarKanbanDashboardTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="kanban_mgr", password="password123", is_staff=True)
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name="Aditi Sharma",
            phone="+91 9876543210",
            city="Jaipur"
        )
        self.booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('5.00'),
            panel_type="Waaree 540W Mono PERC",
            inverter_type="Solis 5kW On-Grid",
            booking_amount=Decimal('250000.00'),
            advance_payment=Decimal('100000.00'),
            assigned_salesperson="Rohan Gupta",
            assigned_team_driver="Crew Alpha"
        )

    def test_kanban_dashboard_view_and_footer_actions(self):
        url = reverse('bookings:list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Solar Installation Pipeline")
        self.assertContains(resp, "Aditi Sharma")
        self.assertContains(resp, "5.0 kW")
        self.assertContains(resp, "View Order")
        # Ensure redundant right-arrow button in card footer is removed
        self.assertNotContains(resp, "bi-arrow-right")

    def test_kanban_filters(self):
        url = reverse('bookings:list')

        # Filter by customer search query
        resp_q = self.client.get(url, {'q': 'Aditi'})
        self.assertEqual(resp_q.status_code, 200)
        self.assertContains(resp_q, "Aditi Sharma")

        # Filter by payment status 'pending' (has balance of 150000)
        resp_pending = self.client.get(url, {'payment_status': 'pending'})
        self.assertEqual(resp_pending.status_code, 200)
        self.assertContains(resp_pending, "Aditi Sharma")

        # Filter by payment status 'settled' (should not contain Aditi)
        resp_settled = self.client.get(url, {'payment_status': 'settled'})
        self.assertEqual(resp_settled.status_code, 200)
        self.assertNotContains(resp_settled, "Aditi Sharma")






class TasksSystemTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="task_lead", password="password123", is_staff=True)
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            name="Rahul Mehra",
            phone="+91 9988776655",
            city="New Delhi"
        )
        self.booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('8.00'),
            booking_amount=Decimal('380000.00'),
            advance_payment=Decimal('100000.00')
        )

    def test_task_create_and_audit_log(self):
        url = reverse('bookings:task_create')
        resp = self.client.post(url, {
            'title': 'Submit Net-Metering Application to BSES',
            'description': 'Customer sanction load verified at 10kW',
            'category': 'PERMITS',
            'priority': 'HIGH',
            'booking_id': self.booking.pk,
            'assigned_name': 'Permits Officer'
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        task = Task.objects.filter(booking=self.booking).first()
        self.assertIsNotNone(task)
        self.assertEqual(task.title, 'Submit Net-Metering Application to BSES')
        self.assertEqual(task.category, 'PERMITS')
        self.assertEqual(task.priority, 'HIGH')
        self.assertFalse(task.is_completed)
        self.assertEqual(self.booking.pending_tasks_count, 1)

        # Verify audit log recorded
        audit = BookingAuditLog.objects.filter(booking=self.booking, action='TASK_CREATED').first()
        self.assertIsNotNone(audit)
        self.assertIn("Submit Net-Metering", audit.notes)

    def test_task_toggle_ajax(self):
        task = Task.objects.create(
            title='Inverter Testing & Earth Pit Resistance Check',
            category='INSTALLATION',
            priority='URGENT',
            booking=self.booking,
            created_by=self.user
        )
        url = reverse('bookings:task_toggle', kwargs={'pk': task.pk})

        # Complete task via AJAX
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['is_completed'])
        task.refresh_from_db()
        self.assertTrue(task.is_completed)
        self.assertEqual(task.status, Task.STATUS_COMPLETED)

        # Reopen task via AJAX
        resp_reopen = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_reopen.status_code, 200)
        data_reopen = resp_reopen.json()
        self.assertFalse(data_reopen['is_completed'])
        task.refresh_from_db()
        self.assertFalse(task.is_completed)

    def test_task_list_views_and_filters(self):
        task1 = Task.objects.create(
            title='Active Survey Task',
            category='SURVEY',
            priority='high',
            booking=self.booking
        )
        task2 = Task.objects.create(
            title='Completed Payment Followup',
            category='FINANCIAL',
            is_completed=True,
            status=Task.STATUS_COMPLETED
        )

        url = reverse('bookings:task_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Active Survey Task")
        self.assertContains(resp, "Completed Payment Followup")

        # Kanban view
        resp_kanban = self.client.get(url, {'view': 'kanban'})
        self.assertEqual(resp_kanban.status_code, 200)
        self.assertContains(resp_kanban, "Active Survey Task")

        # Status filter
        resp_pending = self.client.get(url, {'status': 'pending'})
        self.assertEqual(resp_pending.status_code, 200)
        self.assertContains(resp_pending, "Active Survey Task")
        self.assertNotContains(resp_pending, "Completed Payment Followup")

    def test_booking_detail_renders_tasks(self):
        Task.objects.create(
            title='Inspect Rooftop Waterproofing',
            category='SURVEY',
            booking=self.booking
        )
        url = reverse('bookings:detail', kwargs={'pk': self.booking.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Tasks & Action Items")
        self.assertContains(resp, "Inspect Rooftop Waterproofing")


    def test_task_checklist_creation_and_progress(self):
        task = Task.objects.create(
            title="Structural Load Analysis",
            category="SURVEY",
            priority="HIGH",
            booking=self.booking
        )
        self.assertTrue(task.is_high_priority)
        self.assertEqual(task.checklist_total, 0)
        self.assertEqual(task.checklist_progress_pct, 0)

        from bookings.models import TaskChecklistItem
        item1 = TaskChecklistItem.objects.create(task=task, title="Check rafter spans", is_completed=True, order=0)
        item2 = TaskChecklistItem.objects.create(task=task, title="Measure tile thickness", is_completed=False, order=1)

        task.refresh_from_db()
        self.assertEqual(task.checklist_total, 2)
        self.assertEqual(task.checklist_completed_count, 1)
        self.assertEqual(task.checklist_progress_pct, 50)
        self.assertTrue(task.has_checklist)

    def test_task_checklist_toggle_ajax(self):
        from bookings.models import TaskChecklistItem
        task = Task.objects.create(
            title="Inverter Earthing Test",
            booking=self.booking
        )
        item = TaskChecklistItem.objects.create(task=task, title="Measure ground pit resistance", is_completed=False)

        url = reverse('bookings:checklist_toggle', kwargs={'pk': item.pk})
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['is_completed'])
        self.assertEqual(data['checklist_progress_pct'], 100)

        item.refresh_from_db()
        self.assertTrue(item.is_completed)

        # Toggle back
        resp2 = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp2.status_code, 200)
        item.refresh_from_db()
        self.assertFalse(item.is_completed)

    def test_task_checklist_add_and_delete_ajax(self):
        task = Task.objects.create(title="Site Survey Tasks", booking=self.booking)

        add_url = reverse('bookings:checklist_add', kwargs={'task_id': task.pk})
        resp = self.client.post(add_url, {'title': 'Verify DISCOM meter reading'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        item_id = data['item_id']

        task.refresh_from_db()
        self.assertEqual(task.checklist_total, 1)

        del_url = reverse('bookings:checklist_delete', kwargs={'pk': item_id})
        resp_del = self.client.post(del_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_del.status_code, 200)

        task.refresh_from_db()
        self.assertEqual(task.checklist_total, 0)

    def test_task_create_with_high_priority_and_checklist(self):
        url = reverse('bookings:task_create')
        resp = self.client.post(url, {
            'title': 'High Priority Commissioning Steps',
            'category': 'INSTALLATION',
            'is_high_priority': 'true',
            'checklist_items[]': ['Verify AC voltage', 'Sync mobile app'],
            'booking_id': self.booking.pk
        })
        self.assertEqual(resp.status_code, 302)

        task = Task.objects.filter(title='High Priority Commissioning Steps').first()
        self.assertIsNotNone(task)
        self.assertTrue(task.is_high_priority)
        self.assertEqual(task.priority, 'HIGH')
        self.assertEqual(task.checklist_total, 2)


class OperationsCalendarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='operations_admin', password='password123', is_staff=True)
        self.client.login(username='operations_admin', password='password123')
        self.customer = Customer.objects.create(name='Priya Nair', phone='9876543210', email='priya@example.com')
        self.booking = SolarBooking.objects.create(
            customer=self.customer,
            system_capacity_kw=Decimal('6.5'),
            booking_amount=Decimal('8000.00'),
            survey_scheduled_date=datetime.now().date(),
            expected_installation_date=(datetime.now() + timedelta(days=5)).date()
        )
        self.task = Task.objects.create(
            title='Structural Load Test',
            booking=self.booking,
            due_date=datetime.now().date(),
            priority='high'
        )

    def test_calendar_page_loads_200(self):
        url = reverse('bookings:calendar')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Operations Calendar')
        self.assertContains(resp, 'fullCalendarRoot')

    def test_calendar_events_json_feed(self):
        url = reverse('bookings:calendar_events_json')
        resp = self.client.get(url, {
            'start': (datetime.now() - timedelta(days=10)).date().isoformat(),
            'end': (datetime.now() + timedelta(days=20)).date().isoformat(),
            'layers': 'surveys,installations,tasks,handovers'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(len(data), 2)
        event_types = [ev['extendedProps']['type'] for ev in data]
        self.assertIn('SURVEY', event_types)
        self.assertIn('INSTALLATION', event_types)
        self.assertIn('TASK', event_types)

    def test_calendar_event_move_survey(self):
        url = reverse('bookings:calendar_event_move')
        new_date = (datetime.now() + timedelta(days=12)).date()
        resp = self.client.post(url, {
            'event_id': f'survey-{self.booking.pk}',
            'new_date': new_date.isoformat()
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.survey_scheduled_date, new_date)

    def test_calendar_event_move_task(self):
        url = reverse('bookings:calendar_event_move')
        new_date = (datetime.now() + timedelta(days=8)).date()
        resp = self.client.post(url, {
            'event_id': f'task-{self.task.pk}',
            'new_date': new_date.isoformat()
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')
        self.task.refresh_from_db()
        self.assertEqual(self.task.due_date, new_date)

    def test_task_detail_json_view(self):
        url = reverse('bookings:task_detail_json', kwargs={'pk': self.task.pk})
        resp = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['title'], 'Structural Load Test')
        self.assertIn('created_by', data)
        self.assertIn('created_at', data)
        self.assertIn('due_date', data)
        self.assertEqual(data['due_date'], self.task.due_date.strftime('%b %d, %Y'))
        self.assertFalse(data['is_completed'])
