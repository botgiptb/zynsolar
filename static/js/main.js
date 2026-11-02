// Solar CRM Main JavaScript & Global Error Management System

// Global Toast Notification Utility
window.SolarToast = {
  show: function (message, type = 'info', title = '') {
    let container = document.getElementById('solarToastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'solarToastContainer';
      container.className = 'toast-container position-fixed top-0 end-0 p-3 pt-4';
      container.style.zIndex = '1095';
      document.body.appendChild(container);
    }

    const toastId = 'toast_' + Math.random().toString(36).substring(2, 9);
    const icons = {
      success: '<i class="bi bi-check-circle-fill text-success fs-5"></i>',
      danger: '<i class="bi bi-exclamation-octagon-fill text-danger fs-5"></i>',
      error: '<i class="bi bi-exclamation-octagon-fill text-danger fs-5"></i>',
      warning: '<i class="bi bi-exclamation-triangle-fill text-warning fs-5"></i>',
      info: '<i class="bi bi-info-circle-fill text-primary fs-5"></i>'
    };
    const titles = {
      success: 'Success',
      danger: 'Error Encountered',
      error: 'Error',
      warning: 'Attention',
      info: 'Notification'
    };

    const normalizedType = type === 'error' ? 'danger' : type;
    const icon = icons[normalizedType] || icons.info;
    const headerTitle = title || titles[normalizedType] || 'Notice';

    const toastHtml = `
      <div id="${toastId}" class="toast align-items-center shadow-lg border-0 mb-2 rounded-3 bg-white" role="alert" aria-live="assertive" aria-atomic="true" style="min-width: 320px; max-width: 440px; border-left: 4px solid ${normalizedType === 'danger' ? '#ef4444' : normalizedType === 'success' ? '#10b981' : normalizedType === 'warning' ? '#f59e0b' : '#3b82f6'} !important;">
        <div class="d-flex align-items-start p-3">
          <div class="me-2.5 flex-shrink-0 mt-0.5">${icon}</div>
          <div class="flex-grow-1 me-2 overflow-hidden">
            <div class="fw-bold text-dark small mb-0.5">${headerTitle}</div>
            <div class="text-secondary small text-break" style="font-size: 0.82rem; line-height: 1.4;">${message}</div>
          </div>
          <button type="button" class="btn-close ms-auto flex-shrink-0" data-bs-dismiss="toast" aria-label="Close" style="font-size: 0.75rem;"></button>
        </div>
      </div>
    `;

    container.insertAdjacentHTML('beforeend', toastHtml);
    const toastEl = document.getElementById(toastId);
    if (toastEl && window.bootstrap && window.bootstrap.Toast) {
      const bsToast = new bootstrap.Toast(toastEl, { delay: 5000 });
      toastEl.addEventListener('hidden.bs.toast', function () {
        toastEl.remove();
      });
      bsToast.show();
    }
  },
  success: function (msg, title = 'Success') { this.show(msg, 'success', title); },
  error: function (msg, title = 'Error Encountered') { this.show(msg, 'danger', title); },
  warning: function (msg, title = 'Attention') { this.show(msg, 'warning', title); },
  info: function (msg, title = 'Notice') { this.show(msg, 'info', title); }
};

