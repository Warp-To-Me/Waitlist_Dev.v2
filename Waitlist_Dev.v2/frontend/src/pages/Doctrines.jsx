import { useState, useEffect } from 'react';
import axios from 'axios';
import { Copy, Check, Ship } from 'lucide-react';

export default function Doctrines() {
    const [categories, setCategories] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchDoctrines = async () => {
            try {
                // Fetch data from our Django API
                const response = await axios.get('/api/doctrines/');

                // Debug: Log the actual data received
                console.log("Doctrines API Response:", response.data);

                if (Array.isArray(response.data)) {
                    // Scenario A: API returned a clean list (Expected)
                    setCategories(response.data);
                } else if (response.data && Array.isArray(response.data.results)) {
                    // Scenario B: API returned a paginated object { results: [...] }
                    setCategories(response.data.results);
                } else {
                    // Scenario C: API returned something unexpected (HTML or Error Object)
                    console.error("Unexpected data format:", response.data);
                    setError("Received invalid data format from backend.");
                    setCategories([]); // Prevent .map crash
                }

                setLoading(false);
            } catch (err) {
                console.error("Error fetching doctrines:", err);
                setError("Failed to load doctrines. Is the backend running?");
                setLoading(false);
            }
        };

        fetchDoctrines();
    }, []);

    if (loading) return (
        <div className="flex justify-center items-center min-h-[50vh]">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
    );

    if (error) return (
        <div className="text-center text-red-400 mt-10 p-4 border border-red-900 bg-red-900/20 rounded max-w-lg mx-auto">
            <p className="font-bold">Error Loading Data</p>
            <p className="text-sm mt-1">{error}</p>
        </div>
    );

    // Safety check: Ensure categories is an array before mapping
    if (!Array.isArray(categories)) {
        return <div className="text-center text-yellow-400 mt-10">Data loaded but format is incorrect. Check console.</div>;
    }

    return (
        <div className="space-y-12 pb-20">
            <div className="border-b border-slate-700 pb-6">
                <h1 className="text-3xl font-bold text-white">Alliance Doctrines</h1>
                <p className="text-slate-400 mt-2">Approved fits for fleet operations.</p>
            </div>

            {categories.length === 0 && (
                <div className="text-center text-slate-500 py-10">
                    No active doctrines found.
                </div>
            )}

            {categories.map(category => (
                <div key={category.id} className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <h2 className="text-xl font-semibold text-blue-400 mb-6 flex items-center gap-2">
                        <span className="w-2 h-8 bg-blue-500 rounded-sm inline-block"></span>
                        {category.name}
                    </h2>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                        {category.fits.map(fit => (
                            <FitCard key={fit.id} fit={fit} />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

function FitCard({ fit }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(fit.eft_format);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="bg-slate-800 rounded-lg overflow-hidden border border-slate-700 hover:border-slate-500 transition-all shadow-lg flex flex-col group">
            {/* Header / Image */}
            <div className="relative h-48 bg-slate-900 overflow-hidden flex items-center justify-center">
                {/* EVE Image Server URL */}
                <img
                    src={`https://images.evetech.net/types/${fit.hull_id}/render?size=640`}
                    alt={fit.hull_name}
                    className="h-full object-contain p-2 group-hover:scale-110 transition-transform duration-500"
                    onError={(e) => {
                        e.target.style.display = 'none'; // Hide if image fails
                    }}
                />

                {/* Tags Overlay */}
                <div className="absolute top-2 right-2 flex flex-col gap-1 items-end">
                    {fit.tags.map(tag => (
                        <span
                            key={tag.id}
                            className="px-2 py-1 text-[10px] uppercase font-bold tracking-wider rounded bg-slate-900/80 text-white backdrop-blur-sm border border-slate-600 shadow-sm"
                            style={{ borderColor: tag.color, color: tag.color }}
                        >
                            {tag.name}
                        </span>
                    ))}
                </div>
            </div>

            {/* Content */}
            <div className="p-4 flex-1 flex flex-col">
                <div className="mb-4">
                    <h3 className="text-lg font-bold text-white leading-tight">{fit.name}</h3>
                    <div className="flex items-center gap-1 text-slate-400 text-sm mt-1">
                        <Ship className="w-3 h-3" />
                        <span>{fit.hull_name}</span>
                    </div>
                </div>

                <div className="mt-auto pt-4 border-t border-slate-700/50">
                    <button
                        onClick={handleCopy}
                        className={`w-full flex items-center justify-center gap-2 py-2 px-4 rounded font-medium text-sm transition-all active:scale-95 ${copied
                                ? 'bg-green-600 text-white'
                                : 'bg-blue-600 hover:bg-blue-500 text-white'
                            }`}
                    >
                        {copied ? (
                            <>
                                <Check className="w-4 h-4" />
                                Copied!
                            </>
                        ) : (
                            <>
                                <Copy className="w-4 h-4" />
                                Copy to Clipboard
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}