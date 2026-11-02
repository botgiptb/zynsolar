from datetime import datetime, timedelta
import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View, TemplateView
from django.urls import reverse
from django.contrib import messages
from django.db.models import Case, When, Value, IntegerField, Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import SolarBooking, BookingAuditLog, BookingAttachment, PipelineStage, BookingPayment, BookingNote, Task, TaskChecklistItem, BookingCustomField
from .forms import (
    SolarBookingForm, StageAdvanceForm, CancelBookingForm, BookingAttachmentForm,
    BookingPaymentForm, BookingNoteForm, UpdateBookingInternalNotesForm, BookingCustomFieldForm
)
from customers.models import Customer
from core.models import CatalogItem

logger = logging.getLogger(__name__)


class BookingListView(LoginRequiredMixin, ListView):
    model = SolarBooking
    template_name = 'bookings/booking_list.html'
    context_object_name = 'bookings'

    def get_queryset(self):
        qs = SolarBooking.objects.select_related('customer').all()

        query = self.request.GET.get('q', '').strip()
        if query:
            qs = qs.filter(
                Q(booking_ref__icontains=query) |
                Q(customer__name__icontains=query) |
                Q(customer__phone__icontains=query) |
                Q(customer__customer_id__icontains=query) |
                Q(consumer_number__icontains=query) |
                Q(customer__consumer_number__icontains=query) |
                Q(assigned_salesperson__icontains=query) |
                Q(assigned_team_driver__icontains=query) |
                Q(panel_type__icontains=query)
            )

        stage = self.request.GET.get('stage')
        if stage == 'CANCELLED':
            qs = qs.filter(is_cancelled=True)
        elif stage == 'ON_HOLD':
            qs = qs.filter(is_on_hold=True, is_cancelled=False)
        elif stage in [SolarBooking.STAGE_NEW, SolarBooking.STAGE_SURVEY, SolarBooking.STAGE_INSTALLATION, SolarBooking.STAGE_COMPLETED]:
            qs = qs.filter(stage=stage, is_cancelled=False)
        elif stage == 'ACTIVE_PROGRESS':
            qs = qs.filter(stage__in=[SolarBooking.STAGE_SURVEY, SolarBooking.STAGE_INSTALLATION], is_cancelled=False)

        salesperson = self.request.GET.get('salesperson')
        if salesperson:
            qs = qs.filter(assigned_salesperson=salesperson)

        date_from = self.request.GET.get('date_from')
        if date_from:
            qs = qs.filter(booking_date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            qs = qs.filter(booking_date__lte=date_to)

        payment_status = self.request.GET.get('payment_status')
        if payment_status == 'settled':
            qs = qs.filter(balance_amount__lte=Decimal('0.00'))
        elif payment_status == 'pending':
            qs = qs.filter(balance_amount__gt=Decimal('0.00'))
        elif payment_status == 'overdue':
            cutoff = timezone.now().date() - timezone.timedelta(days=30)
            qs = qs.filter(
                Q(balance_amount__gt=Decimal('0.00')) &
                (Q(stage=SolarBooking.STAGE_COMPLETED) | Q(booking_date__lte=cutoff))
            )

        qs = qs.annotate(
            priority_weight=Case(
                When(priority='URGENT', then=Value(4)),
                When(priority='HIGH', then=Value(3)),
                When(priority='NORMAL', then=Value(2)),
                When(priority='LOW', then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            )
        )

        sort_by = self.request.GET.get('sort', 'kanban_order')
        valid_sorts = [
            'kanban_order',
            'priority', '-priority',
            'booking_date', '-booking_date',
            'booking_ref', '-booking_ref',
            'booking_amount', '-booking_amount',
            'system_capacity_kw', '-system_capacity_kw',
            'customer__name', '-customer__name',
            'expected_completion_date', '-expected_completion_date'
        ]

        if sort_by == '-priority':
            qs = qs.order_by('-priority_weight', 'kanban_order', '-booking_date', '-id')
        elif sort_by == 'priority':
            qs = qs.order_by('priority_weight', 'kanban_order', '-booking_date', '-id')
        elif sort_by == 'kanban_order':
            qs = qs.order_by('kanban_order', '-priority_weight', '-id')
        elif sort_by in valid_sorts:
            qs = qs.order_by(sort_by, '-id')
        else:
            qs = qs.order_by('kanban_order', '-id')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_qs = SolarBooking.objects.all()

        context['total_bookings'] = all_qs.count()
        context['count_new'] = all_qs.filter(stage=SolarBooking.STAGE_NEW, is_cancelled=False).count()
        context['count_survey'] = all_qs.filter(stage=SolarBooking.STAGE_SURVEY, is_cancelled=False).count()
        context['count_installation'] = all_qs.filter(stage=SolarBooking.STAGE_INSTALLATION, is_cancelled=False).count()
        context['count_in_progress'] = all_qs.filter(stage__in=[SolarBooking.STAGE_SURVEY, SolarBooking.STAGE_INSTALLATION], is_cancelled=False).count()
        context['count_completed'] = all_qs.filter(stage=SolarBooking.STAGE_COMPLETED, is_cancelled=False).count()
        context['count_cancelled'] = all_qs.filter(is_cancelled=True).count()
        context['count_on_hold'] = all_qs.filter(is_on_hold=True, is_cancelled=False).count()

        # Salespersons for filter dropdown
        context['salespersons'] = SolarBooking.objects.values_list('assigned_salesperson', flat=True).distinct().order_by('assigned_salesperson')

        # Current filters
        context['current_query'] = self.request.GET.get('q', '')
        context['current_stage'] = self.request.GET.get('stage', '')
        context['current_salesperson'] = self.request.GET.get('salesperson', '')
        context['current_date_from'] = self.request.GET.get('date_from', '')
        context['current_date_to'] = self.request.GET.get('date_to', '')
        context['current_sort'] = self.request.GET.get('sort', '-booking_date')
        context['current_payment_status'] = self.request.GET.get('payment_status', '')

        # Dynamic Pipeline Stages
        active_stages = list(PipelineStage.get_active_stages())
        stage_configs = []
        for idx, st in enumerate(active_stages):
            next_lbl = f"Advance to {active_stages[idx + 1].name}" if idx + 1 < len(active_stages) else None
            stage_configs.append({
                'key': st.code,
                'title': st.name,
                'short_title': st.name,
                'icon': st.icon,
                'color': st.color,
                'border_color': st.border_color,
                'bg_header': st.bg_header,
                'header_text': st.header_text,
                'next_label': next_lbl,
            })
        context['pipeline_stages'] = active_stages

        # Use current filtered queryset
        filtered_qs = list(self.get_queryset())
        current_stage = context['current_stage']

        pipeline_columns = []
        prev_col = None
        for cfg in stage_configs:
            if not current_stage or current_stage == cfg['key']:
                stage_bookings = [b for b in filtered_qs if b.stage == cfg['key'] and not b.is_cancelled and not b.is_on_hold]
                total_kw = sum((b.system_capacity_kw or Decimal('0')) for b in stage_bookings)
                total_amount = sum((b.booking_amount or Decimal('0')) for b in stage_bookings)
                col_item = {
                    **cfg,
                    'bookings': stage_bookings,
                    'count': len(stage_bookings),
                    'total_kw': total_kw,
                    'total_amount': total_amount,
                    'prev_key': prev_col['key'] if prev_col else None,
                    'prev_title': prev_col['title'] if prev_col else None,
                }
                pipeline_columns.append(col_item)
                prev_col = col_item

        cancelled_bookings = [b for b in filtered_qs if b.is_cancelled]
        cancelled_column = {
            'key': 'CANCELLED',
            'title': 'Cancelled Orders',
            'short_title': 'Cancelled',
            'icon': 'bi-x-circle',
            'color': '#dc2626',
            'border_color': '#fecaca',
            'bg_header': '#fef2f2',
            'header_text': '#b91c1c',
            'bookings': cancelled_bookings,
            'count': len(cancelled_bookings),
            'total_kw': sum((b.system_capacity_kw or Decimal('0')) for b in cancelled_bookings),
            'total_amount': sum((b.booking_amount or Decimal('0')) for b in cancelled_bookings),
            'next_label': None,
        }
        context['cancelled_column'] = cancelled_column

        hold_bookings = [b for b in filtered_qs if b.is_on_hold and not b.is_cancelled]
        hold_column = {
            'key': 'ON_HOLD',
            'title': 'On Hold',
            'short_title': 'On Hold',
            'icon': 'bi-pause-circle',
            'color': '#d97706',
            'border_color': '#fde68a',
            'bg_header': '#fffbeb',
            'header_text': '#92400e',
            'bookings': hold_bookings,
            'count': len(hold_bookings),
            'total_kw': sum((b.system_capacity_kw or Decimal('0')) for b in hold_bookings),
            'total_amount': sum((b.booking_amount or Decimal('0')) for b in hold_bookings),
            'next_label': None,
            'drop_enabled': False,
        }
        context['hold_column'] = hold_column

        if current_stage == 'CANCELLED':
            pipeline_columns.append(cancelled_column)
        elif current_stage == 'ON_HOLD':
            if not any(col.get('key') in ['ON_HOLD', 'ON_HOLD_CANCELLED'] for col in pipeline_columns):
                pipeline_columns.append(hold_column)
        elif not current_stage:
            if not any(col.get('key') in ['ON_HOLD', 'ON_HOLD_CANCELLED'] for col in pipeline_columns):
                pipeline_columns.append(hold_column)

        context['pipeline_columns'] = pipeline_columns
        return context


class BookingDetailView(LoginRequiredMixin, DetailView):
    model = SolarBooking
    template_name = 'bookings/booking_detail.html'
    context_object_name = 'booking'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        booking = self.get_object()
        # The board and the order page must read from the same pipeline
        # configuration.  The order page used to contain a separate, hard-coded
        # four-stage display, so renamed/custom stages could appear differently
        # in the two places.
        active_stages = list(PipelineStage.get_active_stages())
        # The sequential milestone tracker displays progressive stages,
        # excluding exception/hold states like 'ON_HOLD_CANCELLED'.
        workflow_stages_list = [s for s in active_stages if s.code not in ('ON_HOLD_CANCELLED',)]
        workflow_index = next(
            (index for index, stage in enumerate(workflow_stages_list) if stage.code == booking.stage),
            -1 if booking.stage == 'ON_HOLD_CANCELLED' else 0,
        )
        milestone_dates = {
            SolarBooking.STAGE_NEW: booking.stage_new_datetime,
            SolarBooking.STAGE_SURVEY: booking.stage_survey_datetime,
            SolarBooking.STAGE_INSTALLATION: booking.stage_installation_datetime,
            SolarBooking.STAGE_COMPLETED: booking.stage_completed_datetime,
        }
        context['workflow_stages'] = [
            {
                'stage': stage,
                'is_current': index == workflow_index,
                'is_completed': workflow_index != -1 and index < workflow_index,
                'timestamp': milestone_dates.get(stage.code),
            }
            for index, stage in enumerate(workflow_stages_list)
        ]
        context['workflow_progress'] = (
            int((workflow_index / (len(workflow_stages_list) - 1)) * 100)
            if len(workflow_stages_list) > 1 and workflow_index > 0 else 0
        )
        context['pipeline_stages'] = active_stages

        # Calculate next recommended milestone and smart-sorted options
        next_stage = workflow_stages_list[workflow_index + 1] if 0 <= workflow_index < len(workflow_stages_list) - 1 else None
        current_index = next(
            (index for index, stage in enumerate(active_stages) if stage.code == booking.stage),
            0,
        )

        status_options = []
        forward_stages = []
        backward_stages = []
        for idx, st in enumerate(active_stages):
            if st.code == booking.stage:
                continue
            is_next = (next_stage and st.code == next_stage.code)
            is_forward = (idx > current_index)
            st_dict = {
                'code': st.code,
                'name': st.name,
                'order': st.order,
                'icon': st.icon,
                'color': st.color,
                'border_color': st.border_color,
                'bg_header': st.bg_header,
                'header_text': st.header_text,
                'is_terminal': st.is_terminal,
                'is_next': is_next,
                'is_forward': is_forward,
            }
            if is_next:
                status_options.insert(0, st_dict)
            elif is_forward:
                forward_stages.append(st_dict)
            else:
                backward_stages.append(st_dict)

        all_options = status_options + forward_stages + backward_stages
        context['status_options'] = all_options
        context['default_target_stage'] = all_options[0] if all_options else None
        context['audit_logs'] = booking.audit_logs.all().order_by('-timestamp')
        context['advance_form'] = StageAdvanceForm()
        context['cancel_form'] = CancelBookingForm()
        context['attachments'] = booking.attachments.all()
        context['attachment_form'] = BookingAttachmentForm()
        context['payments'] = booking.payments.all().order_by('-payment_date', '-id')
        context['payment_form'] = BookingPaymentForm(initial={
            'payment_date': timezone.now().date(),
            'amount': booking.balance_amount if booking.balance_amount > Decimal('0.00') else None,
            'milestone': 'FINAL_COMMISSIONING' if booking.stage == SolarBooking.STAGE_COMPLETED else (
                'INSTALLATION_PROGRESS' if booking.stage == SolarBooking.STAGE_INSTALLATION else (
                    'FEASIBILITY_APPROVAL' if booking.stage == SolarBooking.STAGE_SURVEY else 'AD_HOC'
                )
            )
        })
        context['notes_list'] = booking.notes_list.all().select_related('author')
        context['note_form'] = BookingNoteForm()
        context['primary_notes_form'] = UpdateBookingInternalNotesForm(instance=booking)
        context['booking_tasks'] = booking.tasks.select_related('assigned_to', 'completed_by').prefetch_related('checklist_items').all()
        context['custom_fields'] = booking.custom_fields.all()
        context['custom_field_form'] = BookingCustomFieldForm()
        return context


class BookingCreateView(LoginRequiredMixin, CreateView):
    model = SolarBooking
    form_class = SolarBookingForm
    template_name = 'bookings/booking_form.html'

    def get_initial(self):
        initial = super().get_initial()
        customer_id = self.request.GET.get('customer_id')
        if customer_id:
            try:
                customer = Customer.objects.get(pk=customer_id)
                initial['customer'] = customer
            except Customer.DoesNotExist:
                pass
        stage_param = self.request.GET.get('stage')
        if stage_param:
            initial['stage'] = stage_param
        return initial

    def form_valid(self, form):
        self.object = form.save(commit=False)
        if self.request.user.is_authenticated:
            self.object.created_by = self.request.user
        self.object.save()

        # Sync consumer_number to customer record if missing
        if self.object.consumer_number and self.object.customer and not self.object.customer.consumer_number:
            self.object.customer.consumer_number = self.object.consumer_number
            self.object.customer.save(update_fields=['consumer_number'])

        # Process any uploaded documents with title
        doc_files = self.request.FILES.getlist('document_files')
        doc_titles = self.request.POST.getlist('document_titles')
        doc_categories = self.request.POST.getlist('document_categories')

        if not doc_files and self.request.FILES.get('document_file'):
            doc_files = [self.request.FILES.get('document_file')]
            doc_titles = [self.request.POST.get('document_title') or 'Project Document']
            doc_categories = [self.request.POST.get('document_category') or 'OTHER']

        for i, file_obj in enumerate(doc_files):
            if file_obj:
                title = doc_titles[i].strip() if i < len(doc_titles) and doc_titles[i].strip() else file_obj.name
                category = doc_categories[i] if i < len(doc_categories) and doc_categories[i] else 'OTHER'
                BookingAttachment.objects.create(
                    booking=self.object,
                    title=title,
                    category=category,
                    file=file_obj,
                    file_size=file_obj.size if hasattr(file_obj, 'size') else 0,
                    uploaded_by=self.request.user if self.request.user.is_authenticated else None
                )

        # Set milestone timestamps
        if not self.object.stage_new_at:
            self.object.stage_new_at = self.object.created_at or timezone.now()
        if self.object.stage in [SolarBooking.STAGE_SURVEY, SolarBooking.STAGE_INSTALLATION, SolarBooking.STAGE_COMPLETED]:
            self.object.stage_survey_at = self.object.created_at or timezone.now()
        if self.object.stage in [SolarBooking.STAGE_INSTALLATION, SolarBooking.STAGE_COMPLETED]:
            self.object.stage_installation_at = self.object.created_at or timezone.now()
        if self.object.stage == SolarBooking.STAGE_COMPLETED:
            self.object.stage_completed_at = self.object.created_at or timezone.now()
        self.object.save()

        # Create initial advance payment receipt if advance_payment was provided
        if self.object.advance_payment and self.object.advance_payment > Decimal('0.00'):
            BookingPayment.objects.create(
                booking=self.object,
                amount=self.object.advance_payment,
                payment_date=self.object.booking_date,
                payment_method='UPI',
                milestone='BOOKING_ADVANCE',
                notes='Initial booking advance payment deposit.',
                recorded_by=self.request.user if self.request.user.is_authenticated else None
            )

        # Create audit entry
        user_name = self.request.user.get_full_name() or self.request.user.username if self.request.user.is_authenticated else "System Staff"
        BookingAuditLog.objects.create(
            booking=self.object,
            action='CREATED',
            from_stage=None,
            to_stage=self.object.stage,
            user=self.request.user if self.request.user.is_authenticated else None,
            user_name=user_name,
            notes=f"Initial booking created for {self.object.system_capacity_kw} kW system. Advance received: ₹{self.object.advance_payment:,.2f}"
        )

        messages.success(self.request, f"Solar Booking {self.object.booking_ref} created successfully!")
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        logger.warning("BookingCreateView validation failed: %s", form.errors.as_json())
        messages.error(self.request, "Please review and correct the highlighted errors below before saving.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Solar Booking'
        context['btn_text'] = 'Create Booking'
        context['all_customers'] = Customer.objects.filter(status='ACTIVE').order_by('name')
        context['accessory_shelf_items'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_ACCESSORY)
        context['catalog_panel_brands'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_PANEL_BRAND)
        context['catalog_panel_techs'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_PANEL_TECH)
        context['catalog_inverters'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_INVERTER)
        context['catalog_mountings'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_MOUNTING)
        context['catalog_lead_sources'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_LEAD_SOURCE)
        return context


class BookingUpdateView(LoginRequiredMixin, UpdateView):
    model = SolarBooking
    form_class = SolarBookingForm
    template_name = 'bookings/booking_form.html'

    def form_valid(self, form):
        self.object = form.save()

        # Sync consumer_number to customer record if missing
        if self.object.consumer_number and self.object.customer and not self.object.customer.consumer_number:
            self.object.customer.consumer_number = self.object.consumer_number
            self.object.customer.save(update_fields=['consumer_number'])

        # Process any uploaded documents with title
        doc_files = self.request.FILES.getlist('document_files')
        doc_titles = self.request.POST.getlist('document_titles')
        doc_categories = self.request.POST.getlist('document_categories')

        if not doc_files and self.request.FILES.get('document_file'):
            doc_files = [self.request.FILES.get('document_file')]
            doc_titles = [self.request.POST.get('document_title') or 'Project Document']
            doc_categories = [self.request.POST.get('document_category') or 'OTHER']

        for i, file_obj in enumerate(doc_files):
            if file_obj:
                title = doc_titles[i].strip() if i < len(doc_titles) and doc_titles[i].strip() else file_obj.name
                category = doc_categories[i] if i < len(doc_categories) and doc_categories[i] else 'OTHER'
                BookingAttachment.objects.create(
                    booking=self.object,
                    title=title,
                    category=category,
                    file=file_obj,
                    file_size=file_obj.size if hasattr(file_obj, 'size') else 0,
                    uploaded_by=self.request.user if self.request.user.is_authenticated else None
                )

        user_name = self.request.user.get_full_name() or self.request.user.username if self.request.user.is_authenticated else "Staff"
        BookingAuditLog.objects.create(
            booking=self.object,
            action='DETAILS_EDITED',
            from_stage=self.object.stage,
            to_stage=self.object.stage,
            user=self.request.user if self.request.user.is_authenticated else None,
            user_name=user_name,
            notes="Booking specifications & details updated."
        )
        messages.success(self.request, f"Booking {self.object.booking_ref} updated successfully.")
        return redirect(self.object.get_absolute_url())

    def form_invalid(self, form):
        logger.warning("BookingUpdateView validation failed for booking %s: %s", self.object.booking_ref, form.errors.as_json())
        messages.error(self.request, "Please review and correct the highlighted errors below before saving.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Edit Booking: {self.object.booking_ref}"
        context['btn_text'] = 'Update Booking'
        context['is_edit'] = True
        context['all_customers'] = Customer.objects.filter(status='ACTIVE').order_by('name')
        context['accessory_shelf_items'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_ACCESSORY)
        context['catalog_panel_brands'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_PANEL_BRAND)
        context['catalog_panel_techs'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_PANEL_TECH)
        context['catalog_inverters'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_INVERTER)
        context['catalog_mountings'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_MOUNTING)
        context['catalog_lead_sources'] = CatalogItem.get_active_choices(CatalogItem.CATEGORY_LEAD_SOURCE)
        return context


class BookingAdvanceStageView(LoginRequiredMixin, View):
    """Transition booking from Stage N to Stage N+1 with stage-specific updates"""
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)

        if booking.is_cancelled:
            logger.warning("Attempted to advance cancelled booking %s", booking.booking_ref)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': False, 'message': 'Cannot advance a cancelled booking. Reopen it first.'}, status=400)
            messages.error(request, "Cannot advance a cancelled booking. Reopen it first.")
            return redirect('bookings:detail', pk=pk)

        if booking.is_on_hold:
            messages.error(request, "This order is on hold. Resume it before changing the project status.")
            return redirect('bookings:detail', pk=pk)

        target_stage = request.POST.get('target_stage')
        valid_stages = list(PipelineStage.get_active_stages().values_list('code', flat=True))
        if not valid_stages:
            valid_stages = [SolarBooking.STAGE_NEW, SolarBooking.STAGE_SURVEY, SolarBooking.STAGE_INSTALLATION, SolarBooking.STAGE_COMPLETED]
        if target_stage not in valid_stages:
            logger.warning("Invalid target stage '%s' requested for booking %s", target_stage, booking.booking_ref)
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': False, 'message': f"Invalid target stage '{target_stage}'."}, status=400)
            messages.error(request, f"Invalid target stage '{target_stage}'.")
            return redirect('bookings:detail', pk=pk)

        notes = request.POST.get('notes', '').strip()
        user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"

        old_stage = booking.stage
        target_stage_obj = PipelineStage.objects.filter(code=target_stage).first()
        booking.stage = target_stage

        if target_stage == SolarBooking.STAGE_SURVEY:
            # Transition to Site Survey
            survey_date = request.POST.get('survey_scheduled_date')
            survey_time = request.POST.get('survey_time')
            survey_team = request.POST.get('survey_team_driver')
            if survey_date:
                booking.survey_scheduled_date = survey_date
                booking.survey_status = 'SCHEDULED'
                try:
                    if survey_time:
                        dt = timezone.make_aware(datetime.strptime(f"{survey_date} {survey_time}", "%Y-%m-%d %H:%M"))
                    else:
                        dt = timezone.now()
                    booking.stage_survey_at = dt
                except Exception:
                    booking.stage_survey_at = timezone.now()
            else:
                booking.stage_survey_at = timezone.now()

            if survey_team:
                booking.survey_team_driver = survey_team
            if notes:
                booking.survey_notes = (booking.survey_notes or "") + f"\n[{timezone.now().strftime('%Y-%m-%d')}] {notes}"

        elif target_stage == SolarBooking.STAGE_INSTALLATION:
            # Transition to Installation In Progress
            inst_date = request.POST.get('installation_scheduled_date')
            inst_time = request.POST.get('installation_time')
            inst_team = request.POST.get('installation_team')
            if inst_date:
                booking.installation_scheduled_date = inst_date
                try:
                    if inst_time:
                        dt = timezone.make_aware(datetime.strptime(f"{inst_date} {inst_time}", "%Y-%m-%d %H:%M"))
                    else:
                        dt = timezone.now()
                    booking.stage_installation_at = dt
                except Exception:
                    booking.stage_installation_at = timezone.now()
            else:
                booking.stage_installation_at = timezone.now()
            exp_comp_date = request.POST.get('expected_completion_date')
            measurements = request.POST.get('survey_roof_measurements')
            survey_status = request.POST.get('survey_status')

            if inst_team:
                booking.installation_team = inst_team
            if exp_comp_date:
                booking.expected_completion_date = exp_comp_date
            if measurements:
                booking.survey_roof_measurements = measurements
            if survey_status:
                booking.survey_status = survey_status
            if not booking.survey_status or booking.survey_status == 'PENDING':
                booking.survey_status = 'COMPLETED_FEASIBLE'
            if booking.installation_progress == 0:
                booking.installation_progress = 15
            if notes:
                booking.installation_notes = (booking.installation_notes or "") + f"\n[{timezone.now().strftime('%Y-%m-%d')}] {notes}"

        elif target_stage == SolarBooking.STAGE_COMPLETED or (target_stage_obj and target_stage_obj.is_terminal):
            # Transition to Completed
            booking.installation_progress = 100
            actual_date = request.POST.get('actual_completion_date') or timezone.now().date()
            comp_time = request.POST.get('completion_time')
            booking.actual_completion_date = actual_date
            try:
                if comp_time and actual_date:
                    dt = timezone.make_aware(datetime.strptime(f"{actual_date} {comp_time}", "%Y-%m-%d %H:%M"))
                else:
                    dt = timezone.now()
                booking.stage_completed_at = dt
            except Exception:
                booking.stage_completed_at = timezone.now()
            
            final_payment = request.POST.get('final_payment_received')
            if final_payment:
                try:
                    fp_dec = Decimal(final_payment)
                    booking.final_payment_received = fp_dec
                    if fp_dec > Decimal('0.00'):
                        BookingPayment.objects.create(
                            booking=booking,
                            amount=fp_dec,
                            payment_date=actual_date,
                            payment_method='NEFT_RTGS',
                            milestone='FINAL_COMMISSIONING',
                            notes='Final balance payment recorded upon project completion and handover sign-off.',
                            recorded_by=request.user if request.user.is_authenticated else None
                        )
                except Exception:
                    pass

            net_metering = request.POST.get('net_metering_status')
            if net_metering:
                booking.net_metering_status = net_metering
            
            if request.POST.get('warranty_certificate_issued') == 'on':
                booking.warranty_certificate_issued = True

            if notes:
                booking.completion_notes = (booking.completion_notes or "") + f"\n[{timezone.now().strftime('%Y-%m-%d')}] {notes}"
        else:
            if notes:
                booking.installation_notes = (booking.installation_notes or "") + f"\n[{timezone.now().strftime('%Y-%m-%d')}] [{booking.get_stage_display()}] {notes}"

        booking.save()

        BookingAuditLog.objects.create(
            booking=booking,
            action='STAGE_TRANSITION',
            from_stage=old_stage,
            to_stage=booking.stage,
            user=request.user if request.user.is_authenticated else None,
            user_name=user_name,
            notes=notes or f"Moved from {old_stage} to {booking.stage}"
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            from django.http import JsonResponse
            return JsonResponse({
                'success': True,
                'booking_id': booking.pk,
                'booking_ref': booking.booking_ref,
                'new_stage': booking.stage,
                'stage_display': booking.get_stage_display(),
                'message': f"Booking {booking.booking_ref} transitioned to {booking.get_stage_display()}!"
            })

        messages.success(request, f"Booking {booking.booking_ref} successfully transitioned to {booking.get_stage_display()}!")
        return redirect('bookings:detail', pk=pk)


class BookingCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        category = request.POST.get('cancellation_category', '').strip()
        reason = request.POST.get('cancellation_reason', '').strip()

        valid_categories = {choice[0] for choice in SolarBooking.CANCELLATION_CATEGORY_CHOICES}
        if category not in valid_categories or not reason:
            messages.error(request, "Select a cancellation category and enter a reason.")
            return redirect('bookings:detail', pk=pk)

        booking.is_cancelled = True
        booking.cancellation_category = category
        booking.cancellation_reason = reason
        booking.cancelled_at = timezone.now()
        if request.user.is_authenticated:
            booking.cancelled_by = request.user
        booking.save()

        user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"
        BookingAuditLog.objects.create(
            booking=booking,
            action='CANCELLED',
            from_stage=booking.stage,
            to_stage='CANCELLED',
            user=request.user if request.user.is_authenticated else None,
            user_name=user_name,
            notes=f"Booking cancelled — {booking.get_cancellation_category_display()}: {reason}"
        )

        messages.warning(request, f"Booking {booking.booking_ref} has been marked as CANCELLED.")
        return redirect('bookings:detail', pk=pk)


class BookingReopenView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        reopen_reason = request.POST.get('reopen_reason', '').strip()
        previous_stage = booking.get_stage_display()
        booking.is_cancelled = False
        # The audit log keeps the cancellation history.  Clearing these fields
        # makes the reopened order an active record again rather than a stale
        # cancelled record.
        booking.cancellation_category = ''
        booking.cancellation_reason = None
        booking.cancelled_at = None
        booking.cancelled_by = None
        booking.save()

        user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"
        BookingAuditLog.objects.create(
            booking=booking,
            action='REOPENED',
            from_stage='CANCELLED',
            to_stage=booking.stage,
            user=request.user if request.user.is_authenticated else None,
            user_name=user_name,
            notes=f"Booking reopened to {previous_stage}. {reopen_reason}".strip()
        )

        messages.success(request, f"Booking {booking.booking_ref} reopened successfully.")
        return redirect('bookings:detail', pk=pk)


class BookingHoldView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        reason = request.POST.get('hold_reason', '').strip()
        if booking.is_cancelled:
            messages.error(request, "A cancelled order must be reopened before it can be put on hold.")
            return redirect('bookings:detail', pk=pk)
        if not reason:
            messages.error(request, "A reason is required before putting an order on hold.")
            return redirect('bookings:detail', pk=pk)

        booking.is_on_hold = True
        booking.hold_reason = reason
        booking.held_at = timezone.now()
        booking.held_by = request.user if request.user.is_authenticated else None
        booking.save()
        BookingAuditLog.objects.create(
            booking=booking, action='DETAILS_EDITED', from_stage=booking.stage, to_stage='ON_HOLD',
            user=request.user if request.user.is_authenticated else None,
            user_name=request.user.get_full_name() or request.user.username if request.user.is_authenticated else 'Staff',
            notes=f"Order put on hold: {reason}",
        )
        messages.warning(request, f"Booking {booking.booking_ref} is now on hold.")
        return redirect('bookings:detail', pk=pk)


class BookingResumeHoldView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        resume_note = request.POST.get('resume_note', '').strip()
        booking.is_on_hold = False
        booking.hold_reason = None
        booking.held_at = None
        booking.held_by = None
        booking.save()
        BookingAuditLog.objects.create(
            booking=booking, action='DETAILS_EDITED', from_stage='ON_HOLD', to_stage=booking.stage,
            user=request.user if request.user.is_authenticated else None,
            user_name=request.user.get_full_name() or request.user.username if request.user.is_authenticated else 'Staff',
            notes=f"Order resumed from hold. {resume_note}".strip(),
        )
        messages.success(request, f"Booking {booking.booking_ref} resumed at {booking.get_stage_display()}.")
        return redirect('bookings:detail', pk=pk)


class BookingUpdateProgressView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        progress = request.POST.get('installation_progress')
        progress_notes = request.POST.get('progress_notes', '').strip()

        if progress is not None:
            try:
                progress_val = int(progress)
                booking.installation_progress = max(0, min(100, progress_val))
            except ValueError:
                pass

        if progress_notes:
            booking.installation_notes = (booking.installation_notes or "") + f"\n[{timezone.now().strftime('%Y-%m-%d %H:%M')}] {progress_notes}"

        booking.save()

        user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"
        BookingAuditLog.objects.create(
            booking=booking,
            action='INSTALLATION_UPDATED',
            from_stage=booking.stage,
            to_stage=booking.stage,
            user=request.user if request.user.is_authenticated else None,
            user_name=user_name,
            notes=f"Installation progress updated to {booking.installation_progress}%. Remarks: {progress_notes}"
        )

        messages.success(request, f"Progress updated to {booking.installation_progress}%.")
        return redirect('bookings:detail', pk=pk)


class BookingAttachmentUploadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        form = BookingAttachmentForm(request.POST, request.FILES)
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('accept', '') or
            request.POST.get('format') == 'json'
        )

        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.booking = booking
            if request.user.is_authenticated:
                attachment.uploaded_by = request.user
            attachment.save()

            user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"
            BookingAuditLog.objects.create(
                booking=booking,
                action='ATTACHMENT_ADDED',
                from_stage=booking.stage,
                to_stage=booking.stage,
                user=request.user if request.user.is_authenticated else None,
                user_name=user_name,
                notes=f"Uploaded {attachment.get_category_display()}: '{attachment.title}' ({attachment.file_size_formatted})"
            )
            success_msg = f"Document '{attachment.title}' uploaded successfully."
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': success_msg,
                    'attachment': {
                        'id': attachment.pk,
                        'title': attachment.title,
                        'category': attachment.get_category_display(),
                        'file_url': attachment.file.url,
                        'file_size': attachment.file_size_formatted,
                        'is_image': attachment.is_image,
                        'is_pdf': attachment.is_pdf,
                        'uploaded_at': attachment.uploaded_at.strftime("%b %d, %Y")
                    }
                })
            messages.success(request, success_msg)
        else:
            logger.warning("Booking attachment upload validation error for booking %s: %s", pk, form.errors.as_json())
            errors = []
            for field, errs in form.errors.items():
                for err in errs:
                    errors.append(str(err))
                    if not is_ajax:
                        messages.error(request, f"{err}")
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': " ".join(errors) or "Failed to upload file. Please check form inputs."
                }, status=400)

        return redirect('bookings:detail', pk=pk)


class BookingAttachmentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, attachment_pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        attachment = get_object_or_404(BookingAttachment, pk=attachment_pk, booking=booking)
        title = attachment.title
        try:
            attachment.file.delete(save=False)
        except Exception as e:
            logger.warning("Could not delete booking attachment file on disk (%s): %s", attachment.file.name, e)
        attachment.delete()

        user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"
        BookingAuditLog.objects.create(
            booking=booking,
            action='ATTACHMENT_DELETED',
            from_stage=booking.stage,
            to_stage=booking.stage,
            user=request.user if request.user.is_authenticated else None,
            user_name=user_name,
            notes=f"Deleted document/photo: '{title}'"
        )
        messages.info(request, f"Attachment '{title}' removed.")
        return redirect('bookings:detail', pk=pk)


class RecordPaymentView(LoginRequiredMixin, View):
    """Records an inward milestone or ad-hoc customer payment for a booking"""
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)

        if booking.is_cancelled:
            messages.error(request, "Cannot record payment on a cancelled booking. Reopen the booking first.")
            return redirect(request.POST.get('next') or booking.get_absolute_url())

        form = BookingPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.booking = booking
            if request.user.is_authenticated:
                payment.recorded_by = request.user
            payment.save()

            user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"
            BookingAuditLog.objects.create(
                booking=booking,
                action='PAYMENT_UPDATED',
                from_stage=booking.stage,
                to_stage=booking.stage,
                user=request.user if request.user.is_authenticated else None,
                user_name=user_name,
                notes=f"Payment received: ₹{payment.amount:,.2f} via {payment.get_payment_method_display()} [{payment.get_milestone_display()}]. Receipt #{payment.receipt_number}. Remaining Balance: ₹{booking.balance_amount:,.2f}"
            )

            messages.success(
                request,
                f"Payment of ₹{payment.amount:,.2f} recorded successfully! Receipt #{payment.receipt_number} issued. Remaining balance: ₹{booking.balance_amount:,.2f}"
            )
        else:
            first_err = next(iter(form.errors.values()))[0] if form.errors else "Invalid payment details."
            messages.error(request, f"Failed to record payment: {first_err}")

        return redirect(request.POST.get('next') or booking.get_absolute_url())


