import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views import View
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from customers.models import Customer
from bookings.models import SolarBooking, PipelineStage, Task
from core.models import CompanySetting, TeamMember, UserProfile, CatalogItem
from core.forms import RegistrationForm, TeamMemberForm

logger = logging.getLogger(__name__)


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        filter_period = request.GET.get('period', 'this_month')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        now = timezone.now().date()
        start_date = None
        end_date = now

        if filter_period == 'today':
            start_date = now
        elif filter_period == 'this_week':
            start_date = now - timedelta(days=now.weekday())
        elif filter_period == 'this_month':
            start_date = now.replace(day=1)
        elif filter_period == 'this_year':
            start_date = now.replace(month=1, day=1)
        elif filter_period == 'custom' and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = None

        # Base querysets
        bookings_qs = SolarBooking.objects.select_related('customer').all()
        customers_qs = Customer.objects.all()

        if start_date:
            bookings_qs = bookings_qs.filter(booking_date__gte=start_date)
            customers_qs = customers_qs.filter(created_at__date__gte=start_date)
        if end_date:
            bookings_qs = bookings_qs.filter(booking_date__lte=end_date)
            customers_qs = customers_qs.filter(created_at__date__lte=end_date)

        # KPI Metrics
        total_customers = customers_qs.count()
        total_bookings = bookings_qs.count()
        new_bookings = bookings_qs.filter(stage=SolarBooking.STAGE_NEW, is_cancelled=False).count()
        bookings_in_progress = bookings_qs.filter(
            stage__in=[SolarBooking.STAGE_SURVEY, SolarBooking.STAGE_INSTALLATION],
            is_cancelled=False
        ).count()
        survey_count = bookings_qs.filter(stage=SolarBooking.STAGE_SURVEY, is_cancelled=False).count()
        installation_count = bookings_qs.filter(stage=SolarBooking.STAGE_INSTALLATION, is_cancelled=False).count()
        completed_bookings = bookings_qs.filter(stage=SolarBooking.STAGE_COMPLETED, is_cancelled=False).count()
        cancelled_bookings = bookings_qs.filter(is_cancelled=True).count()

        financial_stats = bookings_qs.filter(is_cancelled=False).aggregate(
            total_rev=Sum('booking_amount'),
            total_adv=Sum('advance_payment'),
            total_bal=Sum('balance_amount'),
            total_kw=Sum('system_capacity_kw')
        )
        total_revenue = financial_stats['total_rev'] or Decimal('0.00')
        total_collected = (financial_stats['total_adv'] or Decimal('0.00')) + (bookings_qs.filter(is_cancelled=False).aggregate(f=Sum('final_payment_received'))['f'] or Decimal('0.00'))
        total_balance = financial_stats['total_bal'] or Decimal('0.00')
        total_kw = financial_stats['total_kw'] or Decimal('0.00')

        # Recent Items
        recent_bookings = bookings_qs.order_by('-booking_date', '-id')[:6]
        recent_customers = customers_qs.order_by('-created_at')[:6]

        # Charts Data Preparation
        # 1. Doughnut Chart: Dynamic Stage Distribution from PipelineStage
        from bookings.models import PipelineStage
        active_stages = PipelineStage.objects.filter(is_active=True).order_by('order')
        stage_labels = []
        stage_counts = []
        stage_colors = []
        matched_stage_codes = set()

        for st in active_stages:
            matched_stage_codes.add(st.code)
            cnt = bookings_qs.filter(stage=st.code, is_cancelled=False).count()
            if cnt > 0:
                stage_labels.append(st.name)
                stage_counts.append(cnt)
                stage_colors.append(st.color or '#2563eb')

        other_cnt = bookings_qs.filter(is_cancelled=False).exclude(stage__in=matched_stage_codes).count()
        if other_cnt > 0:
            stage_labels.append('Other Stages')
            stage_counts.append(other_cnt)
            stage_colors.append('#64748b')

        cancelled_cnt = bookings_qs.filter(is_cancelled=True).count()
        if cancelled_cnt > 0:
            stage_labels.append('Cancelled')
            stage_counts.append(cancelled_cnt)
            stage_colors.append('#e11d48')

        # 2. Line Chart: Bookings Over Time (Past 7 or 14 days or monthly)
        timeline_days = 14
        chart_timeline_labels = []
        chart_timeline_counts = []
        chart_timeline_values = []

        base_date = now - timedelta(days=timeline_days - 1)
        for i in range(timeline_days):
            day_cursor = base_date + timedelta(days=i)
            day_str = day_cursor.strftime('%b %d')
            chart_timeline_labels.append(day_str)
            
            day_bookings = SolarBooking.objects.filter(booking_date=day_cursor)
            cnt = day_bookings.count()
            val = float(day_bookings.filter(is_cancelled=False).aggregate(s=Sum('booking_amount'))['s'] or 0)
            
            chart_timeline_counts.append(cnt)
            chart_timeline_values.append(val)

        # 3. Bar Chart: Monthly Performance (Last 6 months)
        months_labels = []
        months_counts = []
        months_revenue = []

        for m_offset in range(5, -1, -1):
            target_month_date = (now.replace(day=1) - timedelta(days=m_offset * 30)).replace(day=1)
            month_label = target_month_date.strftime('%b %Y')
            months_labels.append(month_label)

            m_bookings = SolarBooking.objects.filter(
                booking_date__year=target_month_date.year,
                booking_date__month=target_month_date.month
            )
            m_cnt = m_bookings.count()
            m_rev = float(m_bookings.filter(is_cancelled=False).aggregate(s=Sum('booking_amount'))['s'] or 0) / 1000.0  # in Thousands

            months_counts.append(m_cnt)
            months_revenue.append(round(m_rev, 1))

        context = {

            'filter_period': filter_period,
            'start_date': start_date_str or '',
            'end_date': end_date_str or '',

            # KPI Cards
            'total_customers': total_customers,
            'total_bookings': total_bookings,
            'new_bookings': new_bookings,
            'bookings_in_progress': bookings_in_progress,
            'survey_count': survey_count,
            'installation_count': installation_count,
            'completed_bookings': completed_bookings,
            'cancelled_bookings': cancelled_bookings,
            'total_revenue': total_revenue,
            'total_collected': total_collected,
            'total_kw': total_kw,
            'total_balance': total_balance,

            # Recent Lists
            'recent_bookings': recent_bookings,
            'recent_customers': recent_customers,

            # Chart JSON payloads
            'chart_stage_labels': json.dumps(stage_labels),
            'chart_stage_data': json.dumps(stage_counts),
            'chart_stage_colors': json.dumps(stage_colors),
            'chart_timeline_labels': json.dumps(chart_timeline_labels),
            'chart_timeline_counts': json.dumps(chart_timeline_counts),
            'chart_timeline_values': json.dumps(chart_timeline_values),
            'chart_months_labels': json.dumps(months_labels),
            'chart_months_counts': json.dumps(months_counts),
            'chart_months_revenue': json.dumps(months_revenue),
        }
        return render(request, 'core/dashboard.html', context)


