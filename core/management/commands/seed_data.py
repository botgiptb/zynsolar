from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.models import CompanySetting, TeamMember
from customers.models import Customer
from bookings.models import SolarBooking, BookingAuditLog

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds realistic sample data for Solar CRM system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing Solar CRM seed data..."))

        # 1. Superuser / Staff User
        user, created = User.objects.get_or_create(username='admin', defaults={
            'email': 'admin@heliossolar.com',
            'first_name': 'Rafi',
            'last_name': 'Admin',
            'is_staff': True,
            'is_superuser': True,
        })
        if created:
            user.set_password('admin123')
            user.save()
            self.stdout.write(self.style.SUCCESS("Created admin user (admin / admin123)"))
        else:
            self.stdout.write("Admin user already exists.")

        # 2. Company Settings
        company = CompanySetting.get_settings()
        company.company_name = "Helios Solar Distribution & Energy Solutions"
        company.tagline = "Commercial & Residential High-Efficiency Solar Distribution"
        company.phone = "+1 (800) 555-7652"
        company.email = "operations@heliossolar.com"
        company.address = "1200 CleanEnergy Parkway, Suite 500, Phoenix, AZ 85004"
        company.tax_id = "US-AZ-8839210-GST"
        company.currency_symbol = "$"
        company.standard_kw_rate = Decimal('1250.00')
        company.save()
        self.stdout.write(self.style.SUCCESS("Configured company settings"))

        # 3. Team Members & Logistics Specialists
        members_data = [
            ("Sarah Jenkins", "SALES", "+1 (555) 201-9988", "sarah.j@heliossolar.com"),
            ("David Kim", "SALES", "+1 (555) 302-1144", "david.k@heliossolar.com"),
            ("Marcus Vance", "SURVEYOR", "+1 (555) 404-5533", "marcus.v@heliossolar.com"),
            ("Elena Rostova", "SURVEYOR", "+1 (555) 505-7722", "elena.r@heliossolar.com"),
            ("Apex Alpha Installation Crew", "INSTALLER", "+1 (555) 880-1122", "crew.alpha@heliossolar.com"),
            ("John Martinez (Logistics Specialist)", "DRIVER", "+1 (555) 991-3344", "john.driver@heliossolar.com"),
        ]

        for name, role, phone, email in members_data:
            TeamMember.objects.get_or_create(name=name, defaults={'role': role, 'phone': phone, 'email': email})

        # 4. Customers
        customers_seed = [
            {
                'name': "Robert & Clara Sterling",
                'phone': "+1 480-555-0101",
                'alt_phone': "+1 480-555-0102",
                'email': "robert.sterling@gmail.com",
                'customer_type': 'INDIVIDUAL',
                'house_building': "Villa 42, Sunrise Ridge",
                'street': "4501 E Camelback Rd",
                'city': "Phoenix",
                'state': "Arizona",
                'postal_code': "85018",
                'coordinates': "33.5092, -111.9865",
                'company_name': "",
                'lead_source': 'WEBSITE',
                'notes': "Customer requested premium all-black monocrystalline panels with battery backup provision.",
            },
            {
                'name': "SunRidge Cold Storage Inc.",
                'phone': "+1 602-555-0202",
                'alt_phone': "",
                'email': "facilities@sunridgecold.com",
                'customer_type': 'BUSINESS',
                'house_building': "Warehouse 3B, Industrial Park",
                'street': "7200 W Van Buren St",
                'city': "Phoenix",
                'state': "Arizona",
                'postal_code': "85043",
                'coordinates': "33.4510, -112.2130",
                'company_name': "SunRidge Cold Storage Logistics LLC",
                'tax_id': "GST-AZ-994821",
                'lead_source': 'FIELD_AGENT',
                'notes': "Commercial warehouse roof. High daytime refrigeration load. 50kW ground/roof hybrid.",
            },
            {
                'name': "Dr. Jennifer Walsh",
                'phone': "+1 480-555-0303",
                'alt_phone': "+1 480-555-0304",
                'email': "jennifer.walsh@scottsdalemed.org",
                'customer_type': 'INDIVIDUAL',
                'house_building': "Lot 18, Desert Mountain",
                'street': "38700 N Desert Mountain Pkwy",
                'city': "Scottsdale",
                'state': "Arizona",
                'postal_code': "85262",
                'coordinates': "33.8201, -111.8702",
                'company_name': "",
                'lead_source': 'REFERRAL',
                'notes': "Spacious slanted Spanish tile roof. Needs specialized tile brackets without tile cutting.",
            },
            {
                'name': "Apex Auto Dealership",
                'phone': "+1 480-555-0404",
                'alt_phone': "",
                'email': "mgmt@apexautomotive.com",
                'customer_type': 'BUSINESS',
                'house_building': "Showroom & Service Center",
                'street': "1550 E Baseline Rd",
                'city': "Tempe",
                'state': "Arizona",
                'postal_code': "85283",
                'coordinates': "33.3789, -111.9123",
                'company_name': "Apex Motors Holdings",
                'tax_id': "GST-AZ-441029",
                'lead_source': 'SOCIAL_MEDIA',
                'notes': "Carport solar canopy over customer parking lot with EV charging station integration.",
            },
            {
                'name': "David & Amanda Miller",
                'phone': "+1 480-555-0505",
                'alt_phone': "",
                'email': "miller.david.81@yahoo.com",
                'customer_type': 'INDIVIDUAL',
                'house_building': "House 104",
                'street': "2210 S Dobson Rd",
                'city': "Chandler",
                'state': "Arizona",
                'postal_code': "85286",
                'coordinates': "33.2710, -111.8720",
                'company_name': "",
                'lead_source': 'WEBSITE',
                'notes': "Standard suburban 2-story home with asphalt shingle roof. Unshaded south exposure.",
            },
            {
                'name': "Green Valley Organic Farm",
                'phone': "+1 520-555-0606",
                'alt_phone': "",
                'email': "orders@greenvalleyorganics.com",
                'customer_type': 'BUSINESS',
                'house_building': "Main Barn & Processing Shed",
                'street': "1840 W Duval Mine Rd",
                'city': "Tucson",
                'state': "Arizona",
                'postal_code': "85614",
                'coordinates': "31.9012, -110.9984",
                'company_name': "Green Valley Agrotech Co.",
                'tax_id': "GST-AZ-772910",
                'lead_source': 'FIELD_AGENT',
                'notes': "Ground mounted solar array powering water pumping station and crop processing facility.",
            },
            {
                'name': "Richard 'Rick' Hansen",
                'phone': "+1 623-555-0707",
                'alt_phone': "+1 623-555-0708",
                'email': "rick.hansen@outlook.com",
                'customer_type': 'INDIVIDUAL',
                'house_building': "Residence 9",
                'street': "5840 W Bell Rd",
                'city': "Glendale",
                'state': "Arizona",
                'postal_code': "85308",
                'coordinates': "33.6390, -112.1850",
                'company_name': "",
                'lead_source': 'DIRECT_CALL',
                'notes': "Older electrical service panel (100A). Requires main electrical panel upgrade to 200A.",
            },
            {
                'name': "Mesa Micro-Brewery & Taproom",
                'phone': "+1 480-555-0808",
                'alt_phone': "",
                'email': "taproom@mesabrewco.com",
                'customer_type': 'BUSINESS',
                'house_building': "Brewery Bldg A",
                'street': "210 W Main St",
                'city': "Mesa",
                'state': "Arizona",
                'postal_code': "85201",
                'coordinates': "33.4150, -111.8380",
                'company_name': "Desert Hops Brewing LLC",
                'tax_id': "GST-AZ-330192",
                'lead_source': 'REFERRAL',
                'notes': "Flat metal tin roof. Fast turnaround needed before summer electricity peak tariff season.",
            },
        ]

        created_customers = []
        for cdata in customers_seed:
            cust = Customer.objects.filter(phone=cdata['phone']).first()
            if not cust:
                cust = Customer.objects.create(**cdata)
                self.stdout.write(f"Created customer: {cust.name} ({cust.customer_id})")
            created_customers.append(cust)

        # 5. Solar Bookings across all 4 stages and cancellations
        now = timezone.now().date()
        bookings_seed = [
            # Stage 1: New Bookings
            {
                'customer': created_customers[0], # Robert Sterling
                'stage': SolarBooking.STAGE_NEW,
                'is_cancelled': False,
                'system_capacity_kw': Decimal('7.20'),
                'panel_type': "Bifacial Mono PERC 550W Half-Cut (Tier 1)",
                'inverter_type': "Growatt 7kW Smart Hybrid Inverter",
                'number_of_panels': 14,
                'installation_type': 'ROOFTOP_RCC',
                'required_accessories': "AC/DC Distribution Box with Class II SPD, 3x Copper Earthing Electrodes",
                'booking_amount': Decimal('9800.00'),
                'advance_payment': Decimal('2500.00'),
                'booking_date': now - timedelta(days=2),
                'expected_installation_date': now + timedelta(days=14),
                'expected_completion_date': now + timedelta(days=18),
                'assigned_salesperson': "Sarah Jenkins",
                'assigned_team_driver': "Apex Alpha Installation Crew",
                'internal_notes': "Fresh booking confirmed with client. Survey visit scheduled next week.",
            },
            {
                'customer': created_customers[4], # David Miller
                'stage': SolarBooking.STAGE_NEW,
                'is_cancelled': False,
                'system_capacity_kw': Decimal('5.50'),
                'panel_type': "Canadian Solar 550W High Efficiency",
                'inverter_type': "Solis 5kW On-Grid Inverter with Wi-Fi Logger",
                'number_of_panels': 10,
                'installation_type': 'ROOFTOP_RCC',
                'required_accessories': "Standard Balance of System kit, 25mm PV Solar Cables",
                'booking_amount': Decimal('7200.00'),
                'advance_payment': Decimal('2000.00'),
                'booking_date': now - timedelta(days=4),
                'expected_installation_date': now + timedelta(days=20),
                'expected_completion_date': now + timedelta(days=25),
                'assigned_salesperson': "David Kim",
                'assigned_team_driver': "John Martinez (Logistics Specialist)",
                'internal_notes': "Customer paid 2k deposit by credit card. Awaiting survey team slot.",
            },

            # Stage 2: Site Survey
            {
                'customer': created_customers[2], # Dr. Jennifer Walsh
                'stage': SolarBooking.STAGE_SURVEY,
                'is_cancelled': False,
                'system_capacity_kw': Decimal('10.80'),
                'panel_type': "SunPower Maxeon 400W Premium Black Panels",
                'inverter_type': "SolarEdge 10kW Inverter with DC Power Optimizers",
                'number_of_panels': 26,
                'installation_type': 'ROOFTOP_TILED',
                'required_accessories': "QuickMount Tile Hooks, Lightning Arrester, Rapid Shutdown Box",
                'booking_amount': Decimal('16500.00'),
                'advance_payment': Decimal('4500.00'),
                'booking_date': now - timedelta(days=10),
                'survey_scheduled_date': now - timedelta(days=1),
                'survey_team_driver': "Marcus Vance (Survey Engineer)",
                'survey_status': 'COMPLETED_FEASIBLE',
                'survey_roof_measurements': "850 sq.ft South & Southwest facing, 22° tile pitch, 0% shading",
                'survey_notes': "Survey completed yesterday. Structure inspected with drone camera. Roof rafters are sturdy. Ready for installer crew dispatch.",
                'expected_installation_date': now + timedelta(days=7),
                'expected_completion_date': now + timedelta(days=12),
                'assigned_salesperson': "Sarah Jenkins",
                'assigned_team_driver': "Marcus Vance (Surveyor)",
                'internal_notes': "Tile replacement spares are available on site.",
            },
            {
                'customer': created_customers[7], # Mesa Micro-Brewery
                'stage': SolarBooking.STAGE_SURVEY,
                'is_cancelled': False,
                'system_capacity_kw': Decimal('18.00'),
                'panel_type': "Trina Solar 500W Vertex Bifacial",
                'inverter_type': "Huawei 20kW Three-Phase Commercial Inverter",
                'number_of_panels': 36,
                'installation_type': 'ROOFTOP_TIN',
                'required_accessories': "Trapezoidal Sheet Clamps, Aluminium Walkway Mesh, SPD Class I+II",
                'booking_amount': Decimal('22500.00'),
                'advance_payment': Decimal('6000.00'),
                'booking_date': now - timedelta(days=7),
                'survey_scheduled_date': now + timedelta(days=1),
                'survey_team_driver': "Elena Rostova (Inspector)",
                'survey_status': 'SCHEDULED',
                'survey_roof_measurements': "Pending tomorrow inspection",
                'survey_notes': "Site visit scheduled for tomorrow morning 10 AM. Client brewery manager will open gate.",
                'expected_installation_date': now + timedelta(days=15),
                'expected_completion_date': now + timedelta(days=21),
                'assigned_salesperson': "David Kim",
                'assigned_team_driver': "Elena Rostova (Surveyor)",
                'internal_notes': "Commercial rate tier applied.",
            },

            # Stage 3: Installation In Progress
            {
                'customer': created_customers[1], # SunRidge Cold Storage
                'stage': SolarBooking.STAGE_INSTALLATION,
                'is_cancelled': False,
                'system_capacity_kw': Decimal('48.50'),
                'panel_type': "JA Solar 545W DeepBlue 3.0 Pro Monocrystalline",
                'inverter_type': "Sungrow 50kW Multi-MPPT Commercial Inverter",
                'number_of_panels': 90,
                'installation_type': 'ROOFTOP_RCC',
                'required_accessories': "Heavy Duty Ballasted Mounting Racks, 35mm Solar Cable, DC Combiner Box",
                'booking_amount': Decimal('54000.00'),
                'advance_payment': Decimal('20000.00'),
                'booking_date': now - timedelta(days=22),
                'survey_scheduled_date': now - timedelta(days=16),
                'survey_status': 'COMPLETED_FEASIBLE',
                'survey_roof_measurements': "3,200 sq.ft industrial concrete slab roof",
                'installation_scheduled_date': now - timedelta(days=5),
                'installation_team': "Apex Alpha Installation Crew (4 Technicians)",
                'installation_progress': 65,
                'installation_notes': "Racking rails bolted down. 70 out of 90 panels mounted. DC combiner box wired. Inverter room conduits in progress.",
                'expected_installation_date': now - timedelta(days=5),
                'expected_completion_date': now + timedelta(days=4),
                'assigned_salesperson': "David Kim",
                'assigned_team_driver': "Apex Alpha Installation Crew",
                'internal_notes': "High priority commercial account.",
            },
            {
                'customer': created_customers[3], # Apex Auto Dealership
                'stage': SolarBooking.STAGE_INSTALLATION,
                'is_cancelled': False,
                'system_capacity_kw': Decimal('24.00'),
                'panel_type': "Bifacial Glass-Glass 500W Modules",
                'inverter_type': "Fronius Symo 20.0-3-M Three-Phase Inverter",
                'number_of_panels': 48,
                'installation_type': 'CARPORT',
                'required_accessories': "Galvanized Steel Carport Structure, Cable Trays, LED Under-Canopy Lighting",
                'booking_amount': Decimal('32000.00'),
                'advance_payment': Decimal('10000.00'),
                'booking_date': now - timedelta(days=18),
                'survey_status': 'COMPLETED_FEASIBLE',
                'survey_roof_measurements': "2,000 sq ft parking footprint",
                'installation_scheduled_date': now - timedelta(days=3),
                'installation_team': "Apex Alpha Installation Crew",
                'installation_progress': 40,
                'installation_notes': "Steel canopy upright posts erected and aligned. Beam cross-members bolted.",
                'expected_installation_date': now - timedelta(days=3),
                'expected_completion_date': now + timedelta(days=8),
                'assigned_salesperson': "Sarah Jenkins",
                'assigned_team_driver': "Apex Alpha Installation Crew",
                'internal_notes': "Integrated with 4 Level-2 EV charging pedestals.",
            },

            # Stage 4: Completed Bookings
            {
                'customer': created_customers[5], # Green Valley Organic Farm
                'stage': SolarBooking.STAGE_COMPLETED,
                'is_cancelled': False,
                'system_capacity_kw': Decimal('15.00'),
                'panel_type': "Vikram Solar 500W Somera High Output",
                'inverter_type': "Growatt 15kW Three Phase Solar Inverter",
                'number_of_panels': 30,
                'installation_type': 'GROUND_MOUNT',
                'required_accessories': "Ground screw piles, Concrete footings, DC Surge Protection",
                'booking_amount': Decimal('18500.00'),
                'advance_payment': Decimal('6000.00'),
                'final_payment_received': Decimal('12500.00'),
                'balance_amount': Decimal('0.00'),
                'booking_date': now - timedelta(days=45),
                'survey_status': 'COMPLETED_FEASIBLE',
                'survey_roof_measurements': "Open agricultural ground lot, South 180°",
                'installation_scheduled_date': now - timedelta(days=25),
                'installation_progress': 100,
                'actual_completion_date': now - timedelta(days=12),
                'completion_notes': "System synchronized with local utility grid. Bi-directional smart meter active. Full customer demonstration complete. Warranty booklet handed over.",
                'net_metering_status': "Meter Installed & Grid Active",
                'warranty_certificate_issued': True,
                'assigned_salesperson': "David Kim",
                'assigned_team_driver': "Apex Alpha Installation Crew",
                'internal_notes': "Zero balance outstanding. Customer gave 5-star Google review.",
            },

            # Cancelled Booking
            {
                'customer': created_customers[6], # Rick Hansen
                'stage': SolarBooking.STAGE_NEW,
                'is_cancelled': True,
                'cancellation_reason': "Customer decided to sell home and relocate out of state before installation phase.",
                'cancelled_at': timezone.now() - timedelta(days=3),
                'system_capacity_kw': Decimal('6.00'),
                'panel_type': "Standard Mono 450W Panels",
                'inverter_type': "Single Phase 5kW String Inverter",
                'number_of_panels': 13,
                'installation_type': 'ROOFTOP_RCC',
                'booking_amount': Decimal('7800.00'),
                'advance_payment': Decimal('1000.00'),
                'booking_date': now - timedelta(days=20),
                'assigned_salesperson': "Sarah Jenkins",
                'assigned_team_driver': "Unassigned",
                'internal_notes': "Advance deposit refunded minus admin fee.",
            }
        ]

        for bdata in bookings_seed:
            customer = bdata.pop('customer')
            # Check if booking exists for this customer with same capacity
            existing = SolarBooking.objects.filter(customer=customer, system_capacity_kw=bdata['system_capacity_kw']).first()
            if not existing:
                booking = SolarBooking(customer=customer, **bdata)
                booking.created_by = user
                booking.save()

                # Add initial audit log
                BookingAuditLog.objects.create(
                    booking=booking,
                    action='CREATED',
                    from_stage=None,
                    to_stage=SolarBooking.STAGE_NEW,
                    user=user,
                    user_name="Sarah Jenkins (Sales Exec)",
                    timestamp=timezone.now() - timedelta(days=30),
                    notes="Order confirmed and entered into Solar CRM."
                )

                if booking.stage in [SolarBooking.STAGE_SURVEY, SolarBooking.STAGE_INSTALLATION, SolarBooking.STAGE_COMPLETED]:
                    BookingAuditLog.objects.create(
                        booking=booking,
                        action='STAGE_TRANSITION',
                        from_stage=SolarBooking.STAGE_NEW,
                        to_stage=SolarBooking.STAGE_SURVEY,
                        user=user,
                        user_name="Marcus Vance (Survey Lead)",
                        timestamp=timezone.now() - timedelta(days=20),
                        notes="Site survey inspection scheduled and measurements recorded."
                    )

                if booking.stage in [SolarBooking.STAGE_INSTALLATION, SolarBooking.STAGE_COMPLETED]:
                    BookingAuditLog.objects.create(
                        booking=booking,
                        action='STAGE_TRANSITION',
                        from_stage=SolarBooking.STAGE_SURVEY,
                        to_stage=SolarBooking.STAGE_INSTALLATION,
                        user=user,
                        user_name="Apex Alpha Lead Tech",
                        timestamp=timezone.now() - timedelta(days=10),
                        notes="Survey approved feasible. Installation team dispatched with solar hardware."
                    )

                if booking.stage == SolarBooking.STAGE_COMPLETED:
                    BookingAuditLog.objects.create(
                        booking=booking,
                        action='STAGE_TRANSITION',
                        from_stage=SolarBooking.STAGE_INSTALLATION,
                        to_stage=SolarBooking.STAGE_COMPLETED,
                        user=user,
                        user_name="Rafi Admin",
                        timestamp=timezone.now() - timedelta(days=5),
                        notes="Grid net-metering active, full payment settled, 25-yr warranty certificate issued."
                    )

                if booking.is_cancelled:
                    BookingAuditLog.objects.create(
                        booking=booking,
                        action='CANCELLED',
                        from_stage=SolarBooking.STAGE_NEW,
                        to_stage='CANCELLED',
                        user=user,
                        user_name="Sarah Jenkins",
                        timestamp=timezone.now() - timedelta(days=3),
                        notes=f"Order cancelled: {booking.cancellation_reason}"
                    )

                self.stdout.write(self.style.SUCCESS(f"Created Booking {booking.booking_ref} ({booking.stage})"))

        self.stdout.write(self.style.SUCCESS("All seed data created successfully!"))
