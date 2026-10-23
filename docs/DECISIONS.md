# Decisions

Newest first. Each entry: the date, what was decided, and why.

## 2026-10-23: One app for every club; Capacitor setup

Decided by @Sasha while building chunk 1.

- **Multi-club:** the app is not built for one club. One backend and one store app serve
  every club. Each club's Seasons, Nights, Divisions, Fields, Teams, Fixtures, settings and
  ledger belong to that Club, and its Admins and Referees see and change only that Club's
  data. No club's name goes in code, app ids or store listings. Old Parks, named in the
  PRD, is the first club, not the only one.
- **App id:** `za.co.leagueapp`, name "League App". It cannot change once the app is in
  the stores, so confirm it (and that the domain is ours) before the first upload.
- **API address in the installed app:** the build reads `VITE_API_BASE_URL`
  (`frontend/.env.example`). The browser keeps using its own origin and the Vite proxy.
  On a simulator or emulator it is `http://127.0.0.1:8000`; the Android emulator reaches
  it through `adb reverse tcp:8000 tcp:8000`.
- **CORS:** `capacitor://localhost` (iOS) and `https://localhost` (Android) are always
  allowed, in every environment, because they are the installed app's own origins. No
  credentials: the app uses token auth.
- **Cleartext HTTP:** allowed only in Android debug builds, only to 127.0.0.1, localhost and
  10.0.2.2 (`frontend/android/app/src/debug/`). Release builds block it.
- **Toolchain:** Capacitor 8. iOS uses Swift Package Manager, so CocoaPods is not needed.
  Android needs JDK 21.

## 2026-10-23: Platform, gateway, scheduler, Fixture source, credit

Decided by @Sasha while splitting the PRD into build chunks. Added to `docs/PRD.md` as FR-52,
FR-53 and new rows in its Decisions table.

- **Platform:** not a native app, but installed from the App Store and Google Play. The React
  web app is wrapped with Capacitor (`frontend/ios/`, `frontend/android/`), which gives native
  push notifications on iOS without the home-screen-only limit of Web Push. This closes the
  open point in the 2026-10-21 entry below. What store release needs:
  - Push goes through Firebase Cloud Messaging for both platforms (APNs key uploaded to
    Firebase), using `@capacitor/push-notifications` in the app and `firebase-admin` in the
    backend.
  - Gate scanning uses the device camera through a native Capacitor barcode plugin, not a
    browser camera API.
  - The app talks to the API with token auth, not session cookies, because the wrapped app
    runs on its own origin (`capacitor://localhost` on iOS, `https://localhost` on Android).
  - Apple rejects apps that are only a website in a frame (App Review Guideline 4.2). Native
    push, native scanning and app-only flows are what keep this app above that line.
  - League fees and field bookings are real-world services, so card payment through PayFast
    is allowed in the app and no Apple or Google in-app purchase is needed (Guideline 3.1.5(a)).
  - The club needs an Apple Developer account and a Google Play Console account, a privacy
    policy URL, and store listings.
- **Payment gateway:** PayFast first. Peach Payments and Yoco come later, so payments go
  through one gateway interface with PayFast as the first provider.
- **Timed jobs:** Celery Beat runs the T-36h and T-6h checkpoints and the booking payment
  cutoff. Each job must be safe to run twice for the same fixture.
- **Fixtures:** the Admin imports them from Excel, like Nights and Divisions (FR-53). Syncing
  from an external fixtures system stays under FR-40 for later.
- **Credit (FR-52):** held by Players and by Teams. Player credit belongs to the Player and can
  be spent on any Team's match they play in. Team credit belongs to the Team and only its
  Captain can spend or manage it. Credit goes back to whoever paid: a Player's contribution
  becomes Player credit, and a payment for the whole Team becomes Team credit.

## 2026-10-21: React + Django web app

The app is built as a web app: a React frontend (`frontend/`) over a Django REST API
(`backend/`), the same stack as Swingbok.

- The PRD lists iOS and Android as the platforms, and the designs in `design/` are mobile
  screens at 375 × 812. The web app is therefore built mobile-first from those designs.
- **Still open:** push notifications are the PRD's core mechanism. A web app sends them with
  Web Push, and iOS delivers Web Push only to a web app added to the home screen (iOS 16.4 and
  later). Whether that is enough, or the app needs a native wrapper, is not decided yet.

## 2026-10-21: Design source

The UI follows the League App design system: tokens, type styles and `la-` components.
Its files are in `design/src/ds/`, copied unchanged from `League App Design System.zip`
(dated 2026-10-20) because the claude.ai artifact link could not be read from Claude Code.
`design/` also holds the canvas generator and the key-moments draft
(`design/key-moments-draft.html`).

## Open questions

Raised while drawing the key moments; the PRD does not answer them.

1. Does a borrowed Player pay for a league match, how much, and who pays? FR-24 sets a fee
   only for friendlies.
2. Is the Captain notified when a Player or Goalkeeper Request fills? The PRD names no
   notification for it.

Raised by the multi-club decision (2026-10-23); settle in chunks 2 and 3.

3. Can one Player play for Teams at more than one club, with one account?
4. How does a new club join: does it sign up in the app, or do we set it up?
5. Does each club take card payments into its own PayFast merchant account?
6. Does a Player's credit (FR-52) belong to one club, or can it be spent at any club?
