import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Landing from './pages/Landing';
import Doctrines from './pages/Doctrines';
import Profile from './pages/Profile';
import Management from './pages/Management';
import ManagementDashboard from './pages/management/ManagementDashboard';
import ManagementUsers from './pages/management/ManagementUsers';
import ManagementFleets from './pages/management/ManagementFleets';
import ManagementBans from './pages/management/ManagementBans';
import ManagementSDE from './pages/management/ManagementSDE';
import ManagementSRP from './pages/management/ManagementSRP';
import FleetDashboard from './pages/FleetDashboard';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/landing/" element={<Landing />} />
          <Route path="/doctrines" element={<Doctrines />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/fleet/:token" element={<FleetDashboard />} />

          <Route path="/management" element={<Management />}>
            <Route index element={<ManagementDashboard />} />
            <Route path="users" element={<ManagementUsers />} />
            <Route path="fleets" element={<ManagementFleets />} />
            <Route path="bans" element={<ManagementBans />} />
            <Route path="sde" element={<ManagementSDE />} />
            <Route path="srp" element={<ManagementSRP />} />
            <Route path="*" element={<div className="p-10 text-slate-500">Feature Coming Soon</div>} />
          </Route>

          <Route path="*" element={<div className="p-10 text-center text-slate-500">Page Not Found</div>} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;