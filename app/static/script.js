const BASE = window.location.origin;
document.getElementById('pixel-url').textContent = BASE + '/track?id=recipient';

// Update status indicator
const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const statusEl = document.querySelector('.live');
if (statusEl) {
    statusEl.innerHTML = `<span class="live-dot" style="background:${isLocal ? '#facc15' : '#4ade80'}"></span> ${isLocal ? 'Localhost' : 'Live'}`;
}

// Search Interaction
function toggleSearch() {
    const wrap = document.querySelector('.search-wrap');
    const input = document.getElementById('search-q');
    wrap.classList.toggle('active');
    if (wrap.classList.contains('active')) {
        setTimeout(() => input.focus(), 300);
    }
}
// Close search if clicked outside
document.addEventListener('click', (e) => {
    const wrap = document.querySelector('.search-wrap');
    if (wrap && !wrap.contains(e.target) && wrap.classList.contains('active') && !document.getElementById('search-q').value) {
        wrap.classList.remove('active');
    }
});

async function load() {
    try {
        const stats = await (await fetch('/api/stats')).json();
        document.getElementById('stat-unique').textContent = stats.summary.total_unique;
        document.getElementById('stat-opens').textContent = stats.summary.total_opens;
        document.getElementById('stat-clicks').textContent = stats.summary.total_clicks;
        document.getElementById('stat-avg').textContent = stats.summary.avg_opens;

        renderChart('countries', stats.geographic);
        renderChart('devices', stats.devices);
        renderChart('browsers', stats.browsers);

        const q = document.getElementById('search-q') ? document.getElementById('search-q').value : '';
        const url = q ? `/api/tracks?q=${encodeURIComponent(q)}` : '/api/tracks?limit=50';

        const data = await (await fetch(url)).json();
        window.loadedTracks = data.tracks; // Store for modal
        renderTracks(data.tracks);
    } catch (e) {
        console.error(e);
    }
}

function renderChart(id, data) {
    const el = document.getElementById(id);
    if (!data || !data.length) {
        el.innerHTML = '<div class="empty">No data</div>';
        return;
    }
    const max = Math.max(...data.map(d => d.count));
    el.innerHTML = data.slice(0, 5).map(d => `
        <div class="chart-row">
            <span>${d.country || d.device_type || d.browser || '-'}</span>
            <div class="chart-bar"><div class="chart-fill" style="width:${(d.count / max * 100)}%"></div></div>
            <span>${d.count}</span>
        </div>
    `).join('');
}

function renderTracks(tracks) {
    const el = document.getElementById('tracks');
    if (!tracks || !tracks.length) {
        el.innerHTML = '<tr><td colspan="6" class="empty">No recent activity</td></tr>';
        return;
    }

    el.innerHTML = tracks.map(t => `
        <tr onclick="openDetail('${t.track_id}')" style="cursor:pointer; border-bottom:1px solid rgba(255,255,255,0.05); transition:background 0.2s">
            <td style="padding:1rem">
                <div style="font-weight:600; color:#e5e5e5; font-size:0.9rem; margin-bottom:2px">${esc(t.label || 'Unknown Client')}</div>
                <div class="mono" style="font-size:0.75rem; color:#555">${esc(t.track_id)}</div>
            </td>
            <td style="padding:1rem; font-size:0.85rem; color:#aaa">
                ${t.city ? `<span style="color:#ddd">${esc(t.city)}</span>, ` : ''}${esc(t.country || 'Unknown')}
            </td>
            <td class="hide-mobile" style="padding:1rem; font-size:0.85rem; color:#888">
                ${esc(t.device_type || 'Desktop')} <span style="opacity:0.5">•</span> ${esc(t.os || '-')}
            </td>
            <td style="padding:1rem; text-align:center">
                <div style="display:inline-flex; align-items:center; gap:6px; background:#1a1a1a; padding:4px 8px; border-radius:12px; border:1px solid #333">
                    <span style="color:#4ade80; font-weight:600; font-size:0.8rem">${t.open_count}</span>
                    <span style="width:1px; height:10px; background:#333"></span>
                    <span style="color:#60a5fa; font-size:0.8rem">${t.click_count || 0}</span>
                </div>
            </td>
            <td style="padding:1rem; text-align:right; font-size:0.8rem; color:#666; font-family:monospace">
                ${t.last_seen ? timeAgo(new Date(t.last_seen)) : '-'}
            </td>
            <td style="padding:1rem; text-align:right" onclick="event.stopPropagation()">
                <button class="btn-icon" style="padding:0.4rem; color:#444" onclick="deleteTrack('${t.track_id}')" title="Delete">
                    <svg class="icon" style="width:16px;height:16px" viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                </button>
            </td>
        </tr>
    `).join('');
}

function timeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    let interval = seconds / 31536000;
    if (interval > 1) return Math.floor(interval) + "y";
    interval = seconds / 2592000;
    if (interval > 1) return Math.floor(interval) + "mo";
    interval = seconds / 86400;
    if (interval > 1) return Math.floor(interval) + "d";
    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + "h";
    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + "m";
    return "just now";
}

