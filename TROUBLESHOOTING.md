# Troubleshooting Guide

Common issues and their fixes for OpsBrief.

---

## App shows blank screen

**Cause:** The frontend cannot reach the backend API.

**Fixes:**

1. Check that the `API_URL` in your frontend or `capacitor.config.ts` is correct and accessible.
2. Verify CORS is configured properly on the backend (`CORS_ORIGINS` in `.env` must include your domain).
3. Confirm the backend is running and healthy by visiting `GET /health` (should return `{"status":"ok"}`).
4. If using Docker, check `docker-compose ps` to ensure all containers are up.

---

## Briefing not ready

**Cause:** The daily briefing has not been generated yet.

**Fixes:**

1. Wait up to 24 hours for the first automated briefing (Celery Beat runs daily at 3 AM).
2. Manually trigger the pipeline: run the `fetch_all_intel()` and `generate_briefings()` tasks from the admin dashboard or via Python shell.
3. Verify that Redis and Celery worker are running (required for scheduled tasks).

---

## Redis connection refused

**Cause:** Redis server is not running or is unreachable.

**Fixes:**

1. The app will automatically fall back to an in-memory cache. This is fine for development but not for production.
2. For production, install and start Redis: `docker run -d -p 6379:6379 redis:latest` or use a managed Redis provider.
3. Verify the `REDIS_URL` in `.env` matches your Redis instance.

---

## OpenAI 401 error

**Cause:** The OpenAI API key is missing or invalid.

**Fixes:**

1. Add `OPENAI_API_KEY=sk-...` to your `.env` file.
2. Ensure the key has billing enabled and sufficient credits.
3. Restart the backend after updating `.env` so the new key is loaded.

---

## Docker build fails

**Cause:** Docker daemon issue, insufficient disk space, or network timeout.

**Fixes:**

1. Check that Docker Desktop (or Docker daemon) is running.
2. Ensure you have at least 10 GB of free disk space.
3. Try cleaning unused Docker images: `docker system prune -a`.
4. Re-run the build: `docker-compose up -d --build`.

---

## Android build fails

**Cause:** Missing dependencies, incorrect Node.js version, or misconfigured Android SDK.

**Fixes:**

1. Check your Node.js version: `node --version` should be v20.x or higher.
2. Verify the Android SDK is installed with API Level 34 and Build-Tools 34.0.0.
3. Ensure `JAVA_HOME` points to Java 17 (Adoptium Temurin 17 LTS is recommended).
4. Run `npm install` and `npx cap sync android` before building.
5. If Gradle fails, open the project in Android Studio and let it sync dependencies.

---

## Google Play rejection

**Cause:** Missing compliance requirements or incorrect configuration.

**Fixes:**

1. Check that `targetSdkVersion` is set to the latest stable API (34 or higher) in `build.gradle`.
2. Ensure your privacy policy is live at a publicly accessible URL and linked in the Play Console.
3. Complete the Data Safety form accurately (see `store-assets/data-safety.md`).
4. Verify your app has a proper data deletion mechanism (email request or self-service).
5. Make sure your app does not request unnecessary permissions.
6. Review the pre-launch report for crashes or ANRs and fix them before resubmitting.
