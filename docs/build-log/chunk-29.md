# Chunk 29: Store release

Prompt: prepare the App Store and Google Play release (icons, splash, name, version and
build numbers; Android signing from env and an iOS signing checklist; permission texts and
a privacy policy page; a Guideline 4.2 and Google Play policy checklist with the listing
fields; TestFlight and Play internal testing steps). PRD: NFR Security, Platforms; the
2026-10-23 platform decision. Unattended run: choices made without asking are in
docs/OPEN_QUESTIONS.md "Chunk 29: Store release".

## Plan

- No new models. One new endpoint and one public page in the backend:
  - `GET /api/v1/legal/privacy/` (open to everyone): the privacy policy as data (title,
    last updated, operator, contact email, sections). The operator name and contact email
    come from the environment (`PRIVACY_OPERATOR_NAME`, `PRIVACY_CONTACT_EMAIL`), never a
    club's name in code.
  - `GET /privacy/`: the same policy as a plain HTML page, so the store listings have a
    public URL that works without the app.
- Screen: `/privacy` (public, no sign-in) renders the policy from the API; linked from
  Sign up and Profile. Profile shows the app version and build ("Version 1.0.0 (1)").
- Icons and splash: `frontend/scripts/app-assets.mjs` (`npm run assets`) draws the icon (a
  pitch outline in `accent` on `ground`, read from `src/styles/tokens.css`) and renders it
  with sharp into the iOS AppIcon (1024, no alpha), the Android launcher icons (legacy,
  round, adaptive foreground) and every splash. Android adaptive background and Android 12
  splash colour set to `ground`; the iOS launch screen background too.
- Version: `frontend/release.json` holds `version` and `build`. Android Gradle reads it;
  `npm run version:apply` writes it into the iOS project (MARKETING_VERSION,
  CURRENT_PROJECT_VERSION); `npm run version:bump` adds one to the build. Vite exposes it
  to the app.
- Android signing: a `release` signing config read only from env
  (`LEAGUEAPP_KEYSTORE_FILE`, `LEAGUEAPP_KEYSTORE_PASSWORD`, `LEAGUEAPP_KEY_ALIAS`,
  `LEAGUEAPP_KEY_PASSWORD`); keystores git-ignored.
- iOS: `ITSAppUsesNonExemptEncryption` false (HTTPS only), `arm64` instead of `armv7`,
  clearer camera text; a privacy manifest `PrivacyInfo.xcprivacy` (added to the target by
  hand).
- docs/STORE_RELEASE.md: assets and version steps, Android signing, iOS signing
  checklist, permission texts, Guideline 4.2 and Google Play policy checklists, the store
  listing fields to fill in, TestFlight and Play internal testing steps.
- Tests: pytest for the policy endpoint and page (open to all, env values, no club name);
  Vitest for the privacy screen, the version line, the asset and version scripts.

## Later (not in this chunk)

- In-app account deletion (App Store Guideline 5.1.1(v), Google Play account deletion
  policy). Needed before submission; how it meets the append-only ledger is a decision.
- A real home screen and tab bar (the home is still the chunk 1 placeholder; Guideline
  4.2 and 2.1 reviewers open it first).
- Firebase on iOS (chunk 10 manual steps) and a feature graphic for Google Play.

## Result

### Built

- Privacy policy (`backend/core/legal.py`): `GET /api/v1/legal/privacy/` (open to all,
  ignores auth) and the public page `GET /privacy/` (Django template, escaped, design
  tokens). Operator and contact from `PRIVACY_OPERATOR_NAME` and `PRIVACY_CONTACT_EMAIL`
  (in `.env.example`). Written for POPIA and for what the app keeps; says card data and
  camera images are never kept.
- Screen `/privacy` (no sign-in) with Back, Retry, the contact email as a link and the app
  version; linked from Sign up and Profile. Profile shows "Version 1.0.0 (1)". Proposed
  component `la-link`.
- Icons and splash: `npm run assets` (`frontend/scripts/app-assets.mjs`, sharp) draws a
  pitch outline in `accent` on the Night `ground` from `tokens.css` into the iOS AppIcon
  (1024, opaque) and launch image, Android legacy/round/adaptive icons and every splash,
  and the store icons in `frontend/assets/store/`. Android adaptive background and
  Android 12+ splash colour, and the iOS launch screen background, are `ground`.
- Version: `frontend/release.json` (1.0.0, build 1). Gradle reads it; `npm run
  version:apply|bump|set` writes it into the iOS project; Vite exposes it to the app.
- Android release signing from `LEAGUEAPP_KEYSTORE_FILE`, `LEAGUEAPP_KEYSTORE_PASSWORD`,
  `LEAGUEAPP_KEY_ALIAS`, `LEAGUEAPP_KEY_PASSWORD` only; keystores, `.p12`, `.p8` and
  provisioning profiles git-ignored. Checked with a throwaway key: `bundleRelease` signs.
- Android `minSdkVersion` 24 to 26: the chunk 21 barcode scanner needs 26 and the
  Android build failed its manifest merge without it.
- iOS: camera text, `ITSAppUsesNonExemptEncryption` false, `arm64` instead of `armv7`,
  `PrivacyInfo.xcprivacy` added to the App target (no tracking, data as in the policy,
  UserDefaults reason CA92.1). Simulator build succeeds; Package.resolved pins
  OSBarcodeLib-iOS 3.0.0.
- docs/STORE_RELEASE.md: what the repo holds, Android signing, iOS signing checklist,
  permission texts, privacy answers for both stores, Guideline 4.2 and Google Play policy
  checklists, store listing fields, TestFlight and Play internal testing steps.
- Tests: `backend/core/tests/test_privacy.py` (6); Vitest `PrivacyPage.test.tsx` (5), a
  Profile test, `scripts/app-version.test.mjs` (11), `scripts/app-assets.test.mjs` (7).
  `npm run gen:api` run.

### Not built

- In-app account deletion (App Store 5.1.1(v), Google Play): needs a decision on the
  ledger (OPEN_QUESTIONS.md). Blocks review.
- The real home screen and tab bar: `/` is still the chunk 1 placeholder. Blocks review.
- Google Play feature graphic (1024 x 500) and store screenshots.
- Store accounts, uploads and listings (need a person).

### By hand

1. Set `PRIVACY_OPERATOR_NAME` and `PRIVACY_CONTACT_EMAIL` in the production backend and
   have the policy text checked by the POPIA Information Officer.
2. Make the Android upload keystore and export the four `LEAGUEAPP_*` variables
   (docs/STORE_RELEASE.md section 2).
3. Apple Developer and Google Play developer accounts (organisation, D-U-N-S), the iOS
   signing checklist (section 3) and the chunk 10 Firebase steps.
4. Fill in the store listings and privacy answers (sections 6 and 8), with demo accounts
   for review.
5. Ship TestFlight and Play internal testing builds (sections 9 and 10).
6. Answer the Chunk 29 open questions (account deletion, home screen, iPad, operator).

Checks: make test 978 passed; make lint clean; npm test 364 passed (60 files); npm run
build ok; npx cap sync ok; iOS simulator build ok; Android assembleDebug and signed
bundleRelease ok.
