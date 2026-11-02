import os
import uuid
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Customer(models.Model):
    CUSTOMER_TYPE_CHOICES = [
        ('INDIVIDUAL', 'Individual / Residential'),
        ('BUSINESS', 'Commercial / Business'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('ARCHIVED', 'Archived'),
    ]

    LEAD_SOURCE_CHOICES = [
        ('Website Inquiry', 'Website Inquiry'),
        ('Customer Referral', 'Customer Referral'),
        ('Social Media Campaign', 'Social Media Campaign'),
        ('Field Sales Agent', 'Field Sales Agent'),
        ('Direct Phone Call', 'Direct Phone Call'),
        ('Other / Walk-in', 'Other / Walk-in'),
        # Backward compatibility for legacy codes
        ('WEBSITE', 'Website Inquiry'),
        ('REFERRAL', 'Customer Referral'),
        ('SOCIAL_MEDIA', 'Social Media Campaign'),
        ('FIELD_AGENT', 'Field Sales Agent'),
        ('DIRECT_CALL', 'Direct Phone Call'),
        ('OTHER', 'Other / Walk-in'),
    ]

    @classmethod
    def get_lead_source_choices(cls):
        """Dynamic lead source choices derived from CatalogItem."""
        try:
            from core.models import CatalogItem
            sources = CatalogItem.get_active_choices(CatalogItem.CATEGORY_LEAD_SOURCE)
            if sources:
                return [(s, s) for s in sources]
        except Exception:
            pass
        return [
            ('Website Inquiry', 'Website Inquiry'),
            ('Customer Referral', 'Customer Referral'),
            ('Social Media Campaign', 'Social Media Campaign'),
            ('Field Sales Agent', 'Field Sales Agent'),
            ('Direct Phone Call', 'Direct Phone Call'),
            ('Other / Walk-in', 'Other / Walk-in'),
        ]

    def get_lead_source_display(self):
        code_map = {
            'WEBSITE': 'Website Inquiry',
            'REFERRAL': 'Customer Referral',
            'SOCIAL_MEDIA': 'Social Media Campaign',
            'FIELD_AGENT': 'Field Sales Agent',
            'DIRECT_CALL': 'Direct Phone Call',
            'OTHER': 'Other / Walk-in',
        }
        if self.lead_source in code_map:
            return code_map[self.lead_source]
        return self.lead_source or 'Website Inquiry'

    customer_id = models.CharField(max_length=30, unique=True, db_index=True, editable=False)
    name = models.CharField(max_length=150, help_text="Full Name or Primary Contact")
    phone = models.CharField(max_length=20, db_index=True)
    alt_phone = models.CharField(max_length=20, blank=True, null=True, help_text="Alternative phone number")
    email = models.EmailField(blank=True, null=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='INDIVIDUAL')

    # Address Details
    house_building = models.CharField(max_length=150, blank=True, default='', help_text="House / Building Name or No.")
    street = models.CharField(max_length=200, blank=True, default='', help_text="Street / Area / Locality")
    city = models.CharField(max_length=100, db_index=True, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    coordinates = models.CharField(max_length=100, blank=True, null=True, help_text="GPS coordinates or Google Maps link")

    # Electricity & Consumer Connection
    consumer_number = models.CharField(max_length=50, blank=True, null=True, db_index=True, help_text="Electricity Board / DISCOM Consumer Number (e.g. 13-digit KSEB Consumer ID)")

    # Business Information
    company_name = models.CharField(max_length=150, blank=True, null=True)
    tax_id = models.CharField(max_length=50, blank=True, null=True, help_text="GST / Tax Identification Number")
    notes = models.TextField(blank=True, null=True, help_text="Internal notes or customer preferences")
    lead_source = models.CharField(max_length=100, choices=LEAD_SOURCE_CHOICES, default='Website Inquiry', blank=True)
    customer_category = models.CharField(max_length=50, default='Residential', blank=True)
    whatsapp_number = models.CharField(max_length=25, blank=True, null=True)
    website = models.URLField(max_length=200, blank=True, null=True)
    preferred_comm = models.CharField(max_length=30, default='Phone', blank=True)

    # Status & Audit
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['phone']),
            models.Index(fields=['city']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.customer_id})"

    def save(self, *args, **kwargs):
        if not self.customer_id:
            # Generate auto customer ID like CUST-1001, CUST-1002, etc.
            last_cust = Customer.objects.order_by('-id').first()
            if last_cust and last_cust.id:
                next_num = last_cust.id + 1001
            else:
                next_num = 1001
            self.customer_id = f"CUST-{next_num:04d}"
        super().save(*args, **kwargs)

    @property
    def full_address(self):
        parts = [self.house_building, self.street, self.city, self.state, self.postal_code]
        return ", ".join([p for p in parts if p])

    @property
    def total_bookings(self):
        return self.bookings.count()

    @property
    def active_bookings(self):
        return self.bookings.filter(is_cancelled=False).exclude(stage='COMPLETED').count()

    @property
    def completed_bookings(self):
        return self.bookings.filter(stage='COMPLETED', is_cancelled=False).count()

    @property
    def total_spent(self):
        return self.bookings.filter(is_cancelled=False).aggregate(models.Sum('booking_amount'))['booking_amount__sum'] or 0

    def get_absolute_url(self):
        return reverse('customers:detail', kwargs={'pk': self.pk})

    @property
    def whatsapp_phone(self):
        """Clean phone string formatted for WhatsApp click-to-chat"""
        import re
        digits = re.sub(r'\D', '', self.phone or '')
        if len(digits) == 10:
            return f"91{digits}"
        return digits


def get_customer_folder_name(customer):
    """
    Generate a clean, filesystem-safe folder name for a customer.
    Format: <Clean_Customer_Name>_<Customer_ID>
    e.g. 'ANAS_BCA_CUST-1001' or 'sujith_CUST-1004'
    """
    if not customer:
        return 'unassigned_clients'
    import re
    raw_name = customer.name or 'client'
    clean_name = re.sub(r'[^\w\s-]', '', raw_name).strip()
    clean_name = re.sub(r'[-\s]+', '_', clean_name)
    if not clean_name:
        clean_name = 'client'
    cid = getattr(customer, 'customer_id', None) or f"id_{customer.id}"
    return f"{clean_name}_{cid}"


def customer_attachment_upload_path(instance, filename):
    """
    Store customer documents in a dedicated client folder:
    media/clients/<Customer_Name>_<Customer_ID>/customer_docs/<filename>
    """
    customer = getattr(instance, 'customer', None)
    folder = get_customer_folder_name(customer)
    clean_filename = os.path.basename(filename)
    return f"clients/{folder}/customer_docs/{clean_filename}"


class CustomerAttachment(models.Model):
    CATEGORY_CHOICES = [
        ('ELECTRICITY_BILL', 'Customer Electricity Bill / Tariff Sanction'),
        ('KYC_ID', 'ID Proof / Aadhaar / Passport / Tax ID'),
        ('PROPERTY_TAX', 'Property Tax Receipt / Ownership Document'),
        ('SITE_MAP', 'Site Layout / Building Plan'),
        ('OTHER', 'Other Customer Document'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='attachments')
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default='OTHER', db_index=True)
    title = models.CharField(max_length=200, help_text="Document title or description")
    file = models.FileField(upload_to=customer_attachment_upload_path)
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='uploaded_customer_attachments')
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} - {self.customer.name}"

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

