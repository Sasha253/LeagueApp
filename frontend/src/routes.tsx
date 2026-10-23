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
import { FixturePage } from "./pages/fixtures/FixturePage";
import { ImportFixturesPage } from "./pages/fixtures/ImportFixturesPage";
import { MyFixturesPage } from "./pages/fixtures/MyFixturesPage";
import { TonightPage } from "./pages/fixtures/TonightPage";
import { ClubTeamPage } from "./pages/teams/ClubTeamPage";
import { ClubTeamsPage } from "./pages/teams/ClubTeamsPage";
import { FindTeamPage } from "./pages/teams/FindTeamPage";
import { MyTeamsPage } from "./pages/teams/MyTeamsPage";
import { RequestTeamPage } from "./pages/teams/RequestTeamPage";
import { TeamPage } from "./pages/teams/TeamPage";
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
      { path: "/fixtures", element: <MyFixturesPage /> },
      { path: "/fixtures/:fixtureId", element: <FixturePage /> },
      { path: "/teams", element: <MyTeamsPage /> },
      { path: "/teams/find", element: <FindTeamPage /> },
      { path: "/teams/new", element: <RequestTeamPage /> },
      { path: "/teams/:teamId", element: <TeamPage /> },
      { path: "/inbox", element: <InboxPage /> },
      { path: "/inbox/:notificationId", element: <NotificationPage /> },
    ],
  },
];

export const routes: RouteObject[] = [{ element: <AppShell />, children: screens }];
