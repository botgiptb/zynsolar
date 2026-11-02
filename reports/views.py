import csv
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.shortcuts import render
from django.views import View
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin

from bookings.models import SolarBooking
from customers.models import Customer
from core.models import CompanySetting, TeamMember

logger = logging.getLogger(__name__)

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


class ReportDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        from bookings.models import PipelineStage

        report_type = request.GET.get('report_type', 'all')
        date_preset = request.GET.get('preset', 'this_month')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        salesperson_filter = request.GET.get('salesperson')
        city_filter = request.GET.get('city')

        now = timezone.now().date()
        start_date = None
        end_date = now

        # Preset date calculation
        if date_preset == 'today':
            start_date = now
        elif date_preset == 'this_week':
            start_date = now - timedelta(days=now.weekday())
        elif date_preset == 'this_month':
            start_date = now.replace(day=1)
        elif date_preset == 'last_month':
            first_day_current_month = now.replace(day=1)
            last_day_prev_month = first_day_current_month - timedelta(days=1)
            start_date = last_day_prev_month.replace(day=1)
            end_date = last_day_prev_month
        elif date_preset == 'this_year':
            start_date = now.replace(month=1, day=1)
        elif date_preset == 'all_time':
            start_date = None
        elif date_preset == 'custom' and start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                start_date = now.replace(day=1)

        # Base queries
        bookings_qs = SolarBooking.objects.select_related('customer').all()
        customers_qs = Customer.objects.all()

        if start_date:
            bookings_qs = bookings_qs.filter(booking_date__gte=start_date)
            customers_qs = customers_qs.filter(created_at__date__gte=start_date)
        if end_date:
            bookings_qs = bookings_qs.filter(booking_date__lte=end_date)
            customers_qs = customers_qs.filter(created_at__date__lte=end_date)

        if salesperson_filter:
            bookings_qs = bookings_qs.filter(assigned_salesperson=salesperson_filter)

        if city_filter:
            bookings_qs = bookings_qs.filter(customer__city__iexact=city_filter)
            customers_qs = customers_qs.filter(city__iexact=city_filter)

        # Core Financial & Operational KPIs
        total_bookings_count = bookings_qs.count()

        financial_agg = bookings_qs.filter(is_cancelled=False).aggregate(
            total_val=Sum('booking_amount'),
            total_adv=Sum('advance_payment'),
            total_final=Sum('final_payment_received'),
            total_bal=Sum('balance_amount'),
            avg_val=Avg('booking_amount'),
            total_kw=Sum('system_capacity_kw')
        )

        total_value = financial_agg['total_val'] or Decimal('0.00')
        total_advance = financial_agg['total_adv'] or Decimal('0.00')
        total_final = financial_agg['total_final'] or Decimal('0.00')
        total_collected = total_advance + total_final
        total_balance = financial_agg['total_bal'] or Decimal('0.00')
        total_kw = financial_agg['total_kw'] or Decimal('0.00')
        collection_rate = round((total_collected / total_value) * 100, 1) if total_value > 0 else 0.0

        total_customers = customers_qs.count()

        # Dynamic stages lookup for orders list (supports custom stages seamlessly)
        stages_map = {s.code: s for s in PipelineStage.objects.all()}
        bookings_list = list(bookings_qs.order_by('-booking_date')[:60])
        for b in bookings_list:
            stage_obj = stages_map.get(b.stage)
            if stage_obj:
                b.stage_display_name = stage_obj.name
                b.stage_display_color = stage_obj.color
            else:
                b.stage_display_name = b.stage.replace('_', ' ').title()
                b.stage_display_color = '#64748b'

        # City distribution
        city_distribution = bookings_qs.values('customer__city').annotate(
            booking_count=Count('id'),
            total_value=Sum('booking_amount')
        ).order_by('-booking_count')[:10]

        # Filter dropdown lists
        all_salespersons = SolarBooking.objects.values_list('assigned_salesperson', flat=True).distinct().order_by('assigned_salesperson')
        # Clean distinct non-empty cities with case normalization
        raw_cities = Customer.objects.exclude(city='').exclude(city__isnull=True).values_list('city', flat=True).distinct()
        cities_dict = {}
        for c in raw_cities:
            if c and c.strip():
                clean_c = c.strip()
                c_key = clean_c.lower()
                if c_key not in cities_dict:
                    cities_dict[c_key] = clean_c.title()
        all_cities = sorted(cities_dict.values())

        context = {
            'report_type': report_type,
            'preset': date_preset,
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else '',
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else '',
            'salesperson_filter': salesperson_filter,
            'city_filter': city_filter,
            
            # 4 Core KPI Cards
            'total_bookings_count': total_bookings_count,
            'total_value': total_value,
            'total_collected': total_collected,
            'collection_rate': collection_rate,
            'total_balance': total_balance,
            'total_kw': total_kw,
            'total_customers': total_customers,

            # Data lists & groupings
            'bookings': bookings_list,
            'city_distribution': city_distribution,

            # Dropdowns
            'all_salespersons': all_salespersons,
            'all_cities': all_cities,
        }
        return render(request, 'reports/report_dashboard.html', context)



