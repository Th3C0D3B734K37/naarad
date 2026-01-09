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

        const data = await (await fetch('/api/tracks?limit=20')).json();
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
        el.innerHTML = '<tr><td colspan="6" class="empty">No events yet</td></tr>';
        return;
    }
    el.innerHTML = tracks.map(t => `
        <tr onclick="openDetail('${t.track_id}')" style="cursor:pointer">
            <td><span class="mono">${esc(t.track_id?.slice(0, 16) || '-')}</span></td>
            <td>${esc(t.city || '-')}, ${esc(t.country || '-')}</td>
            <td class="hide-mobile">${esc(t.sender || '-')}</td>
            <td class="hide-mobile">${esc(t.recipient || '-')}</td>
            <td class="hide-mobile">${esc(t.subject || '-')}</td>
            <td class="hide-mobile"><span class="badge">${esc(t.device_type || '-')}</span></td>
            <td>${t.open_count || 0}</td>
            <td style="color:var(--text-muted);font-size:0.7rem">${t.last_seen ? new Date(t.last_seen).toLocaleString() : '-'}</td>
        </tr>
    `).join('');
}

function openDetail(id) {
    const t = window.loadedTracks.find(x => x.track_id === id);
    if (!t) return;

    const sections = [
        {
            title: "Message Context",
            items: [
                { label: 'Subject', value: t.subject, full: true, highlight: true },
                { label: 'Sender', value: t.sender },
                { label: 'Recipient', value: t.recipient },
                { label: 'Event ID', value: t.track_id, mono: true }
            ]
        },
        {
            title: "Network & Location",
            items: [
                { label: 'Location', value: `${t.city || ''}, ${t.region || ''}, ${t.country || ''}` },
                { label: 'IP Address', value: t.ip_address, mono: true },
                { label: 'ISP', value: t.isp },
                { label: 'Timezone', value: t.timezone }
            ]
        },
        {
            title: "Device & Client",
            items: [
                { label: 'Browser', value: `${t.browser} ${t.browser_version || ''}` },
                { label: 'OS', value: `${t.os} ${t.os_version || ''}` },
                { label: 'Device', value: `${t.device_brand || ''} ${t.device_type || ''}` },
                { label: 'User Agent', value: t.user_agent, full: true, small: true }
            ]
        },
        {
            title: "Timestamps",
            items: [
                { label: 'First Seen', value: t.first_seen ? new Date(t.first_seen).toLocaleString() : '-' },
                { label: 'Last Seen', value: t.last_seen ? new Date(t.last_seen).toLocaleString() : '-' },
                { label: 'Sent At', value: t.sent_at ? new Date(t.sent_at).toLocaleString() : '-' },
                { label: 'Opens', value: t.open_count }
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
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('<hr class="modal-divider">');

    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

// Close on outside click
document.getElementById('modal').addEventListener('click', (e) => {
    if (e.target.id === 'modal') closeModal();
});

// Close on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

function esc(s) {
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
