function Footer() {
    return (
        <footer className="footer mt-auto py-3">
            <div className="container text-center">
                <span className="text-muted">
                    &copy; {new Date().getFullYear()} Warp To Me Incursions. All rights reserved.
                    <span className="mx-2">|</span>
                    <span className="mono-font text-small">v2.0.0-beta</span>
                </span>
            </div>
        </footer>
    );
}

export default Footer;