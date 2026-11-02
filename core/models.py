from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


class CompanySetting(models.Model):
    company_name = models.CharField(max_length=150, default="Helios Solar Energy Solutions")
    tagline = models.CharField(max_length=200, default="Commercial & Residential Solar Power CRM")
    phone = models.CharField(max_length=50, default="+1 (800) 555-SOLAR")
    email = models.EmailField(default="sales@heliossolar.com")
    address = models.TextField(default="742 Evergreen Solar Way, Suite 400, CleanTech Park")
    tax_id = models.CharField(max_length=60, default="TAX-US-994821", blank=True)
    currency_symbol = models.CharField(max_length=10, default="₹")
    currency_code = models.CharField(max_length=10, default="INR")
    standard_kw_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1200.00'), help_text="Average standard rate per kW")

    def __str__(self):
        return self.company_name

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj


class TeamMember(models.Model):
    name = models.CharField(max_length=120)
    designation = models.CharField(max_length=120, blank=True, null=True, help_text="e.g. Senior Solar Advisor, Technical Lead, Field Operations")
    role = models.CharField(max_length=30, default='MEMBER', blank=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True, null=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='team_member', help_text="Optional linked CRM login user")
    monthly_target_kw = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), blank=True, help_text="Monthly target in kW (optional)")
    joined_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        if self.designation:
            return f"{self.name} ({self.designation})"
        return self.name

    def get_search_names(self):
        names = [self.name]
        if self.user:
            names.append(self.user.username)
            full = f"{self.user.first_name} {self.user.last_name}".strip()
            if full:
                names.append(full)
        return list(set(filter(None, names)))

    def get_assigned_bookings_queryset(self):
        from django.apps import apps
        from django.db.models import Q
        SolarBooking = apps.get_model('bookings', 'SolarBooking')
        names = self.get_search_names()

        q = Q()
        for n in names:
            q |= (
                Q(assigned_salesperson__iexact=n) |
                Q(assigned_salesperson__icontains=n) |
                Q(survey_team_driver__icontains=n) |
                Q(installation_team__icontains=n) |
                Q(assigned_team_driver__icontains=n)
            )
        return SolarBooking.objects.filter(q).select_related('customer')

    def get_performance(self, date_from=None, date_to=None):
        from django.apps import apps
        from django.db.models import Q, Sum, Avg, Count
        SolarBooking = apps.get_model('bookings', 'SolarBooking')
        names = self.get_search_names()

        # Combined Projects
        all_qs = self.get_assigned_bookings_queryset()

        if date_from:
            all_qs = all_qs.filter(booking_date__gte=date_from)
        if date_to:
            all_qs = all_qs.filter(booking_date__lte=date_to)

        all_valid_projects = all_qs.filter(is_cancelled=False).order_by('-booking_date')
        project_count = all_valid_projects.count()

        agg = all_valid_projects.aggregate(
            total_rev=Sum('booking_amount'),
            total_adv=Sum('advance_payment'),
            total_final=Sum('final_payment_received'),
            total_kw=Sum('system_capacity_kw'),
            total_bal=Sum('balance_amount'),
            avg_deal=Avg('booking_amount')
        )
        total_rev = agg['total_rev'] or Decimal('0.00')
        total_coll = (agg['total_adv'] or Decimal('0.00')) + (agg['total_final'] or Decimal('0.00'))
        total_kw = agg['total_kw'] or Decimal('0.00')
        total_bal = agg['total_bal'] or Decimal('0.00')
        avg_deal = agg['avg_deal'] or Decimal('0.00')

        # Target achievement
        target_pct = 0
        if self.monthly_target_kw and self.monthly_target_kw > 0:
            target_pct = min(100, int((total_kw / self.monthly_target_kw) * 100))

        workload_badge = "bg-success" if self.is_active else "bg-secondary"
        workload_label = f"{project_count} Assigned Project{'s' if project_count != 1 else ''}"

        return {
            'overview': {
                'total_projects': project_count,
                'total_kw': total_kw,
                'total_revenue': total_rev,
                'total_collected': total_coll,
                'total_balance': total_bal,
                'target_pct': target_pct,
            },
            'all_projects': all_valid_projects,
            'active_projects': all_valid_projects,
            'completed_projects': all_qs.none(),
            'sales': {'total_revenue': total_rev, 'total_deals': project_count},
            'installation': {'completed': project_count},
            'workload': {
                'badge': workload_badge,
                'label': workload_label,
            },
        }



