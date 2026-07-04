# OpsBrief v1.0.0 — Release Summary

## What the App Does

**OpsBrief** is an AI-powered daily intelligence briefing app built for IT professionals — network engineers, system administrators, cloud engineers, and security analysts.

### Core Features
- **Daily Briefings**: Curated intel on CVEs, security patches, router/switch advisories, and critical infrastructure updates — delivered every morning based on your tech stack
- **AI Chat Assistant**: Ask natural-language questions about CVEs, configurations, vulnerabilities, and best practices. Powered by Claude 3.5 Sonnet
- **Saved Intel**: Bookmark critical items from your briefing for quick reference
- **Tech Stack Personalization**: Select your gear (Cisco, Juniper, Palo Alto, Fortinet, AWS, Azure, Kubernetes, Linux, Windows, VMware, Docker, GCP) and get only relevant alerts
- **Admin Dashboard**: Analytics, user management, and content moderation tools

### Subscription Model
| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | 1 briefing/day, 5 AI chats/day, 50 saved items |
| **VIP** | $2/year | Unlimited briefings, unlimited AI chats, unlimited saved intel, priority sources & early alerts, full history |

**VIP includes a 1-week free trial.**

---

## Google Play Submission Checklist

### App Information
- **Title**: OpsBrief: IT Intel Daily
- **Short Description**: AI-powered daily security briefings for IT professionals
- **Full Description**: See `google-play-assets/store-listing.txt`
- **Category**: Productivity / Business
- **Content Rating**: Everyone (no violence, no sensitive content)

### Assets
| Asset | File | Dimensions |
|-------|------|------------|
| Feature Graphic | `google-play-assets/feature-graphic.png` | 1024×500 |
| App Icon | `google-play-assets/app-icon.png` | 512×512 |
| Phone Screenshot 1 (Onboarding) | `google-play-assets/phone-1-onboarding.png` | 1082×2402 |
| Phone Screenshot 2 (Briefing) | `google-play-assets/phone-2-briefing.png` | 1082×2402 |
| Phone Screenshot 3 (Chat) | `google-play-assets/phone-3-chat.png` | 1082×2402 |
| Phone Screenshot 4 (Saved) | `google-play-assets/phone-4-saved.png` | 1082×2402 |
| Phone Screenshot 5 (Settings) | `google-play-assets/phone-5-settings.png` | 1082×2402 |
| Phone Screenshot 6 (Pricing) | `google-play-assets/phone-6-pricing.png` | 1082×2402 |
| APK | `OpsBrief-v1.0.0.apk` | 3.6 MB |

### Technical Details
- **Package Name**: `com.opsbrief.app`
- **Version Code**: 1
- **Version Name**: 1.0.0
- **Min SDK**: 24
- **Target SDK**: 35
- **Compile SDK**: 35
- **Architecture**: Universal (ARM, ARM64, x86, x86_64)

---

## SaaS Backend

### Tech Stack
- **Framework**: FastAPI (Python 3.11)
- **Database**: SQLite (default) / PostgreSQL (via `DATABASE_URL`)
- **Auth**: JWT with bcrypt, token refresh, JTI blacklist
- **Cache**: Redis + in-memory LRU fallback
- **AI**: Anthropic Claude 3.5 Sonnet
- **Queue**: Celery (scheduled tasks at 3 AM UTC)
- **Hosting**: Docker Compose with 6 services

### Subscription Endpoints
- `GET /api/subscription/status` — Current subscription state
- `POST /api/subscription/start-trial` — Start 7-day VIP trial
- `POST /api/subscription/upgrade` — Upgrade to VIP (Stripe/PayPal)

### New User Model Fields
- `subscription_tier` (free/vip)
- `subscription_status` (none/trialing/active/cancelled/past_due)
- `trial_started_at`, `trial_ends_at`
- `subscription_started_at`, `subscription_ends_at`, `subscription_renews_at`
- `stripe_customer_id`, `stripe_subscription_id`, `paypal_subscription_id`

---

## Frontend Visual Effects

### Added Effects
- **Animated Gradient Background**: 3-color shifting gradient over 15s
- **Parallax Floating Orbs**: 3 blur orbs with mouse/touch parallax
- **Enhanced Glassmorphism**: Cards, header, nav, chat bubbles, inputs
- **Micro-interactions**: Ripple effects, spring transitions, hover glows
- **Entrance Animations**: Staggered slideUp for cards, messageSlide for chat
- **Sound Effects**: Click, send, success, error (Web Audio API)
- **Shimmer Banner**: Guest demo banner with light sweep animation

---

## Files

### Key Deliverables
| File | Path | Description |
|------|------|-------------|
| APK | `D:/opsbrief/OpsBrief-v1.0.0.apk` | Android debug build |
| Feature Graphic | `D:/opsbrief/google-play-assets/feature-graphic.png` | Store listing banner |
| App Icon | `D:/opsbrief/google-play-assets/app-icon.png` | Launcher icon |
| Store Listing | `D:/opsbrief/google-play-assets/store-listing.txt` | Google Play copy |
| Frontend | `D:/opsbrief/frontend/index.html` | Single-file PWA |
| Backend | `D:/opsbrief/backend/` | FastAPI Python backend |

### Live URLs
- App: https://photon-bounce.com/opsbrief/app/
- Admin: https://photon-bounce.com/opsbrief/app/admin.html
- Privacy Policy: https://photon-bounce.com/opsbrief/privacy-policy.html
- Terms: https://photon-bounce.com/opsbrief/terms-of-service.html
- Microsite: https://photon-bounce.com/opsbrief/

---

## Next Steps for Google Play

1. **Sign the APK**: Create a release keystore and sign the APK for production
   ```bash
   keytool -genkey -v -keystore opsbrief-release.keystore -alias opsbrief -keyalg RSA -keysize 2048 -validity 10000
   ```

2. **Upload to Google Play Console**: Create a new app, upload APK, fill in store listing with provided assets

3. **Content Rating**: Complete the questionnaire (likely "Everyone" or "Teen")

4. **Pricing & Distribution**: Set as free app with in-app subscriptions (VIP $2/year)

5. **Set up Subscription**: Configure VIP subscription in Google Play Console with $2/year price and 1-week trial

6. **Test on Real Devices**: Install APK on physical Android devices for final QA

---

*Built by OpsBrief Team | 2026*