class PaymentReceiptPrintView(LoginRequiredMixin, DetailView):
    """Renders printable receipt voucher for a specific payment"""
    model = BookingPayment
    template_name = 'bookings/payment_receipt.html'
    context_object_name = 'payment'
    pk_url_kwarg = 'payment_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.get_object()
        context['booking'] = payment.booking
        context['customer'] = payment.booking.customer
        context['amount_in_words'] = self.number_to_words(payment.amount)
        return context

    @staticmethod
    def number_to_words(amount):
        """Converts decimal amount to Indian numbering currency words"""
        try:
            num = int(amount)
            if num == 0:
                return "Zero Rupees Only"

            def convert_chunk(n):
                units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                         "Seventeen", "Eighteen", "Nineteen"]
                tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
                res = []
                if n >= 100:
                    res.append(units[n // 100] + " Hundred")
                    n %= 100
                if n >= 20:
                    res.append(tens[n // 10])
                    n %= 10
                if n > 0:
                    res.append(units[n])
                return " ".join(res)

            parts = []
            crore = num // 10000000
            num %= 10000000
            if crore:
                parts.append(f"{convert_chunk(crore)} Crore")

            lakh = num // 100000
            num %= 100000
            if lakh:
                parts.append(f"{convert_chunk(lakh)} Lakh")

            thousand = num // 1000
            num %= 1000
            if thousand:
                parts.append(f"{convert_chunk(thousand)} Thousand")

            hundred = num
            if hundred:
                parts.append(convert_chunk(hundred))

            return " ".join(parts) + " Rupees Only"
        except Exception:
            return f"Rupees {amount:,.2f} Only"


class BookingAddNoteView(LoginRequiredMixin, View):
    """Adds a time-stamped internal note or team instruction to a booking"""
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        form = BookingNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.booking = booking
            if request.user.is_authenticated:
                note.author = request.user
                note.author_name = request.user.get_full_name() or request.user.username
            note.save()

            BookingAuditLog.objects.create(
                booking=booking,
                action='NOTE_ADDED',
                from_stage=booking.stage,
                to_stage=booking.stage,
                user=request.user if request.user.is_authenticated else None,
                user_name=note.author_name,
                notes=f"Added {note.get_category_display()}: {note.note_text[:120]}{'...' if len(note.note_text) > 120 else ''}"
            )
            messages.success(request, "Internal note posted successfully.")
        else:
            first_err = next(iter(form.errors.values()))[0] if form.errors else "Invalid note content."
            messages.error(request, f"Could not save internal note: {first_err}")

        return redirect('bookings:detail', pk=pk)


class BookingDeleteNoteView(LoginRequiredMixin, View):
    """Deletes an internal note from a booking"""
    def post(self, request, pk, note_id):
        booking = get_object_or_404(SolarBooking, pk=pk)
        note = get_object_or_404(BookingNote, pk=note_id, booking=booking)
        note_cat = note.get_category_display()
        note.delete()

        user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"
        BookingAuditLog.objects.create(
            booking=booking,
            action='NOTE_DELETED',
            from_stage=booking.stage,
            to_stage=booking.stage,
            user=request.user if request.user.is_authenticated else None,
            user_name=user_name,
            notes=f"Removed {note_cat}."
        )
        messages.info(request, "Internal note deleted.")
        return redirect('bookings:detail', pk=pk)


class BookingUpdatePrimaryNotesView(LoginRequiredMixin, View):
    """Updates the primary internal notes field on a booking"""
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        form = UpdateBookingInternalNotesForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "Staff"
            BookingAuditLog.objects.create(
                booking=booking,
                action='DETAILS_EDITED',
                from_stage=booking.stage,
                to_stage=booking.stage,
                user=request.user if request.user.is_authenticated else None,
                user_name=user_name,
                notes="Primary project internal notes updated."
            )
            messages.success(request, "Primary internal notes updated successfully.")
        else:
            messages.error(request, "Could not update internal notes.")

        return redirect('bookings:detail', pk=pk)


class CreditManagementView(LoginRequiredMixin, View):
    """
    Redirects to the integrated Customer Credit & Receivables view within Customers.
    """
    def get(self, request, *args, **kwargs):
        return redirect(f"{reverse('customers:list')}?view=credit")



class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = 'bookings/task_list.html'
    context_object_name = 'tasks'

    def get_queryset(self):
        qs = Task.objects.select_related('booking', 'customer', 'assigned_to', 'created_by', 'completed_by').prefetch_related('checklist_items').all()

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(booking__booking_ref__icontains=q) |
                Q(customer__name__icontains=q) |
                Q(assigned_name__icontains=q) |
                Q(assigned_to__username__icontains=q)
            )

        status = self.request.GET.get('status')
        due = self.request.GET.get('due', '')
        priority = self.request.GET.get('priority', '').strip().upper()
        assigned_to = self.request.GET.get('assigned_to', '')
        category = self.request.GET.get('category', '')

        # Default behavior: If no status query param is passed, AND no due/assigned_to/priority/category/q is given,
        # default to 'pending' (To Do), as requested by user.
        if status is None:
            if not due and not priority and not assigned_to and not category and not q:
                status = 'pending'
            else:
                status = ''

        if status == 'pending':
            qs = qs.filter(is_completed=False)
        elif status == 'completed':
            qs = qs.filter(is_completed=True)
        elif status == 'all':
            pass
        elif status in ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED']:
            qs = qs.filter(status=status)

        if priority == 'HIGH':
            qs = qs.filter(priority__in=[Task.PRIORITY_HIGH, Task.PRIORITY_URGENT])
        elif priority == 'NORMAL':
            qs = qs.filter(priority__in=[Task.PRIORITY_NORMAL, Task.PRIORITY_MEDIUM, Task.PRIORITY_LOW])
        elif priority:
            qs = qs.filter(priority=priority)

        if category:
            qs = qs.filter(category=category)
        today = timezone.now().date()
        if due == 'today':
            qs = qs.filter(due_date=today)
        elif due == 'overdue':
            qs = qs.filter(due_date__lt=today, is_completed=False)
        elif due == 'upcoming':
            qs = qs.filter(due_date__gt=today)

        assigned_to = self.request.GET.get('assigned_to', '')
        if assigned_to:
            if assigned_to == 'me':
                qs = qs.filter(assigned_to=self.request.user)
            else:
                qs = qs.filter(assigned_to_id=assigned_to)

        booking_id = self.request.GET.get('booking_id', '')
        if booking_id:
            qs = qs.filter(booking_id=booking_id)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_tasks = Task.objects.all()
        today = timezone.now().date()
        start_of_week = today - timezone.timedelta(days=today.weekday())

        context['total_tasks'] = all_tasks.count()
        context['pending_tasks'] = all_tasks.filter(is_completed=False).count()
        context['due_today_tasks'] = all_tasks.filter(is_completed=False, due_date=today).count()
        context['overdue_tasks'] = all_tasks.filter(is_completed=False, due_date__lt=today).count()
        context['completed_this_week'] = all_tasks.filter(is_completed=True, completed_at__date__gte=start_of_week).count()

        from django.contrib.auth import get_user_model
        User = get_user_model()
        context['users'] = User.objects.filter(is_active=True).order_by('username')
        context['active_bookings'] = SolarBooking.objects.filter(is_cancelled=False).select_related('customer').order_by('-id')[:50]
        context['pipeline_stages'] = PipelineStage.objects.filter(is_active=True).order_by('order')

        context['current_q'] = self.request.GET.get('q', '')
        status = self.request.GET.get('status')
        due = self.request.GET.get('due', '')
        priority = self.request.GET.get('priority', '').strip().upper()
        assigned_to = self.request.GET.get('assigned_to', '')
        category = self.request.GET.get('category', '')
        q = self.request.GET.get('q', '').strip()

        if status is None:
            if not due and not priority and not assigned_to and not category and not q:
                status = 'pending'
            else:
                status = ''

        context['current_status'] = status
        context['current_priority'] = priority
        context['current_category'] = category
        context['current_due'] = due
        context['current_assigned_to'] = assigned_to

        # Persistent View Mode (URL query -> Django Session -> Cookie -> default 'list')
        view_param = self.request.GET.get('view')
        if view_param in ['list', 'kanban']:
            current_view = view_param
            self.request.session['task_view_mode'] = current_view
        elif 'task_view_mode' in self.request.session:
            current_view = self.request.session['task_view_mode']
        elif 'solar_tasks_view_mode' in self.request.COOKIES:
            current_view = self.request.COOKIES['solar_tasks_view_mode']
        else:
            current_view = 'list'

        context['current_view'] = current_view

        filtered_tasks = list(self.get_queryset())
        if current_view == 'kanban' and self.request.GET.get('status') is None and not due and not priority and not assigned_to and not category and not q:
            context['kanban_pending'] = [t for t in all_tasks if not t.is_completed and t.status != Task.STATUS_IN_PROGRESS]
            context['kanban_in_progress'] = [t for t in all_tasks if not t.is_completed and t.status == Task.STATUS_IN_PROGRESS]
            context['kanban_completed'] = [t for t in all_tasks if t.is_completed][:20]
        else:
            context['kanban_pending'] = [t for t in filtered_tasks if not t.is_completed and t.status != Task.STATUS_IN_PROGRESS]
            context['kanban_in_progress'] = [t for t in filtered_tasks if not t.is_completed and t.status == Task.STATUS_IN_PROGRESS]
            context['kanban_completed'] = [t for t in filtered_tasks if t.is_completed]

        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        current_view = context.get('current_view', 'list')
        response.set_cookie('solar_tasks_view_mode', current_view, max_age=365*24*3600, samesite='Lax')
        return response


class TaskCreateView(LoginRequiredMixin, View):
    def post(self, request):
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, "Task title is required.")
            return redirect(request.META.get('HTTP_REFERER', 'bookings:task_list'))

        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', Task.CATEGORY_GENERAL)
        is_high_priority = request.POST.get('is_high_priority') in ['1', 'true', 'True', 'on'] or request.POST.get('priority') in ['HIGH', 'URGENT']
        priority = Task.PRIORITY_HIGH if is_high_priority else Task.PRIORITY_NORMAL
        due_date_str = request.POST.get('due_date', '').strip()
        due_date = due_date_str if due_date_str else None
        due_time_str = request.POST.get('due_time', '').strip()
        due_time = due_time_str if due_time_str else None

        booking_id = request.POST.get('booking_id') or request.POST.get('booking')
        booking = SolarBooking.objects.filter(pk=booking_id).first() if booking_id else None
        customer = booking.customer if booking else None
        if not customer:
            customer_id = request.POST.get('customer_id') or request.POST.get('customer')
            if customer_id:
                customer = Customer.objects.filter(pk=customer_id).first()

        assigned_to_id = request.POST.get('assigned_to')
        from django.contrib.auth import get_user_model
        User = get_user_model()
        assigned_to = User.objects.filter(pk=assigned_to_id).first() if assigned_to_id else None
        assigned_name = request.POST.get('assigned_name', '').strip()
        if assigned_to and not assigned_name:
            assigned_name = assigned_to.get_full_name() or assigned_to.username

        status_req = request.POST.get('status', '').strip().upper()
        if status_req not in [Task.STATUS_PENDING, Task.STATUS_IN_PROGRESS, Task.STATUS_COMPLETED]:
            status_req = Task.STATUS_PENDING
        is_completed = (status_req == Task.STATUS_COMPLETED)
        completed_at = timezone.now() if is_completed else None
        completed_by = request.user if is_completed else None

        task = Task.objects.create(
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=status_req,
            is_completed=is_completed,
            completed_at=completed_at,
            completed_by=completed_by,
            due_date=due_date,
            due_time=due_time,
            booking=booking,
            customer=customer,
            assigned_to=assigned_to,
            assigned_name=assigned_name,
            created_by=request.user
        )

        # Parse checklist items
        checklist_titles = request.POST.getlist('checklist_items[]') or request.POST.getlist('checklist_items')
        if not checklist_titles:
            raw_checklist = request.POST.get('checklist_text', '').strip()
            if raw_checklist:
                checklist_titles = [line.strip() for line in raw_checklist.splitlines() if line.strip()]

        for idx, item_title in enumerate(checklist_titles):
            item_title = item_title.strip()
            if item_title:
                TaskChecklistItem.objects.create(
                    task=task,
                    title=item_title,
                    order=idx
                )
        if booking:
            BookingAuditLog.objects.create(
                booking=booking,
                action='TASK_CREATED',
                user=request.user,
                user_name=request.user.get_full_name() or request.user.username,
                notes=f"Created task: '{task.title}' ({task.get_priority_display()} priority)"
            )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'task_id': task.pk,
                'title': task.title,
                'priority': task.priority,
                'category': task.category,
                'is_completed': False,
            })

        messages.success(request, f"Task '{task.title}' created successfully.")
        return redirect(request.META.get('HTTP_REFERER', 'bookings:task_list'))


class TaskStatusUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        new_status = request.POST.get('status', '').strip().upper()
        
        if new_status == Task.STATUS_COMPLETED:
            task.mark_as_completed(request.user)
            status_msg = f"Task marked as completed."
        elif new_status == Task.STATUS_IN_PROGRESS:
            task.mark_as_in_progress(request.user)
            status_msg = f"Task moved to In Progress."
        elif new_status in [Task.STATUS_PENDING, 'TODO']:
            task.mark_as_pending(request.user)
            status_msg = f"Task moved to To Do."
        else:
            return JsonResponse({'status': 'error', 'message': f"Invalid status '{new_status}'."}, status=400)

        completed_by_name = task.completed_by_name if task.is_completed else None
        completed_at_display = task.completed_at.strftime('%b %d, %Y, %I:%M %p') if task.completed_at else None

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'status': 'success',
                'task_id': task.pk,
                'status_code': task.status,
                'status_display': task.get_status_display(),
                'is_completed': task.is_completed,
                'completed_by': completed_by_name,
                'completed_at': completed_at_display,
                'message': status_msg,
            })

        messages.success(request, status_msg)
        return redirect(request.META.get('HTTP_REFERER', 'bookings:task_list'))


class TaskToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        status_req = request.POST.get('status', '').strip().upper()
        if status_req == Task.STATUS_IN_PROGRESS:
            task.mark_as_in_progress(request.user)
            status_msg = "Task moved to In Progress."
        elif status_req == Task.STATUS_COMPLETED:
            task.mark_as_completed(request.user)
            status_msg = "Task marked as completed."
        elif status_req in [Task.STATUS_PENDING, 'TODO']:
            task.mark_as_pending(request.user)
            status_msg = "Task moved to To Do."
        elif task.is_completed:
            task.mark_as_pending(request.user)
            status_msg = "Task reopened successfully."
        else:
            task.mark_as_completed(request.user)
            status_msg = "Task marked as completed."

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            completed_by_name = (task.completed_by.get_full_name() or task.completed_by.username) if task.completed_by else None
            completed_at_display = task.completed_at.strftime('%b %d, %Y, %I:%M %p') if task.completed_at else None
            return JsonResponse({
                'status': 'success',
                'task_id': task.pk,
                'is_completed': task.is_completed,
                'status_code': task.status,
                'status_display': 'Completed' if task.is_completed else 'To Do (Reopened)',
                'completed_at': completed_at_display,
                'completed_at_raw': task.completed_at.strftime('%Y-%m-%d %H:%M') if task.completed_at else None,
                'completed_by': completed_by_name,
                'message': status_msg,
            })

        messages.success(request, status_msg)
        return redirect(request.META.get('HTTP_REFERER', 'bookings:task_list'))


class TaskDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        title = task.title
        booking = task.booking
        task.delete()

        if booking:
            BookingAuditLog.objects.create(
                booking=booking,
                action='TASK_DELETED',
                user=request.user,
                user_name=request.user.get_full_name() or request.user.username,
                notes=f"Deleted task: '{title}'"
            )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': f"Task '{title}' deleted."})

        messages.info(request, f"Task '{title}' deleted.")
        return redirect(request.META.get('HTTP_REFERER', 'bookings:task_list'))


class TaskDetailJsonView(LoginRequiredMixin, View):
    def get(self, request, pk):
        task = get_object_or_404(
            Task.objects.select_related(
                'created_by', 'assigned_to', 'completed_by', 'booking', 'booking__customer', 'customer'
            ).prefetch_related('checklist_items'),
            pk=pk
        )

        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('format') != 'json':
            return redirect(reverse('bookings:task_list') + f'?task={pk}')

        created_by_name = task.created_by.get_full_name() or task.created_by.username if task.created_by else 'System'
        created_by_role = 'Administrator' if task.created_by and task.created_by.is_superuser else ('Staff' if task.created_by and task.created_by.is_staff else 'Team Member')

        from django.utils.timesince import timesince
        created_at_str = task.created_at.strftime('%b %d, %Y at %I:%M %p') if task.created_at else None
        created_at_relative = f"{timesince(task.created_at)} ago" if task.created_at else None

        checklist_data = []
        for item in task.checklist_items_all:
            checklist_data.append({
                'id': item.pk,
                'title': item.title,
                'is_completed': item.is_completed,
                'completed_at': item.completed_at.strftime('%b %d, %I:%M %p') if item.completed_at else None,
                'toggle_url': reverse('bookings:checklist_toggle', kwargs={'pk': item.pk}),
                'delete_url': reverse('bookings:checklist_delete', kwargs={'pk': item.pk}),
            })

        booking_data = None
        if task.booking:
            booking_data = {
                'id': task.booking.pk,
                'booking_ref': task.booking.booking_ref,
                'url': task.booking.get_absolute_url(),
                'customer_name': task.booking.customer.name,
                'customer_phone': task.booking.customer.phone,
                'system_capacity_kw': str(task.booking.system_capacity_kw) if task.booking.system_capacity_kw else None,
                'stage_display': task.booking.get_stage_display()
            }

        customer_data = None
        if task.customer and not task.booking:
            customer_data = {
                'id': task.customer.pk,
                'name': task.customer.name,
                'phone': task.customer.phone
            }

        data = {
            'status': 'success',
            'id': task.pk,
            'title': task.title,
            'description': task.description or '',
            'category': task.category,
            'category_display': task.get_category_display(),
            'category_icon': task.category_icon,
            'priority': task.priority,
            'is_high_priority': task.is_high_priority,
            'status_code': task.status,
            'is_completed': task.is_completed,
            'created_by': {
                'name': created_by_name,
                'role': created_by_role,
                'avatar': created_by_name[:1].upper()
            },
            'created_at': created_at_str,
            'created_at_relative': created_at_relative,
            'due_date': task.due_date.strftime('%b %d, %Y') if task.due_date else None,
            'due_date_raw': task.due_date.isoformat() if task.due_date else None,
            'due_time': task.due_time.strftime('%I:%M %p') if task.due_time else None,
            'is_overdue': task.is_overdue,
            'completed_at': task.completed_at.strftime('%b %d, %Y at %I:%M %p') if task.completed_at else None,
            'completed_by': task.completed_by.get_full_name() or task.completed_by.username if task.completed_by else None,
            'assigned_to': {
                'name': task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else (task.assigned_name or 'Unassigned'),
                'avatar': (task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else (task.assigned_name or 'U'))[:1].upper()
            },
            'booking': booking_data,
            'customer': customer_data,
            'checklist': checklist_data,
            'checklist_stats': {
                'total': task.checklist_total,
                'completed': task.checklist_completed_count,
                'pct': task.checklist_progress_pct
            },
            'toggle_url': reverse('bookings:task_toggle', kwargs={'pk': task.pk}),
            'delete_url': reverse('bookings:task_delete', kwargs={'pk': task.pk}),
            'add_checklist_url': reverse('bookings:checklist_add', kwargs={'task_id': task.pk})
        }
        return JsonResponse(data)





class TaskChecklistToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(TaskChecklistItem, pk=pk)
        if item.is_completed:
            item.mark_pending(request.user)
            action_msg = "Item marked pending"
        else:
            item.mark_completed(request.user)
            action_msg = "Item completed"

        task = item.task
        completed_by_name = (item.completed_by.get_full_name() or item.completed_by.username) if item.completed_by else None
        completed_at_display = item.completed_at.strftime('%b %d, %I:%M %p') if item.completed_at else None
        return JsonResponse({
            'status': 'success',
            'item_id': item.pk,
            'is_completed': item.is_completed,
            'completed_at': completed_at_display,
            'completed_by': completed_by_name,
            'checklist_total': task.checklist_total,
            'checklist_completed_count': task.checklist_completed_count,
            'checklist_progress_pct': task.checklist_progress_pct,
            'message': action_msg,
        })


class TaskChecklistAddItemView(LoginRequiredMixin, View):
    def post(self, request, task_id):
        task = get_object_or_404(Task, pk=task_id)
        title = request.POST.get('title', '').strip()
        if not title:
            return JsonResponse({'status': 'error', 'message': 'Title is required'}, status=400)

        order = task.checklist_items.count()
        item = TaskChecklistItem.objects.create(
            task=task,
            title=title,
            order=order
        )
        return JsonResponse({
            'status': 'success',
            'item_id': item.pk,
            'title': item.title,
            'is_completed': item.is_completed,
            'checklist_total': task.checklist_total,
            'checklist_completed_count': task.checklist_completed_count,
            'checklist_progress_pct': task.checklist_progress_pct,
        })