function openDetail(id) {
    const t = window.loadedTracks.find(x => x.track_id === id);
    if (!t) return;

    // Google Maps Link
    const mapLink = (t.latitude && t.longitude)
        ? `<a href="https://www.google.com/maps/search/?api=1&query=${t.latitude},${t.longitude}" target="_blank" style="color:#60a5fa; text-decoration:none; display:flex; align-items:center; gap:4px; font-size:0.8rem; margin-top:4px">
             See on Map <svg style="width:12px;height:12px;fill:currentColor" viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
           </a>`
        : '';

    // Ensure all fields are safe
    const sections = [
        {
            title: "Identity & Context",
            items: [
                { label: 'Label', value: t.label || '-', highlight: true },
                { label: 'Event ID', value: t.track_id, mono: true },
                { label: 'Recipient', value: t.recipient },
                { label: 'Subject', value: t.subject, full: true }
            ]
        },
        {
            title: "Location & Network",
            items: [
                { label: 'Generic', value: `${t.city || ''}, ${t.country || ''}` },
                { label: 'IP Address', value: t.ip_address, mono: true },
                { label: 'ISP / Org', value: t.isp || t.org },
                { label: 'Location', value: `${t.city || '-'}, ${t.country || '-'}`, raw: mapLink },
                { label: 'Coordinates', value: (t.latitude && t.longitude) ? `${t.latitude}, ${t.longitude}` : '-', mono: true }
            ]
        },
        {
            title: "Device Fingerprint",
            items: [
                { label: 'Browser', value: `${t.browser} ${t.browser_version || ''}` },
                { label: 'Platform', value: `${t.os} ${t.os_version || ''}` },
                { label: 'Device', value: `${t.device_brand || ''} ${t.device_type || ''}` },
                { label: 'User Agent', value: t.user_agent, full: true, small: true, mono: true }
            ]
        },
        {
            title: "Timeline",
            items: [
                { label: 'First Seen', value: t.first_seen ? new Date(t.first_seen).toLocaleString() : '-' },
                { label: 'Last Activity', value: t.last_seen ? new Date(t.last_seen).toLocaleString() : '-' },
                { label: 'Total Opens', value: t.open_count, highlight: true },
                { label: 'Total Clicks', value: t.click_count || 0, highlight: true }
            ]
        }
    ];

    document.getElementById('modal-content').innerHTML = sections.map(section => `
        <div class="modal-section">
            <h4 class="section-title">${section.title}</h4>
            <div class="detail-grid">
                ${section.items.map(f => `
                    <div class="detail-item ${f.full ? 'full-width' : ''}">
                        <div class="detail-label">${f.label}</div>
                        <div class="detail-value ${f.mono ? 'mono' : ''} ${f.highlight ? 'text-highlight' : ''} ${f.small ? 'text-small' : ''}">
                            ${esc(f.value || '-')}
                            ${f.raw || ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('<hr class="modal-divider">') +
        `<div style="margin-top:1.5rem; text-align:right">
        <button class="btn" style="border:1px solid #333; color:#ef4444" onclick="deleteTrack('${t.track_id}'); closeModal()">Delete Pixel</button>
     </div>`;

    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

// Close on outside click
document.getElementById('modal').addEventListener('click', (e) => {
    if (e.target.id === 'modal') closeModal();
});

// Modal Actions
function generateRandomId() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < 8; i++) result += chars.charAt(Math.floor(Math.random() * chars.length));
    document.getElementById('new-id').value = 'client-' + result;
}

function openCreateModal() {
    resetCreateModal();
    generateRandomId();
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

async function submitCreateTrack() {
    const id = document.getElementById('new-id').value.trim();
    const label = document.getElementById('new-label').value.trim();

    if (!id) return alert("ID is required");

    try {
        const res = await fetch('/api/track', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ track_id: id, label: label })
        });
        const data = await res.json();

        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }

        // Show success step
        document.getElementById('create-step-1').style.display = 'none';
        document.getElementById('create-step-2').style.display = 'block';

        const origin = window.location.origin;
        document.getElementById('res-pixel-code').textContent =
            `<img src="${origin}/track?id=${data.track_id}" width="1" height="1" style="display:none" />`;

        document.getElementById('res-link-code').textContent =
            `${origin}/track?id=${data.track_id}&r=https://example.com`;

        load();
    } catch (e) {
        alert('Failed to create pixel');
    }
}

async function deleteTrack(id) {
    if (!confirm(`Delete pixel "${id}"? This history cannot be recovered.`)) return;

    try {
        await fetch(`/api/track/${id}`, { method: 'DELETE' });
        load();
    } catch (e) {
        alert('Delete failed');
    }
}

async function editLabel(id, current) {
    const newLabel = prompt("Enter new label:", current);
    if (newLabel === null) return;

    try {
        await fetch(`/api/track/${id}`, {
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

function copyLink(id) {
    const url = window.location.origin + '/track?id=' + id;
    navigator.clipboard.writeText(url).then(() => {
        // Simple toast or feedback
        const btn = event.target;
        const old = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = old, 1000);
    });
}

function copyText(el) {
    const text = el.textContent;
    navigator.clipboard.writeText(text).then(() => {
        const old = el.style.borderColor;
        el.style.borderColor = '#4ade80';
        setTimeout(() => el.style.borderColor = '#333', 500);
    });
}

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function exportData() {
    window.open('/api/export?format=csv', '_blank');
}



load();
setInterval(load, 30000);
