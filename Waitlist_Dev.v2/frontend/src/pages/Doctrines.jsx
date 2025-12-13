import { useState, useEffect } from 'react';

function Doctrines() {
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetch('/api/doctrines/')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                // Check if response is actually JSON
                const contentType = response.headers.get("content-type");
                if (!contentType || !contentType.includes("application/json")) {
                    throw new Error("Received non-JSON response from backend");
                }
                return response.json();
            })
            .then(data => {
                setCategories(data.categories);
                setLoading(false);
            })
            .catch(err => {
                console.error("Error fetching doctrines:", err);
                setError(err.message);
                setLoading(false);
            });
    }, []);

    if (loading) {
        return (
            <div className="container py-5 text-center">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-2 text-muted">Loading Doctrines...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="container py-5 text-center">
                <div className="alert alert-danger d-inline-block">
                    <i className="bi bi-exclamation-triangle-fill me-2"></i>
                    Error Loading Data: {error}
                </div>
                <p className="small text-muted">Ensure your Django server is running on port 8000.</p>
            </div>
        );
    }

    return (
        <div className="container py-4">
            <h1 className="h2 brand-font text-uppercase mb-4 text-center text-lg-start">
                Alliance Doctrines
            </h1>

            {categories.map(category => (
                <div key={category.id} className="mb-5">
                    <div className="d-flex align-items-center mb-3 border-bottom border-secondary pb-2">
                        <h3 className="h4 brand-font text-primary mb-0 me-3">{category.name}</h3>
                        <span className="text-muted small">{category.description}</span>
                    </div>

                    <div className="row g-4">
                        {category.fits.map(fit => (
                            <div key={fit.id} className="col-md-6 col-xl-4">
                                <div className={`card h-100 ${fit.is_primary ? 'border-primary' : 'border-secondary'}`}>
                                    <div className="card-header d-flex justify-content-between align-items-center">
                                        <span className="fw-bold">{fit.name}</span>
                                        {fit.is_primary && (
                                            <span className="badge bg-primary text-dark">Preferred</span>
                                        )}
                                    </div>
                                    <div className="card-body">
                                        <div className="d-flex justify-content-between mb-3">
                                            <span className="badge bg-secondary">{fit.role}</span>
                                            {fit.price_estimate && (
                                                <small className="text-muted">
                                                    ~{(fit.price_estimate / 1000000).toFixed(0)}M ISK
                                                </small>
                                            )}
                                        </div>

                                        <p className="card-text small text-muted mb-4">
                                            {fit.description || "No description available."}
                                        </p>

                                        <div className="d-grid">
                                            <button
                                                className="btn btn-outline-primary btn-sm"
                                                onClick={() => alert(`This would copy the EFT fit for ${fit.name}`)}
                                            >
                                                <i className="bi bi-clipboard me-2"></i>
                                                Copy to Clipboard
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}

            {categories.length === 0 && (
                <div className="text-center text-muted py-5">
                    <i className="bi bi-box-seam fs-1 d-block mb-3"></i>
                    <p>No doctrines found.</p>
                </div>
            )}
        </div>
    );
}

export default Doctrines;