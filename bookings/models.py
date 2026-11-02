import os
from decimal import Decimal
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from customers.models import Customer

User = get_user_model()


class PipelineStage(models.Model):
    name = models.CharField(max_length=60, help_text="Human-readable stage title")
    code = models.SlugField(max_length=40, unique=True, help_text="Internal code identifier (e.g. NEW, SITE_SURVEY)")
    order = models.PositiveIntegerField(default=1, db_index=True, help_text="Column display order (1, 2, 3...)")

    # Visual customization
    color = models.CharField(max_length=25, default="#2563eb", help_text="Accent color")
    border_color = models.CharField(max_length=25, default="#bfdbfe", help_text="Border tint color")
    bg_header = models.CharField(max_length=25, default="#eff6ff", help_text="Header background tint")
    header_text = models.CharField(max_length=25, default="#1d4ed8", help_text="Header text color")
    icon = models.CharField(max_length=50, default="bi-circle", help_text="Bootstrap icon class")

    # Workflow properties
    is_initial = models.BooleanField(default=False, help_text="Initial stage for new bookings")
    is_terminal = models.BooleanField(default=False, help_text="Marks booking as fully completed/commissioned")
    is_system = models.BooleanField(default=False, help_text="System-locked stage (cannot be deleted, only renamed/styled)")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Whether this stage appears in the active pipeline")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Pipeline Stage'
        verbose_name_plural = 'Pipeline Stages'

    @property
    def priority_badge_info(self):
        mapping = {
            'URGENT': {
                'bg': '#fee2e2',
                'color': '#b91c1c',
                'border': '#fca5a5',
                'label': 'Urgent',
                'icon': 'bi-exclamation-triangle-fill'
            },
            'HIGH': {
                'bg': '#ffedd5',
                'color': '#c2410c',
                'border': '#fdba74',
                'label': 'High Priority',
                'icon': 'bi-arrow-up-circle-fill'
            },
            'LOW': {
                'bg': '#f1f5f9',
                'color': '#64748b',
                'border': '#e2e8f0',
                'label': 'Low Priority',
                'icon': 'bi-arrow-down-circle'
            },
            'NORMAL': {
                'bg': '#f0fdf4',
                'color': '#166534',
                'border': '#bbf7d0',
                'label': 'Normal',
                'icon': 'bi-dash-circle'
            },
        }
        return mapping.get(self.priority, mapping['NORMAL'])

    @property
    def age_days_display(self):
        if not self.created_at:
            return "1d"
        delta = timezone.now() - self.created_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            return f"{max(1, hours)}h"
        return f"{delta.days}d"

    def __str__(self):
        return f"{self.order}. {self.name}"

    def active_bookings_count(self):
        return SolarBooking.objects.filter(stage=self.code, is_cancelled=False).count()

    @classmethod
    def ensure_defaults(cls):
        defaults = [
            {
                'code': 'NEW',
                'name': 'New Lead',
                'order': 1,
                'color': '#2563eb',
                'border_color': '#bfdbfe',
                'bg_header': '#eff6ff',
                'header_text': '#1d4ed8',
                'icon': 'bi-star-fill',
                'is_initial': True,
                'is_terminal': False,
                'is_system': True,
                'is_active': True,
            },
            {
                'code': 'SITE_SURVEY',
                'name': 'Site Survey',
                'order': 2,
                'color': '#d97706',
                'border_color': '#fde68a',
                'bg_header': '#fffbeb',
                'header_text': '#b45309',
                'icon': 'bi-geo-alt-fill',
                'is_initial': False,
                'is_terminal': False,
                'is_system': False,
                'is_active': True,
            },
            {
                'code': 'INSTALLATION',
                'name': 'Installation in Progress',
                'order': 3,
                'color': '#7c3aed',
                'border_color': '#ddd6fe',
                'bg_header': '#f5f3ff',
                'header_text': '#6d28d9',
                'icon': 'bi-tools',
                'is_initial': False,
                'is_terminal': False,
                'is_system': False,
                'is_active': True,
            },
            {
                'code': 'COMPLETED',
                'name': 'Installed',
                'order': 4,
                'color': '#059669',
                'border_color': '#a7f3d0',
                'bg_header': '#ecfdf5',
                'header_text': '#047857',
                'icon': 'bi-check2-circle',
                'is_initial': False,
                'is_terminal': True,
                'is_system': True,
                'is_active': True,
            },
        ]
        for d in defaults:
            cls.objects.get_or_create(code=d['code'], defaults=d)

    @classmethod
    def get_active_stages(cls):
        cls.ensure_defaults()
        return cls.objects.filter(is_active=True).order_by('order', 'id')


