// ──────────────────────────────────────────────
// Naarad Dashboard — script.js
// ──────────────────────────────────────────────

const BASE = window.location.origin;
document.getElementById('pixel-url').textContent = BASE + '/track?id=recipient-id';

// Live / Local indicator
const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const statusEl = document.querySelector('.live');
if (statusEl) {
    statusEl.innerHTML = `<span class="live-dot" style="background:${isLocal ? '#facc15' : ''}"></span> ${isLocal ? 'Localhost' : 'Live'}`;
}

// ── Search toggle ──────────────────────────────
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

// ── Data Loading ───────────────────────────────
async function load() {
    try {
        const [statsRes, tracksRes] = await Promise.all([
            fetch('/api/stats'),
            fetch(`/api/tracks?limit=100&${buildQuery()}`)
        ]);
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
        renderTracks(window.loadedTracks);

        const countEl = document.getElementById('track-count');
        if (countEl) countEl.textContent = `${data.total ?? data.tracks?.length ?? 0} total`;

    } catch (e) {
        console.error('Load failed:', e);
    }
}

function buildQuery() {
    const q = document.getElementById('search-q')?.value?.trim();
    return q ? `q=${encodeURIComponent(q)}` : '';
}

// ── Charts ─────────────────────────────────────
function renderChart(id, data, key) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!data?.length) { el.innerHTML = '<div class="empty">No data</div>'; return; }
    const max = Math.max(...data.map(d => d.count));
    el.innerHTML = data.slice(0, 6).map(d => `
        <div class="chart-row">
            <span>${esc(d[key] || 'Unknown')}</span>
            <div class="chart-bar"><div class="chart-fill" style="width:${(d.count / max * 100).toFixed(1)}%"></div></div>
            <span>${d.count}</span>
        </div>
    `).join('');
}

// ── Table ──────────────────────────────────────
function renderTracks(tracks) {
    const el = document.getElementById('tracks');
    if (!tracks?.length) {
        el.innerHTML = '<tr><td colspan="7" class="empty">No pixels tracked yet</td></tr>';
        return;
    }
    el.innerHTML = tracks.map(t => `
        <tr onclick="openDetail('${esc(t.track_id)}')">
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
            <td style="text-align:right; color:var(--text-muted); font-size:0.75rem">
                ${t.last_seen ? timeAgo(new Date(t.last_seen)) : '—'}
            </td>
            <td onclick="event.stopPropagation()">
                <button class="row-action" onclick="deleteTrack('${esc(t.track_id)}')" title="Delete pixel">
                    <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                </button>
            </td>
        </tr>
    `).join('');
}

// ── Time Ago ───────────────────────────────────
function timeAgo(date) {
    const s = Math.floor((Date.now() - date) / 1000);
    if (s < 60) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + 'm';
    if (s < 86400) return Math.floor(s / 3600) + 'h';
    if (s < 2592000) return Math.floor(s / 86400) + 'd';
    if (s < 31536000) return Math.floor(s / 2592000) + 'mo';
    return Math.floor(s / 31536000) + 'y';
}

// ── Detail Drawer ──────────────────────────────
function openDetail(id) {
    const t = window.loadedTracks.find(x => x.track_id === id);
    if (!t) return;

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

    document.getElementById('modal-content').innerHTML = sections.map(section => {
        const visibleItems = section.items.filter(f => f.value != null && f.value !== '');
        if (!visibleItems.length) return '';
        return `
        <div class="modal-section">
            <h4 class="section-title">${section.title}</h4>
            <div class="detail-grid">
                ${visibleItems.map(f => `
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
    }).join('') + `
    <div style="margin-top:1rem; display:flex; gap:0.5rem; flex-wrap:wrap">
        <button class="btn" onclick="editLabel('${esc(t.track_id)}', '${esc(t.label || '')}')">Edit Label</button>
        <button class="btn" style="color:#c0392b; border-color:#c0392b" onclick="deleteTrack('${esc(t.track_id)}'); closeModal()">Delete</button>
    </div>`;

    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

document.getElementById('modal').addEventListener('click', e => {
    if (e.target.id === 'modal') closeModal();
});

// ── Create Modal ───────────────────────────────
function generateRandomId() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let id = '';
    for (let i = 0; i < 8; i++) id += chars[Math.floor(Math.random() * chars.length)];
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
    generateRandomId();
}

function closeCreateModal() {
    document.getElementById('create-modal').style.display = 'none';
}

document.getElementById('create-modal').addEventListener('click', e => {
    if (e.target.id === 'create-modal') closeCreateModal();
});

async function submitCreateTrack() {
    const id = document.getElementById('new-id').value.trim();
    const label = document.getElementById('new-label').value.trim();
    if (!id) { alert('Track ID is required'); return; }

    try {
        const res = await fetch('/api/track', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ track_id: id, label })
        });
        const data = await res.json();
        if (data.error) { alert('Error: ' + data.error); return; }

        // Show result step
        document.getElementById('create-step-1').style.display = 'none';
        document.getElementById('create-step-2').style.display = 'block';

        const origin = window.location.origin;
        document.getElementById('res-pixel-code').textContent =
            `<img src="${origin}/track?id=${data.track_id}" width="1" height="1" style="display:none" />`;
        document.getElementById('res-link-code').textContent =
            `${origin}/click/${data.track_id}/YOUR_URL_HERE`;

        load();
    } catch (e) {
        alert('Failed to create pixel. Check console.');
        console.error(e);
    }
}

// ── CRUD ───────────────────────────────────────
async function deleteTrack(id) {
    if (!confirm(`Delete pixel "${id}"?\n\nAll history will be permanently lost.`)) return;
    try {
        await fetch(`/api/track/${encodeURIComponent(id)}`, { method: 'DELETE' });
        load();
    } catch (e) {
        alert('Delete failed');
    }
}

async function editLabel(id, current) {
    const newLabel = prompt('New label:', current);
    if (newLabel === null) return;
    try {
        await fetch(`/api/track/${encodeURIComponent(id)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label: newLabel })
        });
        closeModal();
        load();
    } catch (e) {
        alert('Update failed');
    }
}

// ── Utilities ──────────────────────────────────
function copyText(el) {
    const text = el.textContent.trim();
    navigator.clipboard.writeText(text).then(() => {
        el.classList.add('copy-flash');
        setTimeout(() => el.classList.remove('copy-flash'), 600);
    });
}

function esc(s) {
    if (s == null) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

function exportData() {
    window.open('/api/export?format=csv', '_blank');
}

// ── Init ───────────────────────────────────────
load();
setInterval(load, 30000);