def get_stage_palette(color_key_or_hex):
    palettes = {
        '#2563eb': {'color': '#2563eb', 'bg': '#eff6ff', 'border': '#bfdbfe', 'text': '#1d4ed8'},
        '#0284c7': {'color': '#0284c7', 'bg': '#f0f9ff', 'border': '#bae6fd', 'text': '#0369a1'},
        '#0891b2': {'color': '#0891b2', 'bg': '#ecfeff', 'border': '#a5f3fc', 'text': '#0e7490'},
        '#0d9488': {'color': '#0d9488', 'bg': '#f0fdfa', 'border': '#99f6e4', 'text': '#0f766e'},
        '#059669': {'color': '#059669', 'bg': '#ecfdf5', 'border': '#a7f3d0', 'text': '#047857'},
        '#15803d': {'color': '#15803d', 'bg': '#f0fdf4', 'border': '#bbf7d0', 'text': '#166534'},
        '#65a30d': {'color': '#65a30d', 'bg': '#f7fee7', 'border': '#d9f99d', 'text': '#4d7c0f'},
        '#f59e0b': {'color': '#f59e0b', 'bg': '#fffbeb', 'border': '#fde68a', 'text': '#b45309'},
        '#d97706': {'color': '#d97706', 'bg': '#fffbeb', 'border': '#fde68a', 'text': '#b45309'},
        '#f97316': {'color': '#f97316', 'bg': '#fff7ed', 'border': '#fed7aa', 'text': '#c2410c'},
        '#ea580c': {'color': '#ea580c', 'bg': '#fff7ed', 'border': '#fed7aa', 'text': '#c2410c'},
        '#ef4444': {'color': '#ef4444', 'bg': '#fef2f2', 'border': '#fecaca', 'text': '#b91c1c'},
        '#e11d48': {'color': '#e11d48', 'bg': '#fff1f2', 'border': '#fecdd3', 'text': '#be123c'},
        '#db2777': {'color': '#db2777', 'bg': '#fdf2f8', 'border': '#fbcfe8', 'text': '#be185d'},
        '#c026d3': {'color': '#c026d3', 'bg': '#fdf4ff', 'border': '#f5d0fe', 'text': '#a21caf'},
        '#7c3aed': {'color': '#7c3aed', 'bg': '#f5f3ff', 'border': '#ddd6fe', 'text': '#6d28d9'},
        '#4f46e5': {'color': '#4f46e5', 'bg': '#eef2ff', 'border': '#c7d2fe', 'text': '#3730a3'},
        '#475569': {'color': '#475569', 'bg': '#f8fafc', 'border': '#cbd5e1', 'text': '#334155'},
    }
    hex_clean = (color_key_or_hex or '#059669').strip()
    if not hex_clean.startswith('#'):
        hex_clean = '#' + hex_clean
    hex_lower = hex_clean.lower()
    if hex_lower in palettes:
        return palettes[hex_lower]
    # For any custom chosen RGB hex, generate subtle bg and border
    return {'color': hex_clean, 'bg': hex_clean + '15', 'border': hex_clean + '35', 'text': hex_clean}


