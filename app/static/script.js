const BASE = window.location.origin;
document.getElementById('pixel-url').textContent = BASE + '/track?id=recipient';

// Update status indicator
const isLocal = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const statusEl = document.querySelector('.live');
if (statusEl) {
    statusEl.innerHTML = `<span class="live-dot" style="background:${isLocal ? '#facc15' : '#4ade80'}"></span> ${isLocal ? 'Localhost' : 'Live'}`;
}

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
        el.innerHTML = '<tr><td colspan="5" class="empty">No pixels found</td></tr>';
        return;
    }

    el.innerHTML = tracks.map(t => `
        <tr onclick="openDetail('${t.track_id}')" style="cursor:pointer; border-bottom:1px solid #222; transition:background 0.2s">
            <td style="padding:0.8rem">
                <div style="font-weight:bold; color:white; font-size:0.95rem">${esc(t.label || t.track_id)}</div>
                <div class="mono" style="font-size:0.75rem; color:#666">${esc(t.track_id)}</div>
            </td>
            <td style="padding:0.8rem; font-size:0.9rem; color:#ccc">
                ${esc(t.city || '-')}, ${esc(t.country || '-')}
            </td>
            <td class="hide-mobile" style="padding:0.8rem; font-size:0.9rem; color:#ccc">
                <div>${esc(t.recipient || '-')}</div>
                <div style="font-size:0.75rem; color:#666">${esc(t.subject?.substring(0, 25) || '')}</div>
            </td>
            <td style="padding:0.8rem; text-align:center">
                <span class="badge" style="background:rgba(74, 222, 128, 0.1); color:#4ade80; margin-right:4px" title="Opens">${t.open_count}</span>
                <span class="badge" style="background:rgba(96, 165, 250, 0.1); color:#60a5fa" title="Clicks">${t.click_count || 0}</span>
            </td>
            <td style="padding:0.8rem; text-align:right">
                <button class="btn" style="padding:0.2rem 0.6rem; font-size:0.8rem; background:transparent; border:1px solid #333; margin-right:4px" 
                        onclick="event.stopPropagation(); copyLink('${t.track_id}')" title="Copy Pixel URL">🔗</button>
                <button class="btn" style="padding:0.2rem 0.6rem; font-size:0.8rem; background:transparent; border:1px solid #333; color:#ef4444" 
                        onclick="event.stopPropagation(); deleteTrack('${t.track_id}')" title="Delete">🗑️</button>
            </td>
        </tr>
    `).join('');
}

function openDetail(id) {
    const t = window.loadedTracks.find(x => x.track_id === id);
    if (!t) return;

    document.getElementById('modal-content').innerHTML = `
        <div style="display:grid; gap:1.5rem">
            <div>
                <h4 style="color:#666; font-size:0.8rem; text-transform:uppercase; margin-bottom:0.5rem">Metadata</h4>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.5rem">
                    <div>
                        <div style="font-size:0.75rem; color:#666">Label</div>
                        <div>${esc(t.label || '-')} <button style="background:none;border:none;color:#4ade80;cursor:pointer" onclick="editLabel('${t.track_id}', '${esc(t.label || '')}')">✎</button></div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; color:#666">Track ID</div>
                        <div class="mono">${esc(t.track_id)}</div>
                    </div>
                </div>
            </div>
            <div>
                <h4 style="color:#666; font-size:0.8rem; text-transform:uppercase; margin-bottom:0.5rem">Stats</h4>
                <div style="display:flex; gap:1rem">
                    <div style="background:#111; padding:0.8rem; border-radius:4px; flex:1; text-align:center">
                        <div style="font-size:1.5rem; color:#4ade80; font-weight:bold">${t.open_count}</div>
                        <div style="font-size:0.75rem; color:#666">Opens</div>
                    </div>
                    <div style="background:#111; padding:0.8rem; border-radius:4px; flex:1; text-align:center">
                        <div style="font-size:1.5rem; color:#60a5fa; font-weight:bold">${t.click_count || 0}</div>
                        <div style="font-size:0.75rem; color:#666">Clicks</div>
                    </div>
                </div>
            </div>
             <div>
                <h4 style="color:#666; font-size:0.8rem; text-transform:uppercase; margin-bottom:0.5rem">Location & Device</h4>
                <div class="detail-grid">
                     <div class="detail-item"><div class="detail-label">Location</div><div class="detail-value">${esc(t.city || '-')}, ${esc(t.country || '-')}</div></div>
                     <div class="detail-item"><div class="detail-label">IP Address</div><div class="detail-value mono">${esc(t.ip_address)}</div></div>
                     <div class="detail-item"><div class="detail-label">Device</div><div class="detail-value">${esc(t.device_type || '-')} (${esc(t.os || '-')})</div></div>
                     <div class="detail-item"><div class="detail-label">Browser</div><div class="detail-value">${esc(t.browser || '-')}</div></div>
                </div>
            </div>
        </div>
    `;
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
function openCreateModal() {
    document.getElementById('create-modal').style.display = 'flex';
    document.getElementById('new-id').value = '';
    document.getElementById('new-label').value = '';
}

function closeCreateModal() {
    document.getElementById('create-modal').style.display = 'none';
}

async function submitCreateTrack() {
    const id = document.getElementById('new-id').value.trim();
    const label = document.getElementById('new-label').value.trim();

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

        closeCreateModal();
        load(); // Refresh list

        // Optionally show the links immediately
        prompt("Pixel Created! Copy URL:", window.location.origin + '/track?id=' + data.track_id);
    } catch (e) {
        alert('Failed to create pixel');
    }
}

async function deleteTrack(id) {
    if (!confirm(`Are you sure you want to delete pixel "${id}"? This cannot be undone.`)) return;

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

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function exportData() {
    window.open('/api/export?format=csv', '_blank');
}

// Generator Tools
async function generateTools() {
    const idInput = document.getElementById('gen-id');
    const urlInput = document.getElementById('gen-url');
    const resultDiv = document.getElementById('gen-result');

    let id = idInput.value.trim();
    const url = urlInput.value.trim();

    if (!id) {
        id = 'track-' + Date.now().toString(36);
        idInput.value = id;
    }

    const base = window.location.origin;

    // 1. Pixel
    // Note: We construct this client-side for speed, but could use /api/generate
    const pixelUrl = `${base}/track?id=${encodeURIComponent(id)}`;
    const pixelTag = `<img src="${pixelUrl}" width="1" height="1" style="display:none" alt="" />`;
    document.getElementById('res-pixel').textContent = pixelTag;

    // 2. Link
    const linkGroup = document.getElementById('res-link-group');
    if (url) {
        try {
            // Use API for safe encoding
            const res = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ track_id: id, url: url })
            });
            const data = await res.json();

            if (data.click_url) {
                document.getElementById('res-link').textContent = base + data.click_url;
                linkGroup.style.display = 'block';
            }
        } catch (e) {
            console.error(e);
            // Fallback
            document.getElementById('res-link').textContent = `${base}/click/${encodeURIComponent(id)}/${encodeURIComponent(url)}`;
            linkGroup.style.display = 'block';
        }
    } else {
        linkGroup.style.display = 'none';
    }

    resultDiv.style.display = 'block';
}

function copyText(el) {
    const text = el.textContent;
    navigator.clipboard.writeText(text).then(() => {
        const original = el.style.backgroundColor;
        el.style.backgroundColor = 'rgba(74, 222, 128, 0.2)';
        setTimeout(() => {
            el.style.backgroundColor = original;
        }, 200);
    });
}

load();
setInterval(load, 30000);
