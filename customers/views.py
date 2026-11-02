import re
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Customer, CustomerAttachment
from .forms import CustomerForm, CustomerAttachmentForm

logger = logging.getLogger(__name__)


class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'customers/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 10

    def get_queryset(self):
        qs = Customer.objects.annotate(
            booking_count=Count('bookings'),
            total_spent_val=Sum('bookings__booking_amount'),
            pending_balance=Sum('bookings__balance_amount', filter=Q(bookings__is_cancelled=False))
        )

        query = self.request.GET.get('q', '').strip()
        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(customer_id__icontains=query) |
                Q(consumer_number__icontains=query) |
                Q(phone__icontains=query) |
                Q(email__icontains=query) |
                Q(city__icontains=query) |
                Q(company_name__icontains=query)
            )

        city = self.request.GET.get('city')
        if city:
            qs = qs.filter(city__iexact=city)

        cust_type = self.request.GET.get('customer_type')
        if cust_type:
            qs = qs.filter(customer_type=cust_type)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        view_mode = self.request.GET.get('view', '').strip() or self.request.GET.get('tab', '').strip()
        payment_status = self.request.GET.get('payment_status')
        if view_mode == 'credit' or payment_status == 'pending':
            # Strictly filter only customers who have an actual pending due > 0 (zeros excluded)
            qs = qs.filter(pending_balance__gt=0)
        elif payment_status == 'settled':
            qs = qs.filter(Q(pending_balance=0) | Q(pending_balance__isnull=True))

        sort_by = self.request.GET.get('sort', '-created_at')
        valid_sorts = ['name', '-name', 'created_at', '-created_at', 'city', '-city', 'customer_id', '-customer_id']
        if sort_by in valid_sorts:
            qs = qs.order_by(sort_by)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        raw_cities = Customer.objects.exclude(city='').exclude(city__isnull=True).values_list('city', flat=True).distinct()
        cities_dict = {}
        for c in raw_cities:
            if c and c.strip():
                clean_c = c.strip()
                c_key = clean_c.lower()
                if c_key not in cities_dict:
                    cities_dict[c_key] = clean_c.title()
        context['cities'] = sorted(cities_dict.values())
        context['current_query'] = self.request.GET.get('q', '')
        context['current_city'] = self.request.GET.get('city', '')
        context['current_type'] = self.request.GET.get('customer_type', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_sort'] = self.request.GET.get('sort', '-created_at')
        context['current_payment_status'] = self.request.GET.get('payment_status', '')
        view_mode = self.request.GET.get('view', '').strip() or self.request.GET.get('tab', '').strip()
        is_credit_view = (view_mode == 'credit' or self.request.GET.get('payment_status') == 'pending')
        context['is_credit_view'] = is_credit_view
        context['current_view'] = 'credit' if is_credit_view else 'all' 

        # Pending payments summary
        pending_agg = Customer.objects.annotate(
            pb=Sum('bookings__balance_amount', filter=Q(bookings__is_cancelled=False))
        ).filter(pb__gt=0).aggregate(cnt=Count('id'), tot=Sum('pb'))
        context['pending_payments_count'] = pending_agg['cnt'] or 0
        context['total_pending_amount'] = pending_agg['tot'] or 0
        
        # Summary counts
        context['total_count'] = Customer.objects.count()
        context['active_count'] = Customer.objects.filter(status='ACTIVE').count()
        context['business_count'] = Customer.objects.filter(customer_type='BUSINESS').count()
        context['individual_count'] = Customer.objects.filter(customer_type='INDIVIDUAL').count()
        return context


class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'customers/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        bookings = customer.bookings.all().order_by('-booking_date')
        context['bookings'] = bookings
        context['total_value'] = bookings.filter(is_cancelled=False).aggregate(s=Sum('booking_amount'))['s'] or 0
        context['total_advance'] = bookings.filter(is_cancelled=False).aggregate(s=Sum('advance_payment'))['s'] or 0
        context['total_balance'] = bookings.filter(is_cancelled=False).aggregate(s=Sum('balance_amount'))['s'] or 0
        context['attachments'] = customer.attachments.all()
        context['attachment_form'] = CustomerAttachmentForm()
        return context


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'

    def form_valid(self, form):
        self.object = form.save()

        # Process any uploaded documents with title
        doc_files = self.request.FILES.getlist('document_files')
        doc_titles = self.request.POST.getlist('document_titles')
        doc_categories = self.request.POST.getlist('document_categories')

        if not doc_files and self.request.FILES.get('document_file'):
            doc_files = [self.request.FILES.get('document_file')]
            doc_titles = [self.request.POST.get('document_title') or 'Customer Document']
            doc_categories = [self.request.POST.get('document_category') or 'OTHER']

        for i, file_obj in enumerate(doc_files):
            if file_obj:
                title = doc_titles[i].strip() if i < len(doc_titles) and doc_titles[i].strip() else file_obj.name
                category = doc_categories[i] if i < len(doc_categories) and doc_categories[i] else 'OTHER'
                CustomerAttachment.objects.create(
                    customer=self.object,
                    title=title,
                    category=category,
                    file=file_obj,
                    file_size=file_obj.size if hasattr(file_obj, 'size') else 0,
                    uploaded_by=self.request.user if self.request.user.is_authenticated else None
                )
        
        # Check if requested to save as draft
        if 'save_as_draft' in self.request.POST:
            self.object.status = 'ARCHIVED'
            self.object.save(update_fields=['status'])
            messages.info(self.request, f"Customer '{self.object.name}' ({self.object.customer_id}) saved as draft.")
            return redirect(self.object.get_absolute_url())

        # Check if requested to book solar directly
        if 'save_and_book' in self.request.POST:
            messages.success(self.request, f"Customer '{self.object.name}' ({self.object.customer_id}) created! Proceeding to solar booking.")
            return redirect(f"{reverse('bookings:create')}?customer_id={self.object.pk}")
            
        messages.success(self.request, f"Customer '{self.object.name}' ({self.object.customer_id}) created successfully!")
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        logger.warning("CustomerCreateView validation failed: %s", form.errors.as_json())
        messages.error(self.request, "Please review and correct the highlighted errors below before saving.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Customer'
        context['btn_text'] = 'Save Customer'
        return context


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'

    def form_valid(self, form):
        self.object = form.save()
        if 'save_as_draft' in self.request.POST:
            self.object.status = 'ARCHIVED'
            self.object.save(update_fields=['status'])
            messages.info(self.request, f"Customer '{self.object.name}' saved as draft.")
            return redirect(self.object.get_absolute_url())

        if 'save_and_book' in self.request.POST:
            messages.success(self.request, f"Customer '{self.object.name}' updated! Proceeding to solar booking.")
            return redirect(f"{reverse('bookings:create')}?customer_id={self.object.pk}")

        messages.success(self.request, f"Customer '{self.object.name}' updated successfully.")
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        logger.warning("CustomerUpdateView validation failed for customer %s: %s", self.object.pk, form.errors.as_json())
        messages.error(self.request, "Please review and correct the highlighted errors below before saving.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Edit Customer: {self.object.name}"
        context['btn_text'] = 'Update Customer'
        context['is_edit'] = True
        return context


class CustomerArchiveToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        if customer.status == 'ACTIVE':
            customer.status = 'ARCHIVED'
            messages.info(request, f"Customer '{customer.name}' has been archived.")
        else:
            customer.status = 'ACTIVE'
            messages.success(request, f"Customer '{customer.name}' has been unarchived.")
        customer.save()
        return redirect('customers:detail', pk=customer.pk)


class CustomerQuickCreateAjaxView(LoginRequiredMixin, View):
    """API endpoint to create a customer via modal inside the booking form"""
    def post(self, request):
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        city = request.POST.get('city', '').strip()
        street = request.POST.get('street', '').strip()
        house_building = request.POST.get('house_building', '').strip()
        state = request.POST.get('state', '').strip() or 'Kerala'
        postal_code = request.POST.get('postal_code', '').strip() or ''
        customer_type = request.POST.get('customer_type', 'INDIVIDUAL')
        consumer_number = request.POST.get('consumer_number', '').strip()

        phone = re.sub(r'\D', '', phone)
        if not name or not phone or not city:
            return JsonResponse({'status': 'error', 'message': 'Name, Phone number, and City are required.'}, status=400)

        if len(phone) != 10:
            return JsonResponse({'status': 'error', 'message': 'Mobile phone number must be exactly 10 digits.'}, status=400)

        # Check existing phone
        existing = Customer.objects.filter(phone=phone).first()
        if existing:
            logger.warning("Quick customer duplicate phone attempt: %s (matches %s)", phone, existing.name)
            return JsonResponse({'status': 'error', 'message': f"Customer with phone {phone} already exists: {existing.name} ({existing.customer_id})."}, status=400)

        try:
            customer = Customer.objects.create(
                name=name,
                phone=phone,
                email=email or None,
                customer_type=customer_type,
                consumer_number=consumer_number or None,
                house_building=house_building or "",
                street=street or "",
                city=city,
                state=state,
                postal_code=postal_code,
                lead_source=request.POST.get('lead_source', '').strip() or 'Website Inquiry'
            )
            logger.info("Quick customer created successfully: %s (%s)", customer.name, customer.customer_id)

            return JsonResponse({
                'status': 'success',
                'customer': {
                    'id': customer.pk,
                    'customer_id': customer.customer_id,
                    'name': customer.name,
                    'phone': customer.phone,
                    'email': customer.email or '',
                    'address': customer.full_address,
                    'city': customer.city,
                    'consumer_number': customer.consumer_number or '',
                    'house_building': customer.house_building or '',
                    'street': customer.street or '',
                    'state': customer.state or 'Kerala',
                    'postal_code': customer.postal_code or '',
                    'coordinates': customer.coordinates or '',
                }
            })
        except Exception as e:
            logger.exception("Unexpected error in CustomerQuickCreateAjaxView: %s", e)
            return JsonResponse({
                'status': 'error',
                'message': f"An unexpected error occurred while saving the customer: {str(e)}"
            }, status=500)


class CustomerAttachmentUploadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        form = CustomerAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.customer = customer
            if request.user.is_authenticated:
                attachment.uploaded_by = request.user
            attachment.save()
            messages.success(request, f"Document '{attachment.title}' uploaded successfully.")
        else:
            logger.warning("Customer attachment upload validation error for customer %s: %s", pk, form.errors.as_json())
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{err}")
        return redirect('customers:detail', pk=pk)


class CustomerAttachmentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, attachment_pk):
        customer = get_object_or_404(Customer, pk=pk)
        attachment = get_object_or_404(CustomerAttachment, pk=attachment_pk, customer=customer)
        title = attachment.title
        try:
            attachment.file.delete(save=False)
        except Exception as e:
            logger.warning("Could not delete attachment file on disk (%s): %s", attachment.file.name, e)
        attachment.delete()
        messages.info(request, f"Customer document '{title}' removed.")
        return redirect('customers:detail', pk=pk)

