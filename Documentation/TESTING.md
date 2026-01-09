# Testing Guide

How to test Naarad locally, on private networks, and over the internet with real email clients.

**Related Docs:**
- [SETUP.md](SETUP.md) - Server installation
- [USAGE.md](USAGE.md) - Tracking pixel syntax
- [DEVELOPERS.md](DEVELOPERS.md) - Code architecture

---

## 1. Local Testing (Your Machine Only)

### Start the Server

```bash
python server.py
```

Server runs at `http://localhost:8080`

### Test in Browser

Open these URLs directly:

```
http://localhost:8080/track?id=test_local
http://localhost:8080/track?id=test_rich&sender=me&recipient=client@test.com&subject=TestSubject
```

### Verify
- Open `http://localhost:8080/dashboard`
- You should see the events appear

### Limitation
Only **your machine** can trigger events. "localhost" means "this computer" - it doesn't work for others.

---

## 2. Private Network Testing (Other Devices on Same WiFi)

### Find Your Local IP

**Windows:**
```powershell
ipconfig
# Look for IPv4 Address (e.g., 192.168.1.100)
```

**Mac/Linux:**
```bash
ifconfig | grep inet
# or
hostname -I
```

### Start Server (Already Configured)

The server binds to `0.0.0.0` by default, making it accessible on your network.

### Test from Another Device

On your phone or another computer on the same WiFi:

```
http://192.168.1.100:8080/dashboard
http://192.168.1.100:8080/track?id=phone_test
```

### Test in Email (Private Network)

1. Compose an email to yourself
2. Switch to HTML mode or use an HTML editor
3. Add:
   ```html
   <img src="http://192.168.1.100:8080/track?id=private_test" width="1" height="1" />
   ```
4. Send and open on another device

### Limitation
Only works for devices on the **same network**. Won't work for external recipients.

---

## 3. Internet Testing (Real Email Clients)

For testing with Gmail, Outlook, Thunderbird, ProtonMail, etc., your server must be **publicly accessible**.

### Option A: ngrok (Quick, Temporary)

1. **Install ngrok**: https://ngrok.com/download
2. **Start your server**:
   ```bash
   python server.py
   ```
3. **Start ngrok**:
   ```bash
   ngrok http 8080
   ```
4. **Copy the public URL** (e.g., `https://abc123.ngrok-free.app`)

### Option B: Deploy (Permanent)

Deploy to Railway, Render, or Fly.io (see [SETUP.md](SETUP.md)).

---

## Testing with Email Clients

### Gmail (Web)

Gmail strips most HTML, but you can use:

1. **Compose** a new email
2. Click the **3 dots** → **Show original** (to verify pixel is embedded)
3. Or use **Gmail API** / **Apps Script** to send HTML emails

**Easier Method - Mail Merge:**
Use [Yet Another Mail Merge](https://yamm.com) or similar extension that allows HTML.

### Outlook (Desktop)

1. **New Email** → **Format Text** tab → Select **HTML**
2. Go to **Insert** → **Text** → **Object** → **Text from File**
3. Insert an HTML file containing:
   ```html
   <html>
   <body>
   Your email content here
   <img src="https://YOUR_NGROK_URL/track?id=outlook_test&recipient=friend@email.com" width="1" height="1" />
   </body>
   </html>
   ```

### Outlook (Web)

Web Outlook doesn't support raw HTML editing. Use desktop client or API.

### Thunderbird (Recommended for Testing)

1. **New Message**
2. **Options** → **Delivery Format** → **HTML Only**
3. **Insert** → **HTML** → Paste:
   ```html
   <img src="https://YOUR_NGROK_URL/track?id=thunderbird_test" width="1" height="1" />
   ```

### ProtonMail

ProtonMail proxies all images through their servers for privacy. You'll see ProtonMail's IP, not the recipient's.

### Apple Mail

1. **Format** → **Make Rich Text**
2. **Edit** → **Attachments** → **Insert** → Insert image by URL

---

## Testing Checklist

### Local Test
- [ ] Start server: `python server.py`
- [ ] Open: `http://localhost:8080/track?id=test1`
- [ ] Check dashboard shows event

### Network Test
- [ ] Find local IP (e.g., 192.168.x.x)
- [ ] Open from phone: `http://192.168.x.x:8080/dashboard`
- [ ] Trigger pixel from phone

### Internet Test
- [ ] Start ngrok: `ngrok http 8080`
- [ ] Copy public URL
- [ ] Send test email with pixel
- [ ] Open email on different device/network
- [ ] Verify event appears in dashboard

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Connection refused" on phone | Firewall blocking | Allow Python through firewall |
| Events show "Local" location | Testing from same machine | Test from different device/network |
| Gmail doesn't load images | Images blocked by default | Click "Display images" in email |
| Outlook strips the pixel | Security settings | Use file attachment or API method |
| ngrok URL not working | Free tier limits | Restart ngrok or use paid plan |
| ProtonMail shows wrong IP | Image proxy | Normal - ProtonMail anonymizes IPs |

---

## Quick Test Commands

```bash
# Test pixel via curl (simulates email open)
curl "http://localhost:8080/track?id=curl_test&sender=test@example.com"

# Test with custom User-Agent
curl -A "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)" \
  "http://localhost:8080/track?id=iphone_test"

# Test click tracking
curl -L "http://localhost:8080/click/test_click/https://example.com"
```

---

## Notes on Email Client Behavior

| Client | Image Loading | Notes |
|--------|--------------|-------|
| Gmail | Proxied | Google caches images; may see Google IPs |
| Outlook | Direct | Works well, but may block by default |
| Apple Mail | Direct | Usually loads images automatically |
| Thunderbird | Direct | Best for testing, fully supports HTML |
| ProtonMail | Proxied | Privacy-focused; shows ProtonMail IPs |
| Yahoo Mail | Proxied | Yahoo caches images |

Remember: Many email clients block images by default. The recipient must click "Load images" or have it enabled in settings.
