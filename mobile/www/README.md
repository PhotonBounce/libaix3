# OpsBrief Mobile `www` Directory

This directory is **auto-generated** from the frontend build.

## How it is populated

Run the following from the `mobile/` directory:

```bash
npm run build-www
```

This copies all files from `../frontend/` into this directory so Capacitor can bundle them into the native Android app.

## Do not edit files here

Any manual changes will be overwritten the next time `build-www` runs. Make edits in the `frontend/` directory instead.