class SettingsView(LoginRequiredMixin, View):
    def get(self, request):
        company = CompanySetting.get_settings()
        team_members = TeamMember.objects.all()
        CatalogItem.ensure_defaults()
        PipelineStage.ensure_defaults()

        catalog_panel_brands = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_PANEL_BRAND)
        catalog_panel_techs = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_PANEL_TECH)
        catalog_inverters = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_INVERTER)
        catalog_mountings = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_MOUNTING)
        catalog_accessories = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_ACCESSORY)
        catalog_lead_sources = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_LEAD_SOURCE)
        catalog_roles = CatalogItem.objects.filter(category=CatalogItem.CATEGORY_ASSIGNED_ROLE)

        pipeline_stages = list(PipelineStage.objects.all().order_by('order', 'id'))
        for st in pipeline_stages:
            st.bookings_count = st.active_bookings_count()

        active_tab = request.GET.get('tab', 'company')
        active_cat = request.GET.get('cat', 'PANEL_BRAND')

        return render(request, 'core/settings.html', {
            'company': company,
            'team_members': team_members,
            'catalog_panel_brands': catalog_panel_brands,
            'catalog_panel_techs': catalog_panel_techs,
            'catalog_inverters': catalog_inverters,
            'catalog_mountings': catalog_mountings,
            'catalog_accessories': catalog_accessories,
            'catalog_lead_sources': catalog_lead_sources,
            'catalog_roles': catalog_roles,
            'pipeline_stages': pipeline_stages,
            'active_tab': active_tab,
            'active_cat': active_cat,
        })

    def post(self, request):
        action = request.POST.get('action')
        company = CompanySetting.get_settings()
        active_tab = request.POST.get('active_tab', 'company')
        active_cat = request.POST.get('active_cat', 'PANEL_BRAND')

        if action == 'save_company':
            company.company_name = request.POST.get('company_name', company.company_name)
            company.tagline = request.POST.get('tagline', company.tagline)
            company.phone = request.POST.get('phone', company.phone)
            company.email = request.POST.get('email', company.email)
            company.address = request.POST.get('address', company.address)
            company.tax_id = request.POST.get('tax_id', company.tax_id)
            company.currency_symbol = '₹'
            company.currency_code = 'INR'
            company.save()
            messages.success(request, "Company settings updated successfully.")
            return redirect(f"{reverse('core:settings')}?tab=company")

        elif action == 'add_team_member':
            name = request.POST.get('member_name')
            role = request.POST.get('member_role')
            phone = request.POST.get('member_phone')
            email = request.POST.get('member_email')
            if name and role and phone:
                TeamMember.objects.create(name=name, role=role, phone=phone, email=email or None)
                messages.success(request, f"Team member {name} added.")
            else:
                messages.error(request, "Name, Role, and Phone are required.")
            return redirect(f"{reverse('core:settings')}?tab=team")

        elif action == 'delete_team_member':
            member_id = request.POST.get('member_id')
            if member_id:
                TeamMember.objects.filter(pk=member_id).delete()
                messages.info(request, "Team member removed.")
            return redirect(f"{reverse('core:settings')}?tab=team")

        elif action == 'add_catalog_item':
            category = request.POST.get('category')
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            if category and name:
                item, created = CatalogItem.objects.get_or_create(
                    category=category,
                    name=name,
                    defaults={'description': description or None, 'is_active': True}
                )
                if not created and not item.is_active:
                    item.is_active = True
                    item.save(update_fields=['is_active'])
                    messages.success(request, f"Re-activated '{name}' in {item.get_category_display()}.")
                elif created:
                    messages.success(request, f"Added '{name}' to {item.get_category_display()}.")
                else:
                    messages.info(request, f"'{name}' is already in {item.get_category_display()}.")
            else:
                messages.error(request, "Item name is required.")
            return redirect(f"{reverse('core:settings')}?tab=utilities&cat={category}")

        elif action == 'delete_catalog_item':
            item_id = request.POST.get('item_id')
            cat = request.POST.get('cat', 'PANEL')
            item = get_object_or_404(CatalogItem, pk=item_id)
            name = item.name
            cat_display = item.get_category_display()
            item.delete()
            messages.info(request, f"Removed '{name}' from {cat_display}.")
            return redirect(f"{reverse('core:settings')}?tab=utilities&cat={cat}")

        elif action == 'toggle_catalog_item':
            item_id = request.POST.get('item_id')
            cat = request.POST.get('cat', 'PANEL')
            item = get_object_or_404(CatalogItem, pk=item_id)
            item.is_active = not item.is_active
            item.save(update_fields=['is_active'])
            status_label = "Active" if item.is_active else "Inactive"
            messages.success(request, f"Set '{item.name}' status to {status_label}.")
            return redirect(f"{reverse('core:settings')}?tab=utilities&cat={cat}")

        # =====================================================================
        # PIPELINE STAGE ACTIONS
        # =====================================================================
        elif action == 'add_pipeline_stage':
            name = request.POST.get('name', '').strip()
            raw_code = request.POST.get('code', '').strip().upper()
            color = request.POST.get('color', '#2563eb')
            icon = request.POST.get('icon', 'bi-circle')
            position_after = request.POST.get('position_after', '').strip()

            if not name:
                messages.error(request, "Stage name is required.")
                return redirect(f"{reverse('core:settings')}?tab=pipeline")

            if not raw_code:
                raw_code = slugify(name).upper().replace('-', '_')

            # Ensure unique code
            base_code = raw_code or 'CUSTOM_STAGE'
            unique_code = base_code
            counter = 1
            while PipelineStage.objects.filter(code=unique_code).exists():
                unique_code = f"{base_code}_{counter}"
                counter += 1

            # Determine order position
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
            PipelineStage.objects.create(
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
            messages.success(request, f"Pipeline stage '{name}' added successfully.")
            return redirect(f"{reverse('core:settings')}?tab=pipeline")

        elif action == 'edit_pipeline_stage':
            stage_id = request.POST.get('stage_id')
            stage = get_object_or_404(PipelineStage, pk=stage_id)
            name = request.POST.get('name', '').strip()
            color = request.POST.get('color', stage.color)
            icon = request.POST.get('icon', stage.icon)

            if name:
                stage.name = name
                palette = get_stage_palette(color)
                stage.color = palette['color']
                stage.bg_header = palette['bg']
                stage.border_color = palette['border']
                stage.header_text = palette['text']
                stage.icon = icon
                
                is_initial_checked = request.POST.get('is_initial') in ['on', 'true', '1']
                if is_initial_checked:
                    PipelineStage.objects.all().update(is_initial=False)
                    stage.is_initial = True
                stage.save()
                messages.success(request, f"Pipeline stage '{stage.name}' updated.")
            else:
                messages.error(request, "Stage name cannot be empty.")
            return redirect(f"{reverse('core:settings')}?tab=pipeline")

        elif action == 'reorder_pipeline_stage':
            stage_id = request.POST.get('stage_id')
            direction = request.POST.get('direction')
            stage = get_object_or_404(PipelineStage, pk=stage_id)
            all_stages = list(PipelineStage.objects.all().order_by('order', 'id'))
            try:
                idx = all_stages.index(stage)
                if direction == 'up' and idx > 0:
                    prev_st = all_stages[idx - 1]
                    stage.order, prev_st.order = prev_st.order, stage.order
                    stage.save(update_fields=['order'])
                    prev_st.save(update_fields=['order'])
                    messages.success(request, f"Moved '{stage.name}' earlier in pipeline sequence.")
                elif direction == 'down' and idx < len(all_stages) - 1:
                    next_st = all_stages[idx + 1]
                    stage.order, next_st.order = next_st.order, stage.order
                    stage.save(update_fields=['order'])
                    next_st.save(update_fields=['order'])
                    messages.success(request, f"Moved '{stage.name}' later in pipeline sequence.")
            except ValueError:
                pass
            return redirect(f"{reverse('core:settings')}?tab=pipeline")

        elif action == 'toggle_pipeline_stage':
            stage_id = request.POST.get('stage_id')
            stage = get_object_or_404(PipelineStage, pk=stage_id)
            if stage.is_system and stage.is_active:
                messages.error(request, f"'{stage.name}' is a system anchor stage and cannot be deactivated.")
            else:
                stage.is_active = not stage.is_active
                stage.save(update_fields=['is_active'])
                status = "Active" if stage.is_active else "Inactive"
                messages.success(request, f"Set '{stage.name}' to {status}.")
            return redirect(f"{reverse('core:settings')}?tab=pipeline")

        elif action == 'set_initial_pipeline_stage':
            stage_id = request.POST.get('stage_id')
            stage = get_object_or_404(PipelineStage, pk=stage_id)
            PipelineStage.objects.all().update(is_initial=False)
            stage.is_initial = True
            stage.save(update_fields=['is_initial'])
            messages.success(request, f"'{stage.name}' is now set as the default Initial Stage for new Solar Orders.")
            return redirect(f"{reverse('core:settings')}?tab=pipeline")

        elif action == 'delete_pipeline_stage':
            stage_id = request.POST.get('stage_id')
            reassign_to = request.POST.get('reassign_to')
            stage = get_object_or_404(PipelineStage, pk=stage_id)
            if stage.is_system:
                messages.error(request, f"'{stage.name}' is a core system stage and cannot be deleted. You can rename or customize its colors.")
            else:
                active_count = stage.active_bookings_count()
                if active_count > 0:
                    if not reassign_to or reassign_to == stage.code:
                        messages.error(request, f"Cannot delete '{stage.name}' because {active_count} active project(s) are currently in this stage. Please select another stage to reassign them to.")
                        return redirect(f"{reverse('core:settings')}?tab=pipeline")
                    target_stage_obj = PipelineStage.objects.filter(code=reassign_to).first()
                    target_name = target_stage_obj.name if target_stage_obj else reassign_to
                    SolarBooking.objects.filter(stage=stage.code, is_cancelled=False).update(stage=reassign_to)
                    messages.info(request, f"Reassigned {active_count} booking(s) to '{target_name}'.")
                name = stage.name
                stage.delete()
                # Re-normalize ordering
                for i, s in enumerate(PipelineStage.objects.all().order_by('order', 'id'), start=1):
                    if s.order != i:
                        s.order = i
                        s.save(update_fields=['order'])
                messages.success(request, f"Pipeline stage '{name}' removed successfully.")
            return redirect(f"{reverse('core:settings')}?tab=pipeline")

        return redirect('core:settings')


class CatalogItemAjaxView(LoginRequiredMixin, View):
    """API endpoint to fetch or add master catalog items directly from forms"""
    def get(self, request):
        category = request.GET.get('category')
        if not category:
            return JsonResponse({'status': 'error', 'message': 'Category is required'}, status=400)
        items = CatalogItem.get_active_choices(category)
        return JsonResponse({'status': 'success', 'items': items})

    def post(self, request):
        category = request.POST.get('category', '').strip()
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not category or not name:
            return JsonResponse({'status': 'error', 'message': 'Category and Name are required.'}, status=400)

        valid_categories = [c[0] for c in CatalogItem.CATEGORY_CHOICES]
        if category not in valid_categories:
            return JsonResponse({'status': 'error', 'message': f'Invalid category: {category}'}, status=400)

        item, created = CatalogItem.objects.get_or_create(
            category=category,
            name=name,
            defaults={'description': description or None, 'is_active': True}
        )
        if not created and not item.is_active:
            item.is_active = True
            item.save(update_fields=['is_active'])

        logger.info("Catalog item '%s' (%s) saved via AJAX by %s", name, category, request.user)
        return JsonResponse({
            'status': 'success',
            'created': created,
            'item': {
                'id': item.pk,
                'name': item.name,
                'category': item.category,
                'description': item.description or ''
            }
        })


class CatalogItemDeleteAjaxView(LoginRequiredMixin, View):
    """API endpoint to delete or deactivate a master catalog item via AJAX"""
    def post(self, request, pk):
        item = get_object_or_404(CatalogItem, pk=pk)
        name = item.name
        cat = item.category
        item.delete()
        logger.info("Catalog item '%s' (%s) deleted via AJAX by %s", name, cat, request.user)
        return JsonResponse({
            'status': 'success',
            'message': f"Removed '{name}' from catalog."
        })


class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        form = RegistrationForm()
        return render(request, 'core/register.html', {'form': form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            logger.info("New user registered: %s (pending approval)", user.username)
            messages.success(
                request,
                f"Registration submitted for @{user.username}! Your account is pending administrator approval before you can sign in."
            )
            return redirect('core:login')
        else:
            logger.warning("Registration validation failed: %s", form.errors.as_json())
            messages.error(request, "Please correct the highlighted errors in the registration form.")
            return render(request, 'core/register.html', {'form': form})


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:dashboard')
        form = AuthenticationForm()
        return render(request, 'core/login.html', {'form': form})

    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Check user directly for custom status messages
        user_match = User.objects.filter(username__iexact=username).first()

        if user_match and user_match.check_password(password):
            profile = getattr(user_match, 'profile', None)
            if profile and profile.status == UserProfile.STATUS_PENDING:
                messages.warning(
                    request,
                    f"Account @{user_match.username} is currently pending administrator approval. "
                    "You will be able to log in as soon as an administrator approves your account."
                )
                form = AuthenticationForm(request)
                return render(request, 'core/login.html', {
                    'form': form,
                    'is_pending_approval': True,
                    'entered_username': username,
                })
            elif profile and profile.status == UserProfile.STATUS_REJECTED:
                reason = f" Reason: {profile.rejection_reason}" if profile.rejection_reason else ""
                messages.error(
                    request,
                    f"Account registration for @{user_match.username} was rejected.{reason} Please contact the system administrator."
                )
                form = AuthenticationForm(request)
                return render(request, 'core/login.html', {
                    'form': form,
                    'is_rejected': True,
                    'entered_username': username,
                })
            elif not user_match.is_active:
                messages.error(
                    request,
                    f"Account @{user_match.username} is currently deactivated. Please contact your administrator."
                )
                form = AuthenticationForm(request)
                return render(request, 'core/login.html', {'form': form, 'entered_username': username})
            else:
                login(request, user_match)
                messages.success(request, f"Welcome back, {user_match.first_name or user_match.username}!")
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect('core:dashboard')

        # Fallback to standard AuthenticationForm validation
        form = AuthenticationForm(request, data=request.POST)
        messages.error(request, "Invalid username or password. Please verify your credentials.")
        return render(request, 'core/login.html', {'form': form, 'entered_username': username})


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return redirect('core:login')

    def get(self, request):
        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return redirect('core:login')


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated

    def handle_no_permission(self):
        messages.error(self.request, "Access restricted to system administrators.")
        return redirect('core:dashboard')


class UserApprovalListView(StaffRequiredMixin, View):
    def get(self, request):
        pending_list = UserProfile.objects.filter(status=UserProfile.STATUS_PENDING).select_related('user').order_by('-created_at')
        approved_list = UserProfile.objects.filter(status=UserProfile.STATUS_APPROVED).select_related('user', 'approved_by').order_by('-approved_at', '-created_at')
        rejected_list = UserProfile.objects.filter(status=UserProfile.STATUS_REJECTED).select_related('user', 'approved_by').order_by('-created_at')

        tab = request.GET.get('tab', '')
        if not tab:
            tab = 'pending' if pending_list.exists() else 'approved'

        context = {
            'pending_profiles': pending_list,
            'approved_profiles': approved_list,
            'rejected_profiles': rejected_list,
            'count_pending': pending_list.count(),
            'count_approved': approved_list.count(),
            'count_rejected': rejected_list.count(),
            'active_tab': tab,
        }
        return render(request, 'core/user_approvals.html', context)


class UserApproveActionView(StaffRequiredMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(UserProfile, pk=pk)
        role = request.POST.get('role')
        grant_staff = request.POST.get('grant_staff') == '1'

        profile.status = UserProfile.STATUS_APPROVED
        profile.approved_by = request.user
        profile.approved_at = timezone.now()
        if role:
            valid_roles = [c[0] for c in UserProfile.get_role_choices()]
            if role in valid_roles:
                profile.role = role
        profile.save()

        user = profile.user
        user.is_active = True
        if grant_staff:
            user.is_staff = True
        user.save()

        messages.success(request, f"✓ Successfully approved and activated account @{user.username} ({user.get_full_name() or user.username}) as {profile.get_role_display()}!")
        return redirect('core:user_approvals')


class UserRejectActionView(StaffRequiredMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(UserProfile, pk=pk)
        reason = request.POST.get('reason', '').strip()

        profile.status = UserProfile.STATUS_REJECTED
        profile.approved_by = request.user
        profile.rejection_reason = reason
        profile.save()

        user = profile.user
        user.is_active = False
        user.save()

        messages.warning(request, f"Account registration for @{user.username} has been rejected.")
        return redirect('core:user_approvals')


class UserDeleteActionView(StaffRequiredMixin, View):
    def post(self, request, pk):
        profile = get_object_or_404(UserProfile, pk=pk)
        user = profile.user
        if user == request.user:
            messages.error(request, "You cannot delete your own account.")
            return redirect('core:user_approvals')

        username = user.username
        user.delete()
        messages.info(request, f"User @{username} and registration record were removed.")
        return redirect('core:user_approvals')


def get_unified_users_teams_context(request, default_tab='users'):
    from core.models import Team, TeamMember, UserProfile
    from core.forms import AdminUserCreateForm, TeamForm, TeamMemberForm
    from bookings.models import Task, SolarBooking
    from django.contrib.auth.models import User
    from decimal import Decimal

    tab = request.GET.get('tab', default_tab)
    if tab not in ['users', 'teams']:
        tab = default_tab

    # ---- USERS DATASET ----
    role_filter = request.GET.get('role', '')
    user_status_filter = request.GET.get('user_status', (request.GET.get('status', '') if tab == 'users' else ''))
    user_search_query = request.GET.get('user_q', (request.GET.get('q', '') if tab == 'users' else '')).strip()

    users_qs = User.objects.select_related('profile').order_by('-date_joined')

    if user_search_query:
        users_qs = users_qs.filter(
            Q(username__icontains=user_search_query) |
            Q(first_name__icontains=user_search_query) |
            Q(last_name__icontains=user_search_query) |
            Q(email__icontains=user_search_query)
        )

    if role_filter:
        users_qs = users_qs.filter(profile__role=role_filter)

    if user_status_filter == 'active':
        users_qs = users_qs.filter(is_active=True)
    elif user_status_filter == 'inactive':
        users_qs = users_qs.filter(is_active=False)

    users_list = []
    for u in users_qs:
        tasks = Task.objects.filter(assigned_to=u)
        u.num_total_tasks = tasks.count()
        u.num_pending_tasks = tasks.filter(is_completed=False).count()
        u.num_completed_tasks = tasks.filter(is_completed=True).count()
        users_list.append(u)

    user_form = AdminUserCreateForm()
    total_users_count = User.objects.count()
    active_users_count = User.objects.filter(is_active=True).count()

    # ---- TEAMS DATASET ----
    team_status_filter = request.GET.get('team_status', (request.GET.get('status', 'ALL') if tab == 'teams' else 'ALL'))
    period = request.GET.get('period', 'all_time')
    team_search_query = request.GET.get('team_q', (request.GET.get('q', '') if tab == 'teams' else '')).strip()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    now = timezone.now().date()
    start_date = None
    end_date = now

    if period == 'this_month':
        start_date = now.replace(day=1)
    elif period == 'this_quarter':
        quarter_month = 1 + 3 * ((now.month - 1) // 3)
        start_date = now.replace(month=quarter_month, day=1)
    elif period == 'this_year':
        start_date = now.replace(month=1, day=1)
    elif period == 'custom' and start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = None

    members_qs = TeamMember.objects.all().select_related('user')

    if team_status_filter == 'ACTIVE':
        members_qs = members_qs.filter(is_active=True)
    elif team_status_filter == 'INACTIVE':
        members_qs = members_qs.filter(is_active=False)

    if team_search_query:
        members_qs = members_qs.filter(
            Q(name__icontains=team_search_query) |
            Q(phone__icontains=team_search_query) |
            Q(email__icontains=team_search_query) |
            Q(designation__icontains=team_search_query) |
            Q(user__username__icontains=team_search_query)
        )

    members = list(members_qs)

    for m in members:
        m.perf = m.get_performance(date_from=start_date, date_to=end_date)

    all_members = TeamMember.objects.all()
    total_members_count = all_members.count()
    active_members_count = all_members.filter(is_active=True).count()

    crm_teams = list(Team.objects.all().prefetch_related('members').select_related('leader'))
    all_staff_users = list(User.objects.filter(is_active=True).select_related('profile').order_by('first_name', 'username'))
    team_create_form = TeamForm()

    teams_with_forms = []
    for t in crm_teams:
        teams_with_forms.append({
            'team': t,
            'edit_form': TeamForm(instance=t)
        })

    total_teams_count = len(crm_teams)
    active_teams_count = sum(1 for t in crm_teams if t.is_active)
    total_active_orders = sum(t.active_orders_count for t in crm_teams)
    total_kw_delivered = sum(float(t.total_kw_installed) for t in crm_teams)

    return {
        'active_tab': tab,
        # Users data
        'users': users_list,
        'form': user_form,
        'user_form': user_form,
        'role_choices': UserProfile.get_role_choices(),
        'current_role': role_filter,
        'current_status': user_status_filter,
        'current_q': user_search_query,
        'total_users': total_users_count,
        'active_users': active_users_count,
        # Teams data
        'teams': crm_teams,
        'teams_with_forms': teams_with_forms,
        'team_create_form': team_create_form,
        'total_teams_count': total_teams_count,
        'active_teams_count': active_teams_count,
        'total_active_orders': total_active_orders,
        'total_kw_delivered': total_kw_delivered,
        'members': members,
        'status_filter': team_status_filter,
        'period': period,
        'search_query': team_search_query,
        'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
        'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
        'total_members_count': total_members_count,
        'active_members_count': active_members_count,
        'member_form': TeamMemberForm(),
        'all_staff_users': all_staff_users,
    }


class TeamListView(LoginRequiredMixin, View):
    def get(self, request):
        context = get_unified_users_teams_context(request, default_tab='teams')
        return render(request, 'core/users_teams.html', context)


class TeamMemberDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        member = get_object_or_404(TeamMember, pk=pk)
        period = request.GET.get('period', 'all_time')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')

        now = timezone.now().date()
        start_date = None
        end_date = now

        if period == 'this_month':
            start_date = now.replace(day=1)
        elif period == 'this_quarter':
            quarter_month = 1 + 3 * ((now.month - 1) // 3)
            start_date = now.replace(month=quarter_month, day=1)
        elif period == 'this_year':
            start_date = now.replace(month=1, day=1)
        elif period == 'custom' and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = None

        perf = member.get_performance(date_from=start_date, date_to=end_date)

        context = {
            'member': member,
            'perf': perf,
            'period': period,
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
            'edit_form': TeamMemberForm(instance=member),
        }
        return render(request, 'core/team_detail.html', context)


class TeamMemberCreateView(LoginRequiredMixin, View):
    def post(self, request):
        form = TeamMemberForm(request.POST)
        if form.is_valid():
            member = form.save()
            messages.success(request, f"Team member '{member.name}' added successfully.")
            return redirect('core:team_detail', pk=member.pk)
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{err}")
            return redirect('core:team_list')


class TeamMemberUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        member = get_object_or_404(TeamMember, pk=pk)
        form = TeamMemberForm(request.POST, instance=member)
        if form.is_valid():
            member = form.save()
            messages.success(request, f"Team member '{member.name}' updated successfully.")
            return redirect('core:team_detail', pk=member.pk)
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{err}")
            return redirect('core:team_detail', pk=pk)


class TeamMemberDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        member = get_object_or_404(TeamMember, pk=pk)
        name = member.name
        member.delete()
        messages.info(request, f"Team member '{name}' has been removed.")
        return redirect('core:team_list')


class TeamMemberToggleActiveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        member = get_object_or_404(TeamMember, pk=pk)
        member.is_active = not member.is_active
        member.save()
        status_label = "Active" if member.is_active else "Inactive"
        messages.success(request, f"Status for '{member.name}' set to {status_label}.")
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('core:team_list')
        return redirect(next_url)


class TeamSyncUsersView(LoginRequiredMixin, View):
    """Syncs existing approved UserProfiles into TeamMember directory."""
    def post(self, request):
        approved_profiles = UserProfile.objects.filter(status=UserProfile.STATUS_APPROVED).select_related('user')
        synced_count = 0

        for prof in approved_profiles:
            u = prof.user
            full_name = f"{u.first_name} {u.last_name}".strip()
            display_name = full_name if full_name else u.username

            # Check if already linked or exists by name or user
            existing = TeamMember.objects.filter(Q(user=u) | Q(name__iexact=display_name)).first()
            if not existing:
                TeamMember.objects.create(
                    name=display_name,
                    user=u,
                    role='MEMBER',
                    designation=prof.get_role_display(),
                    phone=prof.phone or '',
                    email=u.email or '',
                    is_active=u.is_active
                )
                synced_count += 1
            else:
                # Update link if missing
                if not existing.user:
                    existing.user = u
                    existing.save()

        if synced_count > 0:
            messages.success(request, f"Successfully synced {synced_count} user accounts into Team directory.")
        else:
            messages.info(request, "All approved users are already synchronized with the Team directory.")
        return redirect('core:team_list')


# =============================================================================
# GLOBAL HTTP ERROR HANDLERS (404, 500, 403, 400, CSRF)
# =============================================================================

def custom_page_not_found_view(request, exception=None):
    """Custom 404 Handler for Page Not Found with Content-Negotiation"""
    logger.warning("404 Not Found: %s [Method: %s] User: %s", request.path, request.method, getattr(request, 'user', 'Anonymous'))
    is_json = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '') or
        '/api/' in request.path
    )
    if is_json:
        return JsonResponse({
            'status': 'error',
            'code': 404,
            'error': 'NotFound',
            'message': f"The requested resource '{request.path}' was not found on this server."
        }, status=404)
    return render(request, '404.html', {'path': request.path}, status=404)


def custom_server_error_view(request):
    """Custom 500 Handler for Internal Server Error with Content-Negotiation"""
    logger.error("500 Server Error: %s [Method: %s] User: %s", request.path, request.method, getattr(request, 'user', 'Anonymous'))
    is_json = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '') or
        '/api/' in request.path
    )
    if is_json:
        return JsonResponse({
            'status': 'error',
            'code': 500,
            'error': 'InternalServerError',
            'message': 'An unexpected server error occurred. Our engineering team has been notified.'
        }, status=500)
    return render(request, '500.html', status=500)


def custom_permission_denied_view(request, exception=None):
    """Custom 403 Handler for Permission Denied with Content-Negotiation"""
    logger.warning("403 Forbidden: %s [Method: %s] User: %s", request.path, request.method, getattr(request, 'user', 'Anonymous'))
    is_json = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '') or
        '/api/' in request.path
    )
    if is_json:
        return JsonResponse({
            'status': 'error',
            'code': 403,
            'error': 'PermissionDenied',
            'message': 'You do not have permission to view this resource or perform this operation.'
        }, status=403)
    return render(request, '403.html', {'exception': str(exception) if exception else None}, status=403)


def custom_bad_request_view(request, exception=None):
    """Custom 400 Handler for Bad Request with Content-Negotiation"""
    logger.warning("400 Bad Request: %s [Method: %s] User: %s", request.path, request.method, getattr(request, 'user', 'Anonymous'))
    is_json = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '') or
        '/api/' in request.path
    )
    if is_json:
        return JsonResponse({
            'status': 'error',
            'code': 400,
            'error': 'BadRequest',
            'message': 'The request was invalid or malformed.'
        }, status=400)
    return render(request, '400.html', {'exception': str(exception) if exception else None}, status=400)