class TaskChecklistDeleteItemView(LoginRequiredMixin, View):
    def post(self, request, pk):
        item = get_object_or_404(TaskChecklistItem, pk=pk)
        task = item.task
        item.delete()
        return JsonResponse({
            'status': 'success',
            'item_id': pk,
            'checklist_total': task.checklist_total,
            'checklist_completed_count': task.checklist_completed_count,
            'checklist_progress_pct': task.checklist_progress_pct,
        })


class QuickStageCreateView(LoginRequiredMixin, View):
    def post(self, request):
        name = request.POST.get('name', '').strip()
        raw_code = request.POST.get('code', '').strip().upper()
        color = request.POST.get('color', '#2563eb')
        icon = request.POST.get('icon', 'bi-circle')
        position_after = request.POST.get('position_after', '').strip()

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Stage name is required.'}, status=400)

        from django.utils.text import slugify
        from bookings.models import PipelineStage
        from core.views import get_stage_palette
        from django.db import models

        if not raw_code:
            raw_code = slugify(name).upper().replace('-', '_')

        base_code = raw_code or 'CUSTOM_STAGE'
        unique_code = base_code
        counter = 1
        while PipelineStage.objects.filter(code=unique_code).exists():
            unique_code = f"{base_code}_{counter}"
            counter += 1

        if position_after:
            after_stage = PipelineStage.objects.filter(code=position_after).first()
            if after_stage:
                target_order = after_stage.order + 1
                for s in PipelineStage.objects.filter(order__gte=target_order).order_by('-order'):
                    s.order += 1
                    s.save(update_fields=['order'])
                new_order = target_order
            else:
                new_order = (PipelineStage.objects.aggregate(m=models.Max('order'))['m'] or 0) + 1
        else:
            new_order = (PipelineStage.objects.aggregate(m=models.Max('order'))['m'] or 0) + 1

        is_initial_checked = request.POST.get('is_initial') in ['on', 'true', '1']
        if is_initial_checked:
            PipelineStage.objects.all().update(is_initial=False)

        palette = get_stage_palette(color)
        stage = PipelineStage.objects.create(
            name=name,
            code=unique_code,
            order=new_order,
            color=palette['color'],
            bg_header=palette['bg'],
            border_color=palette['border'],
            header_text=palette['text'],
            icon=icon,
            is_initial=is_initial_checked,
            is_system=False,
            is_active=True,
        )
        return JsonResponse({
            'status': 'success',
            'message': f"Pipeline stage '{name}' added successfully.",
            'stage': {
                'code': stage.code,
                'name': stage.name,
                'order': stage.order,
                'color': stage.color
            }
        })


class CalendarView(LoginRequiredMixin, TemplateView):
    template_name = 'bookings/calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import Team
        from django.contrib.auth import get_user_model
        User = get_user_model()

        today = timezone.now().date()
        context['teams'] = Team.objects.filter(is_active=True).order_by('name')
        context['staff_users'] = User.objects.filter(is_active=True).order_by('username')
        context['active_bookings'] = SolarBooking.objects.filter(
            is_cancelled=False
        ).select_related('customer').order_by('-id')[:40]

        # Scheduled Action & Deadline KPIs (Decoupled from pipeline status)
        tasks_qs = Task.objects.filter(due_date__isnull=False)
        context['total_scheduled_count'] = tasks_qs.count()
        context['due_today_count'] = tasks_qs.filter(due_date=today).count()
        context['high_priority_count'] = tasks_qs.filter(priority__in=['HIGH', 'URGENT']).count()
        context['upcoming_week_count'] = tasks_qs.filter(due_date__gte=today, due_date__lte=today + timedelta(days=7)).count()

        return context


