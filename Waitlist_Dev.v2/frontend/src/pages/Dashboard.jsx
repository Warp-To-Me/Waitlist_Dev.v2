import { useState } from 'react';
import { useAuth } from "../context/AuthContext";
import { Link } from 'react-router-dom';

function Dashboard() {
    const { user } = useAuth();

    // --- Mock Data (Replace with API calls later) ---
    const [activeFleets, setActiveFleets] = useState([
        {
            id: 1,
            fc_name: "CCP Fozzie",
            boss_name: "Fleet Boss A",
            system: "Inaya",
            constellation: "Ur-Len",
            dockup: "Inaya - WTM HQ Citadel",
            type: "Headquarters",
            status: "open", // open, closed, invite_only
            motd: "<b>Welcome to Warp To Me Incursions!</b><br/><br/>Current Focus: <i>TCRC > NCN > TPPH</i>.<br/>Please ensure you have the correct exotic dancers in cargo."
        }
    ]);

    const [myEntries, setMyEntries] = useState([
        {
            id: 101,
            fit_name: "Vindicator - Hybrid DPS",
            role: "DPS",
            group: "Hybrid",
            time_added: "14:20",
            status: "pending" // pending, invited, in_fleet
        }
    ]);

    // --- Actions ---
    const handleXUp = () => {
        alert("This would open the X-UP Modal to select fits.");
    };

    const handleRemoveEntry = (id) => {
        if (confirm("Remove this fit from the waitlist?")) {
            setMyEntries(myEntries.filter(e => e.id !== id));
        }
    };

    return (
        <div className="container py-4">
            {/* Header Section */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h1 className="h2 mb-0 brand-font text-uppercase">
                        Dashboard
                    </h1>
                    <p className="text-muted mb-0">
                        Welcome back, <span className="text-primary fw-bold">{user?.eve_character?.character_name || "Pilot"}</span>.
                    </p>
                </div>
                <div>
                    {/* Status Indicators */}
                    <span className="badge bg-success-subtle text-success border border-success me-2">
                        <i className="bi bi-circle-fill me-1" style={{ fontSize: '0.6em' }}></i>
                        Online
                    </span>
                </div>
            </div>

            <div className="row g-4">
                {/* LEFT COLUMN: Fleets & Actions */}
                <div className="col-lg-8">

                    {/* Active Fleets Section */}
                    {activeFleets.length > 0 ? (
                        activeFleets.map(fleet => (
                            <div key={fleet.id} className="card mb-4 border-primary">
                                <div className="card-header d-flex justify-content-between align-items-center bg-primary bg-opacity-10">
                                    <div className="d-flex align-items-center gap-2">
                                        <i className="bi bi-diagram-3-fill text-primary"></i>
                                        <span className="fw-bold text-uppercase">{fleet.type} Fleet</span>
                                        <span className="badge bg-primary">{fleet.system}</span>
                                    </div>
                                    <div className="small text-muted">
                                        FC: <span className="text-white">{fleet.fc_name}</span>
                                    </div>
                                </div>
                                <div className="card-body">
                                    <div className="row mb-3">
                                        <div className="col-md-6">
                                            <small className="text-muted d-block text-uppercase" style={{ fontSize: '0.7rem' }}>Location</small>
                                            <div className="d-flex align-items-center gap-2">
                                                <i className="bi bi-geo-alt text-primary"></i>
                                                <span>{fleet.system} <span className="text-muted">({fleet.constellation})</span></span>
                                            </div>
                                        </div>
                                        <div className="col-md-6 mt-2 mt-md-0">
                                            <small className="text-muted d-block text-uppercase" style={{ fontSize: '0.7rem' }}>Status</small>
                                            <div className="d-flex align-items-center gap-2">
                                                <i className="bi bi-activity text-success"></i>
                                                <span className="text-capitalize">{fleet.status.replace('_', ' ')}</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="alert alert-dark border-secondary bg-black bg-opacity-25 mb-3">
                                        <div className="d-flex align-items-start gap-2">
                                            <i className="bi bi-info-circle-fill text-primary mt-1"></i>
                                            <div className="small" dangerouslySetInnerHTML={{ __html: fleet.motd }}></div>
                                        </div>
                                    </div>

                                    <div className="d-flex gap-2">
                                        <button onClick={handleXUp} className="btn btn-primary btn-lg flex-grow-1 brand-font">
                                            <i className="bi bi-plus-circle-dotted me-2"></i>
                                            JOIN WAITLIST (X-UP)
                                        </button>
                                        {/* Mock Check-in button */}
                                        <button className="btn btn-outline-light" title="I am here">
                                            <i className="bi bi-hand-index-thumb"></i>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))
                    ) : (
                        <div className="alert alert-secondary text-center py-5">
                            <i className="bi bi-moon-stars fs-1 d-block mb-3 text-muted"></i>
                            <h4 className="alert-heading">No Active Fleets</h4>
                            <p className="mb-0">There are currently no fleets running. Check back later or start one yourself!</p>
                        </div>
                    )}

                    {/* My Entries Section */}
                    <div className="card">
                        <div className="card-header">
                            <i className="bi bi-list-check me-2"></i>
                            My Active Fits
                        </div>
                        <div className="card-body p-0">
                            {myEntries.length > 0 ? (
                                <div className="list-group list-group-flush">
                                    {myEntries.map(entry => (
                                        <div key={entry.id} className="list-group-item bg-transparent d-flex align-items-center justify-content-between py-3">
                                            <div className="d-flex align-items-center gap-3">
                                                <div className="rounded-circle bg-primary bg-opacity-10 p-2 text-primary">
                                                    <i className="bi bi-cpu-fill"></i>
                                                </div>
                                                <div>
                                                    <div className="fw-bold text-white">{entry.fit_name}</div>
                                                    <div className="small text-muted">
                                                        <span className="badge bg-secondary me-2">{entry.role}</span>
                                                        <i className="bi bi-clock me-1"></i> {entry.time_added}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="d-flex align-items-center gap-2">
                                                <span className="badge bg-warning text-dark border border-warning">
                                                    {entry.status.toUpperCase()}
                                                </span>
                                                <button
                                                    className="btn btn-outline-danger btn-sm"
                                                    onClick={() => handleRemoveEntry(entry.id)}
                                                    title="Remove from waitlist"
                                                >
                                                    <i className="bi bi-trash"></i>
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-4 text-muted">
                                    You are not currently on the waitlist.
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* RIGHT COLUMN: Character Stats & Tools */}
                <div className="col-lg-4">
                    {/* Character Card */}
                    <div className="card mb-4">
                        <div className="card-body text-center pt-4">
                            <img
                                src={user?.eve_character?.portrait_url || "https://images.evetech.net/characters/1/portrait?size=128"}
                                className="rounded-circle border border-2 border-primary mb-3 shadow"
                                width="96"
                                height="96"
                                alt="Character"
                            />
                            <h4 className="brand-font mb-1">{user?.eve_character?.character_name}</h4>
                            <div className="text-muted small mb-3">Warp To Me Incursions</div>

                            <hr className="border-secondary" />

                            <div className="row text-center mt-3">
                                <div className="col-6 border-end border-secondary">
                                    <div className="h5 mb-0 text-white">0 ISK</div>
                                    <div className="small text-muted text-uppercase" style={{ fontSize: '0.7rem' }}>Wallet</div>
                                </div>
                                <div className="col-6">
                                    <div className="h5 mb-0 text-white">0 LP</div>
                                    <div className="small text-muted text-uppercase" style={{ fontSize: '0.7rem' }}>Concord LP</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Quick Links / Tools */}
                    <div className="card">
                        <div className="card-header">
                            <i className="bi bi-tools me-2"></i>
                            Tools
                        </div>
                        <div className="list-group list-group-flush">
                            <Link to="/doctrines" className="list-group-item list-group-item-action bg-transparent text-white">
                                <i className="bi bi-book me-2 text-primary"></i>
                                View Doctrines
                            </Link>
                            <a href="#" className="list-group-item list-group-item-action bg-transparent text-white">
                                <i className="bi bi-discord me-2 text-primary"></i>
                                Join Discord
                            </a>
                            <a href="#" className="list-group-item list-group-item-action bg-transparent text-white">
                                <i className="bi bi-teamspeak me-2 text-primary"></i>
                                TeamSpeak Info
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Dashboard;