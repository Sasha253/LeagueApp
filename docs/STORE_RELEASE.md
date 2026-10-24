# Store release: App Store and Google Play

How League App goes from this repo to TestFlight and Google Play internal testing, and what
must be true before it goes to review. The app is the React frontend wrapped with Capacitor
(frontend/ios, frontend/android); see the 2026-10-23 platform decision in DECISIONS.md.

Built in chunk 29. Choices made without asking are in OPEN_QUESTIONS.md, "Chunk 29: Store
release".

## 1. What the repo already holds

| What | Where | How to change it |
|---|---|---|
| App id / bundle id | `za.co.leagueapp` (capacitor.config.ts, Android `applicationId`, iOS `PRODUCT_BUNDLE_IDENTIFIER`) | Never, once uploaded: the stores tie the listing to it |
| App name on the phone | "League App" (capacitor.config.ts, Android `strings.xml`, iOS `CFBundleDisplayName`) | All three together; "League App" is the design system's working name |
| Version and build | `frontend/release.json` | `npm run version:bump` (build + 1) or `npm run version:set -- 1.1.0` (new version, build + 1) |
| Icons and splash | Generated into the iOS and Android projects, store icons in `frontend/assets/store/` | Change the mark or tokens, then `npm run assets` |
| Privacy policy | `backend/core/legal.py`; public page `/privacy/` on the API host; in the app at `/privacy` (Sign up and Profile link to it) | Edit `legal.py`, move `UPDATED_ON`, update the store privacy answers (section 6) |
| Permission texts | iOS `Info.plist`, Android `AndroidManifest.xml` | Section 4 |
| iOS privacy manifest | `frontend/ios/App/App/PrivacyInfo.xcprivacy` (in the App target) | Keep in step with section 6 |
| Android release signing | `frontend/android/app/build.gradle`, from environment variables only | Section 2 |

Version rules: `version` is what people see ("1.0.0", iOS `MARKETING_VERSION`, Android
`versionName`). `build` is one whole number for both stores (iOS `CURRENT_PROJECT_VERSION`,
Android `versionCode`). Each upload to either store needs a build number it has not seen,
so run `npm run version:bump` before every upload and commit `release.json` and
`project.pbxproj`. Android reads `release.json` at build time; iOS reads the Xcode project,
which `version:bump`, `version:set` and `version:apply` keep in step (a test checks it).

Icons: the design system has no logo yet, so the icon is a pitch outline in `accent` on the
Night `ground`, drawn by `frontend/scripts/app-assets.mjs` from `src/styles/tokens.css`.
No text, no club crest. When a brand mark exists, replace `pitchMark` in that script and
run `npm run assets`; every size follows.

## 2. Android signing

Google Play App Signing holds the key that signs the installed app; you keep an **upload
key** and sign each bundle with it. The keystore and its passwords never go in git
(`*.jks` and `*.keystore` are ignored) and are read only from the environment.

1. Make the upload keystore once, outside the repo, and back it up with its passwords in
   the team password manager (losing it means asking Google to reset the upload key):
   ```sh
   keytool -genkeypair -v -storetype PKCS12 -keystore ~/secure/leagueapp-upload.jks \
     -alias upload -keyalg RSA -keysize 2048 -validity 10000
   ```
2. Export these before a release build (a shell profile outside the repo, or CI secrets):
   ```sh
   export LEAGUEAPP_KEYSTORE_FILE=~/secure/leagueapp-upload.jks
   export LEAGUEAPP_KEYSTORE_PASSWORD=...
   export LEAGUEAPP_KEY_ALIAS=upload
   export LEAGUEAPP_KEY_PASSWORD=...
   ```
   Without all four, `bundleRelease` still builds but the bundle is unsigned and Play
   refuses it.
3. Build the bundle (section 8 has the full steps):
   `cd frontend/android && ./gradlew bundleRelease` gives
   `app/build/outputs/bundle/release/app-release.aab`.
4. Check it is signed with the upload key:
   `keytool -printcert -jarfile app/build/outputs/bundle/release/app-release.aab`.

## 3. iOS signing checklist

- [ ] Apple Developer Program membership, enrolled as the organisation that runs the app
      (needs a D-U-N-S number), not a person and not a club.
- [ ] Identifier `za.co.leagueapp` registered (Certificates, Identifiers & Profiles) with
      the Push Notifications capability.
- [ ] Xcode (`npx cap open ios` in frontend/): App target > Signing & Capabilities: your
      Team, "Automatically manage signing" on. Xcode makes the Apple Distribution
      certificate and the App Store profile. The Team id it writes into `project.pbxproj`
      is not a secret and may be committed.
