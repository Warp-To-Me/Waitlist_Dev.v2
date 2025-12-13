import { Link, useLocation } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';

function Navbar() {
    const location = useLocation();
    const { theme, setTheme } = useTheme();

    // Helper to check active link
    const isActive = (path) => location.pathname === path ? 'active' : '';

    // Mock User State
    const user = {
        isAuthenticated: true,
        isStaff: true,
        username: "Guest Pilot",
        eve_character: {
            character_id: 1,
            character_name: "Test Character"
        }
    };

    // Theme Options for the dropdown
    const themes = [
        { id: 'default', name: 'WTM Standard', color: '#D4AF37' },
        { id: 'caldari', name: 'Caldari State', color: '#4aa3df' },
        { id: 'gallente', name: 'Gallente Federation', color: '#2ecc71' },
        { id: 'minmatar', name: 'Minmatar Republic', color: '#d35400' },
        { id: 'amarr', name: 'Amarr Empire', color: '#f1c40f' },
    ];

    return (
        <nav className="navbar navbar-expand-lg navbar-dark sticky-top">
            <div className="container-fluid px-4">
                <Link className="navbar-brand d-flex align-items-center gap-2" to="/">
                    <i className="bi bi-rocket-takeoff-fill" style={{ color: 'var(--wtm-gold)' }}></i>
                    WTM Waitlist
                </Link>

                <button
                    className="navbar-toggler border-0"
                    type="button"
                    data-bs-toggle="collapse"
                    data-bs-target="#navbarContent"
                >
                    <span className="navbar-toggler-icon"></span>
                </button>

                <div className="collapse navbar-collapse" id="navbarContent">
                    <ul className="navbar-nav me-auto mb-2 mb-lg-0">
                        <li className="nav-item">
                            <Link className={`nav-link ${isActive('/')}`} to="/">
                                <i className="bi bi-speedometer2 me-1"></i> Dashboard
                            </Link>
                        </li>
                        <li className="nav-item">
                            <Link className={`nav-link ${isActive('/doctrines')}`} to="/doctrines">
                                <i className="bi bi-book me-1"></i> Doctrines
                            </Link>
                        </li>

                        {(user.isStaff) && (
                            <li className="nav-item dropdown">
                                <a className="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                                    <i className="bi bi-shield-lock me-1"></i> Management
                                </a>
                                <ul className="dropdown-menu">
                                    <li><Link className="dropdown-item" to="/admin/dashboard">Admin Dashboard</Link></li>
                                    <li><Link className="dropdown-item" to="/admin/fleets">Fleet Management</Link></li>
                                    <li><Link className="dropdown-item" to="/admin/bans">Ban Management</Link></li>
                                </ul>
                            </li>
                        )}
                    </ul>

                    <ul className="navbar-nav align-items-lg-center gap-2">
                        {/* Theme Selector Dropdown */}
                        <li className="nav-item dropdown">
                            <a
                                className="nav-link dropdown-toggle d-flex align-items-center"
                                href="#"
                                role="button"
                                data-bs-toggle="dropdown"
                                title="Change Theme"
                            >
                                <i className="bi bi-palette-fill"></i>
                            </a>
                            <ul className="dropdown-menu dropdown-menu-end">
                                <li><h6 className="dropdown-header">Select Theme</h6></li>
                                {themes.map((t) => (
                                    <li key={t.id}>
                                        <button
                                            className={`dropdown-item d-flex align-items-center justify-content-between ${theme === t.id ? 'active' : ''}`}
                                            onClick={() => setTheme(t.id)}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <span>{t.name}</span>
                                            <span
                                                className="rounded-circle border border-secondary"
                                                style={{ width: '12px', height: '12px', backgroundColor: t.color }}
                                            ></span>
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        </li>

                        {/* User Menu */}
                        {user.isAuthenticated ? (
                            <li className="nav-item dropdown border-start border-secondary ps-lg-2 ms-lg-2">
                                <a
                                    className="nav-link dropdown-toggle d-flex align-items-center gap-2 py-0"
                                    href="#"
                                    role="button"
                                    data-bs-toggle="dropdown"
                                >
                                    <div className="d-flex flex-column align-items-end lh-1 d-none d-lg-flex">
                                        <span className="fw-bold text-white" style={{ fontSize: '0.9rem' }}>
                                            {user.eve_character?.character_name || user.username}
                                        </span>
                                        <small className="text-muted" style={{ fontSize: '0.75rem' }}>
                                            Logged In
                                        </small>
                                    </div>

                                    <img
                                        src={`https://images.evetech.net/characters/${user.eve_character?.character_id || 1}/portrait?size=64`}
                                        className="rounded border border-secondary"
                                        width="38"
                                        height="38"
                                        alt="Portrait"
                                        onError={(e) => { e.target.src = 'https://images.evetech.net/characters/1/portrait?size=64' }}
                                    />
                                </a>
                                <ul className="dropdown-menu dropdown-menu-end">
                                    <li>
                                        <div className="px-3 py-2 d-lg-none">
                                            <div className="fw-bold text-white">{user.eve_character?.character_name}</div>
                                        </div>
                                    </li>
                                    <li>
                                        <Link className="dropdown-item" to="/profile">
                                            <i className="bi bi-person-gear me-2"></i>Profile Settings
                                        </Link>
                                    </li>
                                    <li><hr className="dropdown-divider" /></li>
                                    <li>
                                        <button className="dropdown-item text-danger" onClick={() => console.log('Logout')}>
                                            <i className="bi bi-box-arrow-right me-2"></i>Logout
                                        </button>
                                    </li>
                                </ul>
                            </li>
                        ) : (
                            <li className="nav-item ms-lg-2">
                                <Link className="btn btn-outline-primary btn-sm px-4" to="/login">
                                    LOGIN WITH EVE
                                </Link>
                            </li>
                        )}
                    </ul>
                </div>
            </div>
        </nav>
    );
}

export default Navbar;