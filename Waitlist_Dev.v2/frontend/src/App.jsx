import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Doctrines from './pages/Doctrines';

function App() {
    return (
        <Router>
            <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-blue-500/30">
                <Navbar />
                <main className="container mx-auto px-4 py-8">
                    <Routes>
                        <Route path="/" element={<Home />} />
                        <Route path="/doctrines" element={<Doctrines />} />
                    </Routes>
                </main>
            </div>
        </Router>
    );
}

export default App;