class SolarBooking(models.Model):
    STAGE_NEW = 'NEW'
    STAGE_SURVEY = 'SITE_SURVEY'
    STAGE_INSTALLATION = 'INSTALLATION'
    STAGE_COMPLETED = 'COMPLETED'

    STAGE_CHOICES = [
        (STAGE_NEW, 'New Lead'),
        (STAGE_SURVEY, 'Site Survey'),
        (STAGE_INSTALLATION, 'Installation in Progress'),
        (STAGE_COMPLETED, 'Installed'),
    ]

    STAGE_ORDER = [STAGE_NEW, STAGE_SURVEY, STAGE_INSTALLATION, STAGE_COMPLETED]

    INSTALLATION_TYPE_CHOICES = [
        ('ROOFTOP_RCC', 'Rooftop - Concrete / RCC Flat Roof'),
        ('ROOFTOP_TIN', 'Rooftop - Metal / Tin Shed'),
        ('ROOFTOP_TILED', 'Rooftop - Slanted Tiled Roof'),
        ('GROUND_MOUNT', 'Ground Mounted Elevated Structure'),
        ('CARPORT', 'Solar Carport Canopy'),
        ('OTHER', 'Other Custom Mount'),
    ]

    SURVEY_STATUS_CHOICES = [
        ('PENDING', 'Pending Schedule'),
        ('SCHEDULED', 'Visit Scheduled'),
        ('COMPLETED_FEASIBLE', 'Completed - Feasible'),
        ('NEEDS_REINFORCEMENT', 'Completed - Structure Reinforcement Required'),
        ('NOT_FEASIBLE', 'Not Feasible / Obstacles'),
    ]

    NET_METERING_CHOICES = [
        ('Application Submitted', 'Application Submitted to DISCOM'),
        ('Feasibility Approved', 'Feasibility / DISCOM Sanction Approved'),
        ('WCR Submitted', 'Work Completion Report (WCR) Submitted'),
        ('Inspection Completed', 'DISCOM Site Inspection Completed'),
        ('Bi-directional Meter Installed & Grid Synchronized', 'Bi-directional Meter Installed & Grid Synchronized'),
        ('Grid Active & Solar Export Operational', 'Grid Active & Solar Export Operational'),
        ('Meter Installed & Grid Active', 'Meter Installed & Grid Active'),
        ('Not Applicable (Off-Grid / Zero Export)', 'Not Applicable (Off-Grid / Zero Export)'),
    ]

    CANCELLATION_CATEGORY_CHOICES = [
        ('CUSTOMER_CANCELLED', 'Customer cancelled / changed decision'),
        ('PRICE_OR_FINANCE', 'Price or finance issue'),
        ('SITE_NOT_FEASIBLE', 'Site not technically feasible'),
        ('OUTSIDE_SERVICE_AREA', 'Outside service area'),
        ('DUPLICATE_OR_ERROR', 'Duplicate or incorrect order'),
        ('OTHER', 'Other reason'),
    ]

    # Core Identifiers
    # Priority & Kanban Order
    PRIORITY_URGENT = 'URGENT'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_NORMAL = 'NORMAL'
    PRIORITY_LOW = 'LOW'

    PRIORITY_CHOICES = [
        (PRIORITY_URGENT, 'Urgent'),
        (PRIORITY_HIGH, 'High Priority'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_LOW, 'Low Priority'),
    ]

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
        db_index=True,
        verbose_name="Priority"
    )
    kanban_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        verbose_name="Kanban Order Index",
        help_text="Vertical ordering position within Kanban pipeline columns"
    )

    booking_ref = models.CharField(max_length=40, unique=True, db_index=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='bookings')
    stage = models.CharField(max_length=40, default=STAGE_NEW, db_index=True, help_text='Current pipeline stage code (references PipelineStage.code)')
    consumer_number = models.CharField(max_length=50, blank=True, null=True, db_index=True, help_text="Electricity Board / DISCOM Consumer Number (e.g. 13-digit KSEB Consumer ID)")

    # Site Location & Installation Address (Indian Standard Format)
    site_house_flat = models.CharField(
        max_length=200, 
        blank=True, 
        default='', 
        verbose_name="House / Flat / Building No. & Name",
        help_text="e.g. Building No. 12/450, Green Villa / Sunrise Apartments"
    )
    site_street_area = models.CharField(
        max_length=250, 
        blank=True, 
        default='', 
        verbose_name="Street / Road / Locality / Landmark",
        help_text="e.g. MG Road, Near Civil Station, Kaloor"
    )
    site_city = models.CharField(
        max_length=100, 
        blank=True, 
        default='', 
        verbose_name="City / Town / Village",
        help_text="e.g. Kochi / Thiruvananthapuram / Kozhikode"
    )
    site_district = models.CharField(
        max_length=100, 
        blank=True, 
        default='', 
        verbose_name="District",
        help_text="e.g. Ernakulam / Palakkad / Thrissur"
    )
    site_state = models.CharField(
        max_length=100, 
        blank=True, 
        default='Kerala', 
        verbose_name="State",
        help_text="e.g. Kerala, Tamil Nadu, Karnataka"
    )
    site_pincode = models.CharField(
        max_length=20, 
        blank=True, 
        default='', 
        verbose_name="PIN Code",
        help_text="6-digit Indian Postal PIN Code (e.g. 682016)"
    )
    site_location_url = models.CharField(
        max_length=300, 
        blank=True, 
        default='', 
        verbose_name="GPS Coordinates / Google Maps Link",
        help_text="e.g. 10.015860, 76.341870 or Google Maps link"
    )
    
    # Cancellation tracking (separate from primary 4 stages)
    is_cancelled = models.BooleanField(default=False, db_index=True)
    cancellation_category = models.CharField(max_length=40, choices=CANCELLATION_CATEGORY_CHOICES, blank=True, default='')
    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='cancelled_bookings')

    # A hold pauses work without losing the order's real workflow stage.
    is_on_hold = models.BooleanField(default=False, db_index=True)
    hold_reason = models.TextField(blank=True, null=True)
    held_at = models.DateTimeField(blank=True, null=True)
    held_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='held_bookings')

    # Solar System Specifications
    system_capacity_kw = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), blank=True, help_text="Capacity in Kilowatts (e.g. 5.50 kW)")
    panel_brand = models.CharField(max_length=100, blank=True, default="", verbose_name="Panel Brand / Manufacturer")
    panel_wattage = models.PositiveIntegerField(default=0, blank=True, verbose_name="Panel Wattage (Wp)")
    panel_tech = models.CharField(max_length=100, blank=True, default="", verbose_name="Panel Technology / Type")
    panel_type = models.CharField(max_length=150, blank=True, default="")
    inverter_type = models.CharField(max_length=150, blank=True, default="")
    number_of_panels = models.PositiveIntegerField(default=0, blank=True)
    installation_type = models.CharField(max_length=150, blank=True, default="")
    required_accessories = models.TextField(blank=True, null=True, help_text="e.g. AC/DC DB, Surge Protection (SPD), Earthing Kit, Cable Tray")
    additional_requirements = models.TextField(blank=True, null=True, help_text="Special customer requests or technical considerations")

    # Financial Details
    booking_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), blank=True, help_text="Total Project / Booking Amount")
    advance_payment = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Advance Received")
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Outstanding Balance")

    # Dates & Planning
    booking_date = models.DateField(default=timezone.now, db_index=True)
    expected_installation_date = models.DateField(blank=True, null=True)
    expected_completion_date = models.DateField(blank=True, null=True)
    actual_completion_date = models.DateField(blank=True, null=True)

    # Assignments
    assigned_salesperson = models.CharField(max_length=120, default="Unassigned", help_text="Assigned staff member responsible")
    assigned_team = models.ForeignKey(
        'core.Team',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='bookings',
        help_text="Operations team assigned to this project (e.g. Alpha, Beta, Omega)"
    )
    assigned_team_driver = models.CharField(max_length=150, default="Unassigned", help_text="Installation team or delivery driver")

    # Stage 2: Site Survey Information
    survey_scheduled_date = models.DateField(blank=True, null=True)
    survey_visit_date = models.DateField(blank=True, null=True)
    survey_team_driver = models.CharField(max_length=150, blank=True, null=True)
    survey_status = models.CharField(max_length=30, choices=SURVEY_STATUS_CHOICES, default='PENDING')
    survey_roof_measurements = models.CharField(max_length=200, blank=True, null=True, help_text="Roof area, orientation, azimuth angle")
    survey_notes = models.TextField(blank=True, null=True, help_text="Shadow analysis, roof structural integrity, cable route notes")

    # Stage 3: Installation Tracking
    installation_scheduled_date = models.DateField(blank=True, null=True)
    installation_team = models.CharField(max_length=150, blank=True, null=True)
    installation_progress = models.PositiveIntegerField(default=0, help_text="Progress from 0 to 100%")
    installation_notes = models.TextField(blank=True, null=True, help_text="Mounting progress, electrical wiring, testing remarks")

    # Stage 4: Completion & Handover
    completion_notes = models.TextField(blank=True, null=True, help_text="Handover notes, customer sign-off, system commissioning")
    final_payment_received = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Final balance cleared")
    net_metering_status = models.CharField(max_length=100, choices=NET_METERING_CHOICES, default="Application Submitted", blank=True)
    warranty_certificate_issued = models.BooleanField(default=False)

    # General
    internal_notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_bookings')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Stage Milestone Timestamps (Date & Time for Workflow Tracker)
    stage_new_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when New Booking was created")
    stage_survey_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when Site Survey stage was reached")
    stage_installation_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when Installation stage was reached")
    stage_completed_at = models.DateTimeField(blank=True, null=True, help_text="Timestamp when Completed stage was reached")

    class Meta:
        ordering = ['-booking_date', '-id']
        indexes = [
            models.Index(fields=['booking_ref']),
            models.Index(fields=['stage']),
            models.Index(fields=['is_cancelled']),
            models.Index(fields=['booking_date']),
            models.Index(fields=['assigned_salesperson']),
        ]

    @property
    def priority_badge_info(self):
        mapping = {
            'URGENT': {
                'bg': '#fee2e2',
                'color': '#b91c1c',
                'border': '#fca5a5',
                'label': 'Urgent',
                'icon': 'bi-exclamation-triangle-fill'
            },
            'HIGH': {
                'bg': '#ffedd5',
                'color': '#c2410c',
                'border': '#fdba74',
                'label': 'High Priority',
                'icon': 'bi-arrow-up-circle-fill'
            },
            'LOW': {
                'bg': '#f1f5f9',
                'color': '#64748b',
                'border': '#e2e8f0',
                'label': 'Low Priority',
                'icon': 'bi-arrow-down-circle'
            },
            'NORMAL': {
                'bg': '#f0fdf4',
                'color': '#166534',
                'border': '#bbf7d0',
                'label': 'Normal',
                'icon': 'bi-dash-circle'
            },
        }
        return mapping.get(self.priority, mapping['NORMAL'])

    @property
    def age_days_display(self):
        if not self.created_at:
            return "1d"
        delta = timezone.now() - self.created_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            return f"{max(1, hours)}h"
        return f"{delta.days}d"

    def __str__(self):
        return f"{self.booking_ref} - {self.customer.name} ({self.system_capacity_kw}kW)"

    def clean(self):
        super().clean()
        if self.booking_amount is not None:
            if self.pk and self.payments.exists():
                adv_db = self.payments.filter(milestone='BOOKING_ADVANCE').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
                adv_comp = adv_db if adv_db > Decimal('0.00') else (self.advance_payment or Decimal('0.00'))
                non_adv_db = self.payments.exclude(milestone='BOOKING_ADVANCE').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
                total_paid = adv_comp + non_adv_db
                self.balance_amount = max(Decimal('0.00'), self.booking_amount - total_paid)
            else:
                advance = self.advance_payment or Decimal('0.00')
                final_p = self.final_payment_received or Decimal('0.00')
                self.balance_amount = max(Decimal('0.00'), self.booking_amount - (advance + final_p))

    def save(self, *args, **kwargs):
        # Auto calculate balance amount
        if self.pk and self.payments.exists():
            adv_db = self.payments.filter(milestone='BOOKING_ADVANCE').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            adv_comp = adv_db if adv_db > Decimal('0.00') else (self.advance_payment or Decimal('0.00'))
            non_adv_db = self.payments.exclude(milestone='BOOKING_ADVANCE').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            total_paid = adv_comp + non_adv_db
            if self.booking_amount is not None:
                self.balance_amount = max(Decimal('0.00'), self.booking_amount - total_paid)
        else:
            advance = self.advance_payment or Decimal('0.00')
            final_p = self.final_payment_received or Decimal('0.00')
            if self.booking_amount is not None:
                self.balance_amount = max(Decimal('0.00'), self.booking_amount - (advance + final_p))

        # Generate unique booking reference e.g. SB-2026-0001
        if not self.booking_ref:
            current_year = timezone.now().year
            last_booking = SolarBooking.objects.filter(booking_ref__startswith=f"SB-{current_year}-").order_by('-id').first()
            if last_booking:
                try:
                    last_num = int(last_booking.booking_ref.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = self.id or 1
            else:
                next_num = 1
            self.booking_ref = f"SB-{current_year}-{next_num:04d}"

                # Auto-initialize stage milestone timestamps
        if not self.stage_new_at:
            self.stage_new_at = self.created_at or timezone.now()
        if self.stage in [self.STAGE_SURVEY, self.STAGE_INSTALLATION, self.STAGE_COMPLETED] and not self.stage_survey_at:
            self.stage_survey_at = self.created_at or timezone.now()
        if self.stage in [self.STAGE_INSTALLATION, self.STAGE_COMPLETED] and not self.stage_installation_at:
            self.stage_installation_at = self.created_at or timezone.now()
        if self.stage == self.STAGE_COMPLETED and not self.stage_completed_at:
            self.stage_completed_at = self.created_at or timezone.now()

        # Sync assigned_team name with legacy field if empty or default
        if self.assigned_team and (not self.assigned_team_driver or self.assigned_team_driver == "Unassigned"):
            self.assigned_team_driver = self.assigned_team.name

        super().save(*args, **kwargs)

    def recalculate_financials(self):
        """
        Recalculates balance_amount and total paid based on recorded BookingPayment entries.
        Seamlessly supports legacy advance_payment / final_payment_received.
        """
        payments = self.payments.all()
        if payments.exists():
            adv_db = payments.filter(milestone='BOOKING_ADVANCE').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            if adv_db > Decimal('0.00'):
                self.advance_payment = adv_db
            adv_comp = self.advance_payment or Decimal('0.00')

            non_adv_db = payments.exclude(milestone='BOOKING_ADVANCE').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            self.final_payment_received = non_adv_db

            total_paid = adv_comp + self.final_payment_received
            if self.booking_amount is not None:
                self.balance_amount = max(Decimal('0.00'), self.booking_amount - total_paid)
        else:
            adv = self.advance_payment or Decimal('0.00')
            fin = self.final_payment_received or Decimal('0.00')
            if self.booking_amount is not None:
                self.balance_amount = max(Decimal('0.00'), self.booking_amount - (adv + fin))
        SolarBooking.objects.filter(pk=self.pk).update(
            advance_payment=self.advance_payment,
            final_payment_received=self.final_payment_received,
            balance_amount=self.balance_amount
        )
    @property
    def site_full_address(self):
        parts = [
            self.site_house_flat,
            self.site_street_area,
            self.site_city,
            self.site_district,
            f"{self.site_state} - {self.site_pincode}".strip(' -') if (self.site_state or self.site_pincode) else ''
        ]
        addr = ", ".join(p.strip() for p in parts if p and p.strip())
        if not addr and self.customer and hasattr(self.customer, 'full_address'):
            return self.customer.full_address
        return addr or "Address not specified"

    @property
    def site_map_url(self):
        if self.site_location_url and self.site_location_url.strip():
            loc = self.site_location_url.strip()
            if loc.startswith('http://') or loc.startswith('https://'):
                return loc
            return f"https://maps.google.com/?q={loc}"
        elif self.site_full_address and self.site_full_address != "Address not specified":
            import urllib.parse
            return f"https://maps.google.com/?q={urllib.parse.quote(self.site_full_address)}"
        return None

    @property
    def total_paid(self):
        if not self.pk or not self.payments.exists():
            return (self.advance_payment or Decimal('0.00')) + (self.final_payment_received or Decimal('0.00'))
        adv_db = self.payments.filter(milestone='BOOKING_ADVANCE').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        adv_comp = adv_db if adv_db > Decimal('0.00') else (self.advance_payment or Decimal('0.00'))
        non_adv_db = self.payments.exclude(milestone='BOOKING_ADVANCE').aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        return adv_comp + non_adv_db

    @property
    def payment_percentage(self):
        if not self.booking_amount or self.booking_amount <= 0:
            return 0
        pct = int((self.total_paid / self.booking_amount) * 100)
        return min(100, max(0, pct))

    @property
    def is_fully_paid(self):
        return (self.balance_amount or Decimal('0.00')) <= Decimal('0.00')

    @property
    def credit_status(self):
        """
        Returns credit/receivable status dictionary for credit management view:
        - status: 'SETTLED', 'CURRENT', 'HIGH_RISK', 'OVERDUE'
        - label: text badge
        - badge_class: bootstrap badge class
        - days_pending: int
        """
        if self.is_cancelled:
            return {'status': 'CANCELLED', 'label': 'Cancelled', 'badge_class': 'bg-secondary', 'days_pending': 0}
        if self.is_fully_paid:
            return {'status': 'SETTLED', 'label': 'Fully Paid', 'badge_class': 'bg-success', 'days_pending': 0}
        
        days = (timezone.now().date() - self.booking_date).days
        if self.stage == self.STAGE_COMPLETED:
            if days > 15:
                return {'status': 'OVERDUE', 'label': f'Overdue ({days}d)', 'badge_class': 'bg-danger', 'days_pending': days}
            return {'status': 'HIGH_RISK', 'label': f'Pending Handover ({days}d)', 'badge_class': 'bg-warning text-dark', 'days_pending': days}
        
        if days > 45:
            return {'status': 'HIGH_RISK', 'label': f'Aging ({days}d)', 'badge_class': 'bg-warning text-dark', 'days_pending': days}
        return {'status': 'CURRENT', 'label': f'Within Terms ({days}d)', 'badge_class': 'bg-info text-dark', 'days_pending': days}

    @property
    def all_notes_count(self):
        cnt = self.notes_list.count()
        if self.internal_notes and self.internal_notes.strip():
            cnt += 1
        return cnt

    @property
    def pending_tasks_count(self):
        return self.tasks.filter(is_completed=False).count()

    @property
    def all_tasks_count(self):
        return self.tasks.count()

    @property
    def stage_step_number(self):
        if self.is_cancelled:
            return 0
        if self.stage == self.STAGE_NEW:
            return 1
        elif self.stage == self.STAGE_SURVEY:
            return 2
        elif self.stage == self.STAGE_INSTALLATION:
            return 3
        elif self.stage == self.STAGE_COMPLETED:
            return 4
        return 1

    @property
    def stage_percentage(self):
        if self.is_cancelled:
            return 0
        mapping = {
            self.STAGE_NEW: 25,
            self.STAGE_SURVEY: 50,
            self.STAGE_INSTALLATION: 75,
            self.STAGE_COMPLETED: 100
        }
        return mapping.get(self.stage, 25)

    @property
    def stage_badge_class(self):
        if self.is_cancelled:
            return "bg-danger"
        mapping = {
            self.STAGE_NEW: "badge-stage-new",
            self.STAGE_SURVEY: "badge-stage-survey",
            self.STAGE_INSTALLATION: "badge-stage-installation",
            self.STAGE_COMPLETED: "badge-stage-completed",
        }
        return mapping.get(self.stage, "bg-secondary")

    def get_stage_display(self):
        try:
            st = PipelineStage.objects.filter(code=self.stage).first()
            if st:
                return st.name
        except Exception:
            pass
        return dict(self.STAGE_CHOICES).get(self.stage, self.stage)

    @property
    def stage_name_clean(self):
        if self.is_cancelled:
            return "Cancelled"
        return self.get_stage_display()

    @property
    def next_stage(self):
        if self.is_cancelled:
            return None
        try:
            active_codes = list(PipelineStage.get_active_stages().values_list('code', flat=True))
            if not active_codes:
                active_codes = self.STAGE_ORDER
            if self.stage in active_codes:
                curr_idx = active_codes.index(self.stage)
                if curr_idx + 1 < len(active_codes):
                    return active_codes[curr_idx + 1]
        except Exception:
            pass
        return None

    @property
    def prev_stage(self):
        if self.is_cancelled:
            return None
        try:
            active_codes = list(PipelineStage.get_active_stages().values_list('code', flat=True))
            if not active_codes:
                active_codes = self.STAGE_ORDER
            if self.stage in active_codes:
                curr_idx = active_codes.index(self.stage)
                if curr_idx > 0:
                    return active_codes[curr_idx - 1]
        except Exception:
            pass
        return None

    @property
    def stage_info(self):
        try:
            st = PipelineStage.objects.filter(code=self.stage).first()
            if st:
                return {
                    'name': st.name,
                    'color': st.color,
                    'border_color': st.border_color,
                    'bg_header': st.bg_header,
                    'header_text': st.header_text,
                    'icon': st.icon,
                    'is_terminal': st.is_terminal,
                }
        except Exception:
            pass
        return {
            'name': dict(self.STAGE_CHOICES).get(self.stage, self.stage),
            'color': '#2563eb',
            'border_color': '#bfdbfe',
            'bg_header': '#eff6ff',
            'header_text': '#1d4ed8',
            'icon': 'bi-circle',
            'is_terminal': (self.stage == self.STAGE_COMPLETED),
        }

    def get_installation_type_display(self):
        dict_choices = dict(self.INSTALLATION_TYPE_CHOICES)
        return dict_choices.get(self.installation_type, self.installation_type)

    @property
    def installation_type_short(self):
        mapping = {
            'ROOFTOP_RCC': 'RCC Flat Roof',
            'ROOFTOP_TIN': 'Tin / Metal Shed',
            'ROOFTOP_TILED': 'Slanted Tiled',
            'GROUND_MOUNT': 'Ground Mount',
            'CARPORT': 'Carport Canopy',
            'OTHER': 'Custom Mount',
        }
        val = mapping.get(self.installation_type)
        if val:
            return val
        raw = str(self.installation_type or '').strip()
        if raw.startswith('Rooftop - '):
            return raw.replace('Rooftop - ', '')
        return raw if raw else 'Standard'

    def get_absolute_url(self):
        return reverse('bookings:detail', kwargs={'pk': self.pk})

    def log_audit_trail(self, action='STAGE_TRANSITION', from_stage=None, to_stage=None, user=None, action_by=None, notes=''):
        """Helper method to safely record a BookingAuditLog entry for this booking."""
        actual_user = user or action_by
        user_name = "System Staff"
        if actual_user and actual_user.is_authenticated:
            user_name = actual_user.get_full_name() or actual_user.username
        try:
            return self.audit_logs.create(
                action=action,
                from_stage=from_stage or self.stage,
                to_stage=to_stage,
                user=actual_user if (actual_user and actual_user.is_authenticated) else None,
                user_name=user_name,
                notes=notes
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not log audit trail: {e}")
            return None



    @property
    def stage_new_datetime(self):
        return self.stage_new_at or self.created_at

    @property
    def stage_survey_datetime(self):
        if self.stage_survey_at:
            return self.stage_survey_at
        log = self.audit_logs.filter(to_stage=self.STAGE_SURVEY).order_by('timestamp').first()
        if log:
            return log.timestamp
        if self.stage in [self.STAGE_SURVEY, self.STAGE_INSTALLATION, self.STAGE_COMPLETED]:
            return self.created_at
        return None

    @property
    def stage_installation_datetime(self):
        if self.stage_installation_at:
            return self.stage_installation_at
        log = self.audit_logs.filter(to_stage=self.STAGE_INSTALLATION).order_by('timestamp').first()
        if log:
            return log.timestamp
        if self.stage in [self.STAGE_INSTALLATION, self.STAGE_COMPLETED]:
            return self.created_at
        return None

    @property
    def stage_completed_datetime(self):
        if self.stage_completed_at:
            return self.stage_completed_at
        log = self.audit_logs.filter(to_stage=self.STAGE_COMPLETED).order_by('timestamp').first()
        if log:
            return log.timestamp
        if self.stage == self.STAGE_COMPLETED:
            return self.created_at
        return None

class BookingAuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Booking Created'),
        ('STAGE_TRANSITION', 'Stage Advanced'),
        ('STAGE_REGRESSION', 'Stage Moved Back'),
        ('SURVEY_UPDATED', 'Survey Details Updated'),
        ('INSTALLATION_UPDATED', 'Installation Progress Updated'),
        ('COMPLETION_UPDATED', 'Booking Completed'),
        ('PAYMENT_UPDATED', 'Payment Updated'),
        ('DETAILS_EDITED', 'Booking Details Edited'),
        ('CANCELLED', 'Booking Cancelled'),
        ('REOPENED', 'Booking Reopened'),
        ('ATTACHMENT_ADDED', 'Document / Photo Uploaded'),
        ('ATTACHMENT_DELETED', 'Document / Photo Deleted'),
        ('NOTE_ADDED', 'Internal Note Added'),
        ('NOTE_DELETED', 'Internal Note Deleted'),
        ('TASK_CREATED', 'Task Created'),
        ('TASK_COMPLETED', 'Task Completed'),
        ('TASK_REOPENED', 'Task Reopened'),
        ('TASK_DELETED', 'Task Deleted'),
        ('CUSTOM_FIELD_ADDED', 'Custom Field Added'),
        ('CUSTOM_FIELD_UPDATED', 'Custom Field Updated'),
        ('CUSTOM_FIELD_DELETED', 'Custom Field Deleted'),
    ]

    booking = models.ForeignKey(SolarBooking, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    from_stage = models.CharField(max_length=40, blank=True, null=True)
    to_stage = models.CharField(max_length=40, blank=True, null=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    user_name = models.CharField(max_length=150, default="System Admin")
    timestamp = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    @property
    def priority_badge_info(self):
        mapping = {
            'URGENT': {
                'bg': '#fee2e2',
                'color': '#b91c1c',
                'border': '#fca5a5',
                'label': 'Urgent',
                'icon': 'bi-exclamation-triangle-fill'
            },
            'HIGH': {
                'bg': '#ffedd5',
                'color': '#c2410c',
                'border': '#fdba74',
                'label': 'High Priority',
                'icon': 'bi-arrow-up-circle-fill'
            },
            'LOW': {
                'bg': '#f1f5f9',
                'color': '#64748b',
                'border': '#e2e8f0',
                'label': 'Low Priority',
                'icon': 'bi-arrow-down-circle'
            },
            'NORMAL': {
                'bg': '#f0fdf4',
                'color': '#166534',
                'border': '#bbf7d0',
                'label': 'Normal',
                'icon': 'bi-dash-circle'
            },
        }
        return mapping.get(self.priority, mapping['NORMAL'])

    @property
    def age_days_display(self):
        if not self.created_at:
            return "1d"
        delta = timezone.now() - self.created_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            return f"{max(1, hours)}h"
        return f"{delta.days}d"

    def __str__(self):
        return f"{self.booking.booking_ref} - {self.action} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


def booking_attachment_upload_path(instance, filename):
    """
    Store booking/order documents in the dedicated client folder:
    media/clients/<Customer_Name>_<Customer_ID>/orders/<Booking_Ref>/<filename>
    """
    booking = getattr(instance, 'booking', None)
    customer = getattr(booking, 'customer', None) if booking else None

    if customer:
        import re
        raw_name = customer.name or 'client'
        clean_name = re.sub(r'[^\w\s-]', '', raw_name).strip()
        clean_name = re.sub(r'[-\s]+', '_', clean_name)
        if not clean_name:
            clean_name = 'client'
        cid = getattr(customer, 'customer_id', None) or f"id_{customer.id}"
        client_folder = f"{clean_name}_{cid}"
    else:
        client_folder = 'unassigned_clients'

    clean_filename = os.path.basename(filename)
    if booking and getattr(booking, 'booking_ref', None):
        return f"clients/{client_folder}/orders/{booking.booking_ref}/{clean_filename}"
    return f"clients/{client_folder}/orders/{clean_filename}"


class BookingAttachment(models.Model):
    CATEGORY_CHOICES = [
        ('SURVEY_ROOF', 'Site Survey - Roof & Structure Photo'),
        ('SURVEY_METER', 'Site Survey - Meter & Distribution Box'),
        ('ELECTRICITY_BILL', 'Customer Electricity Bill / Tariff Sanction'),
        ('STRUCTURE_REPORT', 'Structural Integrity & Shadow Analysis'),
        ('INSTALL_PROGRESS', 'Installation - Wiring & Progress Photo'),
        ('NET_METERING', 'Net-Metering Application / Discom Approval'),
        ('COMMISSIONING', 'Final Commissioning & Testing Sign-off'),
        ('WARRANTY', 'Manufacturer Warranty Certificate'),
        ('INVOICE_RECEIPT', 'Payment Receipt / Commercial Invoice'),
        ('OTHER', 'Other Document / Photo'),
    ]

    booking = models.ForeignKey(SolarBooking, on_delete=models.CASCADE, related_name='attachments')
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default='OTHER', db_index=True)
    title = models.CharField(max_length=200, help_text="Short label or description")
    file = models.FileField(upload_to=booking_attachment_upload_path)
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='uploaded_booking_attachments')
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-uploaded_at']

    @property
    def priority_badge_info(self):
        mapping = {
            'URGENT': {
                'bg': '#fee2e2',
                'color': '#b91c1c',
                'border': '#fca5a5',
                'label': 'Urgent',
                'icon': 'bi-exclamation-triangle-fill'
            },
            'HIGH': {
                'bg': '#ffedd5',
                'color': '#c2410c',
                'border': '#fdba74',
                'label': 'High Priority',
                'icon': 'bi-arrow-up-circle-fill'
            },
            'LOW': {
                'bg': '#f1f5f9',
                'color': '#64748b',
                'border': '#e2e8f0',
                'label': 'Low Priority',
                'icon': 'bi-arrow-down-circle'
            },
            'NORMAL': {
                'bg': '#f0fdf4',
                'color': '#166534',
                'border': '#bbf7d0',
                'label': 'Normal',
                'icon': 'bi-dash-circle'
            },
        }
        return mapping.get(self.priority, mapping['NORMAL'])

    @property
    def age_days_display(self):
        if not self.created_at:
            return "1d"
        delta = timezone.now() - self.created_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            return f"{max(1, hours)}h"
        return f"{delta.days}d"

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def file_extension(self):
        name, ext = os.path.splitext(self.file.name)
        return ext.lower()

    @property
    def is_image(self):
        return self.file_extension in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.svg']

    @property
    def is_pdf(self):
        return self.file_extension == '.pdf'

    @property
    def file_name(self):
        return os.path.basename(self.file.name)

    @property
    def file_size_formatted(self):
        if not self.file_size:
            return "0 KB"
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.2f} MB"

    @property
    def category_badge_class(self):
        badges = {
            'SURVEY_ROOF': 'bg-info text-dark',
            'SURVEY_METER': 'bg-info text-dark',
            'ELECTRICITY_BILL': 'bg-warning text-dark',
            'STRUCTURE_REPORT': 'bg-primary text-white',
            'INSTALL_PROGRESS': 'bg-primary text-white',
            'NET_METERING': 'bg-success text-white',
            'COMMISSIONING': 'bg-success text-white',
            'WARRANTY': 'bg-success text-white',
            'INVOICE_RECEIPT': 'bg-secondary text-white',
            'OTHER': 'bg-dark text-white',
        }
        return badges.get(self.category, 'bg-secondary text-white')


class BookingPayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('UPI', 'UPI / QR Code (GPay, PhonePe, Paytm)'),
        ('NEFT_RTGS', 'Bank Transfer (NEFT / RTGS / IMPS)'),
        ('CHEQUE', 'Cheque / Demand Draft'),
        ('CASH', 'Cash Payment'),
        ('CARD', 'Debit / Credit Card'),
        ('FINANCE_EMI', 'Solar Loan / EMI Partner'),
        ('OTHER', 'Other Payment Mode'),
    ]

    MILESTONE_CHOICES = [
        ('BOOKING_ADVANCE', '1. Initial Booking Advance'),
        ('FEASIBILITY_APPROVAL', '2. Feasibility & Survey Sign-off'),
        ('MATERIAL_DISPATCH', '3. Hardware & Panel Dispatch'),
        ('INSTALLATION_PROGRESS', '4. Installation & Structure Progress'),
        ('FINAL_COMMISSIONING', '5. Final Commissioning & Handover'),
        ('SUBSIDY_SETTLEMENT', '6. Discom Subsidy / Net-Meter Clearance'),
        ('AD_HOC', '7. Ad-hoc / Part Payment'),
    ]

    booking = models.ForeignKey(SolarBooking, on_delete=models.CASCADE, related_name='payments')
    receipt_number = models.CharField(max_length=40, unique=True, editable=False, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount received (₹)")
    payment_date = models.DateField(default=timezone.now, db_index=True)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='UPI', db_index=True)
    transaction_ref = models.CharField(max_length=120, blank=True, null=True, help_text="UTR Number, Cheque No, or Bank Txn ID")
    milestone = models.CharField(max_length=40, choices=MILESTONE_CHOICES, default='BOOKING_ADVANCE', db_index=True)
    notes = models.TextField(blank=True, null=True, help_text="Payer details, bank name, branch, or collection remarks")
    recorded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='recorded_payments')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date', '-id']
        indexes = [
            models.Index(fields=['receipt_number']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['milestone']),
        ]

    @property
    def priority_badge_info(self):
        mapping = {
            'URGENT': {
                'bg': '#fee2e2',
                'color': '#b91c1c',
                'border': '#fca5a5',
                'label': 'Urgent',
                'icon': 'bi-exclamation-triangle-fill'
            },
            'HIGH': {
                'bg': '#ffedd5',
                'color': '#c2410c',
                'border': '#fdba74',
                'label': 'High Priority',
                'icon': 'bi-arrow-up-circle-fill'
            },
            'LOW': {
                'bg': '#f1f5f9',
                'color': '#64748b',
                'border': '#e2e8f0',
                'label': 'Low Priority',
                'icon': 'bi-arrow-down-circle'
            },
            'NORMAL': {
                'bg': '#f0fdf4',
                'color': '#166534',
                'border': '#bbf7d0',
                'label': 'Normal',
                'icon': 'bi-dash-circle'
            },
        }
        return mapping.get(self.priority, mapping['NORMAL'])

    @property
    def age_days_display(self):
        if not self.created_at:
            return "1d"
        delta = timezone.now() - self.created_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            return f"{max(1, hours)}h"
        return f"{delta.days}d"

    def __str__(self):
        return f"{self.receipt_number} - ₹{self.amount} ({self.booking.booking_ref})"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            current_year = timezone.now().year
            last_receipt = BookingPayment.objects.filter(receipt_number__startswith=f"REC-{current_year}-").order_by('-id').first()
            if last_receipt:
                try:
                    last_num = int(last_receipt.receipt_number.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = self.id or 1
            else:
                next_num = 1
            self.receipt_number = f"REC-{current_year}-{next_num:04d}"

        super().save(*args, **kwargs)
        self.booking.recalculate_financials()

    def delete(self, *args, **kwargs):
        booking = self.booking
        super().delete(*args, **kwargs)
        booking.recalculate_financials()

    @property
    def method_badge_class(self):
        badges = {
            'UPI': 'bg-success text-white',
            'NEFT_RTGS': 'bg-primary text-white',
            'CHEQUE': 'bg-info text-dark',
            'CASH': 'bg-warning text-dark',
            'CARD': 'bg-secondary text-white',
            'FINANCE_EMI': 'bg-dark text-white',
            'OTHER': 'bg-secondary text-white',
        }
        return badges.get(self.payment_method, 'bg-secondary text-white')

    @property
    def method_icon(self):
        icons = {
            'UPI': 'bi-qr-code-scan',
            'NEFT_RTGS': 'bi-bank2',
            'CHEQUE': 'bi-receipt',
            'CASH': 'bi-cash-stack',
            'CARD': 'bi-credit-card-2-front',
            'FINANCE_EMI': 'bi-file-earmark-ruled',
            'OTHER': 'bi-wallet2',
        }
        return icons.get(self.payment_method, 'bi-wallet2')

    @property
    def recorded_by_name(self):
        if self.recorded_by:
            return self.recorded_by.get_full_name() or self.recorded_by.username
        return "Accounts Department"


class BookingNote(models.Model):
    CATEGORY_GENERAL = 'GENERAL'
    CATEGORY_SITE = 'SITE_SURVEY'
    CATEGORY_TECHNICAL = 'TECHNICAL'
    CATEGORY_PAYMENT = 'PAYMENT'
    CATEGORY_CUSTOMER = 'CUSTOMER_PREF'
    CATEGORY_URGENT = 'URGENT'

    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, 'General Note'),
        (CATEGORY_SITE, 'Site & Structure Note'),
        (CATEGORY_TECHNICAL, 'Technical / Hardware Spec'),
        (CATEGORY_PAYMENT, 'Payment & Credit Term'),
        (CATEGORY_CUSTOMER, 'Customer Preference / Request'),
        (CATEGORY_URGENT, 'Urgent / Important Flag'),
    ]

    booking = models.ForeignKey(SolarBooking, on_delete=models.CASCADE, related_name='notes_list')
    author = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='booking_notes')
    author_name = models.CharField(max_length=150, default="Staff")
    category = models.CharField(max_length=60, default=CATEGORY_GENERAL, blank=True, db_index=True)
    note_text = models.TextField(help_text="Internal remarks, technical advice, or customer notes")
    is_pinned = models.BooleanField(default=False, help_text="Pin note to the top of the booking")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['booking', '-created_at']),
            models.Index(fields=['category']),
            models.Index(fields=['is_pinned']),
        ]

    @property
    def priority_badge_info(self):
        mapping = {
            'URGENT': {
                'bg': '#fee2e2',
                'color': '#b91c1c',
                'border': '#fca5a5',
                'label': 'Urgent',
                'icon': 'bi-exclamation-triangle-fill'
            },
            'HIGH': {
                'bg': '#ffedd5',
                'color': '#c2410c',
                'border': '#fdba74',
                'label': 'High Priority',
                'icon': 'bi-arrow-up-circle-fill'
            },
            'LOW': {
                'bg': '#f1f5f9',
                'color': '#64748b',
                'border': '#e2e8f0',
                'label': 'Low Priority',
                'icon': 'bi-arrow-down-circle'
            },
            'NORMAL': {
                'bg': '#f0fdf4',
                'color': '#166534',
                'border': '#bbf7d0',
                'label': 'Normal',
                'icon': 'bi-dash-circle'
            },
        }
        return mapping.get(self.priority, mapping['NORMAL'])

    @property
    def age_days_display(self):
        if not self.created_at:
            return "1d"
        delta = timezone.now() - self.created_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            return f"{max(1, hours)}h"
        return f"{delta.days}d"

    def __str__(self):
        return f"{self.get_category_display()} by {self.author_name} ({self.booking.booking_ref})"

    @property
    def category_badge_class(self):
        mapping = {
            self.CATEGORY_GENERAL: 'bg-light text-dark border',
            self.CATEGORY_SITE: 'bg-info-subtle text-info border border-info-subtle',
            self.CATEGORY_TECHNICAL: 'bg-primary-subtle text-primary border border-primary-subtle',
            self.CATEGORY_PAYMENT: 'bg-success-subtle text-success border border-success-subtle',
            self.CATEGORY_CUSTOMER: 'bg-warning-subtle text-dark border border-warning-subtle',
            self.CATEGORY_URGENT: 'bg-danger text-white',
        }
        return mapping.get(self.category, 'bg-light text-dark border')

    def get_category_display(self):
        return self.category_display

    @property
    def category_display(self):
        if not self.category or self.category == self.CATEGORY_GENERAL:
            return 'General Task'
        stage = PipelineStage.objects.filter(code=self.category).first()
        if stage:
            return stage.name
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category.replace('_', ' ').title())

    @property
    def category_icon(self):
        if self.category:
            stage = PipelineStage.objects.filter(code=self.category).first()
            if stage and stage.icon:
                return stage.icon
        mapping = {
            self.CATEGORY_GENERAL: 'bi-chat-left-text',
            self.CATEGORY_SITE: 'bi-geo-alt',
            self.CATEGORY_TECHNICAL: 'bi-cpu',
            self.CATEGORY_PAYMENT: 'bi-cash-coin',
            self.CATEGORY_CUSTOMER: 'bi-person-heart',
            self.CATEGORY_URGENT: 'bi-exclamation-octagon-fill',
        }
        return mapping.get(self.category, 'bi-chat-left-text')

    @property
    def color_theme(self):
        cat = (self.category or '').upper()
        if 'GREEN' in cat or cat == 'SITE_SURVEY':
            return {
                'name': 'green',
                'bg': '#f0fdf4',
                'header_bg': '#dcfce7',
                'border': '#86efac',
                'text': '#14532d',
                'badge': 'bg-success text-white'
            }
        elif 'BLUE' in cat or cat == 'TECHNICAL':
            return {
                'name': 'blue',
                'bg': '#f0f9ff',
                'header_bg': '#e0f2fe',
                'border': '#7dd3fc',
                'text': '#0c4a6e',
                'badge': 'bg-info text-dark'
            }
        elif 'PURPLE' in cat:
            return {
                'name': 'purple',
                'bg': '#faf5ff',
                'header_bg': '#f3e8ff',
                'border': '#d8b4fe',
                'text': '#581c87',
                'badge': 'bg-primary text-white'
            }
        elif 'PINK' in cat or cat == 'URGENT':
            return {
                'name': 'pink',
                'bg': '#fff1f2',
                'header_bg': '#ffe4e6',
                'border': '#fecdd3',
                'text': '#881337',
                'badge': 'bg-danger text-white'
            }
        else:
            return {
                'name': 'yellow',
                'bg': '#fefce8',
                'header_bg': '#fef08a',
                'border': '#fde047',
                'text': '#713f12',
                'badge': 'bg-warning text-dark'
            }






