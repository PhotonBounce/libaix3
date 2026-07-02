# OpsBrief: Google Play Store Submission Guide

## From Zero to Live on Google Play — Complete Step-by-Step

**Last updated:** June 2025
**Target:** Google Play Console, API Level 35 (Android 15), Closed Testing
**Estimated time:** 2-4 hours (first time), 30 minutes (subsequent releases)

---

## Prerequisites Checklist

Before you start, verify you have:

- [ ] A Google Play Developer account ($25 one-time fee) — https://play.google.com/console
- [ ] A computer with Windows 10/11 or macOS
- [ ] At least 10 GB free disk space
- [ ] The OpsBrief code folder at `D:/opsbrief` (or wherever you cloned it)
- [ ] Your backend deployed and accessible via HTTPS (e.g., `https://api.opsbrief.com`)
- [ ] A valid OpenAI API key (for chat to work in the app)

---

## Phase 1: Install Build Tools (One-Time Setup)

### 1.1 Install Node.js

Download from https://nodejs.org/ — get the LTS version (20.x or higher).

Verify:
```bash
node --version   # Should show v20.x.x
npm --version    # Should show 10.x.x
```

### 1.2 Install Android Studio

Download from https://developer.android.com/studio

During setup, install:
- Android SDK
- Android SDK Platform (API 35)
- Android SDK Build-Tools (35.0.0)
- Android Emulator (optional, for testing)
- Intel x86 Emulator Accelerator (HAXM) (optional)

### 1.3 Set Environment Variables

**Windows:**
```powershell
# Add to System PATH:
# C:\Users\YOURNAME\AppData\Local\Android\Sdk\platform-tools
# C:\Users\YOURNAME\AppData\Local\Android\Sdk\cmdline-tools\latest\bin
# C:\Program Files\nodejs\
```

Verify:
```bash
adb --version
```

### 1.4 Install Java 17

Download from https://adoptium.net/ — Temurin 17 LTS

Set `JAVA_HOME` to the installation directory.

Verify:
```bash
java -version  # Should show 17.x.x
```

---

## Phase 2: Build the Android App

### 2.1 Navigate to Mobile Folder

```bash
cd D:/opsbrief/mobile
```

### 2.2 Install Dependencies

```bash
npm install
```

This installs Capacitor CLI, Android platform, and plugins.

### 2.3 Build and Copy Frontend to Mobile Wrapper

> **Note:** Run `npm run build-www` first to build the frontend before every sync.

```bash
npm run build-www
```

This copies `D:/opsbrief/frontend/*` into `mobile/www/`

### 2.4 Add Android Platform (First Time Only)

```bash
npx cap add android
```

This creates the `mobile/android/` folder with all native Android project files.

### 2.5 Sync Capacitor Configuration

```bash
npx cap sync android
```

This syncs web assets, plugins, and configuration into the Android project.

### 2.6 Verify Icons Are in Place

Check that these files exist:
```
mobile/android/app/src/main/res/
├── mipmap-mdpi/ic_launcher.png
├── mipmap-hdpi/ic_launcher.png
├── mipmap-xhdpi/ic_launcher.png
├── mipmap-xxhdpi/ic_launcher.png
├── mipmap-xxxhdpi/ic_launcher.png
├── mipmap-anydpi-v26/ic_launcher.xml
└── drawable/ic_launcher_background.xml
```

If missing, copy them from `D:/opsbrief/mobile/android/app/src/main/res/` (they should already be there from the icon generation step).

### 2.7 Update Production API URL

Edit `mobile/capacitor.config.ts` and set the production URL:
```typescript
server: {
  androidScheme: 'https',
  cleartext: false,
  url: 'https://api.opsbrief.com',  // YOUR production API
}
```

**IMPORTANT:** Do NOT use `http://localhost:8000` for the store build. The app needs a real HTTPS backend.

### 2.8 Verify build.gradle Settings

