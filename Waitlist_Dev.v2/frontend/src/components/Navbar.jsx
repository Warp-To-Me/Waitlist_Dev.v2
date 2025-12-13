import { Link, useLocation } from 'react-router-dom';
import clsx from 'clsx';
import { Rocket, ShieldAlert, LayoutDashboard } from 'lucide-react';

export default function Navbar() {
    const location = useLocation();

    const navItemClass = (path) =>
        clsx(
            "flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
            location.pathname === path
                ? "bg-slate-700 text-white"
                : "text-slate-300 hover:bg-slate-800 hover:text-white"
        );

    return (
        <nav className="bg-slate-900 border-b border-slate-700 sticky top-0 z-50">
            <div className="container mx-auto px-4">
                <div className="flex items-center justify-between h-16">
                    <div className="flex items-center">
                        <Link to="/" className="text-xl font-bold text-blue-500 flex items-center gap-2">
                            <Rocket className="h-6 w-6" />
                            <span>Waitlist v2</span>
                        </Link>
                        <div className="ml-10 flex items-baseline space-x-4">
                            <Link to="/" className={navItemClass('/')}>
                                <LayoutDashboard className="w-4 h-4" />
                                <span>Dashboard</span>
                            </Link>
                            <Link to="/doctrines" className={navItemClass('/doctrines')}>
                                <ShieldAlert className="w-4 h-4" />
                                <span>Doctrines</span>
                            </Link>
                        </div>
                    </div>
                    <div>
                        {/* Placeholder for User Profile/Auth Status */}
                        <div className="flex items-center gap-3">
                            <div className="text-right hidden md:block">
                                <div className="text-xs text-slate-400">Welcome</div>
                                <div className="text-sm font-bold text-white">Guest Pilot</div>
                            </div>
                            <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600"></div>
                        </div>
                    </div>
                </div>
            </div>
        </nav>
    );
}