class CalendarEventsJsonView(LoginRequiredMixin, View):
    def get(self, request):
        today = timezone.now().date()
        team_id = request.GET.get('team')
        staff = request.GET.get('staff')
        layers = request.GET.get('layers', 'high_priority,standard,project_linked').split(',')

        events = []

        tasks_qs = Task.objects.filter(due_date__isnull=False).select_related('booking', 'booking__customer', 'assigned_to').prefetch_related('checklist_items')
        
        if staff:
            tasks_qs = tasks_qs.filter(Q(assigned_to__username=staff) | Q(assigned_name=staff))
            
        if team_id:
            tasks_qs = tasks_qs.filter(booking__assigned_team_id=team_id)

        for t in tasks_qs:
            is_high = t.is_high_priority
            has_booking = (t.booking is not None)
            
            # Check layer filter
            if is_high and 'high_priority' not in layers and layers != ['']:
                continue
            if not is_high and 'standard' not in layers and layers != ['']:
                continue
            if has_booking and 'project_linked' not in layers and layers != [''] and 'high_priority' not in layers and 'standard' not in layers:
                continue

            bg_color = '#fef2f2' if is_high else ('#eff6ff' if has_booking else '#f0fdf4')
            border_color = '#fecaca' if is_high else ('#bfdbfe' if has_booking else '#bbf7d0')
            text_color = '#991b1b' if is_high else ('#1e40af' if has_booking else '#166534')

            class_names = ['cal-event-task']
            if is_high:
                class_names.append('cal-task-high')
            elif has_booking:
                class_names.append('cal-task-project')
            else:
                class_names.append('cal-task-standard')

            events.append({
                'id': f"task-{t.pk}",
                'title': f"{'⚡ ' if is_high else ''}{t.title}",
                'start': t.due_date.isoformat(),
                'allDay': True,
                'backgroundColor': bg_color,
                'borderColor': border_color,
                'textColor': text_color,
                'classNames': class_names,
                'extendedProps': {
                    'type': 'TASK',
                    'task_id': t.pk,
                    'title': t.title,
                    'description': t.description or '',
                    'due_date': t.due_date.strftime('%b %d, %Y'),
                    'is_high_priority': is_high,
                    'priority_label': 'High Priority' if is_high else 'Normal Priority',
                    'assigned_name': t.assigned_to.get_full_name() if t.assigned_to else (t.assigned_name or 'Unassigned'),
                    'booking_ref': t.booking.booking_ref if t.booking else None,
                    'customer_name': t.booking.customer.name if t.booking and t.booking.customer else None,
                    'customer_phone': t.booking.customer.phone if t.booking and t.booking.customer else None,
                    'capacity_kw': str(t.booking.system_capacity_kw) if t.booking and t.booking.system_capacity_kw else None,
                    'checklist_summary': f"{t.checklist_completed_count}/{t.checklist_total} steps" if t.has_checklist else None,
                    'url': reverse('bookings:task_list') + f"?q={t.title}"
                }
            })

        return JsonResponse(events, safe=False)


class CalendarEventMoveView(LoginRequiredMixin, View):
    def post(self, request):
        event_id = request.POST.get('event_id', '')
        new_date_str = request.POST.get('new_date', '').strip()

        if not event_id or not new_date_str:
            return JsonResponse({'status': 'error', 'message': 'Event ID and new date are required.'}, status=400)

        try:
            prefix, pk_str = event_id.split('-')
            pk = int(pk_str)
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Invalid parameters: {str(e)}'}, status=400)

        if prefix == 'task':
            task = get_object_or_404(Task, pk=pk)
            old_date = task.due_date
            task.due_date = new_date
            task.save(update_fields=['due_date'])
            return JsonResponse({'status': 'success', 'message': f"Schedule for '{task.title}' updated to {new_date}."})

        return JsonResponse({'status': 'error', 'message': f'Unknown event type: {prefix}'}, status=400)



class BookingCustomFieldCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        form = BookingCustomFieldForm(request.POST)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
        if form.is_valid():
            cf = form.save(commit=False)
            cf.booking = booking
            cf.save()
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': f"Specification '{cf.label}' added successfully.",
                    'field': {
                        'id': cf.pk,
                        'label': cf.label,
                        'value': cf.value,
                        'edit_url': reverse('bookings:custom_field_edit', kwargs={'pk': booking.pk, 'field_pk': cf.pk}),
                        'delete_url': reverse('bookings:custom_field_delete', kwargs={'pk': booking.pk, 'field_pk': cf.pk}),
                    }
                })
            messages.success(request, f"Specification '{cf.label}' added successfully.")
        else:
            first_err = next(iter(form.errors.values()))[0] if form.errors else "Failed to add custom field. Please check your inputs."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': first_err}, status=400)
            messages.error(request, first_err)
        return redirect('bookings:detail', pk=pk)


class BookingCustomFieldUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk, field_pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        cf = get_object_or_404(BookingCustomField, pk=field_pk, booking=booking)
        form = BookingCustomFieldForm(request.POST, instance=cf)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
        if form.is_valid():
            form.save()
            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': f"Specification '{cf.label}' updated successfully.",
                    'field': {
                        'id': cf.pk,
                        'label': cf.label,
                        'value': cf.value,
                        'edit_url': reverse('bookings:custom_field_edit', kwargs={'pk': booking.pk, 'field_pk': cf.pk}),
                        'delete_url': reverse('bookings:custom_field_delete', kwargs={'pk': booking.pk, 'field_pk': cf.pk}),
                    }
                })
            messages.success(request, f"Specification '{cf.label}' updated successfully.")
        else:
            first_err = next(iter(form.errors.values()))[0] if form.errors else "Failed to update custom field."
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': first_err}, status=400)
            messages.error(request, first_err)
        return redirect('bookings:detail', pk=pk)


class BookingCustomFieldDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, field_pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        cf = get_object_or_404(BookingCustomField, pk=field_pk, booking=booking)
        label = cf.label
        cf.delete()
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': f"Specification '{label}' deleted successfully."})
        messages.success(request, f"Specification '{label}' deleted successfully.")
        return redirect('bookings:detail', pk=pk)



class ReorderBookingsView(LoginRequiredMixin, View):
    """AJAX endpoint to update vertical kanban_order and stage of cards when dragged up/down or across columns."""
    def post(self, request):
        import json
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST

        ordered_ids = data.get('ordered_ids', [])
        target_stage = data.get('stage')
        
        if isinstance(ordered_ids, str):
            ordered_ids = [int(x) for x in ordered_ids.split(',') if x.strip().isdigit()]

        updated_count = 0
        for index, b_id in enumerate(ordered_ids):
            try:
                b = SolarBooking.objects.get(pk=b_id)
                b.kanban_order = index
                if target_stage and b.stage != target_stage:
                    old_stage = b.stage
                    b.stage = target_stage
                    # Log audit trail safely
                    user_name = request.user.get_full_name() or request.user.username if request.user.is_authenticated else "System Staff"
                    try:
                        BookingAuditLog.objects.create(
                            booking=b,
                            action='STAGE_TRANSITION',
                            from_stage=old_stage,
                            to_stage=target_stage,
                            user=request.user if request.user.is_authenticated else None,
                            user_name=user_name,
                            notes=f"Stage moved via Kanban drag from {old_stage} to {target_stage}"
                        )
                    except Exception as audit_err:
                        logger.warning(f"Audit log creation error during reorder: {audit_err}")

                b.save(update_fields=['kanban_order', 'stage', 'updated_at'])
                updated_count += 1
            except SolarBooking.DoesNotExist:
                continue
            except Exception as e:
                logger.warning(f"Error updating booking #{b_id}: {e}")
                continue

        return JsonResponse({'status': 'ok', 'updated': updated_count})


class UpdateBookingPriorityView(LoginRequiredMixin, View):
    """AJAX endpoint to change a booking's priority (URGENT, HIGH, NORMAL, LOW)"""
    def post(self, request, pk):
        booking = get_object_or_404(SolarBooking, pk=pk)
        priority = request.POST.get('priority') or request.GET.get('priority')
        if not priority and request.body:
            import json
            try:
                data = json.loads(request.body)
                priority = data.get('priority')
            except Exception:
                pass
        
        valid_priorities = [p[0] for p in SolarBooking.PRIORITY_CHOICES]
        if priority in valid_priorities:
            booking.priority = priority
            booking.save(update_fields=['priority', 'updated_at'])
            return JsonResponse({
                'status': 'ok',
                'priority': booking.priority,
                'label': booking.get_priority_display(),
                'badge': booking.priority_badge_info
            })
        return JsonResponse({'status': 'error', 'message': 'Invalid priority'}, status=400)