class Team(models.Model):
    """
    Represents an operational group of users working together on solar projects
    (e.g. Alpha, Beta, Omega).
    """
    name = models.CharField(max_length=100, unique=True, help_text="Unique Team Name (e.g. Alpha, Beta, Omega)")
    description = models.TextField(blank=True, null=True, help_text="Specialization, zone, or coverage notes")
    leader = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='led_teams')
    members = models.ManyToManyField(User, blank=True, related_name='solar_teams')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()

    def get_assigned_bookings(self):
        from django.apps import apps
        from django.db.models import Q
        SolarBooking = apps.get_model('bookings', 'SolarBooking')
        return SolarBooking.objects.filter(
            Q(assigned_team=self) | Q(assigned_team_driver__iexact=self.name)
        )

    @property
    def active_orders_count(self):
        from django.apps import apps
        SolarBooking = apps.get_model('bookings', 'SolarBooking')
        return self.get_assigned_bookings().filter(is_cancelled=False).exclude(stage=SolarBooking.STAGE_COMPLETED).count()

    @property
    def completed_orders_count(self):
        from django.apps import apps
        SolarBooking = apps.get_model('bookings', 'SolarBooking')
        return self.get_assigned_bookings().filter(stage=SolarBooking.STAGE_COMPLETED, is_cancelled=False).count()

    @property
    def total_kw_installed(self):
        from django.apps import apps
        from django.db.models import Sum
        from decimal import Decimal
        SolarBooking = apps.get_model('bookings', 'SolarBooking')
        agg = self.get_assigned_bookings().filter(stage=SolarBooking.STAGE_COMPLETED, is_cancelled=False).aggregate(s=Sum('system_capacity_kw'))
        return agg['s'] or Decimal('0.00')

def user_avatar_upload_path(instance, filename):
    """
    Store agent profile avatars in media/avatars/<clean_username>_<id>.<ext>
    """
    import os, re
    ext = os.path.splitext(filename)[1].lower()
    user_id = instance.user_id or 'new'
    username = getattr(instance.user, 'username', 'user') if hasattr(instance, 'user') and instance.user else 'user'
    clean_username = re.sub(r'[^\w-]', '', username)
    return f"avatars/{clean_username}_{user_id}{ext}"


