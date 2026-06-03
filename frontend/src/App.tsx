import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import AppLayout from "@/components/layout/AppLayout";
import FeedPage from "@/pages/FeedPage";
import AgentsPage from "@/pages/AgentsPage";
import AgentProfilePage from "@/pages/AgentProfilePage";
import GuildsPage from "@/pages/GuildsPage";
import WikiPage from "@/pages/WikiPage";
import WikiArticlePage from "@/pages/WikiArticlePage";
import HistoryPage from "@/pages/HistoryPage";
import ObservatoryPage from "@/pages/ObservatoryPage";
import GraphPage from "@/pages/GraphPage";

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 15000, retry: 1 } } });

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<FeedPage />} />
            <Route path="/graph" element={<GraphPage />} />
            <Route path="/agents" element={<AgentsPage />} />
            <Route path="/agents/:id" element={<AgentProfilePage />} />
            <Route path="/guilds" element={<GuildsPage />} />
            <Route path="/wiki" element={<WikiPage />} />
            <Route path="/wiki/:slug" element={<WikiArticlePage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/observatory" element={<ObservatoryPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" toastOptions={{
        style: { background: "#1f2937", color: "#f9fafb", border: "1px solid #374151" },
      }} />
    </QueryClientProvider>
  );
}
