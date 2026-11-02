/**
 * Country Code Selector & Strict 10-Digit Phone Input Utility
 * Provides:
 *  1. Searchable Country Code Dropdown (type to search country name, code, alias or dial digits)
 *  2. Default: India (+91) with Flag
 *  3. Strict 10-Digit enforcement (only numbers, max 10 digits, real-time validation indicator)
 *  4. Form submit blocker if invalid phone number is entered
 */

(function(window, document) {
  'use strict';

  const COUNTRIES = [
    { name: "India", code: "IN", dial: "+91", flag: "🇮🇳", aliases: "india in bharat hindustan" },
    { name: "United Arab Emirates", code: "AE", dial: "+971", flag: "🇦🇪", aliases: "uae dubai emirates abu dhabi sharjah" },
    { name: "Saudi Arabia", code: "SA", dial: "+966", flag: "🇸🇦", aliases: "saudi ksa riyadh jeddah" },
    { name: "Qatar", code: "QA", dial: "+974", flag: "🇶🇦", aliases: "qatar doha" },
    { name: "Oman", code: "OM", dial: "+968", flag: "🇴🇲", aliases: "oman muscat" },
    { name: "Kuwait", code: "KW", dial: "+965", flag: "🇰🇼", aliases: "kuwait" },
    { name: "Bahrain", code: "BH", dial: "+973", flag: "🇧🇭", aliases: "bahrain manama" },
    { name: "United States", code: "US", dial: "+1", flag: "🇺🇸", aliases: "usa united states america" },
    { name: "United Kingdom", code: "GB", dial: "+44", flag: "🇬🇧", aliases: "uk united kingdom britain england london" },
    { name: "Canada", code: "CA", dial: "+1", flag: "🇨🇦", aliases: "canada" },
    { name: "Australia", code: "AU", dial: "+61", flag: "🇦🇺", aliases: "australia oz sydney melbourne" },
    { name: "Singapore", code: "SG", dial: "+65", flag: "🇸🇬", aliases: "singapore sg" },
    { name: "Malaysia", code: "MY", dial: "+60", flag: "🇲🇾", aliases: "malaysia kl" },
    { name: "Germany", code: "DE", dial: "+49", flag: "🇩🇪", aliases: "germany deutschland berlin" },
    { name: "France", code: "FR", dial: "+33", flag: "🇫🇷", aliases: "france paris" },
    { name: "Italy", code: "IT", dial: "+39", flag: "🇮🇹", aliases: "italy italia rome" },
    { name: "Spain", code: "ES", dial: "+34", flag: "🇪🇸", aliases: "spain espana madrid" },
    { name: "Netherlands", code: "NL", dial: "+31", flag: "🇳🇱", aliases: "netherlands holland amsterdam" },
    { name: "Switzerland", code: "CH", dial: "+41", flag: "🇨🇭", aliases: "switzerland swiss zurich geneva" },
    { name: "New Zealand", code: "NZ", dial: "+64", flag: "🇳🇿", aliases: "new zealand nz auckland" },
    { name: "South Africa", code: "ZA", dial: "+27", flag: "🇿🇦", aliases: "south africa za" },
    { name: "Sri Lanka", code: "LK", dial: "+94", flag: "🇱🇰", aliases: "sri lanka colombo" },
    { name: "Nepal", code: "NP", dial: "+977", flag: "🇳🇵", aliases: "nepal kathmandu" },
    { name: "Bangladesh", code: "BD", dial: "+880", flag: "🇧🇩", aliases: "bangladesh dhaka" },
    { name: "Maldives", code: "MV", dial: "+960", flag: "🇲🇻", aliases: "maldives male" },
    { name: "Philippines", code: "PH", dial: "+63", flag: "🇵🇭", aliases: "philippines manila" },
    { name: "Indonesia", code: "ID", dial: "+62", flag: "🇮🇩", aliases: "indonesia jakarta" },
    { name: "Thailand", code: "TH", dial: "+66", flag: "🇹🇭", aliases: "thailand bangkok" },
    { name: "Japan", code: "JP", dial: "+81", flag: "🇯🇵", aliases: "japan tokyo" },
    { name: "China", code: "CN", dial: "+86", flag: "🇨🇳", aliases: "china beijing" },
    { name: "Ireland", code: "IE", dial: "+353", flag: "🇮🇪", aliases: "ireland dublin" },
    { name: "Sweden", code: "SE", dial: "+46", flag: "🇸🇪", aliases: "sweden stockholm" },
    { name: "Norway", code: "NO", dial: "+47", flag: "🇳🇴", aliases: "norway oslo" },
    { name: "Turkey", code: "TR", dial: "+90", flag: "🇹🇷", aliases: "turkey turkiye istanbul ankara" },
    { name: "Egypt", code: "EG", dial: "+20", flag: "🇪🇬", aliases: "egypt cairo" },
    { name: "Nigeria", code: "NG", dial: "+234", flag: "🇳🇬", aliases: "nigeria lagos" },
    { name: "Kenya", code: "KE", dial: "+254", flag: "🇰🇪", aliases: "kenya nairobi" },
    { name: "Brazil", code: "BR", dial: "+55", flag: "🇧🇷", aliases: "brazil brasil sao paulo" },
    { name: "Mexico", code: "MX", dial: "+52", flag: "🇲🇽", aliases: "mexico mexico city" },
    { name: "Russia", code: "RU", dial: "+7", flag: "🇷🇺", aliases: "russia moscow" }
  ];

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Inject common CSS rules for country selector
  function injectStyles() {
    if (document.getElementById('country-phone-styles')) return;
    const style = document.createElement('style');
    style.id = 'country-phone-styles';
    style.textContent = `
      .country-code-dropdown-wrapper {
        display: flex;
        position: relative;
        z-index: 5;
        flex-shrink: 0;
      }
      .country-code-btn {
        border-top-right-radius: 0 !important;
        border-bottom-right-radius: 0 !important;
        border-color: #cbd5e1;
        background-color: #f8fafc;
        color: #1e293b;
        font-weight: 600;
        min-width: 86px;
        transition: all 0.15s ease;
      }
      .country-code-btn:hover,
      .country-code-btn:focus,
      .country-code-btn.show {
        background-color: #f1f5f9;
        border-color: #94a3b8;
        box-shadow: none;
      }
      .country-code-dropdown-wrapper + .form-control {
        border-top-left-radius: 0 !important;
        border-bottom-left-radius: 0 !important;
      }
      .country-code-menu {
        min-width: 290px;
        max-height: 350px;
        box-shadow: 0 14px 30px rgba(0,0,0,0.15);
        border: 1px solid #e2e8f0;
      }
      .country-item {
        transition: background-color 0.1s ease;
      }
      .country-item:hover {
        background-color: #f1f5f9;
      }
      .country-item.is-selected {
        background-color: #f0fdf4;
        color: #15803d;
        font-weight: 600;
      }
      .phone-digit-feedback {
        font-size: 0.75rem;
        line-height: 1.2;
      }
    `;
    document.head.appendChild(style);
  }

  function setupCountryPhone(inputEl) {
    if (!inputEl || inputEl.dataset.countryPhoneInitialized) return;
    inputEl.dataset.countryPhoneInitialized = "true";

    injectStyles();

    // 1. Enforce 10-digit input attributes
    inputEl.setAttribute('maxlength', '10');
    inputEl.setAttribute('inputmode', 'numeric');
    inputEl.setAttribute('autocomplete', 'tel-national');
    inputEl.setAttribute('pattern', '[0-9]{10}');
    if (!inputEl.placeholder || inputEl.placeholder.includes('+') || inputEl.placeholder.includes('555') || inputEl.placeholder.includes('John')) {
      inputEl.setAttribute('placeholder', '10-digit mobile number');
    }

    // Clean initial value to 10 digits
    if (inputEl.value) {
      inputEl.value = inputEl.value.replace(/\D/g, '').slice(0, 10);
    }

    // 2. Find or create wrapper input-group
    let inputGroup = inputEl.closest('.input-group');
    if (!inputGroup) {
      inputGroup = document.createElement('div');
      inputGroup.className = 'input-group';
      inputEl.parentNode.insertBefore(inputGroup, inputEl);
      inputGroup.appendChild(inputEl);
    }

    // Remove any static country code badges like "IN +91" or telephone icons immediately before input
    const prevSibling = inputEl.previousElementSibling;
    if (prevSibling && prevSibling.classList.contains('input-group-text')) {
      const txt = prevSibling.textContent.trim();
      if (txt.includes('+91') || txt.includes('IN') || prevSibling.querySelector('.bi-telephone')) {
        prevSibling.remove();
      }
    }

    // 3. Build Country Code Dropdown Elements
    const dropdownWrapper = document.createElement('div');
    dropdownWrapper.className = 'country-code-dropdown-wrapper dropdown';

    const defaultCountry = COUNTRIES[0]; // India (+91)
    const btnId = 'countryBtn_' + Math.random().toString(36).substr(2, 9);
    const menuId = 'countryMenu_' + Math.random().toString(36).substr(2, 9);

    dropdownWrapper.innerHTML = `
      <button type="button" class="btn btn-light border country-code-btn d-flex align-items-center justify-content-between px-2.5" id="${btnId}"
              data-bs-toggle="dropdown" data-bs-auto-close="outside" aria-expanded="false"
              style="font-size: 0.84rem; height: 100%;">
        <span class="selected-flag" style="font-size: 1.15rem; line-height: 1; margin-right: 4px;">${defaultCountry.flag}</span>
        <span class="selected-dial font-monospace me-1" style="font-size: 0.82rem;">${defaultCountry.dial}</span>
        <i class="bi bi-chevron-down text-muted" style="font-size: 0.65rem;"></i>
      </button>

      <div class="dropdown-menu country-code-menu shadow-lg rounded-3 p-2" id="${menuId}"
           style="z-index: 1070; font-size: 0.84rem; margin-top: 4px;">
        <!-- Search bar -->
        <div class="country-search-wrapper mb-2 position-relative">
          <i class="bi bi-search position-absolute text-muted" style="left: 10px; top: 50%; transform: translateY(-50%); font-size: 0.78rem;"></i>
          <input type="text" class="form-control form-control-sm ps-4 country-search-input" placeholder="Search country, code, e.g. UAE, 971, Saudi..." autocomplete="off" style="font-size: 0.8rem; border-radius: 6px;">
        </div>

        <!-- Scrollable Country List -->
        <div class="country-list-scroll overflow-auto" style="max-height: 230px;">
          <!-- Rendered dynamically -->
        </div>
      </div>
    `;

    // Hidden input for storing country code
    const hiddenCode = document.createElement('input');
    hiddenCode.type = 'hidden';
    hiddenCode.name = (inputEl.name || 'phone') + '_country_code';
    hiddenCode.value = defaultCountry.dial;
    dropdownWrapper.appendChild(hiddenCode);

    // Insert dropdown button before the input element in the input group
    inputGroup.insertBefore(dropdownWrapper, inputEl);

    // 4. Populate and filter Country List
    const countryListScroll = dropdownWrapper.querySelector('.country-list-scroll');
    const searchInput = dropdownWrapper.querySelector('.country-search-input');
    const triggerBtn = dropdownWrapper.querySelector('.country-code-btn');
    const flagSpan = dropdownWrapper.querySelector('.selected-flag');
    const dialSpan = dropdownWrapper.querySelector('.selected-dial');
    const menuEl = dropdownWrapper.querySelector('.country-code-menu');

    let currentSelectedDial = defaultCountry.dial;

    // Prevent menu close when clicking search or scrolling
    menuEl.addEventListener('click', function(e) {
      if (!e.target.closest('.country-item')) {
        e.stopPropagation();
      }
    });

    function renderCountryList(filterQuery) {
      const q = (filterQuery || '').trim().toLowerCase();
      let matches = COUNTRIES;
      if (q) {
        matches = COUNTRIES.filter(c => 
          c.name.toLowerCase().includes(q) ||
          c.dial.includes(q) ||
          c.dial.replace('+', '').includes(q) ||
          c.code.toLowerCase().includes(q) ||
          (c.aliases && c.aliases.toLowerCase().includes(q))
        );
      }

      if (matches.length === 0) {
        countryListScroll.innerHTML = `
          <div class="text-center py-3 text-muted small" style="font-size: 0.78rem;">
            <i class="bi bi-globe me-1"></i> No countries found for "${escapeHtml(q)}"
          </div>
        `;
        return;
      }

      let html = '';
      matches.forEach(c => {
        const isSelected = c.dial === currentSelectedDial;
        html += `
          <div class="country-item d-flex align-items-center justify-content-between p-1.5 px-2 rounded-2 cursor-pointer ${isSelected ? 'is-selected' : 'text-dark'}"
               data-dial="${c.dial}" data-flag="${c.flag}" data-name="${escapeHtml(c.name)}"
               style="cursor: pointer; margin-bottom: 2px;">
            <div class="d-flex align-items-center gap-2 overflow-hidden">
              <span style="font-size: 1.15rem; line-height: 1;">${c.flag}</span>
              <span class="text-truncate" style="font-size: 0.82rem;">${escapeHtml(c.name)}</span>
            </div>
            <span class="badge ${isSelected ? 'bg-success text-white' : 'bg-light text-secondary border'} font-monospace" style="font-size: 0.72rem; padding: 2px 6px;">
              ${c.dial}
            </span>
          </div>
        `;
      });
      countryListScroll.innerHTML = html;

      // Attach click listeners
      countryListScroll.querySelectorAll('.country-item').forEach(item => {
        item.addEventListener('click', function(e) {
          e.preventDefault();
          e.stopPropagation();
          const dial = this.getAttribute('data-dial');
          const flag = this.getAttribute('data-flag');
          currentSelectedDial = dial;
          flagSpan.textContent = flag;
          dialSpan.textContent = dial;
          hiddenCode.value = dial;

          // Close dropdown via bootstrap
          if (window.bootstrap && window.bootstrap.Dropdown) {
            const ddInstance = window.bootstrap.Dropdown.getOrCreateInstance(triggerBtn);
            if (ddInstance) ddInstance.hide();
          }

          // Focus phone input
          inputEl.focus();
        });
      });
    }

    renderCountryList('');

    // Filter on search typing
    searchInput.addEventListener('input', function() {
      renderCountryList(this.value);
    });

    // Auto-focus search input when dropdown is shown
    triggerBtn.addEventListener('shown.bs.dropdown', function() {
      searchInput.value = '';
      renderCountryList('');
      setTimeout(() => searchInput.focus(), 60);
    });

    // 5. Digit counter / feedback element
    const feedbackBox = document.createElement('div');
    feedbackBox.className = 'phone-digit-feedback mt-1';
    inputGroup.parentNode.insertBefore(feedbackBox, inputGroup.nextSibling);

    function updateDigitFeedback(val) {
      const len = val.length;
      if (len === 0) {
        feedbackBox.innerHTML = '';
        inputEl.classList.remove('is-valid', 'is-invalid');
      } else if (len === 10) {
        feedbackBox.innerHTML = `
          <span class="text-success fw-semibold d-inline-flex align-items-center gap-1">
            <i class="bi bi-check-circle-fill"></i> 10 digits entered
          </span>
        `;
        inputEl.classList.remove('is-invalid');
        inputEl.classList.add('is-valid');
      } else {
        feedbackBox.innerHTML = `
          <span class="text-muted d-inline-flex align-items-center gap-1">
            <span class="badge bg-light text-secondary border font-monospace" style="font-size: 0.68rem;">${len}/10</span>
            <span>Enter ${10 - len} more digits</span>
          </span>
        `;
        inputEl.classList.remove('is-valid');
      }
    }

    // 6. Strict Input Enforcement: ONLY Numbers, Max 10 digits
    inputEl.addEventListener('keydown', function(e) {
      // Allow navigation and shortcut keys
      const allowedKeys = ['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab', 'Home', 'End', 'Enter'];
      if (allowedKeys.includes(e.key) || e.ctrlKey || e.metaKey) {
        return;
      }
      // If not a digit 0-9, block keystroke
      if (!/^\d$/.test(e.key)) {
        e.preventDefault();
      }
      // If already 10 digits and no text is selected, block further typing
      if (this.value.length >= 10 && this.selectionStart === this.selectionEnd) {
        e.preventDefault();
      }
    });

    inputEl.addEventListener('input', function() {
      // Strip any accidental non-digits & clamp to 10
      this.value = this.value.replace(/\D/g, '').slice(0, 10);
      updateDigitFeedback(this.value);
    });

    inputEl.addEventListener('paste', function(e) {
      e.preventDefault();
      const pasted = (e.clipboardData || window.clipboardData).getData('text') || '';
      const digits = pasted.replace(/\D/g, '').slice(0, 10);
      this.value = digits;
      updateDigitFeedback(this.value);
    });

    inputEl.addEventListener('blur', function() {
      if (this.value.length > 0 && this.value.length < 10) {
        this.classList.add('is-invalid');
        feedbackBox.innerHTML = `
          <span class="text-danger fw-medium d-inline-flex align-items-center gap-1">
            <i class="bi bi-exclamation-triangle-fill"></i> Must be exactly 10 digits (${this.value.length}/10 entered)
          </span>
        `;
      }
    });

    // Form submit validation safeguard
    const form = inputEl.closest('form');
    if (form && !form.dataset.phoneSubmitValidated) {
      form.dataset.phoneSubmitValidated = "true";
      form.addEventListener('submit', function(e) {
        const phoneInputs = form.querySelectorAll('input[data-country-phone-initialized="true"]');
        for (const pInput of phoneInputs) {
          const val = pInput.value.replace(/\D/g, '');
          const isRequired = pInput.hasAttribute('required');
          if (isRequired && val.length !== 10) {
            e.preventDefault();
            pInput.focus();
            pInput.classList.add('is-invalid');
            alert('Please enter a valid 10-digit mobile number.');
            return false;
          }
          if (!isRequired && val.length > 0 && val.length !== 10) {
            e.preventDefault();
            pInput.focus();
            pInput.classList.add('is-invalid');
            alert('Phone number must be exactly 10 digits.');
            return false;
          }
        }
      });
    }

    // Initial check
    if (inputEl.value) {
      updateDigitFeedback(inputEl.value);
    }
  }

  // Global Auto-initialization
  function autoInitAllPhoneFields() {
    // 1. Inputs with data-country-phone
    document.querySelectorAll('[data-country-phone]').forEach(setupCountryPhone);

    // 2. Standard phone input IDs across the app
    const knownPhoneIds = [
      'customerPhoneInput',
      'customerAltPhoneInput',
      'id_phone',
      'id_alt_phone',
      'quick_customer_phone',
      'id_user_phone'
    ];

    knownPhoneIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) setupCountryPhone(el);
    });

    // 3. Any input with name="phone" or name="alt_phone"
    document.querySelectorAll('input[name="phone"], input[name="alt_phone"]').forEach(setupCountryPhone);
  }

  // Listen for modals opening (e.g. Quick Customer in Booking, Add User modal)
  document.addEventListener('shown.bs.modal', function() {
    autoInitAllPhoneFields();
  });

  // Run on DOMContentLoaded and export to window
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoInitAllPhoneFields);
  } else {
    autoInitAllPhoneFields();
  }

  window.SolarCountryPhone = {
    setup: setupCountryPhone,
    initAll: autoInitAllPhoneFields,
    COUNTRIES: COUNTRIES
  };

})(window, document);