class ExportCSVReportView(LoginRequiredMixin, View):
    def get(self, request):
        report_type = request.GET.get('type', 'bookings')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="solar_crm_{report_type}_report_{timezone.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)

        if report_type == 'customers':
            writer.writerow(['Customer ID', 'Name', 'Phone', 'Email', 'Customer Type', 'City', 'State', 'Address', 'Status', 'Registered Date'])
            for c in Customer.objects.all().order_by('-created_at'):
                writer.writerow([c.customer_id, c.name, c.phone, c.email or '', c.get_customer_type_display(), c.city, c.state, c.full_address, c.status, c.created_at.strftime('%Y-%m-%d')])
        else:
            writer.writerow(['Booking Ref', 'Customer Name', 'Phone', 'City', 'Capacity (kW)', 'Panel Type', 'Stage', 'Is Cancelled', 'Booking Amount', 'Advance Payment', 'Balance Amount', 'Booking Date', 'Salesperson', 'Team/Driver', 'Expected Completion'])
            for b in SolarBooking.objects.select_related('customer').all().order_by('-booking_date'):
                writer.writerow([
                    b.booking_ref, b.customer.name, b.customer.phone, b.customer.city,
                    b.system_capacity_kw, b.panel_type, b.get_stage_display(),
                    'Yes' if b.is_cancelled else 'No',
                    b.booking_amount, b.advance_payment, b.balance_amount,
                    b.booking_date.strftime('%Y-%m-%d') if b.booking_date else '',
                    b.assigned_salesperson, b.assigned_team_driver,
                    b.expected_completion_date.strftime('%Y-%m-%d') if b.expected_completion_date else ''
                ])

        return response


