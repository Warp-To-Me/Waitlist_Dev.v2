import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Save, Rocket, Palette, X, Trash } from 'lucide-react';
import Picker from 'vanilla-picker';

const ManagementFleetSetup = () => {
    const navigate = useNavigate();
    const [fleetName, setFleetName] = useState("New Fleet");
    const [fcChars, setFcChars] = useState([]);
    const [selectedFc, setSelectedFc] = useState('');
    const [offlineMode, setOfflineMode] = useState(false);
    const [motd, setMotd] = useState('');
    const [previewHtml, setPreviewHtml] = useState('');
    const [templates, setTemplates] = useState([]);
    const [structure, setStructure] = useState([]);
    const pickerRef = useRef(null);

    useEffect(() => {
        // Fetch initial data (FC characters, templates)
        fetch('/api/management/fleets/setup/init/')
            .then(res => res.json())
            .then(data => {
                setFcChars(data.fc_chars || []);
                if (data.fc_chars?.length > 0) {
                    const main = data.fc_chars.find(c => c.is_main) || data.fc_chars[0];
                    setSelectedFc(main.character_id);
                    setFleetName(`${main.character_name}'s Fleet`);
                }
                setTemplates(data.templates || []);
                // Load default structure
                setStructure([{name: "Wing 1", squads: ["Squad 1", "Squad 2"]}]);
            });
    }, []);

    useEffect(() => {
        updatePreview(motd);
    }, [motd]);

    // FC Selection Change Handler
    const handleFcChange = (e) => {
        const id = e.target.value;
        setSelectedFc(id);
        const char = fcChars.find(c => c.character_id == id);
        if (char && fleetName.includes("'s Fleet")) {
            setFleetName(`${char.character_name}'s Fleet`);
        }
    };

    const updatePreview = (text) => {
        let html = text || '';
        html = html.replace(/\n/g, "<br>");
        html = html.replace(/<color=['"]?(?:0x|#)?([0-9a-fA-F]{8})['"]?>/g, '<font color="#$1">');
        html = html.replace(/<\/color>/g, '</font>');
        html = html.replace(/\bcolor=(['"]?)(?:#|0x)?([0-9a-fA-F]{8})\1/g, (match, quote, hex) => {
            const alpha = hex.substring(0, 2);
            const color = hex.substring(2, 8);
            return `color=${quote}#${color}${alpha}${quote}`;
        });
        html = html.replace(/\bsize=['"]?(\d+)['"]?/g, "data-size='$1'");
        html = html.replace(/<a\s+href=(?:['"])([^'"]+)(?:['"])>(.*?)<\/a>/gi, (match, url, label) => {
            let color = '#ffd700';
            const lower = url.toLowerCase();
            if (lower.startsWith('overviewpreset')) color = '#00ffff';
            else if (lower.startsWith('joinchannel')) color = '#a0a0ff';
            return `<span style="color: ${color}; text-decoration: underline; cursor: help;" title="${url}">${label}</span>`;
        });
        setPreviewHtml(html);
    };

    const insertTag = (tag) => {
        const input = document.getElementById('motd-input');
        const start = input.selectionStart;
        const end = input.selectionEnd;
        const text = input.value;
        const selected = text.substring(start, end);
        const replace = tag === 'br' ? '<br>' : `<${tag}>${selected}</${tag}>`;
        const newVal = text.substring(0, start) + replace + text.substring(end);
        setMotd(newVal);
        setTimeout(() => {
            input.focus();
            input.selectionStart = start + replace.length;
            input.selectionEnd = start + replace.length;
        }, 0);
    };

    const insertColor = (color) => {
        let hex = color;
        if (color === 'green') hex = "#00ff00";
        if (color === 'red') hex = "#ff0000";
        if (color === 'yellow') hex = "#ffff00";
        if (color === 'blue') hex = "#00ffff";
        insertColorCode(hex);
    };

    const insertColorCode = (hexCode) => {
        const input = document.getElementById('motd-input');
        const start = input.selectionStart;
        const end = input.selectionEnd;
        const text = input.value;
        const selected = text.substring(start, end);
        const replace = `<font color="${hexCode}">${selected}</font>`;
        const newVal = text.substring(0, start) + replace + text.substring(end);
        setMotd(newVal);
        setTimeout(() => {
            input.focus();
            input.selectionStart = start + replace.length;
            input.selectionEnd = start + replace.length;
        }, 0);
    };

    const openPicker = (e) => {
        if (!pickerRef.current) {
            pickerRef.current = new Picker({
                parent: e.currentTarget.parentElement,
                popup: 'bottom',
                color: '#ffffff',
                alpha: true,
                editor: true,
                onDone: (color) => {
                    let hex = color.hex.substring(0, 7);
                    let alpha = color.rgba[3];
                    if (alpha < 1) {
                        let alphaHex = Math.round(alpha * 255).toString(16).padStart(2, '0');
                        insertColorCode('#' + alphaHex + hex.substring(1));
                    } else {
                        insertColorCode(hex);
                    }
                }
            });
        }
        pickerRef.current.openHandler();
    };

    // Structure Manipulation
    const updateWing = (idx, name) => {
        const newStruct = [...structure];
        newStruct[idx].name = name;
        setStructure(newStruct);
    };
    const addWing = () => setStructure([...structure, { name: `Wing ${structure.length + 1}`, squads: [] }]);
    const removeWing = (idx) => {
        const newStruct = [...structure];
        newStruct.splice(idx, 1);
        setStructure(newStruct);
    };
    const addSquad = (wIdx) => {
        const newStruct = [...structure];
        newStruct[wIdx].squads.push(`Squad ${newStruct[wIdx].squads.length + 1}`);
        setStructure(newStruct);
    };
    const updateSquad = (wIdx, sIdx, val) => {
        const newStruct = [...structure];
        newStruct[wIdx].squads[sIdx] = val;
        setStructure(newStruct);
    };
    const removeSquad = (wIdx, sIdx) => {
        const newStruct = [...structure];
        newStruct[wIdx].squads.splice(sIdx, 1);
        setStructure(newStruct);
    };

    // Actions
    const saveTemplate = () => {
        const name = prompt("Enter a name for this template:", "My Fleet Setup");
        if (!name) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch('/api/management/fleets/templates/save/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ character_id: selectedFc, template_name: name, structure, motd })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                alert("Template saved!");
                // Refresh templates
                fetch('/api/management/fleets/setup/init/').then(r=>r.json()).then(d=>setTemplates(d.templates||[]));
            } else alert("Error: " + data.error);
        });
    };

    const loadTemplate = (tpl) => {
        if (!confirm("Apply template? This will replace your current structure and MOTD.")) return;
        setStructure(tpl.wings.map(w => ({ name: w.name, squads: w.squads })));
        setMotd(tpl.motd || "");
    };

    const deleteTemplate = (id) => {
        if (!confirm("Delete template?")) return;
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch('/api/management/fleets/templates/delete/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ template_id: id })
        }).then(res => res.json()).then(data => {
            if (data.success) {
                setTemplates(templates.filter(t => t.id !== id));
            } else alert("Error: " + data.error);
        });
    };

    const launchFleet = () => {
        const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
        fetch('/api/management/fleets/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({
                action: 'create',
                name: fleetName,
                character_id: selectedFc,
                structure,
                motd,
                is_offline: offlineMode
            })
        }).then(res => res.json()).then(data => {
            if (data.status === 'created') {
                // If the redirect URL is provided by backend, use it, otherwise assume pattern
                if (data.redirect_url) {
                    // Backend returns full path, e.g. /management/fleets/TOKEN/settings
                    // We need to navigate via React Router if possible to avoid full reload
                    navigate(data.redirect_url);
                } else {
                    navigate('/management/fleets');
                }
            } else {
                alert("Launch Failed: " + data.error);
            }
        });
    };

    return (
        <div className="flex flex-col min-h-[calc(100vh-8rem)] bg-dark-950 relative rounded-xl border border-white/5 shadow-2xl">
            {/* Header */}
            <div className="glass-header px-6 py-4 flex justify-between items-center shrink-0 bg-slate-900/90 z-20 border-b border-white/10">
                <div>
                    <h1 className="heading-1 flex items-center gap-3">
                        <span className="text-3xl">🛸</span> Fleet Setup
                    </h1>
                    <p className="text-slate-400 text-sm mt-1">Initialize fleet structure and mappings.</p>
                </div>
                <div className="flex gap-2">
                    <Link to="/management/fleets" className="btn-secondary text-xs py-1.5 px-3">Cancel</Link>
                    <button onClick={saveTemplate} className="btn-secondary text-xs py-1.5 px-3 border-brand-500/30 text-brand-400 hover:bg-brand-500/10">
                        <Save size={14} /> Save Template
                    </button>
                    <button onClick={launchFleet} className="btn-primary text-xs py-1.5 px-4 shadow-lg shadow-brand-500/20">
                        <Rocket size={14} /> Launch Fleet
                    </button>
                </div>
            </div>

            {/* Main Grid */}
            <div className="flex-grow grid grid-cols-1 lg:grid-cols-2 gap-0">
                {/* Left: Config */}
                <div className="bg-dark-900/50 p-6 flex flex-col gap-6 border-r border-white/5">

                    {/* Details */}
                    <div>
                        <h3 className="label-text mb-2">Fleet Details</h3>
                        <div className="space-y-4">
                            <div>
                                <label className="text-xs text-slate-500 block mb-1">Fleet Name</label>
                                <input type="text" value={fleetName} onChange={(e) => setFleetName(e.target.value)} className="input-field" placeholder="e.g. Saturday Roam" />
                            </div>
                            <div>
                                <label className="text-xs text-slate-500 block mb-1">Fleet Commander</label>
                                <select value={selectedFc} onChange={handleFcChange} className="select-field">
                                    {fcChars.map(c => (
                                        <option key={c.character_id} value={c.character_id}>{c.character_name}</option>
                                    ))}
                                </select>
                            </div>
                            <label className="flex items-center gap-3 p-3 rounded bg-white/5 border border-white/5 cursor-pointer group hover:bg-white/10 hover:border-white/20 transition">
                                <input type="checkbox" checked={offlineMode} onChange={(e) => setOfflineMode(e.target.checked)} className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-0 focus:ring-offset-0 transition cursor-pointer" />
                                <div>
                                    <span className="text-xs font-bold text-slate-300 group-hover:text-white block">Offline Mode</span>
                                    <span className="text-[10px] text-slate-500 block">Skip in-game fleet linking (Testing/Emergency)</span>
                                </div>
                            </label>
                        </div>
                    </div>

                    <hr className="border-white/5" />

                    {/* MOTD */}
                    <div>
                        <h3 className="label-text mb-2">Message of the Day</h3>
                        <div className="space-y-2">
                            <div className="flex gap-1 bg-black/20 p-2 rounded border border-white/5 items-center flex-wrap">
                                <button onClick={() => insertTag('b')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs font-bold text-slate-300 hover:text-white">B</button>
                                <button onClick={() => insertTag('i')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs italic text-slate-300 hover:text-white">I</button>
                                <button onClick={() => insertTag('u')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs underline text-slate-300 hover:text-white">U</button>
                                <button onClick={() => insertTag('br')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs text-slate-300 hover:text-white">&crarr;</button>
                                <div className="w-px h-6 bg-white/10 mx-1"></div>
                                <button onClick={() => insertColor('green')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs text-green-400 hover:text-green-300">A</button>
                                <button onClick={() => insertColor('red')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs text-red-400 hover:text-red-300">A</button>
                                <button onClick={() => insertColor('yellow')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs text-yellow-400 hover:text-yellow-300">A</button>
                                <button onClick={() => insertColor('blue')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs text-blue-400 hover:text-blue-300">A</button>
                                <button onClick={() => insertColor('#b2b2b2')} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs text-slate-400 hover:text-white">A</button>
                                <div className="w-px h-6 bg-white/10 mx-1"></div>
                                <button onClick={openPicker} className="p-1 px-2 bg-slate-800 rounded border border-white/10 text-xs hover:bg-slate-700 flex items-center justify-center gap-2 min-w-[40px]">
                                    <Palette size={14} />
                                </button>
                            </div>
                            <textarea
                                id="motd-input"
                                value={motd}
                                onChange={(e) => setMotd(e.target.value)}
                                maxLength={4000}
                                className="input-field h-32 text-xs font-mono resize-none"
                                placeholder="Enter MOTD here... Supports HTML-like tags"
                            />
                            <div className="text-[10px] text-slate-500 text-right">{motd.length}/4000</div>
                            <div className="mt-2 pt-2 border-t border-white/5">
                                <label className="label-text mb-1 text-[13px]">Preview</label>
                                <div dangerouslySetInnerHTML={{ __html: previewHtml }} className="bg-black/40 border border-white/10 rounded p-2 text-slate-300 font-sans whitespace-pre-wrap h-32 overflow-y-auto text-[13px] leading-tight" />
                            </div>
                        </div>
                    </div>

                    <hr className="border-white/5" />

                    {/* Templates */}
                    <div>
                        <div className="flex justify-between items-end mb-2">
                            <h3 className="label-text mb-0">Saved Templates</h3>
                        </div>
                        <div className="space-y-2">
                            <button onClick={() => { if(confirm("Load default?")) setStructure([{name:"Wing 1", squads:["Squad 1", "Squad 2"]}]); }} className="w-full text-left p-3 rounded bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/20 transition group">
                                <div className="font-bold text-sm text-slate-200 group-hover:text-white">Default Basic</div>
                                <div className="text-[10px] text-slate-500">1 Wing, 2 Squads</div>
                            </button>
                            {templates.map(t => (
                                <div key={t.id} className="relative group">
                                    <button onClick={() => loadTemplate(t)} className="w-full text-left p-3 rounded bg-white/5 hover:bg-white/10 border border-white/5 hover:border-brand-500/50 transition pr-8">
                                        <div className="font-bold text-sm text-slate-200 group-hover:text-brand-400">{t.name}</div>
                                        <div className="text-[10px] text-slate-500">{t.wing_count} Wings</div>
                                    </button>
                                    <button onClick={() => deleteTemplate(t.id)} className="absolute top-2 right-2 p-1.5 text-slate-500 hover:text-red-400 hover:bg-white/5 rounded transition opacity-0 group-hover:opacity-100 z-10">
                                        <Trash size={14} />
                                    </button>
                                </div>
                            ))}
                            {templates.length === 0 && <div className="text-xs text-slate-500 italic p-2">No custom templates saved.</div>}
                        </div>
                    </div>
                </div>

                {/* Right: Structure */}
                <div className="lg:col-span-1 flex flex-col overflow-hidden bg-slate-900/50">
                    <div className="p-4 border-b border-white/5 bg-slate-900 flex justify-between items-center">
                        <h3 className="label-text mb-0 text-brand-500">Structure Preview</h3>
                        <button onClick={addWing} className="btn-secondary py-1 px-3 text-xs bg-slate-800 border-slate-700 hover:border-white/30">
                            + Add Wing
                        </button>
                    </div>

                    <div className="flex-grow overflow-y-auto custom-scrollbar p-6 space-y-6 bg-black/20">
                        {structure.length === 0 && <div className="text-center text-slate-500 py-12 italic">No structure defined. Load a template or add a wing.</div>}
                        {structure.map((wing, wIdx) => (
                            <div key={wIdx} className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden group/wing">
                                <div className="p-2 bg-slate-700/50 flex justify-between items-center border-b border-slate-700">
                                    <div className="flex items-center gap-2 w-full">
                                        <span className="text-slate-400 text-[10px] font-bold uppercase w-8">Wing</span>
                                        <input
                                            type="text"
                                            value={wing.name}
                                            onChange={(e) => updateWing(wIdx, e.target.value)}
                                            className="bg-transparent border-b border-transparent hover:border-slate-500 focus:border-brand-500 text-white font-bold text-sm outline-none w-full transition px-1"
                                        />
                                    </div>
                                    <div className="flex gap-1 opacity-0 group-hover/wing:opacity-100 transition shrink-0 ml-2">
                                        <button onClick={() => addSquad(wIdx)} className="text-[10px] bg-slate-600 hover:bg-slate-500 px-1.5 py-0.5 rounded text-white border border-slate-500/50">+Sq</button>
                                        <button onClick={() => removeWing(wIdx)} className="text-[10px] bg-red-900/30 text-red-400 hover:bg-red-900/50 px-1.5 py-0.5 rounded border border-red-900/50">Del</button>
                                    </div>
                                </div>
                                <div className="p-2 bg-dark-900/30">
                                    {wing.squads.map((squad, sIdx) => (
                                        <div key={sIdx} className="flex items-center gap-2 mb-2 pl-4 relative">
                                            <div className="absolute left-2 top-0 bottom-1/2 border-l-2 border-slate-600 w-2 h-full rounded-bl"></div>
                                            <div className="w-2 border-b-2 border-slate-600 h-0 mr-1"></div>
                                            <input
                                                type="text"
                                                value={squad}
                                                onChange={(e) => updateSquad(wIdx, sIdx, e.target.value)}
                                                className="bg-dark-900 border border-slate-700 rounded px-2 py-1 text-xs text-white w-full focus:border-brand-500 outline-none"
                                            />
                                            <button onClick={() => removeSquad(wIdx, sIdx)} className="text-slate-600 hover:text-red-400 px-1">
                                                <X size={12} />
                                            </button>
                                        </div>
                                    ))}
                                    {wing.squads.length === 0 && <div className="text-[10px] text-slate-600 italic pl-8">No squads</div>}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ManagementFleetSetup;