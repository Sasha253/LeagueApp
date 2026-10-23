# Chunk 10: Push and inbox in the app (UI)

Unattended run, 2026-10-23. Builds on the chunk 9 API (`inbox/`, `devices/`). PRD:
"Notifications", "Targeting rules". Designs: design/src/screens/f02-confirmation.mjs
(Inbox, Confirmation, "You're in!"), design/src/ds/Screens.md (Shared 3 and 4).

## Plan

Native wrapper (`frontend/src/native/push.ts`, CLAUDE.md: device features behind
frontend/src/native/ with a browser fallback):
- `registerPush(onToken)`: checks permission, asks once if not yet asked, registers with
  @capacitor/push-notifications and hands back the token. No-op in the browser.
- `onPushTap(handler)`: a tapped push or push action button (notification data and the
  action id). `onPushReceived(handler)`: a push that arrives while the app is open.
- `unregisterPush()`: stop listening on logout.

App side (`frontend/src/push/`):
- `device.ts`: registers the token with `POST /api/v1/devices/` (platform from
  `native/platform`), keeps the device id, and removes it with `DELETE devices/{id}/` on
  logout (before the session ends, so the call is authenticated).
- `links.ts`: where a tapped push or action button goes: the notification's screen
  (`/inbox/{id}`), or for the General "Find a match" button its screen.
- `PushBridge`: in a new root layout route, so it can navigate: listens for taps from the
  first render (a cold start delivers the tap once listeners are added), registers the
  device once someone is signed in.

Screens:
- Inbox (`/inbox`): filters All, Needs reply (with count), Updates; unanswered pinned on
  top under "Needs reply" with a "Reply by Tue 13:40" chip, the rest under "Earlier";
  unread rows marked; empty, loading and error states. Reloads when a push arrives.
- Notification (`/inbox/{id}`): marks it read; a ConfirmationCard with the kind's buttons
  for answerable kinds; after answering, the answer as a chip with "Change" while it can
  still change; "You're in!" after confirming or accepting; a plain message for Updates
  and Reminders; "Find a match" for General; a link to the match when there is one.
- Profile gets an Inbox row with the unread count (no tab bar yet).

Native projects: add @capacitor/push-notifications and `cap sync`; iOS AppDelegate
forwards the device token to Capacitor; presentation options in capacitor.config.ts.

Tests: Vitest for the native wrapper (browser no-op, permission flow), push links,
PushBridge (registers, navigates on tap, forgets the device on logout), Inbox and
Notification screens, the Profile row.

Later (not in this chunk): the tab bar (no chunk owns it yet); push action buttons shown by
the OS (needs a category per kind sent by the backend and registered natively); what an
answer does (chunks 12 onwards); the "Games you can join" screen behind "Find a match"
(chunks 15 and 17).

## Result

