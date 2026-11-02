from decimal import Decimal
from django import forms
from django.utils import timezone
from .models import SolarBooking, BookingAuditLog, BookingAttachment, BookingPayment, BookingNote, BookingCustomField
from customers.models import Customer


class SolarBookingForm(forms.ModelForm):
    INDIAN_STATES_CHOICES = [
        ('Kerala', 'Kerala'),
        ('Tamil Nadu', 'Tamil Nadu'),
        ('Karnataka', 'Karnataka'),
        ('Andhra Pradesh', 'Andhra Pradesh'),
        ('Telangana', 'Telangana'),
        ('Maharashtra', 'Maharashtra'),
        ('Gujarat', 'Gujarat'),
        ('Goa', 'Goa'),
        ('Delhi', 'Delhi (NCR)'),
        ('Rajasthan', 'Rajasthan'),
        ('Uttar Pradesh', 'Uttar Pradesh'),
        ('Madhya Pradesh', 'Madhya Pradesh'),
        ('West Bengal', 'West Bengal'),
        ('Punjab', 'Punjab'),
        ('Haryana', 'Haryana'),
        ('Odisha', 'Odisha'),
        ('Assam', 'Assam'),
        ('Bihar', 'Bihar'),
        ('Other State', 'Other State / UT'),
    ]



    INVERTER_CHOICES = [
        ('', '-- Select Inverter (Optional) --'),
        ('On-Grid Smart Inverter 5kW', 'On-Grid Smart Inverter 5kW'),
        ('Hybrid Smart Inverter 5kW with Battery Ready', 'Hybrid Smart Inverter 5kW with Battery Ready'),
        ('Off-Grid Pure Sine Wave 3kW', 'Off-Grid Pure Sine Wave 3kW'),
        ('Three-Phase Commercial Inverter 10kW', 'Three-Phase Commercial Inverter 10kW'),
        ('Micro-Inverter Multi-String 2.5kW', 'Micro-Inverter Multi-String 2.5kW'),
    ]

    SALESPERSON_CHOICES = [
        ('Unassigned', 'Unassigned'),
        ('Sarah Jenkins', 'Sarah Jenkins'),
        ('Alex Rivera', 'Alex Rivera'),
        ('Michael Chang', 'Michael Chang'),
        ('Jessica Miller', 'Jessica Miller'),
    ]

    TEAM_CHOICES = [
        ('Unassigned', '-- Select Assigned Team (Unassigned) --'),
        ('Team Alpha', 'Team Alpha'),
        ('Team Beta', 'Team Beta'),
        ('Team Omega', 'Team Omega'),
    ]

    KERALA_DISTRICTS = [
        'Alappuzha', 'Ernakulam', 'Idukki', 'Kannur', 'Kasaragod', 'Kollam',
        'Kottayam', 'Kozhikode', 'Malappuram', 'Palakkad', 'Pathanamthitta',
        'Thiruvananthapuram', 'Thrissur', 'Wayanad'
    ]

    site_state = forms.ChoiceField(
        choices=INDIAN_STATES_CHOICES,
        initial='Kerala',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_site_state'}),
        label="State"
    )

    site_district = forms.CharField(
        required=False,
        widget=forms.Select(
            attrs={'class': 'form-select', 'id': 'id_site_district'},
            choices=[('', '-- Select District --')] + [(d, d) for d in KERALA_DISTRICTS]
        ),
        label="District"
    )

    stage = forms.ChoiceField(
        choices=[],
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_stage'}),
        label="Initial Stage"
    )

    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(status='ACTIVE').order_by('name'),
        empty_label="-- Select Existing Customer --",
        widget=forms.Select(attrs={'class': 'form-select select2-customer', 'id': 'id_customer_select'})
    )
    system_capacity_kw = forms.DecimalField(
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control bg-light fw-bold text-dark border-start-0',
            'step': '0.01',
            'id': 'id_system_capacity_kw',
            'placeholder': '0.00',
            'readonly': 'readonly',
            'tabindex': '-1',
            'style': 'cursor: not-allowed; background-color: #f8fafc !important;'
        })
    )
    number_of_panels = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_number_of_panels', 'min': '0', 'placeholder': '0'})
    )
    booking_amount = forms.DecimalField(
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_booking_amount', 'placeholder': '0.00'})
    )
    booking_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    panel_brand = forms.ChoiceField(
        required=False,
        choices=[('', '-- Select Solar Panel Brand (Optional) --')],
        initial='',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_panel_brand'})
    )
    custom_panel_brand = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_custom_panel_brand',
            'placeholder': 'Enter new solar panel brand (e.g. Tata Power Solar)'
        })
    )
    panel_wattage = forms.IntegerField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'id_panel_wattage',
            'min': '0',
            'placeholder': '550'
        })
    )
    panel_tech = forms.ChoiceField(
        required=False,
        choices=[('', '-- Select Panel Technology (Optional) --')],
        initial='',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_panel_tech'})
    )
    custom_panel_tech = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_custom_panel_tech',
            'placeholder': 'Enter new technology (e.g. Mono PERC Half-Cut)'
        })
    )

    installation_type = forms.ChoiceField(
        required=False,
        choices=[('', '-- Select Mounting Structure (Optional) --')] + list(SolarBooking.INSTALLATION_TYPE_CHOICES),
        initial='',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_installation_type'})
    )
    custom_installation_type = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_custom_installation_type',
            'placeholder': 'Enter custom mounting structure (e.g. Ballasted Flat Roof Mount)'
        })
    )
    inverter_type = forms.ChoiceField(
        required=False,
        choices=INVERTER_CHOICES,
        initial='',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_inverter_type'})
    )
    custom_inverter_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_custom_inverter_name',
            'placeholder': 'Enter new inverter model & rating (e.g. Growatt 10kW Hybrid)'
        })
    )
    priority = forms.ChoiceField(
        choices=SolarBooking.PRIORITY_CHOICES,
        initial=SolarBooking.PRIORITY_NORMAL,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_priority'}),
        required=False
    )
    assigned_salesperson = forms.ChoiceField(
        choices=[('Unassigned', '-- Select Assigned Staff (Unassigned) --')],
        initial='Unassigned',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_assigned_salesperson'}),
        label="Assigned Staff"
    )
    assigned_team_driver = forms.ChoiceField(
        choices=TEAM_CHOICES,
        initial='Unassigned',
        label="Assigned Team",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_assigned_team_driver'})
    )
    custom_team_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_custom_team_name',
            'placeholder': 'Enter new installation team or crew (e.g. Delta Installation Crew)'
        })
    )

    class Meta:
        model = SolarBooking
        fields = [
            # Customer & Stage
            'customer', 'stage', 'priority', 'consumer_number',
            # Site Location & Detailed Address (Indian standard format)
            'site_house_flat', 'site_street_area', 'site_city', 'site_district',
            'site_state', 'site_pincode', 'site_location_url',
            # Solar System Details
            'system_capacity_kw', 'panel_brand', 'panel_wattage', 'panel_tech', 'inverter_type', 'number_of_panels',
            'installation_type', 'required_accessories', 'additional_requirements',
            # Financials
            'booking_amount', 'advance_payment',
            # Dates & Assignments
            'booking_date', 'expected_installation_date', 'expected_completion_date',
            'assigned_salesperson', 'assigned_team_driver',
            # Stage 2 Pre-fill (optional)
            'survey_scheduled_date', 'survey_team_driver',
            # Internal
            'internal_notes'
        ]
        widgets = {
            'stage': forms.Select(attrs={'class': 'form-select'}),
            'consumer_number': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_consumer_number',
                'placeholder': 'e.g. 13-digit Consumer ID (KSEB / DISCOM)'
            }),
            'site_house_flat': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_site_house_flat',
                'placeholder': 'e.g. Building No. 12/450, Green Villa / Sunrise Apartments'
            }),
            'site_street_area': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_site_street_area',
                'placeholder': 'e.g. Civil Station Road, Near Post Office, Kaloor'
            }),
            'site_city': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_site_city',
                'placeholder': 'e.g. Kochi / Aluva / Thiruvananthapuram'
            }),
            'site_pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_site_pincode',
                'placeholder': 'e.g. 682016',
                'maxlength': '10'
            }),
            'site_location_url': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_site_location_url',
                'placeholder': 'Paste Google Maps link, Plus code (e.g. QJ94+P2), or Lat, Long'
            }),
            'system_capacity_kw': forms.NumberInput(attrs={
                'class': 'form-control bg-light fw-bold text-dark border-start-0',
                'step': '0.01',
                'id': 'id_system_capacity_kw',
                'placeholder': '0.00',
                'readonly': 'readonly',
                'tabindex': '-1',
                'style': 'cursor: not-allowed; background-color: #f8fafc !important;'
            }),
            'panel_brand': forms.Select(attrs={'class': 'form-select', 'id': 'id_panel_brand'}),
            'panel_wattage': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_panel_wattage', 'min': '0', 'placeholder': '0'}),
            'panel_tech': forms.Select(attrs={'class': 'form-select', 'id': 'id_panel_tech'}),
            'number_of_panels': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_number_of_panels', 'min': '0', 'placeholder': '0'}),
            'installation_type': forms.Select(attrs={'class': 'form-select'}),
            'required_accessories': forms.HiddenInput(),
            'additional_requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Special customer requests, roof elevation details, etc.'}),
            'booking_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_booking_amount', 'placeholder': '0.00'}),
            'advance_payment': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_advance_payment', 'placeholder': '0.00'}),
            'booking_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_installation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_completion_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'survey_scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'survey_team_driver': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Surveyor Mike / Team Alpha'}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Internal notes visible only to staff...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamic District initialization
        existing_district = None
        if self.instance and self.instance.pk and self.instance.site_district:
            existing_district = self.instance.site_district
        elif self.initial.get('site_district'):
            existing_district = self.initial.get('site_district')

        if existing_district:
            curr_choices = [c[0] for c in self.fields['site_district'].widget.choices]
            if existing_district not in curr_choices:
                self.fields['site_district'].widget.choices = list(self.fields['site_district'].widget.choices) + [(existing_district, existing_district)]
            self.initial['site_district'] = existing_district
        from core.models import CatalogItem
        from bookings.models import PipelineStage

        # Dynamic Stage Choices: Load ALL active pipeline stages (including custom stages)
        try:
            active_pipeline_stages = list(PipelineStage.get_active_stages())
        except Exception:
            active_pipeline_stages = []

        if active_pipeline_stages:
            self.fields['stage'].choices = [(s.code, s.name) for s in active_pipeline_stages]
            if not self.instance.pk:
                if not self.initial.get('stage'):
                    init_stage = next((s.code for s in active_pipeline_stages if s.is_initial), None)
                    if not init_stage:
                        init_stage = active_pipeline_stages[0].code
                    self.initial['stage'] = init_stage
        elif self.instance and self.instance.pk and self.instance.stage:
            self.initial['stage'] = self.instance.stage

        # 0A. Solar Panel Brand Choices from Master Catalog & Dynamic Custom Options
        try:
            cat_brands = CatalogItem.get_active_choices(CatalogItem.CATEGORY_PANEL_BRAND)
        except Exception:
            cat_brands = [
                'Tata Power Solar', 'Waaree Energies', 'Adani Solar', 'Vikram Solar',
                'Goldi Solar', 'RenewSys Solar', 'Canadian Solar', 'Trina Solar', 'Rayzon Solar'
            ]
        try:
            db_brands = list(
                SolarBooking.objects.exclude(panel_brand__isnull=True)
                .exclude(panel_brand='')
                .values_list('panel_brand', flat=True)
                .distinct()
            )
        except Exception:
            db_brands = []

        combined_brands = list(cat_brands)
        for b in db_brands:
            if b and b not in combined_brands:
                combined_brands.append(b)

        if self.instance and self.instance.pk and self.instance.panel_brand:
            if self.instance.panel_brand not in combined_brands:
                combined_brands.append(self.instance.panel_brand)

        if self.data:
            post_brand = self.data.get('panel_brand')
            cust_brand = self.data.get('custom_panel_brand', '').strip()
            if post_brand and post_brand != 'Custom Panel Brand' and post_brand not in combined_brands:
                combined_brands.append(post_brand)
            if cust_brand and cust_brand not in combined_brands:
                combined_brands.append(cust_brand)

        brand_choices = [('', '-- Select Solar Panel Brand (Optional) --')] + [(b, b) for b in combined_brands]
        brand_choices.append(('Custom Panel Brand', 'Other / Custom Brand'))
        self.fields['panel_brand'].choices = brand_choices
        self.fields['panel_brand'].required = False

        if self.instance and self.instance.pk and self.instance.panel_brand:
            if self.instance.panel_brand in combined_brands:
                self.initial['panel_brand'] = self.instance.panel_brand
            else:
                self.initial['panel_brand'] = 'Custom Panel Brand'
                self.initial['custom_panel_brand'] = self.instance.panel_brand
        else:
            if 'panel_brand' not in self.initial:
                self.initial['panel_brand'] = ''

        # 0B. Solar Panel Technology Choices from Master Catalog & Dynamic Custom Options
        try:
            cat_techs = CatalogItem.get_active_choices(CatalogItem.CATEGORY_PANEL_TECH)
        except Exception:
            cat_techs = [
                'Mono PERC Half-Cut', 'TopCon N-Type Dual-Glass',
                'Bifacial Dual-Glass', 'Polycrystalline Standard'
            ]
        try:
            db_techs = list(
                SolarBooking.objects.exclude(panel_tech__isnull=True)
                .exclude(panel_tech='')
                .values_list('panel_tech', flat=True)
                .distinct()
            )
        except Exception:
            db_techs = []

        combined_techs = list(cat_techs)
        for t in db_techs:
            if t and t not in combined_techs:
                combined_techs.append(t)

        if self.instance and self.instance.pk and self.instance.panel_tech:
            if self.instance.panel_tech not in combined_techs:
                combined_techs.append(self.instance.panel_tech)

        if self.data:
            post_tech = self.data.get('panel_tech')
            cust_tech = self.data.get('custom_panel_tech', '').strip()
            if post_tech and post_tech != 'Custom Panel Tech' and post_tech not in combined_techs:
                combined_techs.append(post_tech)
            if cust_tech and cust_tech not in combined_techs:
                combined_techs.append(cust_tech)

        tech_choices = [('', '-- Select Panel Technology (Optional) --')] + [(t, t) for t in combined_techs]
        tech_choices.append(('Custom Panel Tech', 'Other / Custom Technology'))
        self.fields['panel_tech'].choices = tech_choices
        self.fields['panel_tech'].required = False

        if self.instance and self.instance.pk and self.instance.panel_tech:
            if self.instance.panel_tech in combined_techs:
                self.initial['panel_tech'] = self.instance.panel_tech
            else:
                self.initial['panel_tech'] = 'Custom Panel Tech'
                self.initial['custom_panel_tech'] = self.instance.panel_tech
        else:
            if 'panel_tech' not in self.initial:
                self.initial['panel_tech'] = ''

        # Wattage initial
        if self.instance and self.instance.pk:
            self.initial['panel_wattage'] = self.instance.panel_wattage or 0
        else:
            if 'panel_wattage' not in self.initial:
                self.initial['panel_wattage'] = 0

        # 2. Mounting Structure Type Choices from Master Catalog & Dynamic Custom Options
        try:
            cat_mount_choices = CatalogItem.get_active_choices(CatalogItem.CATEGORY_MOUNTING)
        except Exception:
            cat_mount_choices = [c[1] for c in SolarBooking.INSTALLATION_TYPE_CHOICES if c[0] != 'OTHER']

        try:
            db_inst = list(
                SolarBooking.objects.exclude(installation_type__isnull=True)
                .exclude(installation_type='')
                .exclude(installation_type='OTHER')
                .values_list('installation_type', flat=True)
                .distinct()
            )
        except Exception:
            db_inst = []

        combined_mounts = list(cat_mount_choices)
        for it in db_inst:
            if it and it not in combined_mounts and it != 'OTHER':
                combined_mounts.append(it)

        if self.instance and self.instance.pk and self.instance.installation_type:
            it = self.instance.installation_type
            if it not in combined_mounts and it != 'OTHER':
                combined_mounts.append(it)

        if self.data:
            post_inst = self.data.get('installation_type')
            custom_inst_input = self.data.get('custom_installation_type', '').strip()
            if post_inst and post_inst != 'OTHER' and post_inst not in combined_mounts:
                combined_mounts.append(post_inst)
            if custom_inst_input and custom_inst_input not in combined_mounts:
                combined_mounts.append(custom_inst_input)

        inst_choices = [('', '-- Select Mounting Structure (Optional) --')] + [(m, m) for m in combined_mounts]
        inst_choices.append(('OTHER', 'Other Custom Mount'))
        self.fields['installation_type'].choices = inst_choices
        self.fields['installation_type'].required = False

        if self.instance and self.instance.pk and self.instance.installation_type:
            it = self.instance.installation_type
            if it in combined_mounts:
                self.initial['installation_type'] = it
            else:
                self.initial['installation_type'] = 'OTHER'
                self.initial['custom_installation_type'] = it
        else:
            self.initial['installation_type'] = ''

        # 3. Inverter Choices from Master Catalog & Dynamic Custom Options
        try:
            base_inverter_choices = CatalogItem.get_active_choices(CatalogItem.CATEGORY_INVERTER)
        except Exception:
            base_inverter_choices = [
                'On-Grid Smart Inverter 5kW',
                'Hybrid Smart Inverter 5kW with Battery Ready',
                'Off-Grid Pure Sine Wave 3kW',
                'Three-Phase Commercial Inverter 10kW',
                'Micro-Inverter Multi-String 2.5kW',
            ]

        try:
            db_inverters = list(
                SolarBooking.objects.exclude(inverter_type__isnull=True)
                .exclude(inverter_type='')
                .exclude(inverter_type='Custom Inverter Spec')
                .values_list('inverter_type', flat=True)
                .distinct()
            )
        except Exception:
            db_inverters = []

        combined_inverters = list(base_inverter_choices)
        for inv in db_inverters:
            if inv and inv not in combined_inverters:
                combined_inverters.append(inv)

        if self.instance and self.instance.pk and self.instance.inverter_type:
            if self.instance.inverter_type not in combined_inverters and self.instance.inverter_type != 'Custom Inverter Spec':
                combined_inverters.append(self.instance.inverter_type)

        if self.data:
            post_inverter = self.data.get('inverter_type')
            custom_inv_input = self.data.get('custom_inverter_name', '').strip()
            if post_inverter and post_inverter != 'Custom Inverter Spec' and post_inverter not in combined_inverters:
                combined_inverters.append(post_inverter)
            if custom_inv_input and custom_inv_input not in combined_inverters:
                combined_inverters.append(custom_inv_input)

        inverter_choices = [('', '-- Select Inverter (Optional) --')] + [(inv, inv) for inv in combined_inverters]
        inverter_choices.append(('Custom Inverter Spec', 'Other / Custom Inverter'))
        self.fields['inverter_type'].choices = inverter_choices
        self.fields['inverter_type'].required = False

        if self.instance and self.instance.pk and self.instance.inverter_type:
            if self.instance.inverter_type in combined_inverters:
                self.initial['inverter_type'] = self.instance.inverter_type
            else:
                self.initial['inverter_type'] = 'Custom Inverter Spec'
                self.initial['custom_inverter_name'] = self.instance.inverter_type
        else:
            self.initial['inverter_type'] = ''

        # 4. Dynamic Assigned Staff Choices (All approved staff from UserProfile & User)
        try:
            from core.models import UserProfile
            approved_profiles = list(
                UserProfile.objects.filter(
                    status=UserProfile.STATUS_APPROVED
                ).select_related('user').order_by('user__first_name', 'user__last_name', 'user__username')
            )
        except Exception:
            approved_profiles = []

        staff_choices = [('Unassigned', '-- Select Assigned Staff (Unassigned) --')]
        added_staff_names = set()

        for prof in approved_profiles:
            u = prof.user
            full_name = f"{u.first_name} {u.last_name}".strip()
            display_name = full_name if full_name else u.username
            role_label = prof.get_role_display()
            label = f"{display_name} ({role_label})" if role_label else display_name
            staff_choices.append((display_name, label))
            added_staff_names.add(display_name)

        # Include active superusers or staff members
        try:
            from django.contrib.auth.models import User
            extra_users = User.objects.filter(is_active=True).filter(
                Q(is_staff=True) | Q(is_superuser=True)
            ).order_by('first_name', 'last_name', 'username')
            for u in extra_users:
                full_name = f"{u.first_name} {u.last_name}".strip()
                display_name = full_name if full_name else u.username
                if display_name not in added_staff_names:
                    role_text = "Administrator" if u.is_superuser else "Staff"
                    staff_choices.append((display_name, f"{display_name} ({role_text})"))
                    added_staff_names.add(display_name)
        except Exception:
            pass

        # Only list staff users in Assigned Staff - do not mix teams into staff

        # If current booking already has an assigned staff value (e.g. legacy/seed data like "Sarah Jenkins"), keep it valid
        if self.instance and self.instance.pk and self.instance.assigned_salesperson:
            current_val = self.instance.assigned_salesperson
            if current_val and current_val not in added_staff_names and current_val != 'Unassigned':
                staff_choices.append((current_val, current_val))
                added_staff_names.add(current_val)

        # If POST data has a staff value
        if self.data:
            post_staff = self.data.get('assigned_salesperson')
            if post_staff and post_staff not in added_staff_names and post_staff != 'Unassigned':
                staff_choices.append((post_staff, post_staff))
                added_staff_names.add(post_staff)

        self.fields['assigned_salesperson'].choices = staff_choices
        self.fields['assigned_salesperson'].label = "Assigned Staff"

        if self.instance and self.instance.pk and self.instance.assigned_salesperson:
            self.initial['assigned_salesperson'] = self.instance.assigned_salesperson

        # 5. Assigned Team Choices: ONLY actual operational Teams (Alpha, Beta, Omega, etc.)
        team_choices = [('Unassigned', '-- Select Assigned Team (Unassigned) --')]
        try:
            from core.models import Team
            db_teams_qs = Team.objects.all().order_by('name')
            for t in db_teams_qs:
                display_team = f"Team {t.name}" if not t.name.lower().startswith("team") else t.name
                team_choices.append((display_team, display_team))
        except Exception:
            team_choices.extend([
                ('Team Alpha', 'Team Alpha'),
                ('Team Beta', 'Team Beta'),
                ('Team Omega', 'Team Omega')
            ])

        # If existing order has custom team name, keep it valid
        existing_team_val = self.instance.assigned_team_driver if (self.instance and self.instance.pk) else None
        if existing_team_val and existing_team_val != 'Unassigned':
            existing_clean = existing_team_val.replace(' (Driver: Mark)', '').replace(' (Driver: John Martinez)', '').strip()
            if not any(existing_clean == c[0] for c in team_choices):
                team_choices.append((existing_clean, existing_clean))

        team_choices.append(('Custom Team Spec', 'Other / Custom Team'))
        self.fields['assigned_team_driver'].choices = team_choices
        self.fields['assigned_team_driver'].label = "Assigned Team" 

        valid_team_keys = [c[0] for c in team_choices]
        if self.instance and self.instance.pk and self.instance.assigned_team_driver:
            if self.instance.assigned_team_driver in valid_team_keys:
                self.initial['assigned_team_driver'] = self.instance.assigned_team_driver
            else:
                self.initial['assigned_team_driver'] = 'Custom Team Spec'
                self.initial['custom_team_name'] = self.instance.assigned_team_driver

        if not (self.instance and self.instance.pk):
            self.initial['number_of_panels'] = 0
            self.initial['system_capacity_kw'] = Decimal('0.00')

        # Make all options after the address section optional
        post_address_fields = [
            'system_capacity_kw', 'inverter_type', 'number_of_panels',
            'installation_type', 'required_accessories', 'additional_requirements',
            'booking_amount', 'advance_payment', 'booking_date',
            'expected_installation_date', 'expected_completion_date',
            'assigned_salesperson', 'assigned_team_driver',
            'survey_scheduled_date', 'survey_team_driver',
            'internal_notes', 'custom_inverter_name',
            'custom_installation_type', 'custom_team_name', 'site_location_url'
        ]
        for f_name in post_address_fields:
            if f_name in self.fields:
                self.fields[f_name].required = False

    def clean_site_district(self):
        district = self.cleaned_data.get('site_district', '').strip()
        if district in ['Other District', '-- Select District --', 'None']:
            return ''
        return district

    def clean(self):
        cleaned_data = super().clean()

        # Provide defaults for optional post-address fields if empty
        if cleaned_data.get('system_capacity_kw') is None:
            cleaned_data['system_capacity_kw'] = Decimal('0.00')
        if cleaned_data.get('booking_amount') is None:
            cleaned_data['booking_amount'] = Decimal('0.00')
        if cleaned_data.get('advance_payment') is None:
            cleaned_data['advance_payment'] = Decimal('0.00')
        if cleaned_data.get('number_of_panels') is None:
            cleaned_data['number_of_panels'] = 0
        if not cleaned_data.get('booking_date'):
            cleaned_data['booking_date'] = timezone.now().date()
        if not cleaned_data.get('assigned_salesperson'):
            cleaned_data['assigned_salesperson'] = 'Unassigned'
        if not cleaned_data.get('assigned_team_driver'):
            cleaned_data['assigned_team_driver'] = 'Unassigned'
        if cleaned_data.get('panel_type') is None:
            cleaned_data['panel_type'] = ''
        if cleaned_data.get('inverter_type') is None:
            cleaned_data['inverter_type'] = ''
        if cleaned_data.get('installation_type') is None:
            cleaned_data['installation_type'] = ''

        booking_amount = cleaned_data.get('booking_amount') or Decimal('0.00')
        advance_payment = cleaned_data.get('advance_payment') or Decimal('0.00')

        if booking_amount > Decimal('0.00') and advance_payment > booking_amount:
            self.add_error('advance_payment', "Advance payment cannot exceed the total booking amount.")

        # Date consistency validation: expected dates cannot precede booking date, and completion cannot precede installation
        booking_date = cleaned_data.get('booking_date')
        expected_installation_date = cleaned_data.get('expected_installation_date')
        expected_completion_date = cleaned_data.get('expected_completion_date')

        if booking_date:
            if expected_installation_date and expected_installation_date < booking_date:
                self.add_error(
                    'expected_installation_date',
                    "Expected installation date cannot be earlier than the booking date."
                )
            if expected_completion_date and expected_completion_date < booking_date:
                self.add_error(
                    'expected_completion_date',
                    "Expected completion date cannot be earlier than the booking date."
                )

        if expected_installation_date and expected_completion_date:
            if expected_completion_date < expected_installation_date:
                self.add_error(
                    'expected_completion_date',
                    "Expected completion date cannot be earlier than the expected installation date."
                )

        # Brand & Custom Brand validation
        panel_brand = cleaned_data.get('panel_brand', '')
        custom_brand = cleaned_data.get('custom_panel_brand', '').strip()
        if panel_brand == 'Custom Panel Brand':
            if custom_brand:
                cleaned_data['panel_brand'] = custom_brand
            else:
                self.add_error('custom_panel_brand', "Please enter the custom solar panel brand.")
        elif custom_brand and (not panel_brand or panel_brand == 'Custom Panel Brand'):
            cleaned_data['panel_brand'] = custom_brand

        # Tech & Custom Tech validation
        panel_tech = cleaned_data.get('panel_tech', '')
        custom_tech = cleaned_data.get('custom_panel_tech', '').strip()
        if panel_tech == 'Custom Panel Tech':
            if custom_tech:
                cleaned_data['panel_tech'] = custom_tech
            else:
                self.add_error('custom_panel_tech', "Please enter the custom panel technology.")
        elif custom_tech and (not panel_tech or panel_tech == 'Custom Panel Tech'):
            cleaned_data['panel_tech'] = custom_tech

        # Auto-calculate system_capacity_kw strictly from panel_wattage and number_of_panels (Readonly)
        panel_wattage = cleaned_data.get('panel_wattage') or 0
        num_panels = cleaned_data.get('number_of_panels') or 0
        if panel_wattage > 0 and num_panels > 0:
            calc_kw = Decimal(str(round((panel_wattage * num_panels) / 1000.0, 2)))
            cleaned_data['system_capacity_kw'] = calc_kw
        else:
            cleaned_data['system_capacity_kw'] = Decimal('0.00')

        # Synthesize composite panel_type
        b_val = cleaned_data.get('panel_brand', '')
        t_val = cleaned_data.get('panel_tech', '')
        syn_parts = []
        if b_val:
            syn_parts.append(b_val)
        if panel_wattage > 0:
            syn_parts.append(f"{panel_wattage}W")
        if t_val:
            syn_parts.append(t_val)
        if syn_parts:
            cleaned_data['panel_type'] = " ".join(syn_parts)
        elif not cleaned_data.get('panel_type'):
            cleaned_data['panel_type'] = ""



        # Mounting structure validation
        installation_type = cleaned_data.get('installation_type')
        custom_inst = cleaned_data.get('custom_installation_type', '').strip()

        if installation_type == 'OTHER':
            if custom_inst:
                cleaned_data['installation_type'] = custom_inst
            else:
                self.add_error('custom_installation_type', "Please enter the custom mounting structure type.")
        elif custom_inst and (not installation_type or installation_type == 'OTHER'):
            cleaned_data['installation_type'] = custom_inst

        # Inverter validation
        inverter_type = cleaned_data.get('inverter_type')
        custom_inverter = cleaned_data.get('custom_inverter_name', '').strip()

        if inverter_type == 'Custom Inverter Spec':
            if custom_inverter:
                cleaned_data['inverter_type'] = custom_inverter
            else:
                self.add_error('custom_inverter_name', "Please enter the new inverter model / rating.")
        elif custom_inverter and (not inverter_type or inverter_type == 'Custom Inverter Spec'):
            cleaned_data['inverter_type'] = custom_inverter

        # Team validation
        assigned_team_driver = cleaned_data.get('assigned_team_driver')
        custom_team = cleaned_data.get('custom_team_name', '').strip()

        if assigned_team_driver == 'Custom Team Spec':
            if custom_team:
                cleaned_data['assigned_team_driver'] = custom_team
            else:
                self.add_error('custom_team_name', "Please enter the custom team or crew name.")
        elif custom_team and (not assigned_team_driver or assigned_team_driver == 'Custom Team Spec'):
            cleaned_data['assigned_team_driver'] = custom_team

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.panel_brand = self.cleaned_data.get('panel_brand', '')
        instance.panel_wattage = self.cleaned_data.get('panel_wattage') or 0
        instance.panel_tech = self.cleaned_data.get('panel_tech', '')
        syn_parts = []
        if instance.panel_brand:
            syn_parts.append(instance.panel_brand)
        if instance.panel_tech:
            syn_parts.append(instance.panel_tech)
        if instance.panel_wattage:
            syn_parts.append(f"{instance.panel_wattage}Wp")
        instance.panel_type = " ".join(syn_parts)

        installation_type = self.cleaned_data.get('installation_type', '')
        if installation_type != 'OTHER':
            instance.installation_type = installation_type or ''

        inverter_type = self.cleaned_data.get('inverter_type', '')
        if inverter_type != 'Custom Inverter Spec':
            instance.inverter_type = inverter_type or ''

        assigned_team_driver = self.cleaned_data.get('assigned_team_driver')
        if assigned_team_driver and assigned_team_driver != 'Custom Team Spec':
            instance.assigned_team_driver = assigned_team_driver

        if commit:
            instance.save()
        return instance


