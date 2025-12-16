import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Layout from './components/Layout';
import BanEnforcer from './components/BanEnforcer';
import Landing from './pages/Landing';
import Doctrines from './pages/Doctrines';
import Profile from './pages/Profile';
import FleetDashboard from './pages/FleetDashboard';
import AccessDenied from './pages/AccessDenied';
import Banned from './pages/Banned';

// Management
import Management from './pages/Management';
import ManagementDashboard from './pages/management/ManagementDashboard';
import ManagementUsers from './pages/management/ManagementUsers';
import ManagementRoles from './pages/management/ManagementRoles';
import ManagementFleets from './pages/management/ManagementFleets';
import ManagementFleetSetup from './pages/management/ManagementFleetSetup';
import ManagementFleetSettings from './pages/management/ManagementFleetSettings';
import ManagementHistory from './pages/management/ManagementHistory';
import ManagementBans from './pages/management/ManagementBans';
import ManagementBanAudit from './pages/management/ManagementBanAudit';
import ManagementSRP from './pages/management/ManagementSRP';
import ManagementSRPConfig from './pages/management/ManagementSRPConfig';
import ManagementDoctrines from './pages/management/ManagementDoctrines';
import ManagementSkills from './pages/management/ManagementSkills';
import ManagementRules from './pages/management/ManagementRules';
import ManagementSDE from './pages/management/ManagementSDE';
import ManagementCelery from './pages/management/ManagementCelery';
import ManagementPermissions from './pages/management/ManagementPermissions';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Layout>
          <BanEnforcer>
            <Routes>
              {/* Public / User Pages */}
              <Route path="/" element={<Landing />} />
            <Route path="/landing/" element={<Landing />} />
            <Route path="/doctrines" element={<Doctrines />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/fleet/:token" element={<FleetDashboard />} />
            
            {/* Error / System Pages */}
            <Route path="/access_denied" element={<AccessDenied />} />
            <Route path="/banned" element={<Banned />} />

            {/* Management Console */}
            <Route path="/management" element={<Management />}>
              <Route index element={<ManagementDashboard />} />
              
              {/* Analysis */}
              <Route path="users" element={<ManagementUsers />} />
              <Route path="roles" element={<ManagementRoles />} />
              
              {/* Operations */}
              <Route path="fleets" element={<ManagementFleets />} />
              <Route path="fleets/setup" element={<ManagementFleetSetup />} />
              <Route path="fleets/:token/settings" element={<ManagementFleetSettings />} />
              <Route path="fleets/:token/history" element={<ManagementHistory />} />
              
              {/* Finance */}
              <Route path="srp" element={<ManagementSRP />} />
              <Route path="srp/config" element={<ManagementSRPConfig />} />
              
              {/* User Mgmt */}
              <Route path="bans" element={<ManagementBans />} />
              <Route path="bans/audit" element={<ManagementBanAudit />} />
              
              {/* System */}
              <Route path="doctrines" element={<ManagementDoctrines />} />
              <Route path="skills" element={<ManagementSkills />} />
              <Route path="rules" element={<ManagementRules />} />
              <Route path="sde" element={<ManagementSDE />} />
              <Route path="celery" element={<ManagementCelery />} />
              <Route path="permissions" element={<ManagementPermissions />} />
              
              {/* Fallback for management sub-routes */}
              <Route path="*" element={<div className="p-10 text-slate-500">Page Not Found</div>} />
            </Route>

              {/* Global Fallback */}
              <Route path="*" element={<div className="p-10 text-center text-slate-500">Page Not Found</div>} />
            </Routes>
          </BanEnforcer>
        </Layout>
      </Router>
    </AuthProvider>
  );
}

export default App;