Open `mobile/android/app/build.gradle` and confirm:
```gradle
compileSdkVersion 35
targetSdkVersion 35
minSdkVersion 26
versionCode 1
versionName "1.0.0"
```

If you need to update these, edit the file before building.

---

## Phase 3: Create Signing Key

### 3.1 Generate Keystore

```bash
cd D:/opsbrief/mobile/android/app

keytool -genkey -v \
  -keystore opsbrief-key.jks \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10000 \
  -alias opsbrief
```

When prompted:
- **Keystore password:** Choose a STRONG password, write it down
- **Key password:** Can be same as keystore password
- **First/Last name:** Your name
- **Organizational unit:** IT
- **Organization:** Photon Bounce
- **City/State:** Your city
- **Country code:** US (or your country)

**CRITICAL:** Back up `opsbrief-key.jks` somewhere safe (Google Drive, password manager). You CANNOT update the app without this file.

### 3.2 Enable Play App Signing (Required for New Apps)

Google Play requires **Play App Signing** for all new apps. This means Google manages the final app signing key.

1. After uploading your first AAB to Google Play, go to **Setup → App integrity**.
2. Select **Play App Signing**.
3. Choose **Create new key** (Google generates and protects the signing key).
4. Upload your `opsbrief-key.jks` as the **upload key** — Google uses this to verify your identity, then re-signs the app with their managed key.
5. Download the `deployment_cert.pem` and store it for CI/CD if needed.

> **Note:** You keep your upload key (`opsbrief-key.jks`), but Google controls the final signing key. This is mandatory and cannot be disabled for new apps.

### 3.3 Configure Keystore in build.gradle

Edit `mobile/android/app/build.gradle` and add:
```gradle
android {
    ...
    signingConfigs {
        release {
            storeFile file('opsbrief-key.jks')
            storePassword 'YOUR_KEYSTORE_PASSWORD'
            keyAlias 'opsbrief'
            keyPassword 'YOUR_KEY_PASSWORD'
        }
    }
    buildTypes {
        release {
            signingConfig signingConfigs.release
            ...
        }
    }
}
```

**SECURITY WARNING:** Never commit this file with passwords. In production, use environment variables or a CI/CD secret manager.

---

## Phase 4: Build Release APK/AAB

### 4.1 Build APK (Testing)

```bash
cd D:/opsbrief/mobile/android
# Windows (Command Prompt / PowerShell):
gradlew.bat assembleDebug
# Git Bash / WSL:
./gradlew assembleDebug
```

Output: `mobile/android/app/build/outputs/apk/debug/app-debug.apk`

### 4.2 Build Release AAB (Google Play Requires AAB)

```bash
cd D:/opsbrief/mobile/android
# Windows (Command Prompt / PowerShell):
gradlew.bat bundleRelease
# Git Bash / WSL:
./gradlew bundleRelease
```

Output: `mobile/android/app/build/outputs/bundle/release/app-release.aab`

**AAB is REQUIRED for Google Play.** Do not upload APK.

### 4.3 Verify Build

Check the file size. It should be 2-8 MB. If it's 100+ MB, something is wrong (check that `node_modules` wasn't copied into `www/`).

---

## Phase 5: Google Play Console Setup

### 5.1 Create Developer Account

1. Go to https://play.google.com/console
2. Sign in with your Google account
3. Pay $25 one-time fee
4. Complete identity verification (may take 1-3 days)

### 5.2 Create App

1. Click "Create app"
2. **App name:** OpsBrief
3. **Default language:** English (United States)
4. **App type:** App
5. **Free or paid:** Free (for now)
6. **Declarations:** Check all required boxes
7. Click "Create app"

### 5.3 Set Up App

Complete each section in the left sidebar:

#### Dashboard → Set up your app

**App access:**
- Select "Functionality is limited without special access — login is required for all core features (briefing, chat, saved intel)."

**Ads:**
- Select "No, my app does not contain ads"

**Content rating:**
- Click "Start questionnaire"
- Category: "News & Magazines"
- Answer "No" to all violence, sexual content, etc. questions
- This is a security tool, not a game

