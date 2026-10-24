import { Outlet, type RouteObject } from "react-router";
import { RequireAuth } from "./auth/RequireAuth";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SignUpPage } from "./pages/SignUpPage";
import { ClubSettingsPage } from "./pages/club/ClubSettingsPage";
import { ClubSetupPage } from "./pages/club/ClubSetupPage";
import { FieldsPage } from "./pages/club/FieldsPage";
import { ImportNightsPage } from "./pages/club/ImportNightsPage";
import { NightsPage } from "./pages/club/NightsPage";
import { PeoplePage } from "./pages/club/PeoplePage";
import { SeasonsPage } from "./pages/club/SeasonsPage";
import { ClubFixturePage } from "./pages/fixtures/ClubFixturePage";
import { ClubFixturesPage } from "./pages/fixtures/ClubFixturesPage";
import { ClubRequestsPage } from "./pages/fixtures/ClubRequestsPage";
import { FixturePage } from "./pages/fixtures/FixturePage";
import { FixtureRequestPage } from "./pages/fixtures/FixtureRequestPage";
import { ImportFixturesPage } from "./pages/fixtures/ImportFixturesPage";
import { MyFixturesPage } from "./pages/fixtures/MyFixturesPage";
import { RequestPlayerPage } from "./pages/fixtures/RequestPlayerPage";
import { TonightPage } from "./pages/fixtures/TonightPage";
import { ClubTeamPage } from "./pages/teams/ClubTeamPage";
import { ClubTeamsPage } from "./pages/teams/ClubTeamsPage";
import { FindTeamPage } from "./pages/teams/FindTeamPage";
import { MyTeamsPage } from "./pages/teams/MyTeamsPage";
import { RequestTeamPage } from "./pages/teams/RequestTeamPage";
import { TeamPage } from "./pages/teams/TeamPage";
import { BarcodePage } from "./pages/payments/BarcodePage";
import { ClubPaymentsPage } from "./pages/payments/ClubPaymentsPage";
import { ClubTeamPaymentPage } from "./pages/payments/ClubTeamPaymentPage";
import { FriendlyBarcodePage } from "./pages/payments/FriendlyBarcodePage";
import { PaymentResultPage } from "./pages/payments/PaymentResultPage";
import { PayPage } from "./pages/payments/PayPage";
import { ScanPage } from "./pages/payments/ScanPage";
import { BookingPage } from "./pages/bookings/BookingPage";
import { BookPage } from "./pages/bookings/BookPage";
import { ClubBookingsPage } from "./pages/bookings/ClubBookingsPage";
import { MyBookingsPage } from "./pages/bookings/MyBookingsPage";
import { ComparisonPage } from "./pages/finance/ComparisonPage";
import { FinancesPage } from "./pages/finance/FinancesPage";
import { TeamLedgerPage } from "./pages/finance/TeamLedgerPage";
import { InboxPage } from "./pages/inbox/InboxPage";
import { NotificationPage } from "./pages/inbox/NotificationPage";
import { PushBridge } from "./push/PushBridge";

/** Around every screen: push taps can open any of them. */
function AppShell() {
  return (
    <>
      <PushBridge />
      <Outlet />
    </>
  );
}

const screens: RouteObject[] = [
  { path: "/", element: <HomePage /> },
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignUpPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: "/profile", element: <ProfilePage /> },
      { path: "/clubs/:clubId/setup", element: <ClubSetupPage /> },
      { path: "/clubs/:clubId/setup/settings", element: <ClubSettingsPage /> },
      { path: "/clubs/:clubId/setup/seasons", element: <SeasonsPage /> },
      { path: "/clubs/:clubId/setup/nights", element: <NightsPage /> },
      { path: "/clubs/:clubId/setup/nights/import", element: <ImportNightsPage /> },
      { path: "/clubs/:clubId/setup/fields", element: <FieldsPage /> },
      { path: "/clubs/:clubId/setup/people", element: <PeoplePage /> },
      { path: "/clubs/:clubId/teams", element: <ClubTeamsPage /> },
      { path: "/clubs/:clubId/teams/:teamId", element: <ClubTeamPage /> },
      { path: "/clubs/:clubId/tonight", element: <TonightPage /> },
      { path: "/clubs/:clubId/fixtures", element: <ClubFixturesPage /> },
      { path: "/clubs/:clubId/fixtures/import", element: <ImportFixturesPage /> },
      { path: "/clubs/:clubId/fixtures/:fixtureId", element: <ClubFixturePage /> },
      { path: "/clubs/:clubId/requests", element: <ClubRequestsPage /> },
      { path: "/clubs/:clubId/payments", element: <ClubPaymentsPage /> },
      { path: "/clubs/:clubId/payments/:teamId", element: <ClubTeamPaymentPage /> },
      { path: "/clubs/:clubId/finances", element: <FinancesPage /> },
      { path: "/clubs/:clubId/finances/compare", element: <ComparisonPage /> },
      { path: "/clubs/:clubId/finances/teams/:teamId", element: <TeamLedgerPage /> },
      { path: "/clubs/:clubId/scan", element: <ScanPage /> },
      { path: "/clubs/:clubId/bookings", element: <ClubBookingsPage /> },
      { path: "/book", element: <BookPage /> },
      { path: "/bookings", element: <MyBookingsPage /> },
      { path: "/bookings/:bookingId", element: <BookingPage /> },
      { path: "/fixtures", element: <MyFixturesPage /> },
      { path: "/fixtures/:fixtureId", element: <FixturePage /> },
      { path: "/fixtures/:fixtureId/request", element: <FixtureRequestPage /> },
      { path: "/fixtures/:fixtureId/players", element: <RequestPlayerPage /> },
      { path: "/friendlies/:fixtureId/barcode", element: <FriendlyBarcodePage /> },
      { path: "/teams", element: <MyTeamsPage /> },
      { path: "/teams/find", element: <FindTeamPage /> },
      { path: "/teams/new", element: <RequestTeamPage /> },
      { path: "/teams/:teamId", element: <TeamPage /> },
      { path: "/teams/:teamId/pay", element: <PayPage /> },
      { path: "/teams/:teamId/barcode", element: <BarcodePage /> },
      // PayFast sends the Player back here (PAYMENT_RETURN_URL, PAYMENT_CANCEL_URL).
      { path: "/payments/done", element: <PaymentResultPage /> },
      { path: "/payments/cancelled", element: <PaymentResultPage left /> },
      { path: "/inbox", element: <InboxPage /> },
      { path: "/inbox/:notificationId", element: <NotificationPage /> },
    ],
  },
];

export const routes: RouteObject[] = [{ element: <AppShell />, children: screens }];