document.addEventListener('DOMContentLoaded', function () {
  // 1. Sidebar Toggle (Desktop Collapse & Mobile Drawer)
  const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
  const sidebar = document.getElementById('appSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');

  // Sidebar Tooltip System for Collapsed State
  let sidebarTooltips = [];
  function refreshSidebarTooltips() {
    if (!sidebar || !window.bootstrap || !window.bootstrap.Tooltip) return;
    sidebarTooltips.forEach(t => {
      try { t.dispose(); } catch (e) {}
    });
    sidebarTooltips = [];

    const isCollapsed = sidebar.classList.contains('collapsed');
    if (isCollapsed && window.innerWidth >= 992) {
      const navLinks = sidebar.querySelectorAll('.nav-link-custom[title]');
      navLinks.forEach(link => {
        const titleText = link.getAttribute('title') || '';
        if (titleText) {
          const t = new bootstrap.Tooltip(link, {
            placement: 'right',
            boundary: 'viewport',
            trigger: 'hover'
          });
          sidebarTooltips.push(t);
        }
      });
    }
  }

  if (sidebarToggleBtn && sidebar) {
    sidebarToggleBtn.addEventListener('click', function () {
      if (window.innerWidth < 992) {
        sidebar.classList.toggle('show-mobile');
        if (backdrop) backdrop.classList.toggle('show');
      } else {
        sidebar.classList.toggle('collapsed');
        const isCollapsed = sidebar.classList.contains('collapsed');
        if (isCollapsed) {
          document.documentElement.classList.add('sidebar-collapsed');
          localStorage.setItem('solar_crm_sidebar_collapsed', '1');
        } else {
          document.documentElement.classList.remove('sidebar-collapsed');
          localStorage.setItem('solar_crm_sidebar_collapsed', '0');
        }
        refreshSidebarTooltips();
      }
    });
  }

  // Handle Reports accordion click when sidebar is collapsed (navigate cleanly to reports dashboard)
  const navReportsToggle = document.getElementById('navReportsToggle');
  if (navReportsToggle) {
    navReportsToggle.addEventListener('click', function (e) {
      const isCollapsed = sidebar && (sidebar.classList.contains('collapsed') || document.documentElement.classList.contains('sidebar-collapsed'));
      if (isCollapsed && window.innerWidth >= 992) {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = '/reports/';
      }
    });
  }

  // Handle Settings accordion click when sidebar is collapsed (navigate cleanly to settings page)
  const navSettingsToggle = document.getElementById('navSettingsToggle');
  if (navSettingsToggle) {
    navSettingsToggle.addEventListener('click', function (e) {
      const isCollapsed = sidebar && (sidebar.classList.contains('collapsed') || document.documentElement.classList.contains('sidebar-collapsed'));
      if (isCollapsed && window.innerWidth >= 992) {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = '/settings/';
      }
    });
  }

  if (backdrop) {
    backdrop.addEventListener('click', function () {
      sidebar.classList.remove('show-mobile');
      backdrop.classList.remove('show');
    });
  }

  // Restore desktop sidebar collapse preference
  if (window.innerWidth >= 992 && localStorage.getItem('solar_crm_sidebar_collapsed') === '1' && sidebar) {
    sidebar.classList.add('collapsed');
  }
  refreshSidebarTooltips();
  window.addEventListener('resize', refreshSidebarTooltips);

  // 2. Auto calculation for Booking Amount & Advance Payment -> Balance Amount
  const bookingAmtInput = document.getElementById('id_booking_amount');
  const advanceAmtInput = document.getElementById('id_advance_payment');
  const balanceDisplay = document.getElementById('calculated_balance_display');

  function updateBalance() {
    if (!bookingAmtInput) return;
    const total = parseFloat(bookingAmtInput.value) || 0;
    const advance = parseFloat(advanceAmtInput ? advanceAmtInput.value : 0) || 0;
    const balance = Math.max(0, total - advance);

    if (balanceDisplay) {
      balanceDisplay.textContent = '₹ ' + balance.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
  }

  if (bookingAmtInput) {
    bookingAmtInput.addEventListener('input', updateBalance);
  }
  if (advanceAmtInput) {
    advanceAmtInput.addEventListener('input', updateBalance);
    updateBalance();
  }

  // 3. Quick Create Customer AJAX handling (for fallback forms without combobox)
  const quickCustomerForm = document.getElementById('quickCustomerForm');
  const customerSelect = document.getElementById('id_customer_select');
  const quickCustModalEl = document.getElementById('quickCustomerModal');

  if (quickCustomerForm && customerSelect && !document.getElementById('customerCombobox')) {
    quickCustomerForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const submitBtn = quickCustomerForm.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';

      const formData = new FormData(quickCustomerForm);

      fetch('/customers/api/quick-create/', {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      })
      .then(res => res.json())
      .then(data => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;

        if (data.status === 'success') {
          // Add new option to select
          const newOption = new Option(`${data.customer.name} (${data.customer.customer_id} - ${data.customer.phone})`, data.customer.id, true, true);
          customerSelect.add(newOption, undefined);
          customerSelect.value = data.customer.id;

          // Close modal
          if (quickCustModalEl) {
            const modalInstance = bootstrap.Modal.getInstance(quickCustModalEl);
            if (modalInstance) modalInstance.hide();
          }

          // Trigger change event
          customerSelect.dispatchEvent(new Event('change'));

          // Notification toast
          SolarToast.success(`Customer "${data.customer.name}" created and selected!`);
          quickCustomerForm.reset();
        } else {
          SolarToast.error(data.message || 'Error creating customer.', 'Validation Error');
        }
      })
      .catch(err => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
        SolarToast.error('A server or network error occurred while creating the customer.', 'Connection Error');
        console.error('Quick customer registration error:', err);
      });
    });
  }

  // 4. Auto dismiss Django banner alerts after 6 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      try {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        if (bsAlert) bsAlert.close();
      } catch (e) {
        // Element may have already been dismissed
      }
    }, 6000);
  });
});