Built:
- `frontend/src/native/push.ts`: `registerPush` (checks permission, asks only if the phone
  hasn't been asked, registers, hands back each token), `onPushTap`, `onPushReceived`,
  `unregisterPush`. Every call is a no-op in the browser.
- `frontend/src/push/`: `device.ts` (register the token with `POST /api/v1/devices/`,
  keep its id, remove it with `DELETE /api/v1/devices/{id}/` on logout before the session
  ends), `links.ts` (tap or button to screen: `/inbox/{id}`, "Find a match" to
  `/fixtures`, else the match or the inbox; buttons never answer by themselves),
  `PushBridge.tsx` (in a new root layout route: listens for taps from the first render,
  registers once signed in), `events.ts` (inbox changed: reloads the inbox and counts).
- Screens: Inbox (`/inbox`: All, Needs reply with count, Updates; "Needs reply" pinned
  with "Reply by Tue 13:40"; unread dot and bold title; empty, loading and Retry states;
  reloads on push) and Notification (`/inbox/{id}`: marks read; ConfirmationCard with
  player-phrase buttons; "You're in!" after confirming; answer chip with Change while it
  can change; "Replies are closed"; Updates as plain messages; "Find a match"; "Open the
  match", the club's Fixture screen for that club's Admins). Profile has an Inbox row
  with the unread count. Logout forgets the device.
- Native: @capacitor/push-notifications 8.1.3 added and synced (Android and iOS SPM);
  `presentationOptions` in capacitor.config.ts; Android `POST_NOTIFICATIONS` permission;
  iOS AppDelegate forwards the device token to Capacitor. `google-services.json` and
  `GoogleService-Info.plist` are git-ignored.
- Proposed components (docs/DECISIONS.md): icon disc, ChoiceChip count, status hero,
  unread dot; Lucide icons in `components/Icon.tsx`.
- Tests (36 new Vitest tests): native push wrapper, push links, PushBridge (registers
  after sign-in only, opens the screen on tap, forgets the device on logout before the
  logout call), Inbox, Notification and the Profile row.

Not built: OS action buttons on the push itself (needs backend categories and native
registration); the tab bar; the Later list above. No API change (`npm run gen:api`:
schema unchanged).

By hand:
1. Firebase project: create one (or use the chunk 9 one), add an Android app with
   package `za.co.leagueapp` and an iOS app with bundle id `za.co.leagueapp`.
2. Android: download `google-services.json` to `frontend/android/app/` (git-ignored; the
   Gradle build applies the google-services plugin only when it is there).
3. iOS, in Xcode (`npm run cap:ios`): add `GoogleService-Info.plist` to the App target
   (`frontend/ios/App/App/`, git-ignored); Signing & Capabilities: add Push Notifications
   and Background Modes > Remote notifications; File > Add Package Dependencies:
   `https://github.com/firebase/firebase-ios-sdk`, product FirebaseMessaging. Then in
   `AppDelegate.swift`: `import FirebaseCore` and `import FirebaseMessaging`, call
   `FirebaseApp.configure()` in `didFinishLaunchingWithOptions`, and replace the body of
   `didRegisterForRemoteNotificationsWithDeviceToken` with:
   ```swift
   Messaging.messaging().apnsToken = deviceToken
   Messaging.messaging().token { token, error in
       if let error = error {
           NotificationCenter.default.post(name: .capacitorDidFailToRegisterForRemoteNotifications, object: error)
       } else if let token = token {
           NotificationCenter.default.post(name: .capacitorDidRegisterForRemoteNotifications, object: token)
       }
   }
   ```
   (the backend sends by FCM token, so iOS must register the FCM token, not the APNs one).
4. APNs key: Apple Developer > Keys > new key with Apple Push Notifications service (APNs);
   upload the .p8 with its Key ID and Team ID in Firebase console > Project settings >
   Cloud Messaging > Apple app configuration.
5. Backend: `PUSH_SENDER=notifications.push.FirebaseSender` and
   `FIREBASE_CREDENTIALS_FILE` (or `FIREBASE_CREDENTIALS_JSON`) from the same Firebase
   project (chunk 9).
6. Try it on a real device (the iOS simulator can't get remote pushes): sign in, allow
   notifications, send one from the Django shell with `notifications.services.notify`,
   tap it, and check it opens the notification.
7. Answer the Chunk 10 open questions in docs/OPEN_QUESTIONS.md.

Checks: make test 404 passed; make lint clean; npm test 162 passed (31 files);
npm run build ok.

## Review (fix: chunk 10 review)

Independent review of 62d4d93 against the chunk 10 prompt and CLAUDE.md.

Checked, no change needed:
- Device features only through `frontend/src/native/push.ts`, every call a no-op in the
  browser; token auth only (no cookies).
- Club isolation: the inbox API (chunk 9) filters by recipient; the app shows only what
  the API returns. "Open the match" picks the club Fixture screen only for an Admin of
  the notification's own Club; the backend still checks the role.
- Nothing decided in the frontend: can_answer, needs_reply and answer_by come from the
  API. No money, ledger or configurable values touched. No API change, so no gen:api.
- Logout removes the device registration before the session ends; a tapped push or
  button only opens a screen and never answers by itself (logged in OPEN_QUESTIONS).
- UI uses design-system tokens and `la-` classes; new pieces are listed as proposed
  components in docs/DECISIONS.md.
- Nothing from later chunks (tab bar, Games you can join, what an answer does).

Fixed:
- Inbox: switching filter kept showing the previous filter's rows (for example every
  notification under "Updates") until the new list arrived, because the shared `useLoad`
  keeps the last result while a new key loads. The list is now its own component keyed by
  the filter, so a new filter starts from the loading state. Test added
  ("never shows the last filter's rows while the next one loads").

Not changed (noted):
- iOS still hands Capacitor the APNs token until Firebase is added by hand (step 3 of
  "By hand"); pushes to iPhones fail until then. Documented by the builder.
- A notification URL with a non-numeric id shows the load error with Retry rather than
  "not found". Cosmetic.

Checks after the fix: make test 404 passed (backend unchanged); make lint clean;
npm test 163 passed (31 files); npm run build ok.
