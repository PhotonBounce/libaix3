# OpsBrief Privacy Policy

**Last Updated:** June 1, 2025

## 1. Introduction

OpsBrief ("we," "our," or "us") is an IT Professional Intelligence Agent that provides daily AI-curated security briefings personalized to your technology stack. This Privacy Policy explains how we collect, use, store, and protect your personal information when you use the OpsBrief mobile application and related services.

By using OpsBrief, you agree to the collection and use of information in accordance with this policy.

## 2. Data We Collect

### 2.1 Account Information
- **Email Address**: Required for account creation, authentication, and communication of critical security alerts.
- **Password**: Stored using industry-standard bcrypt hashing. We never store plain-text passwords.

### 2.2 Preference Data
- **Tech Stack Preferences**: The technologies, frameworks, libraries, and services you select during onboarding. This drives the personalization of your daily security briefings.
- **Notification Settings**: Your preferences for notification frequency and alert types. Push notifications are planned for a future release.
- **Theme Preferences**: Light mode, dark mode, or system default.

### 2.3 Activity Data
- **Saved Intel**: CVEs, security advisories, and other content you bookmark or save within the app.
- **Briefing Interactions**: Which briefings you open, read time, and interaction patterns (used to improve relevance scoring).

### 2.4 Chat Messages
- **Chat History**: All messages sent to and received from the AI chat assistant. This includes follow-up questions, vulnerability comparisons, and remediation requests.
- **Message Metadata**: Timestamps, conversation threads, and context references to CVEs or briefings.

### 2.5 Device & Technical Data
- **Device ID**: Not currently collected. Push notifications are planned for a future release and may require an anonymous device identifier at that time.
- **OS Version**: For compatibility and debugging.
- **App Version**: To ensure feature parity and bug fixes.
- **IP Address**: IP addresses are temporarily logged in server access logs for security monitoring and rate limiting. Logs are retained for 90 days and then purged.

## 3. How We Use Your Data

- **Personalization**: To tailor daily briefings to your specific technology stack.
- **Service Delivery**: To provide the core briefing, chat, and saved intel functionality.
- **AI Processing**: To power the conversational AI assistant with relevant context.
- **Security**: To protect accounts, detect abuse, and prevent unauthorized access.
- **Improvement**: To analyze feature usage and improve briefing relevance and AI response quality (aggregated and anonymized where possible).
- **Communication**: To send critical security alerts, account notifications, and product updates.

## 4. Third-Party Services & Data Sharing

We do not sell your personal data. We share data only with trusted service providers necessary to operate the app:

### 4.1 Anthropic Claude
- **Purpose**: AI chat processing and natural language analysis of security briefings.
- **Data Shared**: Chat messages and related briefing context (CVE IDs, descriptions).
- **Protection**: Anthropic processes data under their API privacy terms; no data is used to train Anthropic models via our API integration.

### 4.2 Intelligence Sources (NVD, GitHub, Cisco)
- **Purpose**: Source vulnerability data for briefings.
- **Data Shared**: None. These are read-only public APIs. We do not send your data to them.

### 4.3 Infrastructure Providers
- **Purpose**: Hosting and database storage.
- **Data Shared**: User data is stored on the server. We recommend configuring HTTPS and database encryption for production deployments.
- **Providers**: [Your hosting provider, e.g., AWS / DigitalOcean / Vercel]

### 4.4 Anthropic Claude Data Processing Disclosure

When you use the AI chat assistant, your chat messages and related briefing context (such as CVE IDs and descriptions) are sent to Anthropic Claude for processing. This does not include your personal information (email, name, or account details) unless you explicitly include it in your chat message. Anthropic processes this data under their API privacy terms, and no data is used to train Anthropic models via our API integration.

## 5. Data Retention

- **Account Data**: Retained as long as your account is active.
- **Chat History**: Retained until you delete your account or request deletion. We are implementing automated data retention policies.
- **Saved Intel**: Retained until you manually delete the items or your account.
- **Briefing Logs**: Retained until you delete your account. We are implementing automated data retention policies.
- **Server Access Logs**: IP addresses are temporarily logged in server access logs for security monitoring and rate limiting. Logs are retained for 90 days and then purged.

## 6. Data Security

- **Encryption in Transit**: HTTPS/TLS is planned for production deployments. The current development setup uses HTTP. For production deployments, we strongly recommend configuring HTTPS (e.g., Let's Encrypt, Cloudflare) to protect data in transit.
- **Encryption at Rest**: We do not currently encrypt database files at rest. We recommend using PostgreSQL with TDE or filesystem encryption for production deployments.
- **Authentication**: JWT tokens with short expiration times; refresh token rotation.
- **Password Security**: bcrypt hashing with salt.
- **Access Controls**: Role-based access on the backend; admin access is strictly audited.

### 6.5 Cookies and Local Storage

This app does not use cookies. We store your authentication token in localStorage (browser storage) and your preferences on our servers.

## 7. Your Rights

You have the right to:
- **Access**: Request a copy of all personal data we hold about you.
- **Correction**: Update or correct inaccurate information through the app or by contacting us.
- **Deletion**: Request complete deletion of your account and all associated data. This is irreversible.
- **Withdraw Consent**: Opt out of non-essential data processing (note: this may limit personalization).
- **Complaint**: Lodge a complaint with your local data protection authority.

To exercise any of these rights, contact us at **privacy@photon-bounce.com**. We will respond within 30 days.

## 8. GDPR Data Deletion Rights

For users in the European Economic Area (EEA), United Kingdom, and Switzerland, we comply with the General Data Protection Regulation (GDPR) and equivalent local privacy laws.

In addition to the rights listed above, you have the following:

- **Right to Erasure ("Right to be Forgotten"):** You may request the complete deletion of all personal data we hold about you, including account data, preferences, saved intel, chat history, and any associated logs. We will process such requests within 30 days and confirm deletion via email.
- **Right to Restrict Processing:** You may request that we temporarily restrict processing of your data while a dispute is resolved.
- **Right to Object:** You may object to the processing of your data for direct marketing or profiling purposes at any time.
- **Automated Decision-Making:** We do not use automated decision-making or profiling that produces legal or similarly significant effects.

To exercise any GDPR rights, contact us at **privacy@photon-bounce.com** with the subject line "GDPR Request." We will respond within 30 days.

Our lawful basis for processing is **contractual necessity** (to provide the Service) and **legitimate interest** (security and fraud prevention). Where consent is required (e.g., for non-essential analytics), you will be asked explicitly.

## 9. Children's Privacy

OpsBrief is not intended for users under the age of 13. We do not knowingly collect personal data from children. If you believe a child has provided us with personal data, contact us immediately and we will delete it.

## 10. Changes to This Policy

We may update this Privacy Policy from time to time. We will notify you of significant changes via email or in-app notification. The "Last Updated" date at the top of this policy reflects the most recent revision.

## 11. Contact Us

For questions, concerns, or data requests related to this Privacy Policy, please contact:

**Email:** privacy@photon-bounce.com

**Company:** Photon Bounce, contact@photon-bounce.com

---

*By using OpsBrief, you acknowledge that you have read and understood this Privacy Policy.*
