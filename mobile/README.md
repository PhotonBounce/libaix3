# OpsBrief Mobile — Capacitor Android Setup

## Prerequisites

1. Node.js 18+ (https://nodejs.org)
2. Android Studio (https://developer.android.com/studio)
3. Android SDK (installed via Android Studio)

## Setup Steps

```bash
# 1. Navigate to mobile directory
cd D:\opsbrief\mobile

# 2. Install dependencies
npm install

# 3. Build and copy frontend files to Capacitor web dir
npm run build-www

# 4. Add Android platform (first time only)
npx cap add android

# 5. Sync changes (run this after every frontend update)
npx cap sync android

# 6. Open in Android Studio
npx cap open android
```


> **⚠️ CRITICAL BUILD WARNING:** Do NOT open the project in Android Studio or run Gradle before executing `npx cap sync android`. The file `capacitor.build.gradle` is generated during sync and is **required** for compilation. Also, on Windows use `gradlew.bat` instead of `./gradlew`.
## Build Release APK

In Android Studio:
1. Build → Generate Signed Bundle / APK
2. Select APK
3. Create or use existing keystore
4. Select release build variant
5. Build

## Push Notifications (FCM)

1. Create Firebase project at https://console.firebase.google.com
2. Add Android app (package: com.opsbrief.app)
3. Download `google-services.json`
4. Place in `android/app/google-services.json`
5. Update `ANDROID_CLIENT_ID` in backend `.env`

## Troubleshooting

### Port 8000 vs production

For development, the frontend hits `http://localhost:8000`. For production, update `API_BASE` in `frontend/index.html` to your production URL (e.g., `https://api.opsbrief.com`).

### CORS issues

The backend allows all origins (`*`) in development. In production, update `allow_origins` in `main.py` to your actual domain.

### Gradle build errors

1. Update Android Studio to latest version
2. Update Gradle plugin: File → Project Structure → Gradle Version → 8.0+
3. Clean build: Build → Clean Project → Rebuild Project

## Google Play Submission

1. Sign up for Google Play Console ($25 one-time fee)
2. Create app: `com.opsbrief.app`
3. Upload signed release APK/AAB
4. Fill store listing, screenshots, privacy policy
5. Submit to Closed Testing track first
6. After review, promote to Production

## Keystore for Signing

```bash
# Generate keystore (do this once, keep file safe)
keytool -genkey -v -keystore opsbrief-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias opsbrief

# Add to android/app/build.gradle:
android {
    signingConfigs {
        release {
            storeFile file('opsbrief-key.jks')
            storePassword 'YOUR_PASSWORD'
            keyAlias 'opsbrief'
            keyPassword 'YOUR_PASSWORD'
        }
    }
    buildTypes {
        release {
            signingConfig signingConfigs.release
        }
    }
}
```
