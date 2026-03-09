// ──────────────────────────────────────────────────────────────────────────
// naarad Dashboard — script.js
// ──────────────────────────────────────────────────────────────────────────

const BASE = window.location.origin;

// ── Status Indicators ────────────────────────────────────────────────────────
const localStatusEl = document.getElementById('local-status');
const syncStatusEl = document.getElementById('sync-status');
const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
let syncEnabled = false;

async function fetchSyncStatus() {
    try {
        const res = await fetch('/api/sync/status', { headers: getAuthHeaders() });
        if (res.ok) {
            const data = await res.json();
            syncEnabled = data.enabled;
        }
    } catch (e) { }

    if (localStatusEl) {
        localStatusEl.innerHTML = `<span class="live-dot" style="background:${isLocal ? '#facc15' : ''}"></span>
            ${isLocal ? 'Local Node' : 'Live Node'}`;
        localStatusEl.title = isLocal ? 'Running locally' : 'Running on public server';
    }

    if (syncStatusEl && syncEnabled) {
        syncStatusEl.style.display = 'inline-flex';
        syncStatusEl.innerHTML = `<span style="font-size:10px; margin-right:4px">☁️</span> Syncing`;
        syncStatusEl.classList.add('sync-active');
    }
}

async function triggerManualSync() {
    if (!syncEnabled) return;
    showToast('Background sync is running...', 'info');
    load();
}

// Update the Quick Embed snippet once we know the origin
const pixelUrlEl = document.getElementById('pixel-url');
if (pixelUrlEl) pixelUrlEl.textContent = BASE + '/track?id=recipient-id';

// ── State ──────────────────────────────────────────────────────────────────
let currentPage = 0;
const PAGE_SIZE = 50;
let totalTracks = 0;
let searchDebounceTimer = null;

// ── Search toggle ──────────────────────────────────────────────────────────
function toggleSearch() {
    const wrap = document.getElementById('search-wrap');
    const input = document.getElementById('search-q');
    wrap.classList.toggle('active');
    if (wrap.classList.contains('active')) setTimeout(() => input.focus(), 310);
}

document.addEventListener('click', e => {
    const wrap = document.getElementById('search-wrap');
    const input = document.getElementById('search-q');
    if (wrap && !wrap.contains(e.target) && wrap.classList.contains('active') && !input.value) {
        wrap.classList.remove('active');
    }
});

// Live search — debounced 350ms
const searchInput = document.getElementById('search-q');
if (searchInput) {
    searchInput.addEventListener('input', () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            currentPage = 0;
            load();
        }, 350);
    });
    searchInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') { clearTimeout(searchDebounceTimer); currentPage = 0; load(); }
        if (e.key === 'Escape') toggleSearch();
    });
}

// ── Skeleton loading helpers ───────────────────────────────────────────────
function showSkeleton() {
    const skeleton = `<tr class="skeleton-row">
        ${Array(7).fill('<td><div class="skeleton-line"></div></td>').join('')}
    </tr>`.repeat(5);
    const tbody = document.getElementById('tracks');
    if (tbody) tbody.innerHTML = skeleton;

    ['stat-unique', 'stat-opens', 'stat-clicks', 'stat-avg'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<span class="skeleton-val"></span>';
    });
}

function showError(message) {
    const tbody = document.getElementById('tracks');
    if (tbody) tbody.innerHTML = `
        <tr><td colspan="7">
            <div class="error-state">
                <div class="error-icon">⚠</div>
                <div class="error-msg">${esc(message)}</div>
                <button class="btn" id="btn-error-retry">Retry</button>
            </div>
        </td></tr>`;

    const retryBtn = document.getElementById('btn-error-retry');
    if (retryBtn) retryBtn.addEventListener('click', load);

    ['stat-unique', 'stat-opens', 'stat-clicks', 'stat-avg'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
    });
}

