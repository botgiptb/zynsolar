from django.core.management.base import BaseCommand
from bookings.models import SolarBooking, BookingAuditLog
from customers.models import Customer
from core.models import TeamMember, CompanySetting


class Command(BaseCommand):
    help = 'Clears all demo customers, bookings, audit logs, and team members'

    def handle(self, *args, **options):
        self.stdout.write("Removing demo data...")
        
        b_count = SolarBooking.objects.count()
        SolarBooking.objects.all().delete()
        BookingAuditLog.objects.all().delete()
        
        c_count = Customer.objects.count()
        Customer.objects.all().delete()
        
        t_count = TeamMember.objects.count()
        TeamMember.objects.all().delete()

        # Reset company setting to a simple clean profile
        company = CompanySetting.get_settings()
        company.company_name = "Solar CRM"
        company.tagline = "Solar Distribution & Installation Management"
        company.phone = "+1 (800) 555-0199"
        company.email = "contact@solarcrm.local"
        company.address = "100 Solar Boulevard, Clean Energy Park"
        company.tax_id = ""
        company.save()

        self.stdout.write(self.style.SUCCESS(
            f"Successfully removed {b_count} bookings, {c_count} customers, and {t_count} team members. System is clean and ready for real data!"
        ))