class StageAdvanceForm(forms.Form):
    """Generic form for advancing stages with relevant inputs"""
    target_stage = forms.CharField(widget=forms.HiddenInput())
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter remarks or findings for this stage transition...'})
    )

    # Fields for Stage 2 (Site Survey)
    survey_scheduled_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    survey_team_driver = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Survey Engineer & Operations Specialist'})
    )
    survey_roof_measurements = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 600 sq ft, 180° South facing, 15° tilt'})
    )
    survey_status = forms.ChoiceField(
        choices=SolarBooking.SURVEY_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Fields for Stage 3 (Installation)
    installation_scheduled_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    installation_team = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lead Technician & Team Name'})
    )
    installation_progress = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=100,
        initial=20,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Percentage 0-100'})
    )
    expected_completion_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    # Fields for Stage 4 (Completion)
    actual_completion_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    final_payment_received = forms.DecimalField(
        required=False,
        min_value=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'})
    )
    net_metering_status = forms.ChoiceField(
        choices=SolarBooking.NET_METERING_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_net_metering_status'})
    )
    warranty_certificate_issued = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class CancelBookingForm(forms.Form):
    cancellation_reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Please specify the exact reason for cancellation (e.g. Customer cancelled due to budget, structural survey failed, etc.).'
        })
    )


