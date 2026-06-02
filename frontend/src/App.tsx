import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "@/components/Layout";
import { Spinner } from "@/components/ui";
import Approvals from "@/routes/Approvals";
import Chat from "@/routes/Chat";
import Dashboard from "@/routes/Dashboard";
import Documents from "@/routes/Documents";
import Finance from "@/routes/Finance";
import HR from "@/routes/HR";
import IT from "@/routes/IT";
import Login from "@/routes/Login";
import SearchPage from "@/routes/Search";
import { useAuth } from "@/store/auth";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/hr" element={<HR />} />
        <Route path="/finance" element={<Finance />} />
        <Route path="/it" element={<IT />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
