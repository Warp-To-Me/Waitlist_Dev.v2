import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export default function Home() {
    return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
            <h1 className="text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-600 mb-6">
                Waitlist v2
            </h1>
            <p className="text-slate-400 text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
                Welcome to the next generation fleet management system.
                <br />
                Streamlined doctrines, real-time fleet tracking, and instant SRP.
            </p>

            <div className="flex gap-4">
                <Link
                    to="/doctrines"
                    className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-lg font-semibold transition-all hover:scale-105"
                >
                    View Doctrines
                    <ArrowRight className="w-4 h-4" />
                </Link>
                <div className="px-8 py-3 rounded-lg border border-slate-700 text-slate-400 cursor-not-allowed">
                    Dashboard (Coming Soon)
                </div>
            </div>
        </div>
    );
}