class BookingAttachmentForm(forms.ModelForm):
    category = forms.ChoiceField(
        choices=BookingAttachment.CATEGORY_CHOICES,
        required=False,
        initial='OTHER',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_attachment_category'})
    )

    class Meta:
        model = BookingAttachment
        fields = ['category', 'title', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_attachment_title', 'placeholder': 'e.g. Roof Angle Photo, Discom Sanction Letter, KSEB Bill'}),
            'file': forms.FileInput(attrs={'class': 'form-control', 'id': 'id_attachment_file'}),
        }

    def clean_category(self):
        return self.cleaned_data.get('category') or 'OTHER'

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if not file:
            raise forms.ValidationError("Please select a file or photo to upload.")
        # Optional: 25MB max size check
        max_size = 25 * 1024 * 1024
        if file.size > max_size:
            raise forms.ValidationError("File size cannot exceed 25MB.")
        return file


class BookingPaymentForm(forms.ModelForm):
    class Meta:
        model = BookingPayment
        fields = ['amount', 'payment_date', 'payment_method', 'milestone', 'transaction_ref', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control fs-5 fw-bold',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-select'
            }),
            'milestone': forms.Select(attrs={
                'class': 'form-select'
            }),
            'transaction_ref': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. UTR / IMPS Ref / Cheque No / Txn ID'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Payer name, bank name, payment remarks...'
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not amount or amount <= Decimal('0.00'):
            raise forms.ValidationError("Payment amount must be greater than zero.")
        return amount