def custom_csrf_failure_view(request, reason=""):
    """Custom CSRF Failure View with user guidance and Content-Negotiation"""
    logger.warning("403 CSRF Verification Failure: %s [Method: %s] Reason: %s", request.path, request.method, reason)
    is_json = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '') or
        '/api/' in request.path
    )
    if is_json:
        return JsonResponse({
            'status': 'error',
            'code': 403,
            'error': 'CSRFTokenExpired',
            'message': 'Security verification failed (CSRF token expired or missing). Please reload the page and try again.'
        }, status=403)
    return render(request, '403_csrf.html', {'reason': reason}, status=403)



class UserListView(StaffRequiredMixin, View):
    """
    Unified User & Team Management: Manage system accounts and operational crews.
    """
    def get(self, request):
        context = get_unified_users_teams_context(request, default_tab='users')
        return render(request, 'core/users_teams.html', context)


class UserCreateView(StaffRequiredMixin, View):
    """
    Create a new system user with designated role and permissions.
    """
    def post(self, request):
        from core.forms import AdminUserCreateForm
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"User account '{user.username}' created successfully.")
        else:
            first_err = next(iter(form.errors.values()))[0] if form.errors else "Invalid data provided."
            messages.error(request, f"Could not create user: {first_err}")
        return redirect('core:user_list')