class Task(models.Model):
    CATEGORY_SURVEY = 'SURVEY'
    CATEGORY_PERMITS = 'PERMITS'
    CATEGORY_PROCUREMENT = 'PROCUREMENT'
    CATEGORY_INSTALLATION = 'INSTALLATION'
    CATEGORY_FINANCIAL = 'FINANCIAL'
    CATEGORY_CUSTOMER = 'CUSTOMER'
    CATEGORY_GENERAL = 'GENERAL'

    CATEGORY_CHOICES = [
        (CATEGORY_SURVEY, 'Site Survey & Feasibility'),
        (CATEGORY_PERMITS, 'Permits & Net-Metering (DISCOM)'),
        (CATEGORY_PROCUREMENT, 'Hardware & Procurement'),
        (CATEGORY_INSTALLATION, 'Installation & Commissioning'),
        (CATEGORY_FINANCIAL, 'Payment & Invoice Follow-up'),
        (CATEGORY_CUSTOMER, 'Customer Communication'),
        (CATEGORY_GENERAL, 'General Task'),
    ]

    PRIORITY_NORMAL = 'NORMAL'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_URGENT = 'URGENT'
    PRIORITY_MEDIUM = 'MEDIUM'
    PRIORITY_LOW = 'LOW'

    PRIORITY_CHOICES = [
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High Priority'),
        (PRIORITY_URGENT, 'High Priority'),
        (PRIORITY_MEDIUM, 'Normal'),
        (PRIORITY_LOW, 'Normal'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'To Do / Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    title = models.CharField(max_length=255, help_text="Short task title or action item")
    description = models.TextField(blank=True, null=True, help_text="Detailed instructions or remarks")
    category = models.CharField(max_length=60, default=CATEGORY_GENERAL, blank=True, db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    is_completed = models.BooleanField(default=False, db_index=True)

    # Relationships
    booking = models.ForeignKey(SolarBooking, null=True, blank=True, on_delete=models.CASCADE, related_name='tasks')
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name='tasks')
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_tasks')
    assigned_name = models.CharField(max_length=150, blank=True, null=True, help_text="Name of staff or contractor")

    # Scheduling
    due_date = models.DateField(null=True, blank=True, db_index=True)
    due_time = models.TimeField(null=True, blank=True)

    # Completion Tracking
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='completed_tasks')

    # Audit & Timestamps
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_tasks')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['is_completed', 'due_date', '-priority', '-created_at']
        indexes = [
            models.Index(fields=['is_completed', 'due_date']),
            models.Index(fields=['booking', 'is_completed']),
            models.Index(fields=['assigned_to', 'is_completed']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
        ]

    @property
    def priority_badge_info(self):
        mapping = {
            'URGENT': {
                'bg': '#fee2e2',
                'color': '#b91c1c',
                'border': '#fca5a5',
                'label': 'Urgent',
                'icon': 'bi-exclamation-triangle-fill'
            },
            'HIGH': {
                'bg': '#ffedd5',
                'color': '#c2410c',
                'border': '#fdba74',
                'label': 'High Priority',
                'icon': 'bi-arrow-up-circle-fill'
            },
            'LOW': {
                'bg': '#f1f5f9',
                'color': '#64748b',
                'border': '#e2e8f0',
                'label': 'Low Priority',
                'icon': 'bi-arrow-down-circle'
            },
            'NORMAL': {
                'bg': '#f0fdf4',
                'color': '#166534',
                'border': '#bbf7d0',
                'label': 'Normal',
                'icon': 'bi-dash-circle'
            },
        }
        return mapping.get(self.priority, mapping['NORMAL'])

    @property
    def age_days_display(self):
        if not self.created_at:
            return "1d"
        delta = timezone.now() - self.created_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            return f"{max(1, hours)}h"
        return f"{delta.days}d"

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_high_priority(self):
        return self.priority in [self.PRIORITY_HIGH, self.PRIORITY_URGENT]

    @property
    def checklist_items_all(self):
        return self.checklist_items.all().order_by('order', 'id')

    @property
    def checklist_total(self):
        return self.checklist_items.count()

    @property
    def checklist_completed_count(self):
        return self.checklist_items.filter(is_completed=True).count()

    @property
    def checklist_progress_pct(self):
        total = self.checklist_total
        if not total:
            return 0
        return int(round((self.checklist_completed_count / total) * 100))

    @property
    def has_checklist(self):
        return self.checklist_items.exists()

    @property
    def is_overdue(self):
        if not self.is_completed and self.due_date:
            return self.due_date < timezone.now().date()
        return False

    @property
    def priority_badge_class(self):
        mapping = {
            self.PRIORITY_URGENT: 'badge-priority-urgent',
            self.PRIORITY_HIGH: 'badge-priority-high',
            self.PRIORITY_MEDIUM: 'badge-priority-medium',
            self.PRIORITY_LOW: 'badge-priority-low',
        }
        return mapping.get(self.priority, 'badge-priority-low')

    def get_category_display(self):
        return self.category_display

    @property
    def category_display(self):
        if not self.category or self.category == self.CATEGORY_GENERAL:
            return 'General Task'
        stage = PipelineStage.objects.filter(code=self.category).first()
        if stage:
            return stage.name
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category.replace('_', ' ').title())

    @property
    def category_icon(self):
        if self.category:
            stage = PipelineStage.objects.filter(code=self.category).first()
            if stage and stage.icon:
                return stage.icon
        mapping = {
            self.CATEGORY_SURVEY: 'bi-geo-alt',
            self.CATEGORY_PERMITS: 'bi-file-earmark-check',
            self.CATEGORY_PROCUREMENT: 'bi-box-seam',
            self.CATEGORY_INSTALLATION: 'bi-tools',
            self.CATEGORY_FINANCIAL: 'bi-cash-coin',
            self.CATEGORY_CUSTOMER: 'bi-chat-dots',
            self.CATEGORY_GENERAL: 'bi-check2-square',
        }
        return mapping.get(self.category, 'bi-check2-square')

    @property
    def completed_by_name(self):
        if self.completed_by:
            return self.completed_by.get_full_name() or self.completed_by.username
        return "Staff"

    def mark_as_completed(self, user=None):
        self.is_completed = True
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save()
        if self.booking:
            BookingAuditLog.objects.create(
                booking=self.booking,
                user=user,
                action='TASK_COMPLETED',
                notes=f"Completed task: '{self.title}'"
            )

    def mark_as_in_progress(self, user=None):
        self.is_completed = False
        self.status = self.STATUS_IN_PROGRESS
        self.completed_at = None
        self.completed_by = None
        self.save()
        if self.booking:
            try:
                BookingAuditLog.objects.create(
                    booking=self.booking,
                    user=user,
                    action='DETAILS_EDITED',
                    notes=f"Moved task to In Progress: '{self.title}'"
                )
            except Exception:
                pass

    def set_status(self, new_status, user=None):
        new_status = (new_status or '').strip().upper()
        if new_status == self.STATUS_COMPLETED:
            self.mark_as_completed(user)
        elif new_status == self.STATUS_IN_PROGRESS:
            self.mark_as_in_progress(user)
        else:
            self.mark_as_pending(user)

    def mark_as_pending(self, user=None):
        self.is_completed = False
        self.status = self.STATUS_PENDING
        self.completed_at = None
        self.completed_by = None
        self.save()
        if self.booking:
            BookingAuditLog.objects.create(
                booking=self.booking,
                user=user,
                action='TASK_REOPENED',
                notes=f"Reopened task: '{self.title}'"
            )


class TaskChecklistItem(models.Model):
    task = models.ForeignKey(Task, related_name='checklist_items', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, help_text="Checklist step description")
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='completed_checklist_items')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['task', 'is_completed']),
            models.Index(fields=['order']),
        ]

    @property
    def priority_badge_info(self):
        mapping = {
            'URGENT': {
                'bg': '#fee2e2',
                'color': '#b91c1c',
                'border': '#fca5a5',
                'label': 'Urgent',
                'icon': 'bi-exclamation-triangle-fill'
            },
            'HIGH': {
                'bg': '#ffedd5',
                'color': '#c2410c',
                'border': '#fdba74',
                'label': 'High Priority',
                'icon': 'bi-arrow-up-circle-fill'
            },
            'LOW': {
                'bg': '#f1f5f9',
                'color': '#64748b',
                'border': '#e2e8f0',
                'label': 'Low Priority',
                'icon': 'bi-arrow-down-circle'
            },
            'NORMAL': {
                'bg': '#f0fdf4',
                'color': '#166534',
                'border': '#bbf7d0',
                'label': 'Normal',
                'icon': 'bi-dash-circle'
            },
        }
        return mapping.get(self.priority, mapping['NORMAL'])

    @property
    def age_days_display(self):
        if not self.created_at:
            return "1d"
        delta = timezone.now() - self.created_at
        if delta.days == 0:
            hours = delta.seconds // 3600
            return f"{max(1, hours)}h"
        return f"{delta.days}d"

    def __str__(self):
        status = "Done" if self.is_completed else "Pending"
        return f"{self.title} [{status}]"

    @property
    def completed_by_name(self):
        if self.completed_by:
            return self.completed_by.get_full_name() or self.completed_by.username
        return "Staff"

    def mark_completed(self, user=None):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save()

    def mark_pending(self, user=None):
        self.is_completed = False
        self.completed_at = None
        self.completed_by = None
        self.save()


class BookingCustomField(models.Model):
    booking = models.ForeignKey(SolarBooking, on_delete=models.CASCADE, related_name='custom_fields')
    label = models.CharField(max_length=150, help_text="Field Header / Label (e.g. Battery Capacity, Sanctioned Load)")
    value = models.CharField(max_length=500, help_text="Field Value")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Booking Custom Field'
        verbose_name_plural = 'Booking Custom Fields'

    def __str__(self):
        return f"{self.label}: {self.value}"