class BookingNoteForm(forms.ModelForm):
    category = forms.CharField(max_length=60, required=False, initial='YELLOW')
    note_text = forms.CharField(widget=forms.Textarea(attrs={'id': 'stickyNoteHiddenText'}), required=True)

    class Meta:
        model = BookingNote
        fields = ['category', 'note_text', 'is_pinned']
        widgets = {
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_note_pinned'}),
        }


class UpdateBookingInternalNotesForm(forms.ModelForm):
    class Meta:
        model = SolarBooking
        fields = ['internal_notes']
        widgets = {
            'internal_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter primary project notes, special contractual conditions, or site background...'
            })
        }





class BookingCustomFieldForm(forms.ModelForm):
    class Meta:
        model = BookingCustomField
        fields = ['label', 'value']
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_custom_field_label',
                'placeholder': 'Field Header / Name (e.g. Battery Capacity, Sanctioned Load, Phase)'
            }),
            'value': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'id_custom_field_value',
                'placeholder': 'Field Value (e.g. 10 kWh LFP, 5 kW, 3-Phase, 15° South)'
            }),
        }

    def clean_label(self):
        label = self.cleaned_data.get('label', '').strip()
        if not label:
            raise forms.ValidationError("Field Header / Label is required.")
        return label

    def clean_value(self):
        val = self.cleaned_data.get('value', '').strip()
        if not val:
            raise forms.ValidationError("Field Value is required.")
        return val