class UserToggleActiveView(StaffRequiredMixin, View):
    """
    Toggle user active/inactive status.
    """
    def post(self, request, pk):
        from django.contrib.auth.models import User
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect('core:user_list')
        
        user.is_active = not user.is_active
        user.save()
        status_label = "activated" if user.is_active else "deactivated"
        messages.success(request, f"User '{user.username}' has been {status_label}.")
        return redirect('core:user_list')


class TeamCreateOperationalView(StaffRequiredMixin, View):
    """
    Create an operational Team (Alpha, Beta, Omega).
    """
    def post(self, request):
        from core.forms import TeamForm
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save()
            messages.success(request, f"Team '{team.name}' created successfully.")
        else:
            first_err = next(iter(form.errors.values()))[0] if form.errors else "Invalid data."
            messages.error(request, f"Could not create team: {first_err}")
        return redirect('core:team_list')


class TeamUpdateOperationalView(StaffRequiredMixin, View):
    """
    Update an operational Team (name, leader, members, description, active status).
    """
    def post(self, request, pk):
        from core.models import Team
        from core.forms import TeamForm
        team = get_object_or_404(Team, pk=pk)
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            team = form.save()
            messages.success(request, f"Team '{team.name}' updated successfully.")
        else:
            first_err = next(iter(form.errors.values()))[0] if form.errors else "Invalid data provided."
            messages.error(request, f"Could not update team: {first_err}")
        return redirect('core:team_list')


