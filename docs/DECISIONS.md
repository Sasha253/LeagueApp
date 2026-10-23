# Decisions

Newest first. Each entry: the date, what was decided, and why.

## 2026-10-23: Club setup and configurable values (chunk 3)

Decided by @Sasha while building chunk 3.

- **Defaults are data:** one `SettingsDefaults` record, seeded by a data migration with the
  PRD values and edited in the Django admin. A new Club's `ClubSettings` is copied from it
  when the Club is created. A later change to the defaults affects only Clubs created after
  it. The seeded values: Confirmations at T-36h, resent once 12 hours later; Reminder and
  readiness at T-6h; at least 5 Players per Division; booking payment taken 24h before;
  50% credit from then to 6h before, none after that or for a no-show, and 100% when the
  club cancels; one late reschedule to a slot within 30 days; card and cash through PayFast.
- **Fees start empty:** the league fee per Team, the friendly fee and the booking hourly
  fee have no default. The club's Admin must set them; settings report what is `missing`,
  and Setup shows it. Blocking Team sign-up and bookings until they are set comes with
  those chunks.
- **Resend (FR-2):** 12 hours after the first Confirmation, so at T-24h. It must go out
  before the readiness check.
- **League fee:** one per Club, and a Division may set its own, which overrides it.
- **Nights and Divisions carry over across Seasons:** a Division belongs to a Night, not
  a Season, so Players' Night opt-ins carry over too. One Night per weekday per Club.
  Teams (chunk 5) will tie a Season to a Division.
- **Hours, not durations:** cutoffs are whole hours before kick-off, and the reschedule
  window is whole days. Credit is a whole percentage from 0 to 100.
- **Inviting Admins and Referees:** a Club's Admin invites by email. An account with that
  email gets the role at once. Otherwise the invite stays open and the role is given when
  someone signs up with that email. The app sends no invite email yet: the Admin tells
  the person. A Club always keeps at least one Admin, and removing a Referee takes them
  off their Fields. A Field's Referee must hold the Referee role at that Club.
- **Not yet safe for store release:** sign-up does not verify email addresses, so whoever
  first signs up with an invited email gets that role. Email verification, or an invite
  link with a code, must come before store release.
- **Deleting:** a Night with Divisions can't be deleted (409). Every other setup record can
  be deleted until later chunks give it Teams, Fixtures or bookings.
- **Proposed components** (`frontend/src/styles/proposed.css`): a ListRow that is a link,
  a back link above the screen title, a section header with an action, and ConfirmButton,
  which asks once more before a delete or removal.

## 2026-10-23: Accounts, roles and token auth (chunk 2)

Decided by @Sasha while building chunk 2. Closes open questions 3 and 4.

- **One account, any club (Q3):** an account is app-wide. One Player can play for Teams at
  more than one club, and can opt into any club's Nights. Only Admin and Referee are held
  per Club (`ClubRole`).
- **New clubs are set up by us (Q4):** clubs do not sign up in the app. We create the Club
  and its first Admin in the Django admin. Giving Admin and Referee roles in the app comes
  with chunk 3 (see the chunk 3 entry above).
- **Login:** email and password only, with the email matched in any case. Phone is asked
  at sign-up (optional) for contact, not for login. Phone login can come later.
- **Roles at sign-up:** the user picks "I play" (a Player, then a position: outfield,
  goalkeeper or both), "I hire a field" (a Booking User), or both. Both can be changed in
  Profile. At least one is required.
- **Captain** is not a stored role: a Player is a Captain of the Team they captain
  (chunk 5).
- **Tokens:** JWT (djangorestframework-simplejwt). The access token lasts 15 minutes and
  the refresh token 60 days. Every refresh hands out a new refresh token and blacklists
  the old one. Logout blacklists it too. The API accepts no session cookies; the Django
  admin keeps its own session login.
- **Token storage:** Capacitor Preferences in the installed app, localStorage in the
  browser (`frontend/src/native/storage.ts`). Preferences is not the iOS Keychain or
  Android Keystore. Moving the refresh token to secure storage is listed for before store
  release.
- **Proposed components** (not in the design system yet, built from its tokens in
  `frontend/src/styles/proposed.css`, recipes from the key-moments draft): TextField,
  ChoiceChip, Banner, ListGroup and ListRow, and a screen layout (`la-screen`).

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

Raised by the multi-club decision (2026-10-23). Questions 3 and 4 were answered in chunk 2
(see the entry above).

5. Does each club take card payments into its own PayFast merchant account?
6. Does a Player's credit (FR-52) belong to one club, or can it be spent at any club?