// Show a prominent auth prompt instead of a generic error
function showAuthPrompt() {
    const tbody = document.getElementById('tracks');
    if (tbody) tbody.innerHTML = `
        <tr><td colspan="7">
            <div class="error-state">
                <div class="error-icon" style="color:var(--text-muted); opacity:0.8; margin-bottom:0.5rem">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M2 18v3c0 .6.4 1 1 1h4v-3h3v-3h2l1.4-1.4a6.5 6.5 0 1 0-4-4Z"/>
                        <circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>
                    </svg>
                </div>
                <div class="error-msg">API key required to access the dashboard.</div>
                <div style="margin-top:0.5rem">
                    <button class="btn btn-primary" id="btn-auth-prompt-settings">Set API Key</button>
                </div>
                <p style="font-size:0.75rem; color:var(--text-muted); margin-top:1rem; max-width:400px; margin-left:auto; margin-right:auto;">
                    Your API key is printed in the server console when running in debug mode. 
                    Enter it via the Settings button above.
                </p>
            </div>
        </td></tr>`;

    // Bind the new button we just injected
    const authBtn = document.getElementById('btn-auth-prompt-settings');
    if (authBtn) authBtn.addEventListener('click', openSettingsModal);

    ['stat-unique', 'stat-opens', 'stat-clicks', 'stat-avg'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
    });
}

// ── Data Loading ───────────────────────────────────────────────────────────
async function load() {
    showSkeleton();
    try {
        const q = buildQuery();
        const [statsRes, tracksRes] = await Promise.all([
            fetch('/api/stats', { headers: getAuthHeaders() }),
            fetch(`/api/tracks?limit=${PAGE_SIZE}&offset=${currentPage * PAGE_SIZE}${q ? '&' + q : ''}`,
                { headers: getAuthHeaders() }),
        ]);

        if (!statsRes.ok || !tracksRes.ok) {
            const status = !statsRes.ok ? statsRes.status : tracksRes.status;
            if (status === 401) {
                showAuthPrompt(); // Better 401 UX
            } else {
                showError(`Server error (${status}). Check the console.`);
            }
            return;
        }

        const stats = await statsRes.json();
        const data = await tracksRes.json();

        // Stats
        document.getElementById('stat-unique').textContent = stats.summary?.total_unique ?? '-';
        document.getElementById('stat-opens').textContent = stats.summary?.total_opens ?? '-';
        document.getElementById('stat-clicks').textContent = stats.summary?.total_clicks ?? '-';
        document.getElementById('stat-avg').textContent = stats.summary?.avg_opens ?? '-';

        // Charts
        renderChart('countries', stats.geographic, 'country');
        renderChart('devices', stats.devices, 'device_type');
        renderChart('browsers', stats.browsers, 'browser');

        // Table
        window.loadedTracks = data.tracks || [];
        totalTracks = data.total ?? data.tracks?.length ?? 0;
        renderTracks(window.loadedTracks);

        const countEl = document.getElementById('track-count');
        if (countEl) countEl.textContent = `${totalTracks} total`;

        renderPagination();

    } catch (e) {
        console.error('Load failed:', e);
        showError('Could not connect to server. Is it running?');
    }
}

function getAuthHeaders() {
    const key = localStorage.getItem('naarad_api_key') || '';
    return key ? { 'X-API-Key': key } : {};
}

function buildQuery() {
    const q = document.getElementById('search-q')?.value?.trim();
    return q ? `q=${encodeURIComponent(q)}` : '';
}

// ── Charts ─────────────────────────────────────────────────────────────────
function renderChart(id, data, key) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!data?.length) { el.innerHTML = '<div class="empty">No data</div>'; return; }

    const max = Math.max(...data.map(d => d.count));
    const safeMax = max || 1;
    const shown = data.slice(0, 8);
    const more = data.length - shown.length;

    el.innerHTML = shown.map(d => `
        <div class="chart-row">
            <span title="${esc(String(d[key] || 'Unknown'))}">${esc(d[key] || 'Unknown')}</span>
            <div class="chart-bar"><div class="chart-fill" style="width:${(d.count / safeMax * 100).toFixed(1)}%"></div></div>
            <span>${d.count}</span>
        </div>
    `).join('') + (more > 0 ? `<div class="chart-more">+${more} more</div>` : '');
}

// ── Pagination ─────────────────────────────────────────────────────────────
function renderPagination() {
    const totalPages = Math.ceil(totalTracks / PAGE_SIZE);
    const el = document.getElementById('pagination');
    if (!el) return;

    if (totalPages <= 1) { el.innerHTML = ''; return; }

    el.innerHTML = `
        <button class="btn" onclick="goPage(${currentPage - 1})" ${currentPage === 0 ? 'disabled' : ''}>← Prev</button>
        <span class="page-info">Page ${currentPage + 1} / ${totalPages}</span>
        <button class="btn" onclick="goPage(${currentPage + 1})" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>Next →</button>
    `;
}