class TeamDeleteOperationalView(StaffRequiredMixin, View):
    """
    Delete an operational Team with optional project reassignment.
    """
    def post(self, request, pk):
        from core.models import Team
        from bookings.models import SolarBooking
        team = get_object_or_404(Team, pk=pk)
        name = team.name
        reassign_to_id = request.POST.get('reassign_to')
        active_count = team.active_orders_count

        if active_count > 0:
            if not reassign_to_id:
                messages.error(request, f"Cannot delete Team '{name}' because {active_count} active solar order(s) are currently assigned to it. Please select another team to reassign them to.")
                return redirect('core:team_list')
            new_team = get_object_or_404(Team, pk=reassign_to_id)
            # Reassign orders
            SolarBooking.objects.filter(assigned_team=team).update(assigned_team=new_team, assigned_team_driver=f"Team {new_team.name}")
            SolarBooking.objects.filter(assigned_team_driver__iexact=team.name).update(assigned_team=new_team, assigned_team_driver=f"Team {new_team.name}")
            messages.info(request, f"Reassigned {active_count} solar order(s) to Team '{new_team.name}'.")

        team.delete()
        messages.success(request, f"Team '{name}' deleted successfully.")
        return redirect('core:team_list')


class TeamOperationalDetailView(LoginRequiredMixin, View):
    """
    Dedicated Team Workspace / Detail View.
    Shows assigned solar orders, team members with active tasks, and delivery KPIs.
    """
    def get(self, request, pk):
        from core.models import Team
        from core.forms import TeamForm
        from bookings.models import SolarBooking, Task
        from decimal import Decimal

        team = get_object_or_404(Team.objects.prefetch_related('members').select_related('leader'), pk=pk)
        assigned_orders_qs = team.get_assigned_bookings().select_related('customer').order_by('-booking_date', '-id')

        # Financial & capacity totals
        active_orders_count = team.active_orders_count
        completed_orders_count = team.completed_orders_count
        total_kw = team.total_kw_installed
        total_rev = assigned_orders_qs.filter(is_cancelled=False).aggregate(s=Sum('booking_amount'))['s'] or Decimal('0.00')

        # Members data with user tasks
        members_list = []
        for u in team.members.all():
            tasks = Task.objects.filter(assigned_to=u)
            members_list.append({
                'user': u,
                'role': getattr(getattr(u, 'profile', None), 'get_role_display', lambda: 'Staff')(),
                'phone': getattr(getattr(u, 'profile', None), 'phone', ''),
                'email': u.email,
                'total_tasks': tasks.count(),
                'pending_tasks': tasks.filter(is_completed=False).count(),
                'completed_tasks': tasks.filter(is_completed=True).count(),
            })

        other_teams = Team.objects.exclude(pk=team.pk)
        edit_form = TeamForm(instance=team)
        all_staff_users = list(User.objects.filter(is_active=True).select_related('profile').order_by('first_name', 'username'))

        context = {
            'team': team,
            'edit_form': edit_form,
            'other_teams': other_teams,
            'orders': assigned_orders_qs,
            'members_list': members_list,
            'active_orders_count': active_orders_count,
            'completed_orders_count': completed_orders_count,
            'total_kw': total_kw,
            'total_rev': total_rev,
            'all_staff_users': all_staff_users,
        }
        return render(request, 'core/team_operational_detail.html', context)


