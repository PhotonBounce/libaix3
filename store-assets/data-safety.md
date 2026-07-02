# OpsBrief Data Safety — Google Play Console Answers

> Ready for copy-paste into Google Play Console Data Safety section.

---

## OVERVIEW

**App Name:** OpsBrief  
**App Package:** com.opsbrief.app  
**Developer:** Photon Bounce Technologies  

---

## DATA COLLECTION & SHARING

### Does your app collect or share any of the required user data types?
**Yes**

### Is all of the user data collected by your app encrypted in transit?
**Yes — HTTPS/TLS is used for all production API communication.**

### Do you provide a way for users to request that their data is deleted?
**Yes** — Users can request deletion via `DELETE /api/auth/me` or by emailing privacy@photon-bounce.com.

---

## DATA TYPES — DETAILED BREAKDOWN

| Data Type | Collected? | Shared? | Encrypted? | Required? | Purpose |
|-----------|------------|---------|------------|-----------|---------|
| **Name** | Yes | No | Yes | Yes | Account creation and personalization |
| **Email address** | Yes | No | Yes | Yes | Account creation, authentication, critical alerts, password reset |
| **Phone number** | No | N/A | N/A | No | N/A |
| **Address** | No | N/A | N/A | No | N/A |
| **User preferences** (tech stack, notifications, theme) | Yes | No | Yes | No | Personalization of daily briefings and app experience |
| **App activity** (saved intel, bookmarks) | Yes | No | Yes | No | Core app feature — user-curated security knowledge base |
| **Messages** (chat with AI assistant) | Yes | Yes — with Anthropic | Yes | No | AI chat processing, threat analysis, remediation guidance |
| **Photos / Videos** | No | N/A | N/A | No | N/A |
| **Location** | No | N/A | N/A | No | N/A |
| **Files / docs** | No | N/A | N/A | No | N/A |
| **Contacts** | No | N/A | N/A | No | N/A |
| **Calendar events** | No | N/A | N/A | No | N/A |
| **Browsing history** | No | N/A | N/A | No | N/A |
| **Financial info** | No | N/A | N/A | No | N/A |
| **Health / fitness** | No | N/A | N/A | No | N/A |
| **Device / other IDs** | No | N/A | N/A | No | N/A |
| **Crash logs** | No | N/A | N/A | No | N/A |
| **Diagnostics** | No | N/A | N/A | No | N/A |
| **App interactions** | Yes | No | Yes | No | Analytics and feature improvement |
| **Search history** | No | N/A | N/A | No | N/A |
| **IP address** | Yes | No | N/A | No | Security monitoring, rate limiting, and abuse prevention. Retained for 90 days. |

---

## THIRD-PARTY DATA SHARING

| Third Party | Data Shared | Purpose | User Consent |
|-------------|-------------|---------|--------------|
| **Anthropic Claude** | Chat messages and briefing context (CVE IDs, descriptions). Personal information (email, name, account details) is not shared. | AI chat processing, natural language threat analysis | Explicit — users must opt in via onboarding checkbox and accept the Terms of Service |
| **NVD (National Vulnerability Database)** | None | Read-only public API — source of CVE data | N/A |
| **GitHub Security Advisories** | None | Read-only public API — source of CVE data | N/A |
| **Cisco Security Advisories** | None | Read-only public API — source of threat intel | N/A |
| **Push notification provider** | None | N/A | N/A |

> **Note:** Push notifications are not yet implemented. No data is currently shared with push notification providers.

> **Note:** No data is sold to any third party. No data is used for advertising or marketing beyond in-app product updates.
> **Onboarding Consent:** New users must explicitly check boxes during registration confirming they are 13 years of age or older, agreeing to the Terms of Service and Privacy Policy, and acknowledging that their chat messages and briefing context will be shared with Anthropic Claude for AI processing. These checkboxes are required before account creation can proceed.

---

## SECURITY PRACTICES

| Practice | Implementation |
|----------|----------------|
| **Transport Encryption** | HTTPS/TLS is used for all production API communication. |
| **Password Hashing** | bcrypt with per-user salt |
| **API Security** | Rate limiting, CORS restrictions, input validation |
| **Third-Party API Keys** | Server-side only; never exposed to client app |

---

## ACCOUNT CREATION & DELETION

| Question | Answer |
|----------|--------|
| **Is account creation required?** | Yes — Required to personalize daily briefings to your tech stack and save intel. |
| **Age verification?** | Yes — Users must confirm they are 13 years of age or older during account creation. |
| **Can users delete their account?** | Yes — Use the `DELETE /api/auth/me` endpoint or email privacy@photon-bounce.com with the subject "Delete My Account." We will delete all personal data within 30 days and confirm via email. |
| **What happens to saved data on deletion?** | All account data, preferences, saved intel, and chat history are permanently deleted. This is irreversible. |
| **Can users export data?** | Data export functionality is planned. Users may also request their data via email to privacy@photon-bounce.com. |

---

## GOOGLE PLAY POLICY COMPLIANCE

- [x] Data collection is clearly disclosed in this document and the Privacy Policy.
- [x] User consent is obtained via Terms of Use acceptance at account creation.
- [x] Data is encrypted in transit (HTTPS/TLS is used for all production API communication).
- [x] Users have a clear path to request data deletion.
- [x] Third-party sharing is limited to essential service providers (Anthropic Claude for AI chat only).
- [x] No data is used for advertising, tracking, or profiling beyond app functionality.
- [x] Children under 13 are not permitted to use the app.

---

**Developer Contact:** privacy@photon-bounce.com  
**Last Updated:** June 1, 2025
