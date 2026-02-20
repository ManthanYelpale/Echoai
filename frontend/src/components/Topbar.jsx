export default function Topbar({ title, sub, panel, onRunAgent }) {
    return (
        <div className="topbar">
            <div>
                <div className="topbar-title">{title}</div>
                <div className="topbar-subtitle">{sub}</div>
            </div>
            <div className="topbar-actions">
                {panel === 'chat' && (
                    <button className="btn-ghost" onClick={() => window.dispatchEvent(new Event('clearChat'))}>
                        Clear chat
                    </button>
                )}
                <button className="btn-primary" onClick={onRunAgent}>⚡ Run Agent</button>
            </div>
        </div>
    )
}