class UserProfileView(LoginRequiredMixin, View):
    def get(self, request):
        user_id = request.GET.get('user_id')
        if user_id:
            user = get_object_or_404(User, pk=user_id)
        else:
            user = request.user

        profile, _ = UserProfile.objects.get_or_create(user=user)
        is_own_profile = (request.user == user)

        context = {
            'agent_user': user,
            'profile': profile,
            'is_own_profile': is_own_profile,
            'can_edit': is_own_profile or request.user.is_superuser,
        }
        return render(request, 'core/profile.html', context)
    def post(self, request):
        action = request.POST.get('action')
        user = request.user
        profile, _ = UserProfile.objects.get_or_create(user=user)

        if action == 'update_profile':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            designation = request.POST.get('designation', '').strip()
            bio = request.POST.get('bio', '').strip()
            remove_avatar = request.POST.get('remove_avatar') == '1'

            if not first_name:
                messages.error(request, "First Name is required.")
                return redirect('core:profile')

            # Check email uniqueness if email changed
            if email and User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, f"Email '{email}' is already taken by another account.")
                return redirect('core:profile')

            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.save()

            profile.phone = phone
            profile.designation = designation
            profile.bio = bio

            if remove_avatar and profile.avatar:
                try:
                    profile.avatar.delete(save=False)
                except Exception:
                    pass
                profile.avatar = None

            if 'avatar' in request.FILES:
                avatar_file = request.FILES['avatar']
                if profile.avatar:
                    try:
                        profile.avatar.delete(save=False)
                    except Exception:
                        pass
                profile.avatar = avatar_file

            profile.save()
            messages.success(request, "✓ Profile details and photo updated successfully!")
            return redirect('core:profile')

        elif action == 'change_password':
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not user.check_password(current_password):
                messages.error(request, "Current password is incorrect. Please try again.")
                return redirect('core:profile')

            if len(new_password) < 6:
                messages.error(request, "New password must be at least 6 characters long.")
                return redirect('core:profile')

            if new_password != confirm_password:
                messages.error(request, "New password and Confirm Password do not match.")
                return redirect('core:profile')

            user.set_password(new_password)
            user.save()

            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)

            messages.success(request, "✓ Password changed successfully! Your account security has been updated.")
            return redirect('core:profile')

        messages.warning(request, "Unknown action requested.")
        return redirect('core:profile')
