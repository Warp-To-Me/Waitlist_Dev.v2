import React from 'react';
import clsx from 'clsx';

const SmartPagination = ({ current, total, onChange }) => {
    // Generate page numbers: <- 2 3 4 5/50 6 7 8 ->
    // We want a window of 7 items centered on current

    if (total <= 1) return null;

    let start = Math.max(1, current - 3);
    let end = Math.min(total, current + 3);

    // Adjust window if close to edges
    if (start === 1) end = Math.min(total, 7);
    if (end === total) start = Math.max(1, total - 6);

    const pages = [];
    for (let i = start; i <= end; i++) {
        pages.push(i);
    }

    return (
        <div className="flex items-center gap-1">
            <button
                onClick={() => onChange(Math.max(1, current - 1))}
                disabled={current === 1}
                className="btn-secondary py-1 px-2 text-[10px] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white/10"
            >
                &larr;
            </button>

            {pages.map(p => (
                <button
                    key={p}
                    onClick={() => onChange(p)}
                    className={clsx(
                        "py-1 px-2.5 text-[10px] rounded transition font-mono",
                        p === current
                            ? "bg-brand-500 text-white font-bold shadow-lg shadow-brand-500/20"
                            : "bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white"
                    )}
                >
                    {p}
                </button>
            ))}

            {/* Show Total if not visible in range */}
            {end < total && (
                <>
                    <span className="text-slate-600 text-[10px]">...</span>
                    <button onClick={() => onChange(total)} className="py-1 px-2 text-[10px] text-slate-500 hover:text-white">{total}</button>
                </>
            )}

            <button
                onClick={() => onChange(Math.min(total, current + 1))}
                disabled={current === total}
                className="btn-secondary py-1 px-2 text-[10px] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white/10"
            >
                &rarr;
            </button>
        </div>
    );
}

export default SmartPagination;