class ExportExcelReportView(LoginRequiredMixin, View):
    def get(self, request):
        if not OPENPYXL_AVAILABLE:
            return HttpResponse("openpyxl library is required for Excel export.", status=500)

        wb = openpyxl.Workbook()
        
        # Style presets
        header_fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=15, bold=True, color="0F172A")
        sub_font = Font(name="Calibri", size=10, italic=True, color="64748B")

        # 1. Bookings Sheet
        ws_bookings = wb.active
        ws_bookings.title = "Solar Bookings"
        
        ws_bookings.append(["HELIOS SOLAR CRM - COMPREHENSIVE BOOKINGS REPORT"])
        ws_bookings.append([f"Generated on {timezone.now().strftime('%Y-%m-%d %H:%M')}"])
        ws_bookings.append([]) # empty row
        
        headers_b = [
            "Booking Ref", "Customer Name", "Customer Phone", "City", "Capacity (kW)", 
            "Panel Type", "Stage", "Status", "Total Amount (₹)", "Advance Paid (₹)", 
            "Balance (₹)", "Booking Date", "Salesperson", "Installation Team / Driver", "Expected Completion"
        ]
        ws_bookings.append(headers_b)

        # Style headers
        header_row_idx = 4
        for col_idx in range(1, len(headers_b) + 1):
            cell = ws_bookings.cell(row=header_row_idx, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for b in SolarBooking.objects.select_related('customer').all().order_by('-booking_date'):
            status_text = "Cancelled" if b.is_cancelled else b.get_stage_display()
            ws_bookings.append([
                b.booking_ref,
                b.customer.name,
                b.customer.phone,
                b.customer.city,
                float(b.system_capacity_kw),
                b.panel_type,
                b.get_stage_display(),
                status_text,
                float(b.booking_amount),
                float(b.advance_payment),
                float(b.balance_amount),
                b.booking_date.strftime('%Y-%m-%d') if b.booking_date else '',
                b.assigned_salesperson,
                b.assigned_team_driver,
                b.expected_completion_date.strftime('%Y-%m-%d') if b.expected_completion_date else ''
            ])

        # Auto-adjust column widths
        for col in ws_bookings.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws_bookings.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # 2. Customers Sheet
        ws_cust = wb.create_sheet(title="Customers")
        headers_c = ["Customer ID", "Name", "Phone", "Email", "Type", "City", "State", "Address", "Status", "Registered Date"]
        ws_cust.append(["HELIOS SOLAR CRM - CUSTOMER DIRECTORY"])
        ws_cust.append([f"Generated on {timezone.now().strftime('%Y-%m-%d %H:%M')}"])
        ws_cust.append([])
        ws_cust.append(headers_c)

        for col_idx in range(1, len(headers_c) + 1):
            cell = ws_cust.cell(row=4, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for c in Customer.objects.all().order_by('-created_at'):
            ws_cust.append([
                c.customer_id,
                c.name,
                c.phone,
                c.email or '',
                c.get_customer_type_display(),
                c.city,
                c.state,
                c.full_address,
                c.status,
                c.created_at.strftime('%Y-%m-%d')
            ])

        for col in ws_cust.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws_cust.column_dimensions[col_letter].width = max(max_len + 3, 12)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="solar_crm_report_{timezone.now().strftime("%Y%m%d_%H%M")}.xlsx"'
        wb.save(response)
        return response


class PrintableReportView(LoginRequiredMixin, View):
    """Clean printable layout optimized for browser printing & PDF generation"""
    def get(self, request):
        now = timezone.now().date()
        bookings = SolarBooking.objects.select_related('customer').all().order_by('-booking_date')
        
        financials = bookings.filter(is_cancelled=False).aggregate(
            total_val=Sum('booking_amount'),
            total_adv=Sum('advance_payment'),
            total_bal=Sum('balance_amount'),
            total_kw=Sum('system_capacity_kw')
        )
        
        context = {
            'company': CompanySetting.get_settings(),
            'generation_date': timezone.now(),
            'bookings': bookings,
            'total_bookings': bookings.count(),
            'active_count': bookings.filter(is_cancelled=False).count(),
                        'cancelled_count': bookings.filter(is_cancelled=True).count(),
            'financials': financials,
        }
        return render(request, 'reports/printable_report.html', context)


class StaffPerformanceReportView(LoginRequiredMixin, View):
    """
    Staff Performance Report: Consolidated sales executive directory, orders booked,
    contracted solar capacity (kW), commercial revenue, active tasks, and last login.
    No hardcoded status names or irrelevant completion rates.
    """
    def get(self, request):
        from django.contrib.auth.models import User
        from bookings.models import Task, SolarBooking
        
        users_qs = User.objects.filter(is_active=True).select_related('profile').order_by('first_name', 'username')
        
        staff_data = []
        total_orders_booked = 0
        total_capacity_kw = Decimal('0.00')
        total_pipeline_value = Decimal('0.00')
        total_active_tasks = 0
        
        from core.models import TeamMember

        for u in users_qs:
            name = u.get_full_name().strip()
            # Link to TeamMember Work Profile
            tm = TeamMember.objects.filter(user=u).first()
            if not tm:
                display_name = name if name else u.username
                tm = TeamMember.objects.filter(name__iexact=display_name).first()
            if not tm:
                display_name = name if name else u.username
                tm_role = u.profile.get_role_display() if hasattr(u, 'profile') and u.profile.role else ('Administrator' if u.is_superuser else 'Staff Agent')
                tm_phone = u.profile.phone if hasattr(u, 'profile') and u.profile.phone else ''
                tm = TeamMember.objects.create(
                    name=display_name,
                    user=u,
                    role='MEMBER',
                    designation=tm_role,
                    phone=tm_phone,
                    email=u.email or '',
                    is_active=u.is_active
                )
            elif not tm.user:
                tm.user = u
                tm.save(update_fields=['user'])
            q_filter = Q(created_by=u)
            if name:
                q_filter |= Q(assigned_salesperson__iexact=name)
            if u.username:
                q_filter |= Q(assigned_salesperson__iexact=u.username)
            q_filter |= Q(assigned_team__members=u)
            
            bookings = SolarBooking.objects.filter(q_filter, is_cancelled=False).distinct()
            orders_count = bookings.count()
            
            agg = bookings.aggregate(
                kw=Sum('system_capacity_kw'),
                val=Sum('booking_amount')
            )
            user_kw = agg['kw'] or Decimal('0.00')
            user_val = agg['val'] or Decimal('0.00')
            
            active_tasks = Task.objects.filter(assigned_to=u, is_completed=False).count()
            
            role = 'Staff Agent'
            avatar_url = None
            if hasattr(u, 'profile'):
                if u.profile.role:
                    role = u.profile.get_role_display()
                if u.profile.avatar:
                    try:
                        avatar_url = u.profile.avatar.url
                    except Exception:
                        avatar_url = None
            elif u.is_superuser:
                role = 'Administrator'
                
            staff_data.append({
                'user': u,
                'team_member': tm,
                'team_member_id': tm.pk,
                'role': role,
                'avatar_url': avatar_url,
                'orders_count': orders_count,
                'total_kw': user_kw,
                'total_value': user_val,
                'active_tasks': active_tasks,
                'last_login': u.last_login,
            })
            
            total_orders_booked += orders_count
            total_capacity_kw += user_kw
            total_pipeline_value += user_val
            total_active_tasks += active_tasks

        # Sort staff by total revenue descending
        staff_data.sort(key=lambda s: (s['total_value'], s['total_kw'], s['orders_count']), reverse=True)
            
        context = {
            'staff_list': staff_data,
            'total_staff': users_qs.count(),
            'total_orders_booked': total_orders_booked,
            'total_capacity_kw': total_capacity_kw,
            'total_pipeline_value': total_pipeline_value,
            'total_active_tasks': total_active_tasks,
        }
        return render(request, 'reports/staff_performance.html', context)



class TeamPerformanceReportView(LoginRequiredMixin, View):
    """
    Team Performance Report: Tracks operational teams (Alpha, Beta, Omega)
    assigned work, completed installations, and capacity delivered.
    """
    def get(self, request):
        from core.models import Team
        from bookings.models import SolarBooking
        
        teams = Team.objects.all().prefetch_related('members').select_related('leader')
        
        team_data = []
        total_orders = 0
        total_capacity_kw = Decimal('0.00')
        total_revenue = Decimal('0.00')
        
        for t in teams:
            orders = SolarBooking.objects.filter(assigned_team=t, is_cancelled=False)
            orders_count = orders.count()
            agg = orders.aggregate(kw=Sum('system_capacity_kw'), val=Sum('booking_amount'))
            kw = agg['kw'] or Decimal('0.00')
            val = agg['val'] or Decimal('0.00')
            
            total_orders += orders_count
            total_capacity_kw += kw
            total_revenue += val
            
            team_data.append({
                'team': t,
                'member_count': t.members.count(),
                'total_orders': orders_count,
                'total_kw': kw,
                'total_val': val,
            })
            
        context = {
            'team_list': team_data,
            'total_teams': teams.count(),
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_capacity_kw': total_capacity_kw,
        }
        return render(request, 'reports/team_performance.html', context)
