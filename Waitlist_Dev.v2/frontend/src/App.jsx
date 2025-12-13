import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Home from './pages/Home';
import Doctrines from './pages/Doctrines';

function App() {
    return (
        <div className="d-flex flex-column min-vh-100">
            <Navbar />

            {/* py-4 adds vertical padding so content isn't flush with navbar/footer
         container-fluid allows content to use full width if needed by child pages
      */}
            <main className="flex-grow-1 py-4">
                <Routes>
                    <Route path="/" element={<Home />} />
                    <Route path="/doctrines" element={<Doctrines />} />

                    {/* Placeholder route for testing */}
                    <Route path="/login" element={
                        <div className="container text-center text-white mt-5">
                            <h2>Login Page</h2>
                            <p className="text-muted">This will be the SSO redirect handler.</p>
                        </div>
                    } />
                </Routes>
            </main>

            <Footer />
        </div>
    );
}

export default App;