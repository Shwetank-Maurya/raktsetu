import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import { useAuth } from "./lib/auth";
import { DEFAULT_FLAGS, loadFlags, type Flags } from "./lib/firebase";
import Login from "./pages/Login";

const CommandCentre = lazy(() => import("./pages/CommandCentre"));
const RiskMap = lazy(() => import("./pages/RiskMap"));
const Matrix = lazy(() => import("./pages/Matrix"));
const Expiry = lazy(() => import("./pages/Expiry"));
const Forecast = lazy(() => import("./pages/Forecast"));
const Transfers = lazy(() => import("./pages/Transfers"));
const Alerts = lazy(() => import("./pages/Alerts"));
const StressTest = lazy(() => import("./pages/StressTest"));
const Copilot = lazy(() => import("./pages/Copilot"));
const Evaluation = lazy(() => import("./pages/Evaluation"));
const DataQuality = lazy(() => import("./pages/DataQuality"));
const Register = lazy(() => import("./pages/Register"));
const Donors = lazy(() => import("./pages/Donors"));
const Inventory = lazy(() => import("./pages/Inventory"));

export default function App() {
  const { user, loading } = useAuth();
  const [flags, setFlags] = useState<Flags>(DEFAULT_FLAGS);
  useEffect(() => { loadFlags().then(setFlags); }, []); // Firebase Remote Config feature flags
  if (loading) return <Spinner label="Starting RaktSetu" />;
  if (!user) return <Login />;
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<CommandCentre />} />
          <Route path="map" element={<RiskMap />} />
          <Route path="matrix" element={<Matrix />} />
          <Route path="expiry" element={<Expiry />} />
          <Route path="forecast" element={<Forecast />} />
          <Route path="transfers" element={<Transfers />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="inventory" element={<Inventory />} />
          {flags.stress_test && <Route path="stress" element={<StressTest />} />}
          {flags.copilot && <Route path="copilot" element={<Copilot />} />}
          {flags.donor_campaigns && <Route path="donors" element={<Donors />} />}
          {flags.register_ocr && <Route path="register" element={<Register />} />}
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="quality" element={<DataQuality />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