function goPage(n) {
    const totalPages = Math.ceil(totalTracks / PAGE_SIZE);
    currentPage = Math.max(0, Math.min(n, totalPages - 1));
    load();
}

// ── Table ──────────────────────────────────────────────────────────────────
function renderTracks(tracks) {
    const el = document.getElementById('tracks');
    if (!tracks?.length) {
        el.innerHTML = '<tr><td colspan="7" class="empty">No pixels tracked yet</td></tr>';
        return;
    }
    el.innerHTML = tracks.map(t => `
        <tr data-track-id="${esc(t.track_id)}" tabindex="0" role="button" aria-label="View details for ${esc(t.label || t.track_id)}">
            <td>
                <div style="font-weight:500; color:var(--text)">${esc(t.label || t.track_id)}</div>
                ${t.label ? `<div class="mono" style="color:var(--text-muted); font-size:0.7rem">${esc(t.track_id)}</div>` : ''}
            </td>
            <td style="color:var(--text-muted)">
                ${t.city ? `<span style="color:var(--text)">${esc(t.city)}</span>, ` : ''}${esc(t.country || '—')}
            </td>
            <td class="hide-mobile" style="color:var(--text-muted)">
                ${esc(t.device_type || '—')}${t.os ? ` / ${esc(t.os)}` : ''}
            </td>
            <td class="hide-mobile" style="color:var(--text-muted); font-size:0.75rem; max-width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap">
                ${esc(t.isp || t.org || '—')}
            </td>
            <td style="text-align:center">
                <span class="count-badge">
                    <span class="opens">${t.open_count ?? 0}</span>
                    <span class="sep">/</span>
                    <span class="clicks">${t.click_count ?? 0}</span>
                </span>
            </td>
            <td style="text-align:right; color:var(--text-muted); font-size:0.75rem"
                title="${t.last_seen ? new Date(t.last_seen).toLocaleString() : ''}">
                ${t.last_seen ? timeAgo(new Date(t.last_seen)) : '—'}
            </td>
            <td>
                <button class="row-action btn-delete-track" data-track-id="${esc(t.track_id)}" title="Delete pixel" aria-label="Delete pixel ${esc(t.track_id)}">
                    <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                </button>
            </td>
        </tr>
    `).join('');
}

// Event delegation for table clicks
document.getElementById('tracks').addEventListener('click', e => {
    // Handle delete button
    const deleteBtn = e.target.closest('.btn-delete-track');
    if (deleteBtn) {
        e.stopPropagation();
        const trackId = deleteBtn.dataset.trackId;
        if (trackId) confirmDelete(trackId);
        return;
    }
    // Handle row click → open detail
    const row = e.target.closest('tr[data-track-id]');
    if (row) {
        const trackId = row.dataset.trackId;
        if (trackId) openDetail(trackId);
    }
});

// Keyboard support for table rows
document.getElementById('tracks').addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
        const row = e.target.closest('tr[data-track-id]');
        if (row) {
            e.preventDefault();
            const trackId = row.dataset.trackId;
            if (trackId) openDetail(trackId);
        }
    }
});

// ── Time Ago ───────────────────────────────────────────────────────────────
function timeAgo(date) {
    if (!(date instanceof Date) || isNaN(date)) return '—';
    const s = Math.floor((Date.now() - date.getTime()) / 1000);
    if (s < 0) return 'just now';   // clock drift / future timestamps
    if (s < 60) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + 'm ago';
    if (s < 86400) return Math.floor(s / 3600) + 'h ago';
    if (s < 604800) return Math.floor(s / 86400) + 'd ago';
    if (s < 2678400) return Math.floor(s / 604800) + 'w ago';
    const then = new Date(date);
    const nowDate = new Date();
    const months = (nowDate.getFullYear() - then.getFullYear()) * 12 + (nowDate.getMonth() - then.getMonth());
    if (months <= 0) return Math.floor(s / 604800) + 'w ago';
    if (months < 12) return months + 'mo ago';
    return Math.floor(months / 12) + 'y ago';
}