- [ ] Capabilities: Push Notifications, and Background Modes > Remote notifications
      (chunk 10, build-log/chunk-10.md "By hand" steps 3 and 4: Firebase SDK,
      `GoogleService-Info.plist`, APNs key uploaded to Firebase).
- [ ] App Store Connect: New App with bundle id `za.co.leagueapp`, SKU (for example
      `leagueapp-ios`), primary language English (U.K.) or English (U.S.).
- [ ] Never commit `.p12` certificates, `.p8` keys or `.mobileprovision` profiles (all
      git-ignored). Keep them in the password manager.
- [ ] Export compliance is answered in `Info.plist` (`ITSAppUsesNonExemptEncryption` =
      false: the app only uses HTTPS), so uploads skip the question.

## 4. Permission texts

| Permission | Platform | Text the person sees | Asked when |
|---|---|---|---|
| Camera | iOS (`NSCameraUsageDescription`) | "League App uses the camera to scan Payment Barcodes at the gate. Nothing the camera sees is saved." | An Admin or Referee first taps Scan ticket |
| Camera | Android (`CAMERA`, camera not required) | The system's own text; the app shows no extra screen | Same |
| Notifications | iOS | The system's own text (iOS allows no custom text) | Right after sign-in, once |
| Notifications | Android 13+ (`POST_NOTIFICATIONS`) | The system's own text | Right after sign-in, once |

Saying no is fine: the inbox shows every notification, and the gate screen can type a
code in. Nothing else is asked for (no location, contacts, photos or tracking).

## 5. Privacy policy

- Store URL: `https://<API host>/privacy/`, served by Django, no sign-in.
- In the app: `/privacy`, open without signing in, linked from Sign up and Profile.
- Set `PRIVACY_OPERATOR_NAME` (the business that runs the app) and
  `PRIVACY_CONTACT_EMAIL` in the backend environment before submitting. Without them the
  page says "The business that runs League App" and sends questions to the Club's Admin,
  which reviewers may reject.
- Have the text read by whoever answers for POPIA (the Information Officer) before launch.

## 6. Store privacy answers

Both stores ask what the app collects. These match `legal.py` and `PrivacyInfo.xcprivacy`;
change all three together.

App Store Connect > App Privacy ("Data linked to you", purpose App Functionality, no
tracking): Name, Email Address, Phone Number, User ID, Purchase History (payments and
bookings), Other User Content (match replies), Device ID (push token). Not collected:
location, contacts, photos, browsing, search, health, financial info (card data goes to
PayFast), diagnostics, advertising data.

Google Play > Data safety: data collected, not shared for advertising, encrypted in
transit, people can ask for deletion (only once account deletion exists, see section 7):
- Personal info: Name, Email address, Phone number (App functionality, Account management;
  required).
- Financial info: Purchase history (App functionality; required). Card details: not
  collected by the app (PayFast).
- App activity: Other user-generated content (match replies) (App functionality).
- Device or other IDs: push token (App functionality).
- Shared with: none for advertising; PayFast and Firebase are service providers acting for
  the app, which Play does not count as sharing.

## 7. Review checklists

### App Store: Guideline 4.2 (minimum functionality) and related

A Capacitor app is reviewed as a possible "repackaged website". What makes League App an
app, and what still has to be done:

- [x] Native push notifications (APNs through Firebase) for match confirmations, requests
      and updates, with buttons on the notification (4.2, 4.5.4: not needed to use the
      app, not used for marketing).
- [x] Camera barcode scanning at the gate (native scanner plugin).
- [x] Sign-in token kept in native storage; no session cookies.
- [x] PayFast opens in the in-app browser and returns to the app.
- [x] Safe areas, no browser chrome, no links out to a website for core features.
- [ ] **Must fix before review: the home screen.** `/` still shows the chunk 1
      placeholder ("API connected"). Reviewers open it first and will reject it under 2.1
      (completeness) and 4.2. It needs the real home and the role-aware tab bar from the
      design system (TabBar).
- [ ] **Must fix before review: account deletion (5.1.1(v)).** An app with sign-up must
      let people delete their account from inside the app. Not built; how deletion meets
      the append-only ledger (FR-50) is an open question (OPEN_QUESTIONS.md, chunk 29).
