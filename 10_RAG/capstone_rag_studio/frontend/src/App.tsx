import AppLayout from "@cloudscape-design/components/app-layout";
import SideNavigation from "@cloudscape-design/components/side-navigation";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import { useNavigate, useLocation, Route, HashRouter as Router, Routes } from "react-router-dom";
import { PrincipalProvider, usePrincipal } from "./PrincipalContext";
import BuildStrategiesPage from "./pages/BuildStrategiesPage";
import ChatPage from "./pages/ChatPage";
import ChatComparePage from "./pages/ChatComparePage";
import EvaluationDashboardPage from "./pages/EvaluationDashboardPage";
import GovernancePage from "./pages/GovernancePage";
import IngestPage from "./pages/IngestPage";
import { testId } from "./testid";

const NAV_ITEMS = [
  { type: "link" as const, text: "Ingest", href: "/ingest" },
  { type: "link" as const, text: "Build Strategies", href: "/build-strategies" },
  { type: "link" as const, text: "Chat", href: "/converse" },
  { type: "link" as const, text: "Chat & Compare", href: "/chat" },
  { type: "link" as const, text: "Evaluation Dashboard", href: "/evaluation" },
  { type: "link" as const, text: "Governance", href: "/governance" },
];

function Shell() {
  const { principal } = usePrincipal();
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <>
      <div id="top-nav" data-testid="nav">
        <TopNavigation
          identity={{ href: "/ingest", title: "RAG Studio", onFollow: (e) => { e.preventDefault(); navigate("/ingest"); } }}
          utilities={[
            {
              type: "button",
              text: `Acting as: ${principal.id}`,
              iconName: "user-profile",
              ...testId("top-bar-principal"),
            },
          ]}
        />
      </div>
      <AppLayout
        headerSelector="#top-nav"
        toolsHide
        navigation={
          <SideNavigation
            activeHref={location.pathname}
            items={NAV_ITEMS}
            onFollow={(e) => {
              e.preventDefault();
              navigate(e.detail.href);
            }}
          />
        }
        content={
          <Routes>
            <Route path="/ingest" element={<IngestPage />} />
            <Route path="/build-strategies" element={<BuildStrategiesPage />} />
            <Route path="/converse" element={<ChatPage />} />
            <Route path="/chat" element={<ChatComparePage />} />
            <Route path="/evaluation" element={<EvaluationDashboardPage />} />
            <Route path="/governance" element={<GovernancePage />} />
            <Route path="*" element={<IngestPage />} />
          </Routes>
        }
      />
    </>
  );
}

function App() {
  return (
    <PrincipalProvider>
      <Router>
        <Shell />
      </Router>
    </PrincipalProvider>
  );
}

export default App;
