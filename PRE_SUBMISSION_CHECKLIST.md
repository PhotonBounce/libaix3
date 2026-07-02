# OpsBrief Pre-Submission Checklist

## BEFORE you build the AAB — Check These

### Code
- [ ] `capacitor.config.ts` has production API URL (not localhost)
- [ ] `mobile/android/app/build.gradle` has `targetSdkVersion 35`
- [ ] All icons exist in `res/mipmap-*/`
- [ ] `www/` folder does NOT contain `node_modules` (should be ~1MB)
- [ ] Version code incremented if this is an update

### Backend
- [ ] Backend deployed and accessible via HTTPS
- [ ] `/health` endpoint returns 200
- [ ] OpenAI API key is set and chat works
- [ ] Database has at least one briefing generated (for testing)

### Google Play Console
- [ ] Developer account created and verified ($25 paid)
- [ ] App created in console
- [ ] App access set to "All functionality available"
- [ ] Ads set to "No ads"
- [ ] Content rating questionnaire completed
- [ ] Target audience: 13+ only
- [ ] Data safety form completed (copy from `store-assets/data-safety.md`)
- [ ] News app: "No"
- [ ] Government app: "No"

### Store Listing
- [ ] App name: "OpsBrief: IT Security Intel"
- [ ] Short description copied from `store-assets/store-listing.md`
- [ ] Full description copied from `store-assets/store-listing.md`
- [ ] App icon uploaded (512x512)
- [ ] Feature graphic uploaded (1024x500)
- [ ] 8 phone screenshots uploaded
- [ ] Category: Productivity
- [ ] Contact email set
- [ ] Website URL set (photon-bounce.com/opsbrief)

### Legal
- [ ] Privacy policy uploaded to photon-bounce.com/opsbrief/privacy
- [ ] Privacy policy URL added to Play Console
- [ ] Terms of service (optional but recommended)

### Build
- [ ] `npm install` completed
- [ ] `npm run build-www` completed
- [ ] `npx cap sync android` completed
- [ ] Keystore generated: `keytool -genkey -v -keystore opsbrief-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias opsbrief`
- [ ] Keystore password written down and backed up
- [ ] Keystore file backed up to 2+ locations (Google Drive, password manager)
- [ ] Release AAB built: `cd android && ./gradlew bundleRelease`
- [ ] AAB file size < 10MB
- [ ] AAB uploaded to Production track
- [ ] Release notes added

### Final Verification
- [ ] Pre-launch report: 0 crashes
- [ ] Pre-launch report: 0 ANRs
- [ ] All compliance checks green
- [ ] Rollout started
- [ ] Status shows "In review"

---

## After Launch
- [ ] Post on Reddit r/sysadmin
- [ ] Post on Reddit r/networking
- [ ] Post on Reddit r/cybersecurity
- [ ] Post on LinkedIn
- [ ] Post on Hacker News (Show HN)
- [ ] Monitor Google Play Console for reviews
- [ ] Monitor admin dashboard for user growth