**Target audience:**
- 18+ only (IT professionals)
- Do NOT select under 18 — this triggers COPPA and extra requirements

**News apps:**
- Select "No, this app is not a news app" (it's a security tool, not a news publisher)

**Data safety:**
- See `store-assets/data-safety.md` — copy all answers from there
- Data collected: Email, Preferences, App activity, Messages
- Shared with: OpenAI (chat processing), NVD/GitHub/Cisco (intel)
- Encryption: Yes (HTTPS/TLS)
- Account required: Yes
- Data deletion: Yes (contact privacy@photon-bounce.com)
- **Data deletion URL:** https://photon-bounce.com/opsbrief/privacy (must be a live, publicly accessible URL linked in the Play Console Data safety form)

**Government apps:**
- Select "No"

---

## Phase 5.5: Closed Testing Track (Required for New Accounts)

> **Important:** New Google Play Developer accounts must complete a **Closed Testing** track before they can access Production. This is a mandatory Google Play policy as of 2023.

### Requirements

- **Minimum duration:** 14 days of active testing
- **Minimum testers:** 20 testers enrolled and active
- **Testing quality:** No critical crashes, no policy violations

### How to Set Up Closed Testing

1. In Google Play Console, go to **Testing → Closed Testing**.
2. Click **Create track** (or use the default "Closed Testing" track).
3. Upload your `app-release.aab` to the Closed Testing track.
4. Add at least **20 testers** via email list or Google Groups.
5. Share the opt-in link with your testers.
6. Wait **14 days** while testers use the app.
7. Monitor the pre-launch report and crash reports.
8. After 14 days with 20+ active testers and no critical issues, Google will unlock the Production track.

### Tester Tips

- Recruit testers from Reddit, LinkedIn, or your professional network.
- Ask testers to verify core features: registration, briefing, chat, saved intel.
- Respond to any crash reports within 48 hours and upload a fixed build if needed.

---

## Phase 6: Store Listing

### 6.1 Main Store Listing

**App name:** OpsBrief: IT Security Intel

**Short description:** (copy from `store-assets/store-listing.md`)

**Full description:** (copy from `store-assets/store-listing.md`)

### 6.2 Upload Graphics

**App icon:**
- Upload `store-assets/feature-graphic.png` (or use the 512x512 icon)
- Actually, the app icon should be the 512x512 PNG. Use `frontend/icon-512.png`.

**Feature graphic:**
- Upload `store-assets/feature-graphic.png` (1024x500)

**Phone screenshots:**
- Upload all 8 screenshots from `store-assets/screenshots/`
- Order: Login → Onboarding → Briefing → Chat → Saved → Settings → Admin → Dark Mode

**Tablet screenshots:** (optional but recommended)
- If you have a tablet, take screenshots there too. Otherwise, skip.

**Video:** (optional)
- Skip for first release. Add later if you have time.

### 6.3 Categorization

**App category:** Productivity
**Tags:** Security, IT, CVE, Network, DevOps

### 6.4 Contact Details

**Email:** your-email@photon-bounce.com
**Website:** https://photon-bounce.com/opsbrief

---

## Phase 7: Upload AAB

### 7.1 Go to Production → Create Release

1. Left sidebar → Production → Create new release
2. Upload your `app-release.aab` file
3. Release name: `1.0.0 (1)`
4. Release notes: Copy from `store-assets/store-listing.md` "What's New" section

### 7.2 Review and Rollout

1. Check "Compliance" section — all green checkmarks?
2. If any issues, fix them (most common: missing data safety, content rating)
3. Click "Start rollout to Production"

---

## Phase 8: Pre-Launch Report (Automatic)

Google Play will automatically test your app on 10+ devices. Wait 1-2 hours.

Check for:
- Crashes
- ANRs (App Not Responding)
- Security warnings
- Performance issues

**If crashes:** Fix the bug, rebuild AAB, upload new version with `versionCode 2`.

---

## Phase 9: Go Live

After pre-launch report passes:

1. Go to Production → Release → Edit
2. Click "Review release"
3. Confirm all checkboxes
4. Click "Start rollout to Production"

**Processing time:** 1-3 days for first review. Subsequent updates are usually instant.

---

## Phase 10: Post-Launch

### 10.1 Monitor

- Google Play Console → Statistics → Installations
- Google Play Console → Reviews → Check for 1-star reviews
- Backend admin dashboard (`frontend/admin.html`) → Monitor user growth

### 10.2 Marketing

Post on:
- Reddit r/sysadmin
- Reddit r/networking
- Reddit r/cybersecurity
- LinkedIn
- Hacker News "Show HN"

### 10.3 Iterate

Based on feedback, plan v1.1:
- Push notifications (FCM)
- Pro tier with in-app purchase
- More data sources (StackExchange, AWS bulletins)
- Team/shared briefings

---

## Troubleshooting

### Build fails with "Could not find gradle"
```bash
# In Android Studio, File → Settings → Build, Execution, Deployment → Build Tools → Gradle
# Select "Use Gradle from: 'gradle-wrapper.properties' file"
```

### AAB is too large (>50MB)
```bash
# Check www/ folder doesn't include node_modules
# Re-run: npm run build-www
# Check: ls -la mobile/www/ | should be ~1MB, not 100MB
```

### App shows blank screen
- Check that the API URL in `capacitor.config.ts` is correct and accessible
- Check browser console for CORS errors
- Verify backend is running and `/health` returns 200

### Keystore lost
- You CANNOT recover a lost keystore
- You must create a new app with a different package ID
- BACK UP YOUR KEYSTORE IMMEDIATELY

### Google Play rejection reasons
1. **Missing privacy policy** → Upload to photon-bounce.com/opsbrief/privacy
2. **App crashes** → Check pre-launch report, fix crashes, rebuild
3. **Misleading description** → Don't claim "official" or "government" status
4. **Inappropriate content** → This is a security tool, not a news app. Clarify category.
5. **Target SDK too low** → Ensure `targetSdkVersion 35` in build.gradle

---

## Quick Reference

| Task | Command |
|------|---------|
| Install deps | `npm install` |
| Copy frontend | `npm run build-www` |
| Add Android | `npx cap add android` |
| Sync config | `npx cap sync android` |
| Open Android Studio | `npx cap open android` |
| Build debug APK | `cd android && gradlew.bat assembleDebug` (Windows) or `./gradlew assembleDebug` (Mac/Linux) |
| Build release AAB | `cd android && gradlew.bat bundleRelease` (Windows) or `./gradlew bundleRelease` (Mac/Linux) |
| Generate keystore | `keytool -genkey -v -keystore opsbrief-key.jks -keyalg RSA -keysize 4096 -validity 10000 -alias opsbrief` |

---

## Files You Need

| File | Purpose |
|------|---------|
| `mobile/android/app/build/outputs/bundle/release/app-release.aab` | Upload to Google Play |
| `mobile/android/app/opsbrief-key.jks` | BACK THIS UP — needed for all updates |
| `store-assets/store-listing.md` | Copy into Play Console |
| `store-assets/data-safety.md` | Copy into Play Console Data Safety |
| `store-assets/privacy-policy.md` | Upload to your website |
| `store-assets/feature-graphic.png` | Upload to Play Console |
| `store-assets/screenshots/*.png` | Upload to Play Console |

---

## You're Done When:

- [x] Backend deployed on HTTPS with working API
- [x] AAB file built and < 10MB
- [x] Keystore backed up in 2+ locations
- [x] Google Play Console app created
- [x] Store listing filled out with all graphics
- [x] Data safety form completed
- [x] Content rating questionnaire completed
- [x] AAB uploaded to Production track
- [x] Pre-launch report passed with 0 crashes
- [x] Rollout started
- [x] App is "Live" on Google Play

**Next: Wait for review, then market the hell out of it.**