// ── Detail Drawer (Fetch from API) ──────────────────────────────────
async function openDetail(id) {
    // Always fetch fresh data from the API instead of relying on cache
    document.getElementById('modal-content').innerHTML = '<div class="empty">Loading…</div>';
    document.getElementById('modal').style.display = 'flex';

    try {
        const res = await fetch(`/api/track/${encodeURIComponent(id)}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const t = data.track;
        if (!t) { showToast('Track not found', 'error'); closeModal(); return; }

        renderDetailContent(t, data.clicks || []);
    } catch (e) {
        document.getElementById('modal-content').innerHTML = `
            <div class="error-state">
                <div class="error-icon">⚠</div>
                <div class="error-msg">Failed to load details: ${esc(e.message)}</div>
                <button class="btn" onclick="closeModal()">Close</button>
            </div>`;
    }
}

function renderDetailContent(t, clicks) {
    const mapLink = (t.latitude && t.longitude)
        ? `<a href="https://maps.google.com/?q=${t.latitude},${t.longitude}" target="_blank"
               style="color:var(--accent); font-size:0.75rem; text-decoration:none; display:inline-flex; align-items:center; gap:3px; margin-top:3px">
             <svg style="width:11px;height:11px;fill:currentColor" viewBox="0 0 24 24">
               <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 010-5 2.5 2.5 0 010 5z"/>
             </svg>Open in Maps</a>`
        : '';

    const sections = [
        {
            title: 'Identity & Targeting',
            items: [
                { label: 'Track ID', value: t.track_id, mono: true, full: true },
                { label: 'Label', value: t.label, highlight: true },
                { label: 'Recipient', value: t.recipient },
                { label: 'Subject', value: t.subject, full: true },
                { label: 'Sender', value: t.sender },
                { label: 'Campaign', value: t.campaign_id },
                { label: 'Sent At', value: t.sent_at },
            ]
        },
        {
            title: 'Engagement',
            items: [
                { label: 'First Seen', value: t.first_seen ? new Date(t.first_seen).toLocaleString() : null },
                { label: 'Last Seen', value: t.last_seen ? new Date(t.last_seen).toLocaleString() : null },
                { label: 'Opens', value: t.open_count, highlight: true },
                { label: 'Clicks', value: t.click_count ?? 0, highlight: true },
            ]
        },
        {
            title: 'Network & Location',
            items: [
                { label: 'IP Address', value: t.ip_address, mono: true },
                { label: 'ISP', value: t.isp },
                { label: 'Org / ASN', value: t.org ? `${t.org}${t.asn ? ' · ' + t.asn : ''}` : t.asn },
                { label: 'Location', value: [t.city, t.region, t.country].filter(Boolean).join(', '), raw: mapLink },
                { label: 'Coordinates', value: (t.latitude && t.longitude) ? `${t.latitude}, ${t.longitude}` : null, mono: true },
                { label: 'Timezone', value: t.timezone },
            ]
        },
        {
            title: 'Device Fingerprint',
            items: [
                { label: 'Browser', value: t.browser ? `${t.browser} ${t.browser_version || ''}`.trim() : null },
                { label: 'OS', value: t.os ? `${t.os} ${t.os_version || ''}`.trim() : null },
                { label: 'Device Type', value: t.device_type },
                { label: 'Brand', value: t.device_brand },
                { label: 'Mobile', value: t.is_mobile != null ? (t.is_mobile ? 'Yes' : 'No') : null },
                { label: 'Bot', value: t.is_bot != null ? (t.is_bot ? 'Yes' : 'No') : null },
                { label: 'User Agent', value: t.user_agent, full: true, small: true, mono: true },
            ]
        },
        {
            title: 'HTTP Headers & Context',
            items: [
                { label: 'Referer', value: t.referer, full: true },
                { label: 'Accept-Language', value: t.accept_language },
                { label: 'Connection', value: t.connection_type },
                { label: 'Do Not Track', value: t.do_not_track },
                { label: 'Cache-Control', value: t.cache_control },
                { label: 'Sec-CH-UA', value: t.sec_ch_ua, full: true, small: true, mono: true },
                { label: 'CH Platform', value: t.sec_ch_ua_platform },
                { label: 'CH Mobile', value: t.sec_ch_ua_mobile },
            ]
        }
    ];

    // Click history section
    let clicksHtml = '';
    if (clicks.length > 0) {
        clicksHtml = `
        <div class="modal-section">
            <h4 class="section-title">Click History (${clicks.length})</h4>
            <div style="max-height:200px; overflow-y:auto;">
                ${clicks.map(c => `
                    <div style="display:flex; justify-content:space-between; padding:0.4rem 0; border-bottom:1px solid var(--border); font-size:0.78rem;">
                        <span style="color:var(--accent); max-width:70%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" title="${esc(c.target_url || '')}">${esc(c.target_url || '—')}</span>
                        <span style="color:var(--text-muted)">${c.timestamp ? timeAgo(new Date(c.timestamp)) : '—'}</span>
                    </div>
                `).join('')}
            </div>
        </div>`;
    }

    document.getElementById('modal-content').innerHTML = sections.map(section => {
        const vis = section.items.filter(f => f.value != null && f.value !== '');
        if (!vis.length) return '';
        return `
        <div class="modal-section">
            <h4 class="section-title">${section.title}</h4>
            <div class="detail-grid">
                ${vis.map(f => `
                    <div class="detail-item ${f.full ? 'full-width' : ''}">
                        <div class="detail-label">${f.label}</div>
                        <div class="detail-value ${f.mono ? 'mono' : ''} ${f.highlight ? 'text-highlight' : ''} ${f.small ? 'text-small' : ''}">
                            ${esc(String(f.value))}
                            ${f.raw || ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>`;
    }).join('') + clicksHtml + `
    <div class="modal-actions">
        <button class="btn" id="btn-edit-label" aria-label="Edit label">Edit Label</button>
        <button class="btn btn-danger" id="btn-delete-detail" aria-label="Delete pixel">Delete</button>
    </div>`;

    document.getElementById('btn-edit-label').addEventListener('click', () => {
        openInlineEdit(t.track_id, t.label || '');
    });
    document.getElementById('btn-delete-detail').addEventListener('click', () => {
        confirmDelete(t.track_id, true);
    });
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

document.getElementById('modal').addEventListener('click', e => {
    if (e.target.id === 'modal') closeModal();
});

// ── Inline Label Edit (replaces prompt()) ─────────────────────────────────
function openInlineEdit(id, current) {
    const overlay = document.getElementById('edit-modal');
    document.getElementById('edit-label-input').value = current;
    document.getElementById('edit-label-input').dataset.trackId = id;
    overlay.style.display = 'flex';
    setTimeout(() => document.getElementById('edit-label-input').focus(), 50);
}

function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
}

document.getElementById('edit-modal').addEventListener('click', e => {
    if (e.target.id === 'edit-modal') closeEditModal();
});

async function submitEditLabel() {
    const input = document.getElementById('edit-label-input');
    const id = input.dataset.trackId;
    const newLabel = input.value.trim();

    try {
        const res = await fetch(`/api/track/${encodeURIComponent(id)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
            body: JSON.stringify({ label: newLabel }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        closeEditModal();
        closeModal();
        load();
    } catch (e) {
        showToast('Update failed: ' + e.message, 'error');
    }
}

// ── Custom Confirm Dialog (replaces confirm()) ─────────────────────────────
let _deleteId = null;
let _deleteCloseMain = false;

function confirmDelete(id, closeMain = false) {
    _deleteId = id;
    _deleteCloseMain = closeMain;
    // Truncate long IDs for display
    const displayId = id.length > 30 ? id.slice(0, 27) + '...' : id;
    document.getElementById('confirm-msg').textContent =
        `Permanently delete pixel "${displayId}" and all its history?`;
    document.getElementById('confirm-modal').style.display = 'flex';
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').style.display = 'none';
    _deleteId = null;
}

document.getElementById('confirm-modal').addEventListener('click', e => {
    if (e.target.id === 'confirm-modal') closeConfirmModal();
});

async function executeDelete() {
    if (!_deleteId) return;
    const id = _deleteId;
    closeConfirmModal();
    try {
        const res = await fetch(`/api/track/${encodeURIComponent(id)}`, {
            method: 'DELETE',
            headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (_deleteCloseMain) closeModal();
        showToast('Pixel deleted', 'success');
        load();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

// ── Create Modal ───────────────────────────────────────────────────────────
function generateRandomId() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    const arr = new Uint8Array(8);
    (window.crypto || window.msCrypto).getRandomValues(arr);
    let id = '';
    for (let i = 0; i < 8; i++) id += chars[arr[i] % chars.length];
    document.getElementById('new-id').value = 'px-' + id;
}

function openCreateModal() {
    resetCreateModal();
    document.getElementById('create-modal').style.display = 'flex';
}

function resetCreateModal() {
    document.getElementById('create-step-1').style.display = 'block';
    document.getElementById('create-step-2').style.display = 'none';
    document.getElementById('new-label').value = '';
    // Clear any error styling
    const idInput = document.getElementById('new-id');
    idInput.style.borderColor = '';
    generateRandomId();
}

function closeCreateModal() {
    document.getElementById('create-modal').style.display = 'none';
}

document.getElementById('create-modal').addEventListener('click', e => {
    if (e.target.id === 'create-modal') closeCreateModal();
});

async function submitCreateTrack() {
    const idInput = document.getElementById('new-id');
    const id = idInput.value.trim();
    const label = document.getElementById('new-label').value.trim();
    if (!id) { showToast('Track ID is required', 'error'); return; }

    try {
        const res = await fetch('/api/track', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
            body: JSON.stringify({ track_id: id, label }),
        });
        const data = await res.json();
        if (!res.ok || data.error) {
            // Highlight the ID input on duplicate error
            if (data.error && data.error.includes('already exists')) {
                idInput.style.borderColor = '#ef4444';
                idInput.focus();
                showToast('This Track ID already exists. Click ↻ to generate a new one.', 'error');
            } else {
                showToast('Error: ' + (data.error || res.status), 'error');
            }
            return;
        }

        // Clear error styling on success
        idInput.style.borderColor = '';

        document.getElementById('create-step-1').style.display = 'none';
        document.getElementById('create-step-2').style.display = 'block';

        const origin = window.location.origin;
        document.getElementById('res-pixel-code').textContent =
            `<img src="${origin}/track?id=${data.track_id}" width="1" height="1" style="display:none" />`;
        document.getElementById('res-link-code').textContent =
            `${origin}/click/${data.track_id}/YOUR_URL_HERE`;

        if (pixelUrlEl) pixelUrlEl.textContent = `${origin}/track?id=${data.track_id}`;

        load();
    } catch (e) {
        showToast('Failed to create pixel: ' + e.message, 'error');
    }
}

// ── Toast Notifications ────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    toast.setAttribute('role', 'alert');
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('visible'));
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ── Utilities ──────────────────────────────────────────────────────────────
function copyText(el) {
    const text = el.textContent.trim();
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            el.classList.add('copy-flash');
            showToast('Copied!', 'success');
            setTimeout(() => el.classList.remove('copy-flash'), 600);
        }).catch(() => fallbackCopy(text, el));
    } else {
        fallbackCopy(text, el);
    }
}

function fallbackCopy(text, el) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        document.execCommand('copy');
        el.classList.add('copy-flash');
        showToast('Copied!', 'success');
        setTimeout(() => el.classList.remove('copy-flash'), 600);
    } catch (e) {
        showToast('Copy failed — please copy manually', 'error');
    }
    document.body.removeChild(ta);
}

function esc(s) {
    if (s == null) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

// Export via fetch + blob download (works with auth headers)
function exportData() {
    fetch('/api/export?format=csv', { headers: getAuthHeaders() })
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.blob();
        })
        .then(blob => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'naarad_export.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        })
        .catch(e => showToast('Export failed: ' + e.message, 'error'));
}

// ── Settings Modal (API Key Setup) ──────────────────────────────────────────
function openSettingsModal() {
    const overlay = document.getElementById('settings-modal');
    const input = document.getElementById('settings-api-key');
    input.value = localStorage.getItem('naarad_api_key') || '';
    overlay.style.display = 'flex';
    setTimeout(() => input.focus(), 50);
}

function closeSettingsModal() {
    document.getElementById('settings-modal').style.display = 'none';
}

function saveSettings() {
    const key = document.getElementById('settings-api-key').value.trim();
    if (key) {
        localStorage.setItem('naarad_api_key', key);
        showToast('API key saved', 'success');
    } else {
        localStorage.removeItem('naarad_api_key');
        showToast('API key cleared', 'info');
    }
    closeSettingsModal();
    load();
}

document.getElementById('settings-modal')?.addEventListener('click', e => {
    if (e.target.id === 'settings-modal') closeSettingsModal();
});

// ── Focus Trapping for Modals (U-04) ───────────────────────────────────────
function trapFocus(modalEl) {
    const focusable = modalEl.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])');
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    modalEl._trapHandler = (e) => {
        if (e.key !== 'Tab') return;
        if (e.shiftKey) {
            if (document.activeElement === first) { e.preventDefault(); last.focus(); }
        } else {
            if (document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
    };
    modalEl.addEventListener('keydown', modalEl._trapHandler);
}

function releaseFocus(modalEl) {
    if (modalEl._trapHandler) {
        modalEl.removeEventListener('keydown', modalEl._trapHandler);
        delete modalEl._trapHandler;
    }
}

// ── Global keyboard shortcut: Escape closes any open modal ─────────────────
document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    ['modal', 'create-modal', 'edit-modal', 'confirm-modal', 'settings-modal'].forEach(id => {
        const el = document.getElementById(id);
        if (el && el.style.display !== 'none') {
            el.style.display = 'none';
            releaseFocus(el);
        }
    });
});

// ── DOM Event Bindings (replaces all inline handlers) ──────────────────────

// Brand hover effect
const brandEl = document.getElementById('brand-title');
if (brandEl) {
    brandEl.addEventListener('mouseenter', () => { brandEl.textContent = 'नारद'; brandEl.classList.add('hindi'); });
    brandEl.addEventListener('mouseleave', () => { brandEl.textContent = 'naarad'; brandEl.classList.remove('hindi'); });
}

// Header actions
document.getElementById('btn-search-toggle')?.addEventListener('click', toggleSearch);
document.getElementById('btn-settings')?.addEventListener('click', openSettingsModal);
document.getElementById('btn-export')?.addEventListener('click', exportData);
document.getElementById('btn-new-pixel')?.addEventListener('click', openCreateModal);
document.getElementById('sync-status')?.addEventListener('click', triggerManualSync);

// Detail modal
document.getElementById('btn-close-modal')?.addEventListener('click', closeModal);

// Create modal
document.getElementById('btn-close-create')?.addEventListener('click', closeCreateModal);
document.getElementById('btn-regen-id')?.addEventListener('click', generateRandomId);
document.getElementById('btn-submit-create')?.addEventListener('click', submitCreateTrack);
document.getElementById('btn-create-another')?.addEventListener('click', resetCreateModal);

// Copy code snippets
document.getElementById('res-pixel-code')?.addEventListener('click', function () { copyText(this); });
document.getElementById('res-link-code')?.addEventListener('click', function () { copyText(this); });

// Edit modal
document.getElementById('btn-cancel-edit')?.addEventListener('click', closeEditModal);
document.getElementById('btn-save-edit')?.addEventListener('click', submitEditLabel);
document.getElementById('edit-label-input')?.addEventListener('keyup', e => { if (e.key === 'Enter') submitEditLabel(); });

// Confirm modal
document.getElementById('btn-cancel-delete')?.addEventListener('click', closeConfirmModal);
document.getElementById('btn-confirm-delete')?.addEventListener('click', executeDelete);

// Settings modal
document.getElementById('btn-cancel-settings')?.addEventListener('click', closeSettingsModal);
document.getElementById('btn-save-settings')?.addEventListener('click', saveSettings);
document.getElementById('settings-api-key')?.addEventListener('keyup', e => { if (e.key === 'Enter') saveSettings(); });

// ── Init ───────────────────────────────────────────────────────────────────
fetchSyncStatus().then(load);

// Pause auto-refresh when tab is backgrounded to save bandwidth/battery
let _autoRefreshId = null;
function startAutoRefresh() {
    if (_autoRefreshId) return;
    _autoRefreshId = setInterval(load, 30000);
}
function stopAutoRefresh() {
    if (_autoRefreshId) { clearInterval(_autoRefreshId); _autoRefreshId = null; }
}
startAutoRefresh();
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    } else {
        load();
        startAutoRefresh();
    }
});