class UserProfile(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    ROLE_ADMIN = 'ADMIN'
    ROLE_MANAGER = 'MANAGER'
    ROLE_SALES = 'SALES'
    ROLE_ENGINEER = 'ENGINEER'
    ROLE_TECHNICIAN = 'TECHNICIAN'
    ROLE_SUPPORT = 'SUPPORT'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'System Administrator'),
        (ROLE_MANAGER, 'Operations Manager'),
        (ROLE_SALES, 'Sales Representative'),
        (ROLE_ENGINEER, 'Solar Project Engineer'),
        (ROLE_TECHNICIAN, 'Installation Technician'),
        ('INSTALLER', 'Installation Lead / Technician'),
        ('SURVEYOR', 'Survey Engineer / Inspector'),
        (ROLE_SUPPORT, 'Customer Support'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to=user_avatar_upload_path, blank=True, null=True, verbose_name="Profile Picture / Avatar")
    phone = models.CharField(max_length=30, blank=True, null=True)
    designation = models.CharField(max_length=120, blank=True, default="", verbose_name="Job Title / Designation")
    bio = models.TextField(blank=True, default="", verbose_name="Bio / Summary")
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='SALES')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='approved_profiles')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ({self.get_status_display()})"

    @property
    def avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return None

    @classmethod
    def get_role_choices(cls):
        """Dynamic role choices derived from active CatalogItem assigned roles."""
        try:
            from core.models import CatalogItem
            role_items = CatalogItem.objects.filter(
                category=CatalogItem.CATEGORY_ASSIGNED_ROLE,
                is_active=True
            ).order_by('order', 'name')

            if not role_items.exists():
                CatalogItem.ensure_defaults(CatalogItem.CATEGORY_ASSIGNED_ROLE)
                role_items = CatalogItem.objects.filter(
                    category=CatalogItem.CATEGORY_ASSIGNED_ROLE,
                    is_active=True
                ).order_by('order', 'name')

            code_map = {
                'System Administrator': cls.ROLE_ADMIN,
                'Operations Manager': cls.ROLE_MANAGER,
                'Sales Representative': cls.ROLE_SALES,
                'Solar Project Engineer': cls.ROLE_ENGINEER,
                'Installation Technician': cls.ROLE_TECHNICIAN,
                'Installation Lead / Technician': 'INSTALLER',
                'Survey Engineer / Inspector': 'SURVEYOR',
                'Customer Support': cls.ROLE_SUPPORT,
            }

            choices = []
            for item in role_items:
                code = code_map.get(item.name, item.name.upper().replace(' ', '_')[:30])
                choices.append((code, item.name))
            return choices or cls.ROLE_CHOICES
        except Exception:
            return cls.ROLE_CHOICES

    @property
    def role_display(self):
        code_to_name = {
            'ADMIN': 'System Administrator',
            'MANAGER': 'Operations Manager',
            'SALES': 'Sales Representative',
            'ENGINEER': 'Solar Project Engineer',
            'TECHNICIAN': 'Installation Technician',
            'INSTALLER': 'Installation Lead / Technician',
            'SURVEYOR': 'Survey Engineer / Inspector',
            'SUPPORT': 'Customer Support',
        }
        if self.role in code_to_name:
            return code_to_name[self.role]
        try:
            from core.models import CatalogItem
            item = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_ASSIGNED_ROLE, name__iexact=self.role).first()
            if item:
                return item.name
        except Exception:
            pass
        return self.get_role_display() or self.role

    @property
    def can_manage_users(self):
        return self.role in ['ADMIN', 'MANAGER'] or self.user.is_superuser or self.user.is_staff

    @property
    def can_manage_settings(self):
        return self.role in ['ADMIN'] or self.user.is_superuser

    @property
    def completed_tasks_count(self):
        return getattr(self.user, 'completed_tasks', User.objects.none()).count()

    @property
    def pending_tasks_count(self):
        return getattr(self.user, 'assigned_tasks', User.objects.none()).filter(is_completed=False).count()


