# Naarad (नारद) - User Guide

This guide covers how to use Naarad for email tracking.

**Related Docs:**
- [SETUP.md](SETUP.md) - Installation & deployment
- [TESTING.md](TESTING.md) - Testing with email clients
- [DEVELOPERS.md](DEVELOPERS.md) - Code architecture for contributors

---

## How Tracking Works

Naarad works by serving a tiny, invisible image (1x1 pixel) from your server:

1. You embed the image tag in an email
2. When the recipient opens the email, their mail client requests the image
3. Naarad records the request details and returns the invisible pixel
4. You see the event in your dashboard

---

## The Localhost Rule

If running locally, **only YOU** can trigger tracking events.

To track real recipients, your server must be **publicly accessible**:
- Use [ngrok](https://ngrok.com) for temporary access
- Deploy to Railway, Render, or Fly.io for permanent hosting

---

## 1. Basic Tracking

### Minimal Pixel

```html
<img src="https://YOUR_SERVER/track?id=my_email" width="1" height="1" style="display:none" />
```

### With Metadata (Recommended)

Track who opened what:

```html
<img src="https://YOUR_SERVER/track?id=proposal_v1&sender=sales@company.com&recipient=client@gmail.com&subject=Q1_Quote" width="1" height="1" style="display:none" />
```

**Parameters:**
| Parameter | Description |
|-----------|-------------|
| `id` | Unique identifier for this email |
| `sender` | Your email address |
| `recipient` | Recipient's email |
| `subject` | Email subject line |
| `campaign` | Campaign name for grouping |
| `sent_at` | When you sent the email (ISO format) |

---

## 2. Link Click Tracking

Track when recipients click links:

```html
<a href="https://YOUR_SERVER/click/proposal_v1/https%3A%2F%2Fexample.com%2Fpricing">
  View Pricing
</a>
```

The recipient is automatically redirected to the target URL.

---

## 3. Viewing Data

### Dashboard

Visit `https://YOUR_SERVER/dashboard` to see:
- **Summary cards**: Total recipients, opens, clicks
- **Recent events**: Table with click-to-view details
- **Charts**: Countries, devices, browsers breakdown

### Event Details

Click any row to see the full event:
- Subject, sender, recipient
- Location (city, region, country)
- IP address, ISP, organization
- Browser, OS, device type
- All timestamps

---

## 4. API Access

All data is available via JSON API:

```bash
# Get statistics
curl https://YOUR_SERVER/api/stats

# List events
curl https://YOUR_SERVER/api/tracks?limit=50

# Get specific event
curl https://YOUR_SERVER/api/track/proposal_v1

# Export as CSV
curl https://YOUR_SERVER/api/export?format=csv
```

---

## 5. What Data is Captured

Each open/click captures:

**Network:**
- IP address
- Geolocation (country, region, city, lat/lon)
- ISP, organization, ASN

**Device:**
- User-Agent string
- Browser name and version
- Operating system
- Device type (Desktop/Mobile/Tablet)
- Client Hints (modern browsers)

**Headers:**
- Accept, Accept-Encoding, Accept-Language
- Referer, Connection, Cache-Control
- Do Not Track (DNT) preference

---

## 6. Troubleshooting

| Issue | Solution |
|-------|----------|
| "Local" location showing | You're viewing from the same machine as the server |
| No events appearing | Check if mail client blocks external images |
| Link doesn't work for others | Use public URL, not localhost |
| Events not real-time | Dashboard refreshes every 30 seconds |

---

## 7. Privacy Notes

- Always comply with local privacy laws (GDPR, CAN-SPAM)
- Consider informing recipients that emails may be tracked
- Data is stored locally in SQLite - back it up regularly
