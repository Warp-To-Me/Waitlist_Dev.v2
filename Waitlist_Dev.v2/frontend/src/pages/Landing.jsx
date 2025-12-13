import { Link } from 'react-router-dom';

function Home() {
    // Mock Auth State (Replace with real context later)
    // If true, shows "Go to Dashboard", if false shows "Log In"
    const isAuthenticated = false;

    return (
        <div className="container">
            <div className="row min-vh-75 align-items-center py-5">
                {/* Left Column: Text Content */}
                <div className="col-lg-6 mb-5 mb-lg-0 text-center text-lg-start">
                    <h1 className="display-2 fw-bold mb-4 brand-font">
                        WARP TO <span className="text-primary">ME</span>
                    </h1>
                    <h2 className="h3 text-muted mb-4 brand-font">
                        INCURSIONS
                    </h2>
                    <p className="lead mb-5">
                        The premier high-sec incursion community. <br className="d-none d-lg-block" />
                        Fly safer, make ISK, and have fun.
                    </p>

                    <div className="d-grid gap-3 d-sm-flex justify-content-sm-center justify-content-lg-start">
                        {isAuthenticated ? (
                            <Link to="/dashboard" className="btn btn-primary btn-lg px-4 gap-3 brand-font">
                                GO TO DASHBOARD
                            </Link>
                        ) : (
                            <Link to="/login" className="btn btn-primary btn-lg px-4 gap-3 brand-font">
                                LOG IN WITH EVE ONLINE
                            </Link>
                        )}
                        <Link to="/doctrines" className="btn btn-outline-light btn-lg px-4 brand-font">
                            VIEW DOCTRINES
                        </Link>
                    </div>

                    <div className="mt-5 pt-3 row g-4 justify-content-center justify-content-lg-start">
                        <div className="col-auto">
                            <div className="d-flex align-items-center">
                                <i className="bi bi-shield-check fs-2 text-primary me-3"></i>
                                <div className="text-start">
                                    <div className="fw-bold brand-font">Safe</div>
                                    <div className="small text-muted">SRP Covered</div>
                                </div>
                            </div>
                        </div>
                        <div className="col-auto">
                            <div className="d-flex align-items-center">
                                <i className="bi bi-graph-up-arrow fs-2 text-primary me-3"></i>
                                <div className="text-start">
                                    <div className="fw-bold brand-font">Profitable</div>
                                    <div className="small text-muted">Consistent ISK/hr</div>
                                </div>
                            </div>
                        </div>
                        <div className="col-auto">
                            <div className="d-flex align-items-center">
                                <i className="bi bi-people-fill fs-2 text-primary me-3"></i>
                                <div className="text-start">
                                    <div className="fw-bold brand-font">Community</div>
                                    <div className="small text-muted">Newbro Friendly</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Column: Hero Graphic */}
                <div className="col-lg-6 text-center">
                    <i
                        className="bi bi-rocket-takeoff-fill text-primary"
                        style={{
                            fontSize: 'clamp(8rem, 20vw, 20rem)',
                            opacity: 0.8,
                            filter: 'drop-shadow(0 0 20px rgba(var(--bs-primary-rgb), 0.3))'
                        }}
                    ></i>
                </div>
            </div>
        </div>
    );
}

export default Home;