class CatalogItem(models.Model):
    """
    Central Master Catalog for dynamic dropdown choices across Solar CRM.
    Allows administrators to add, edit, reorder, and remove choices for equipment,
    accessories, lead channels, and customer categories.
    """
    CATEGORY_PANEL_BRAND = 'PANEL_BRAND'
    CATEGORY_PANEL_TECH = 'PANEL_TECH'
    CATEGORY_INVERTER = 'INVERTER'
    CATEGORY_MOUNTING = 'MOUNTING'
    CATEGORY_ACCESSORY = 'ACCESSORY'
    CATEGORY_LEAD_SOURCE = 'LEAD_SOURCE'
    CATEGORY_ASSIGNED_ROLE = 'ROLE'
    CATEGORY_CUSTOMER_CATEGORY = 'CUSTOMER_CATEGORY'

    CATEGORY_CHOICES = [
        (CATEGORY_PANEL_BRAND, 'Solar Panel Brand / Company'),
        (CATEGORY_PANEL_TECH, 'Panel Technology / Cell Type'),
        (CATEGORY_INVERTER, 'Inverter Model / Rating'),
        (CATEGORY_MOUNTING, 'Mounting Structure Type'),
        (CATEGORY_ACCESSORY, 'Required Accessory / Safety Gear'),
        (CATEGORY_LEAD_SOURCE, 'Customer Lead Source'),
        (CATEGORY_ASSIGNED_ROLE, 'Assigned Role / User Role'),
        (CATEGORY_CUSTOMER_CATEGORY, 'Customer Category / Segment'),
    ]

    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, db_index=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        unique_together = ('category', 'name')

    def __str__(self):
        return f"[{self.get_category_display()}] {self.name}"

    @classmethod
    def get_active_choices(cls, category):
        """Returns list of active names for a category, ensuring defaults if empty."""
        cls.ensure_defaults(category)
        return list(cls.objects.filter(category=category, is_active=True).values_list('name', flat=True))

    @classmethod
    def ensure_defaults(cls, category=None):
        """Pre-populates default options if none exist in the database."""
        defaults = {
            cls.CATEGORY_PANEL_BRAND: [
                'Tata Power Solar',
                'Waaree Energies',
                'Adani Solar',
                'Vikram Solar',
                'Goldi Solar',
                'RenewSys Solar',
                'Canadian Solar',
                'Trina Solar',
                'Rayzon Solar',
            ],
            cls.CATEGORY_PANEL_TECH: [
                'Mono PERC Half-Cut',
                'TopCon N-Type Dual-Glass',
                'Bifacial Dual-Glass',
                'Polycrystalline Standard',
            ],

            cls.CATEGORY_INVERTER: [
                'On-Grid Smart Inverter 5kW',
                'Hybrid Smart Inverter 5kW with Battery Ready',
                'Off-Grid Pure Sine Wave 3kW',
                'Three-Phase Commercial Inverter 10kW',
                'Micro-Inverter Multi-String 2.5kW',
            ],
            cls.CATEGORY_MOUNTING: [
                'Rooftop - Concrete / RCC Flat Roof',
                'Rooftop - Metal / Tin Shed',
                'Rooftop - Slanted Tiled Roof',
                'Ground Mounted Elevated Structure',
                'Solar Carport Canopy',
            ],
            cls.CATEGORY_ACCESSORY: [
                'AC/DC Distribution Box',
                'Surge Protection Device (SPD)',
                'Copper Earthing Rod & Flat',
                'Cable Trays & Conduits',
                'MC4 Solar Connectors',
                'DC Isolator Switch 1000V',
                'Safety Harness & Helmets',
                'Lightning Arrester Class B+C',
                'Solar PV DC Cables (4mm / 6mm)',
                'Fire Extinguisher ABC Type',
            ],
            cls.CATEGORY_LEAD_SOURCE: [
                'Website Inquiry',
                'Customer Referral',
                'Social Media Campaign',
                'Field Sales Agent',
                'Direct Phone Call',
                'Other / Walk-in',
            ],
            cls.CATEGORY_ASSIGNED_ROLE: [
                ('System Administrator', 'Full system administration, settings & user approvals'),
                ('Operations Manager', 'Pipeline, bookings & operations control'),
                ('Sales Representative', 'Lead intake, consultations & customer quotes'),
                ('Solar Project Engineer', 'System design, engineering & approvals'),
                ('Installation Technician', 'Site installations, electrical wiring & hardware'),
                ('Installation Lead / Technician', 'Field crew lead & installation supervision'),
                ('Survey Engineer / Inspector', 'Rooftop survey, feasibility & shadow analysis'),
                ('Customer Support', 'Post-install queries, service tickets & support'),
            ],
        }

        categories_to_check = [category] if category else defaults.keys()
        for cat in categories_to_check:
            if cat in defaults and not cls.objects.filter(category=cat).exists():
                for idx, item_data in enumerate(defaults[cat]):
                    if isinstance(item_data, tuple):
                        name, desc = item_data
                    else:
                        name, desc = item_data, None
                    cls.objects.get_or_create(category=cat, name=name, defaults={'order': idx, 'description': desc})


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.is_superuser or instance.is_staff:
            UserProfile.objects.get_or_create(
                user=instance,
                defaults={
                    'status': UserProfile.STATUS_APPROVED,
                    'role': 'ADMIN',
                    'approved_at': timezone.now()
                }
            )
        else:
            UserProfile.objects.get_or_create(user=instance)