- [ ] Demo accounts for App Review Information: one Player, one Captain, one Admin of a
      demo Club (not a real club's name) with a Night, Division, Teams and a fixture in the
      next days, so the reviewer can reply to a Confirmation, see a Payment Barcode and
      open the scanner. Add a short note explaining the roles.
- [ ] Review notes: card payments are for league fees and field hire, real-world services
      used outside the app (3.1.3(e)), so they go through PayFast, not In-App Purchase.
- [ ] 4.8 (Sign in with Apple) does not apply: the app has only its own email sign-in.
- [ ] 2.3: screenshots show the real app with demo data; no club's name or crest (5.2).
- [ ] iPad: the project allows iPad (`TARGETED_DEVICE_FAMILY = 1,2`), so the listing needs
      13-inch iPad screenshots and reviewers may test on iPad. Either check the screens at
      iPad sizes or set the target to iPhone only before the first upload.
- [ ] Privacy policy URL set and reachable; privacy answers (section 6) filled in.

### Google Play policy

- [x] Target API level 36 (Play requires a recent one; `variables.gradle`).
- [x] Minimum Android 8.0 (API 26): the barcode scanner library needs it; before chunk
      29 the release build failed its manifest merge at 24.
- [x] Only CAMERA (optional hardware) and POST_NOTIFICATIONS; no sensitive permissions
      needing a declaration.
- [x] Privacy policy in the app and at a public URL.
- [ ] **Account deletion**: Play requires an in-app path and a web link where people can
      ask for deletion (Data safety > Data deletion). Same gap as the App Store.
- [ ] **Home screen** placeholder replaced (Play reviews for broken or minimal
      functionality too).
- [ ] App content: Privacy policy, App access (the demo accounts above), Ads (none),
      Content rating (IARC questionnaire: no violence, no user chat, purchases of
      real-world services), Target audience (18 and over), Data safety (section 6),
      Financial features (none: payments for services through PayFast), Government app
      (no), News (no), Health (no).
- [ ] Payments: league fees and field bookings are physical services, outside Google Play
      Billing.
- [ ] If the developer account is a new personal account, Play requires a closed test
      with at least 12 testers for 14 days before production. An organisation account
      (D-U-N-S) does not.

## 8. Store listing fields to fill in

App Store Connect:
- Name (30 characters): "League App" is a working name; decide the product name first.
- Subtitle (30), Promotional text (170), Description (4000), Keywords (100, comma
  separated).
- Support URL (required), Marketing URL (optional), Privacy Policy URL (section 5).
- Category: Sports (primary); secondary optional.
- Age rating questionnaire; Copyright ("2026 <operator>"); Price (Free) and
  availability (South Africa first).
- Screenshots: 6.9-inch iPhone (1320 × 2868 or 1290 × 2796), 13-inch iPad if iPad stays.
- App Review Information: contact name, phone, email, demo accounts, notes.
- App Privacy (section 6). TestFlight Test Information: beta description, feedback email.

Google Play Console:
- App name (30), Short description (80), Full description (4000).
- App icon 512 × 512: `frontend/assets/store/google-play-icon-512.png`.
- Feature graphic 1024 × 500 (required; not made yet: needs the product name set in the
  design system's type).
- Phone screenshots (2 to 8), 7- and 10-inch tablet screenshots optional.
- Category: Sports; tags; contact email (required), website, phone (optional).
- Privacy policy URL, App content (section 7), countries (South Africa first).

## 9. Ship a TestFlight build

1. Once per Mac: Xcode signed in to the Apple account (Settings > Accounts); the section 3
   checklist done.
2. `frontend/.env.production` (git-ignored) with `VITE_API_BASE_URL=https://<API host>`.
3. In frontend/: `npm run version:bump`, then `npm run cap:sync`.
4. `npx cap open ios`. Scheme App, destination "Any iOS Device (arm64)",
   Product > Archive.
5. Organizer > Distribute App > App Store Connect > Upload (automatic signing).
6. App Store Connect > TestFlight: wait for processing (email). Internal testers (up to 100
   App Store Connect users) can install at once from the TestFlight app. External testers
   need Test Information and a Beta App Review first.
7. Commit `release.json` and `project.pbxproj` with the new build number.

## 10. Ship a Google Play internal testing build

1. Play Console: Create app (name, default language, App, Free), accept the declarations.
2. Fill in App content (section 7) and the store listing (section 8); internal testing can
   start before every field is done, but Play shows what is missing.
3. `frontend/android/app/google-services.json` in place (chunk 10), or pushes won't work.
4. `frontend/.env.production` as for TestFlight; in frontend/: `npm run version:bump`,
   `npm run cap:sync`.
5. The section 2 environment variables exported, then
   `cd android && ./gradlew bundleRelease`.
6. Testing > Internal testing > Create new release. Play App Signing is on by default
   (keep it). Upload `app-release.aab`, add release notes, Save, Review, Roll out.
7. Testers tab: an email list (up to 100), then share the opt-in link; testers install
   from Google Play.
8. Commit `release.json` with the new build number.
