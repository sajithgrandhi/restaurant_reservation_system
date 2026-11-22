/**
 * L'Étoile Reserve - Restaurant Table Reservation System Frontend
 * Connects directly to Flask backend and MongoDB Database APIs.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global State
  let currentReservations = [];
  let systemIndexes = {};

  // DOM Elements
  const mongoBadge = document.getElementById('mongo-status-badge');
  const mongoStatusText = document.getElementById('mongo-status-text');
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  const reservationForm = document.getElementById('reservation-form');
  const btnCheckAvailability = document.getElementById('btn-check-availability');
  const availabilityBar = document.getElementById('availability-status');
  const btnSeedData = document.getElementById('btn-seed-data');
  const reservationsTbody = document.getElementById('reservations-tbody');
  const filterSearch = document.getElementById('filter-search');
  const filterStatus = document.getElementById('filter-status');
  const filterDatePreset = document.getElementById('filter-date-preset');
  const customDateContainer = document.getElementById('custom-date-container');
  const filterStartDate = document.getElementById('filter-start-date');
  const filterEndDate = document.getElementById('filter-end-date');
  const btnRefreshList = document.getElementById('btn-refresh-list');
  const btnRefreshAnalytics = document.getElementById('btn-refresh-analytics');

  // Edit Modal Elements
  const editModal = document.getElementById('edit-modal');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnCancelModal = document.getElementById('btn-cancel-modal');
  const editForm = document.getElementById('edit-reservation-form');
  const editErrorBanner = document.getElementById('edit-error-banner');

  // Set default reservation datetime to tomorrow at 19:00 local
  initDefaultDateTime();

  // --------------------------------------------------------------------------
  // Color Theme Switcher Logic
  // --------------------------------------------------------------------------
  const themeSelector = document.getElementById('theme-selector');
  const savedTheme = localStorage.getItem('restaurant_theme') || 'emerald';
  applyTheme(savedTheme);

  if (themeSelector) {
    themeSelector.value = savedTheme;
    themeSelector.addEventListener('change', (e) => {
      const selected = e.target.value;
      applyTheme(selected);
      localStorage.setItem('restaurant_theme', selected);
      const themeLabel = themeSelector.options[themeSelector.selectedIndex].text;
      showToast(`Color theme updated to ${themeLabel}!`, 'info');
    });
  }

  function applyTheme(themeName) {
    document.documentElement.setAttribute('data-theme', themeName);
    document.body.setAttribute('data-theme', themeName);
  }

  // Initialize
  checkSystemHealth();
  loadReservations();
  loadAnalytics();

  // --------------------------------------------------------------------------
  // Tab Switching
  // --------------------------------------------------------------------------
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-tab');
      document.getElementById(targetId).classList.add('active');

      if (targetId === 'tab-list') loadReservations();
      if (targetId === 'tab-analytics') loadAnalytics();
      if (targetId === 'tab-system') renderSystemIndexes();
    });
  });

  // --------------------------------------------------------------------------
  // Default Date & Time Setup
  // --------------------------------------------------------------------------
  function initDefaultDateTime() {
    const input = document.getElementById('reservation_time');
    const now = new Date();
    // Default: tomorrow at 19:00
    now.setDate(now.getDate() + 1);
    now.setHours(19, 0, 0, 0);

    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    input.value = `${year}-${month}-${day}T${hours}:${mins}`;
  }

  // --------------------------------------------------------------------------
  // Health & Connection Check
  // --------------------------------------------------------------------------
  async function checkSystemHealth() {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      if (data.connected) {
        mongoBadge.className = 'mongo-badge status-online';
        mongoStatusText.textContent = `MongoDB Online (v${data.version}) • ${data.document_count} docs`;
        systemIndexes = data.indexes || {};
        renderSystemIndexes();
      } else {
        mongoBadge.className = 'mongo-badge status-offline';
        mongoStatusText.textContent = 'MongoDB Offline (Check connection)';
      }
    } catch (err) {
      mongoBadge.className = 'mongo-badge status-offline';
      mongoStatusText.textContent = 'Backend Error';
    }
  }

  // --------------------------------------------------------------------------
  // Toast Notifications
  // --------------------------------------------------------------------------
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 4000);
  }

  // --------------------------------------------------------------------------
  // Real-Time Table Availability Checker
  // --------------------------------------------------------------------------
  btnCheckAvailability.addEventListener('click', async () => {
    const tableNumber = document.getElementById('table_number').value;
    const reservationTime = document.getElementById('reservation_time').value;
    const durationMinutes = document.getElementById('duration_minutes').value;

    if (!reservationTime) {
      showToast('Please select date and time first', 'warning');
      return;
    }

    try {
      btnCheckAvailability.disabled = true;
      btnCheckAvailability.textContent = 'Checking...';
      const params = new URLSearchParams({
        table_number: tableNumber,
        reservation_time: reservationTime,
        duration_minutes: durationMinutes,
      });

      const res = await fetch(`/api/reservations/check-availability?${params}`);
      const data = await res.json();

      availabilityBar.classList.remove('hidden', 'available', 'conflict');
      if (data.available) {
        availabilityBar.classList.add('available');
        availabilityBar.textContent = `✔ ${data.message} No overlapping intervals detected.`;
      } else {
        availabilityBar.classList.add('conflict');
        availabilityBar.textContent = `✖ ${data.message} Conflict with existing reservation.`;
      }
    } catch (err) {
      showToast('Error checking availability: ' + err.message, 'error');
    } finally {
      btnCheckAvailability.disabled = false;
      btnCheckAvailability.textContent = '🔍 Check Table Availability';
    }
  });

  // --------------------------------------------------------------------------
  // Create Reservation (Form Submit)
  // --------------------------------------------------------------------------
  reservationForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const payload = {
      customer_name: document.getElementById('customer_name').value.trim(),
      customer_email: document.getElementById('customer_email').value.trim(),
      customer_phone: document.getElementById('customer_phone').value.trim(),
      guests: parseInt(document.getElementById('guests').value, 10),
      table_number: parseInt(document.getElementById('table_number').value, 10),
      reservation_time: document.getElementById('reservation_time').value,
      duration_minutes: parseInt(document.getElementById('duration_minutes').value, 10),
      special_requests: document.getElementById('special_requests').value.trim(),
      status: 'confirmed',
    };

    const submitBtn = document.getElementById('btn-submit-booking');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving to MongoDB...';

    try {
      const res = await fetch('/api/reservations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (res.status === 201) {
        showToast(`🎉 Reservation saved! ID: ${data.data._id}`, 'success');
        reservationForm.reset();
        initDefaultDateTime();
        availabilityBar.classList.add('hidden');
        checkSystemHealth();
        loadReservations();
        loadAnalytics();
      } else if (res.status === 409) {
        // Double Booking Conflict
        availabilityBar.classList.remove('hidden', 'available');
        availabilityBar.classList.add('conflict');
        availabilityBar.textContent = `✖ ${data.message}`;
        showToast('Table already booked for that interval!', 'error');
      } else {
        // Schema Validation Error or other
        showToast(data.message || data.error || 'Validation error', 'error');
      }
    } catch (err) {
      showToast('Network error: ' + err.message, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Confirm & Save Reservation';
    }
  });

  // --------------------------------------------------------------------------
  // Seed Demo Data Button
  // --------------------------------------------------------------------------
  btnSeedData.addEventListener('click', async () => {
    btnSeedData.disabled = true;
    btnSeedData.textContent = 'Seeding MongoDB...';
    try {
      const res = await fetch('/api/seed', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        showToast(`Seed complete: ${data.details.inserted} new records, ${data.details.skipped} duplicates skipped.`, 'success');
        checkSystemHealth();
        loadReservations();
        loadAnalytics();
      } else {
        showToast('Seed error: ' + data.error, 'error');
      }
    } catch (err) {
      showToast('Error seeding data: ' + err.message, 'error');
    } finally {
      btnSeedData.disabled = false;
      btnSeedData.textContent = '🌱 Seed Demo Data';
    }
  });

  // --------------------------------------------------------------------------
  // Load & Filter Reservations (find() with $gte, $lt, and regex)
  // --------------------------------------------------------------------------
  async function loadReservations() {
    try {
      const params = new URLSearchParams();

      // Status Filter
      const statusVal = filterStatus.value;
      if (statusVal && statusVal !== 'all') {
        params.append('status', statusVal);
      }

      // Search Query
      const searchVal = filterSearch.value.trim();
      if (searchVal) {
        params.append('search', searchVal);
      }

      // Date Range Presets
      const datePreset = filterDatePreset.value;
      const now = new Date();
      if (datePreset === 'today') {
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
        const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 0);
        params.append('start_date', start.toISOString());
        params.append('end_date', end.toISOString());
      } else if (datePreset === 'tomorrow') {
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 0);
        const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 2, 0, 0, 0);
        params.append('start_date', start.toISOString());
        params.append('end_date', end.toISOString());
      } else if (datePreset === 'next7') {
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
        const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 7, 23, 59, 59);
        params.append('start_date', start.toISOString());
        params.append('end_date', end.toISOString());
      } else if (datePreset === 'custom') {
        if (filterStartDate.value) {
          params.append('start_date', new Date(filterStartDate.value).toISOString());
        }
        if (filterEndDate.value) {
          const endDateObj = new Date(filterEndDate.value);
          endDateObj.setDate(endDateObj.getDate() + 1); // Full day inclusion
          params.append('end_date', endDateObj.toISOString());
        }
      }

      const res = await fetch(`/api/reservations?${params}`);
      const json = await res.json();

      if (json.success) {
        currentReservations = json.data;
        renderReservationsTable(currentReservations);
      } else {
        reservationsTbody.innerHTML = `<tr><td colspan="8" class="text-center py-4" style="color:red;">Error: ${json.error}</td></tr>`;
      }
    } catch (err) {
      reservationsTbody.innerHTML = `<tr><td colspan="8" class="text-center py-4" style="color:red;">Failed to fetch reservations: ${err.message}</td></tr>`;
    }
  }

  // Render Table
  function renderReservationsTable(reservations) {
    if (!reservations || reservations.length === 0) {
      reservationsTbody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-4">No reservations match the selected filters.</td>
        </tr>
      `;
      return;
    }

    reservationsTbody.innerHTML = reservations.map(r => {
      const dt = new Date(r.reservation_time);
      const formattedDate = dt.toLocaleString(undefined, {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });

      const statusBadge = `<span class="badge badge-${r.status}">${r.status}</span>`;
      const tableBadge = `<span class="table-tag">T-${r.table_number}</span>`;

      return `
        <tr data-id="${r._id}">
          <td>
            <strong>${escapeHtml(r.customer_name)}</strong><br>
            <small style="color:var(--text-muted);">${escapeHtml(r.customer_email)} • ${escapeHtml(r.customer_phone)}</small>
          </td>
          <td>${tableBadge}</td>
          <td><strong>${r.guests}</strong> guests</td>
          <td>${formattedDate}</td>
          <td>${r.duration_minutes || 90} min</td>
          <td>${statusBadge}</td>
          <td><small>${escapeHtml(r.special_requests || '—')}</small></td>
          <td>
            <div class="action-group">
              ${r.status === 'confirmed' ? `<button class="btn-action btn-action-seat" onclick="quickUpdateStatus('${r._id}', 'seated')">Seat</button>` : ''}
              ${(r.status === 'confirmed' || r.status === 'seated') ? `<button class="btn-action btn-action-complete" onclick="quickUpdateStatus('${r._id}', 'completed')">Finish</button>` : ''}
              <button class="btn-action" onclick="openEditModal('${r._id}')">Edit</button>
              ${r.status !== 'cancelled' ? `<button class="btn-action btn-action-cancel" onclick="cancelReservation('${r._id}')">Cancel</button>` : ''}
              <button class="btn-action" style="color:#ef4444;" onclick="hardDeleteReservation('${r._id}')" title="Permanently delete from MongoDB">Del</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Filter Listeners
  filterSearch.addEventListener('input', debounce(loadReservations, 300));
  filterStatus.addEventListener('change', loadReservations);
  filterDatePreset.addEventListener('change', () => {
    if (filterDatePreset.value === 'custom') {
      customDateContainer.classList.remove('hidden');
    } else {
      customDateContainer.classList.add('hidden');
      loadReservations();
    }
  });
  filterStartDate.addEventListener('change', loadReservations);
  filterEndDate.addEventListener('change', loadReservations);
  btnRefreshList.addEventListener('click', loadReservations);

  // --------------------------------------------------------------------------
  // Quick Actions (Seat, Complete, Soft-Delete Cancel, Hard-Delete)
  // --------------------------------------------------------------------------
  window.quickUpdateStatus = async function(id, newStatus) {
    try {
      const res = await fetch(`/api/reservations/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Status updated to '${newStatus}'`, 'success');
        loadReservations();
        loadAnalytics();
      } else {
        showToast(data.message || 'Update failed', 'error');
      }
    } catch (err) {
      showToast('Error: ' + err.message, 'error');
    }
  };

  window.cancelReservation = async function(id) {
    const reason = prompt('Optional cancellation reason (e.g. guest called to cancel):');
    if (reason === null) return; // User pressed cancel on dialog

    try {
      const res = await fetch(`/api/reservations/${id}/cancel`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || 'Customer requested cancellation' }),
      });
      const data = await res.json();
      if (data.success) {
        showToast('Reservation cancelled (soft-delete). Table is now available for new bookings.', 'info');
        loadReservations();
        loadAnalytics();
      } else {
        showToast(data.message || 'Cancellation failed', 'error');
      }
    } catch (err) {
      showToast('Error cancelling: ' + err.message, 'error');
    }
  };

  window.hardDeleteReservation = async function(id) {
    if (!confirm('Are you sure you want to permanently delete this document from MongoDB?')) return;

    try {
      const res = await fetch(`/api/reservations/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        showToast('Document permanently deleted (delete_one).', 'info');
        checkSystemHealth();
        loadReservations();
        loadAnalytics();
      } else {
        showToast(data.message || 'Delete failed', 'error');
      }
    } catch (err) {
      showToast('Error deleting: ' + err.message, 'error');
    }
  };

  // --------------------------------------------------------------------------
  // Edit Modal Operations (update_one)
  // --------------------------------------------------------------------------
  window.openEditModal = function(id) {
    const res = currentReservations.find(r => r._id === id);
    if (!res) return;

    document.getElementById('edit-id').value = res._id;
    document.getElementById('edit-name').value = res.customer_name;
    document.getElementById('edit-email').value = res.customer_email;
    document.getElementById('edit-phone').value = res.customer_phone;
    document.getElementById('edit-guests').value = res.guests;
    document.getElementById('edit-table').value = res.table_number;
    document.getElementById('edit-duration').value = res.duration_minutes || 90;
    document.getElementById('edit-status').value = res.status;
    document.getElementById('edit-notes').value = res.special_requests || '';

    // Format datetime-local
    const dt = new Date(res.reservation_time);
    const localIso = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    document.getElementById('edit-time').value = localIso;

    editErrorBanner.classList.add('hidden');
    editModal.classList.remove('hidden');
  };

  function closeModal() {
    editModal.classList.add('hidden');
  }

  btnCloseModal.addEventListener('click', closeModal);
  btnCancelModal.addEventListener('click', closeModal);

  editForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('edit-id').value;

    const payload = {
      customer_name: document.getElementById('edit-name').value.trim(),
      customer_email: document.getElementById('edit-email').value.trim(),
      customer_phone: document.getElementById('edit-phone').value.trim(),
      guests: parseInt(document.getElementById('edit-guests').value, 10),
      table_number: parseInt(document.getElementById('edit-table').value, 10),
      reservation_time: document.getElementById('edit-time').value,
      duration_minutes: parseInt(document.getElementById('edit-duration').value, 10),
      status: document.getElementById('edit-status').value,
      special_requests: document.getElementById('edit-notes').value.trim(),
    };

    try {
      const res = await fetch(`/api/reservations/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (res.status === 200) {
        showToast('Reservation updated in MongoDB!', 'success');
        closeModal();
        loadReservations();
        loadAnalytics();
      } else if (res.status === 409) {
        editErrorBanner.classList.remove('hidden');
        editErrorBanner.textContent = `Double-booking conflict: ${data.message}`;
      } else {
        editErrorBanner.classList.remove('hidden');
        editErrorBanner.textContent = data.message || 'Validation error';
      }
    } catch (err) {
      editErrorBanner.classList.remove('hidden');
      editErrorBanner.textContent = 'Network error: ' + err.message;
    }
  });

  // --------------------------------------------------------------------------
  // MongoDB Aggregation Analytics ($group & $sort)
  // --------------------------------------------------------------------------
  async function loadAnalytics() {
    try {
      const res = await fetch('/api/analytics/summary');
      const data = await res.json();

      if (!data.success) return;

      // 1. Update KPI Cards
      document.getElementById('kpi-total').textContent = data.overall.total_bookings || 0;
      document.getElementById('kpi-guests').textContent = data.overall.total_guests || 0;
      document.getElementById('kpi-active').textContent = (data.overall.confirmed_bookings || 0) + (data.overall.seated_bookings || 0);
      document.getElementById('kpi-cancelled').textContent = data.overall.cancelled_bookings || 0;

      // 2. Render Status Aggregation Table
      const statusContainer = document.getElementById('analytics-status-table-container');
      if (data.by_status && data.by_status.length > 0) {
        statusContainer.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Reservations Count</th>
                <th>Total Guests</th>
              </tr>
            </thead>
            <tbody>
              ${data.by_status.map(s => `
                <tr>
                  <td><span class="badge badge-${s.status}">${s.status}</span></td>
                  <td><strong>${s.booking_count}</strong></td>
                  <td>${s.total_guests}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      } else {
        statusContainer.innerHTML = '<p class="text-center py-4">No aggregated status data yet.</p>';
      }

      // 3. Render Table Utilization Aggregation Table
      const tableContainer = document.getElementById('analytics-table-summary-container');
      if (data.by_table && data.by_table.length > 0) {
        tableContainer.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Table #</th>
                <th>Total Bookings</th>
                <th>Total Guests</th>
                <th>Confirmed</th>
                <th>Seated</th>
                <th>Completed</th>
                <th>Cancelled</th>
              </tr>
            </thead>
            <tbody>
              ${data.by_table.map(t => `
                <tr>
                  <td><span class="table-tag">Table ${t.table_number}</span></td>
                  <td><strong>${t.booking_count}</strong></td>
                  <td>${t.total_guests}</td>
                  <td>${t.confirmed_count}</td>
                  <td>${t.seated_count}</td>
                  <td>${t.completed_count}</td>
                  <td>${t.cancelled_count}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      } else {
        tableContainer.innerHTML = '<p class="text-center py-4">No table utilization data yet.</p>';
      }
    } catch (err) {
      console.error('Analytics aggregation error:', err);
    }
  }

  btnRefreshAnalytics.addEventListener('click', loadAnalytics);

  // --------------------------------------------------------------------------
  // Render System Indexes
  // --------------------------------------------------------------------------
  function renderSystemIndexes() {
    const container = document.getElementById('indexes-display-container');
    if (!systemIndexes || Object.keys(systemIndexes).length === 0) {
      container.innerHTML = '<p>Loading index metadata from MongoDB...</p>';
      return;
    }

    container.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Index Name</th>
            <th>Indexed Fields (Keys)</th>
            <th>Unique Constraint</th>
          </tr>
        </thead>
        <tbody>
          ${Object.entries(systemIndexes).map(([name, info]) => `
            <tr>
              <td><code>${name}</code></td>
              <td><code>${JSON.stringify(info.key)}</code></td>
              <td>${info.unique ? '✔ Yes' : 'No'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  // --------------------------------------------------------------------------
  // Utilities
  // --------------------------------------------------------------------------
  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }
});

