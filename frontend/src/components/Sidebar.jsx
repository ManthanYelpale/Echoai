export default function Sidebar({ panel, setPanel, health, stats, onRunAgent }) {
    const navItems = [
        { id: 'chat', icon: '💬', label: 'Chat with Echo' },
        { id: 'jobs', icon: '🎯', label: 'Job Matches', badge: stats.total_matched },
        { id: 'posts', icon: '📢', label: 'LinkedIn Posts' },
        { id: 'resume', icon: '📄', label: 'My Resume' },
    ]

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div className="logo">
                    <div className="logo-icon">✦</div>
                    <span className="logo-text">Echo</span>
                </div>
                <div className="logo-tagline">Your Career Intelligence Agent</div>
            </div>

            <nav className="sidebar-nav">
                <div className="nav-section-label">Navigate</div>
                {navItems.map(item => (
                    <button
                        key={item.id}
                        className={`nav-btn ${panel === item.id ? 'active' : ''}`}
                        onClick={() => setPanel(item.id)}
                    >
                        <span className="nav-icon">{item.icon}</span>
                        {item.label}
                        {item.badge > 0 && <span className="nav-badge">{item.badge}</span>}
                    </button>
                ))}

                <div className="nav-section-label">Agent</div>
                <button className="nav-btn" onClick={onRunAgent}>
                    <span className="nav-icon">⚡</span> Run Agent Now
                </button>
                <button className={`nav-btn ${panel === 'settings' ? 'active' : ''}`} onClick={() => setPanel('settings')}>
                    <span className="nav-icon">⚙️</span> Settings
                </button>
            </nav>

            <div className="stats-card">
                <div className="stats-card-title">Live Stats</div>
                {[
                    ['Jobs tracked', stats.total_jobs ?? '—'],
                    ['Matched', stats.total_matched ?? '—'],
                    ['Avg score', stats.avg_score ? (stats.avg_score * 100).toFixed(0) + '%' : '—'],
                    ['Last scrape', stats.last_scrape
                        ? new Date(stats.last_scrape).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
                        : 'Never'],
                ].map(([label, value]) => (
                    <div className="stat-row" key={label}>
                        <span className="stat-label">{label}</span>
                        <span className="stat-value">{value}</span>
                    </div>
                ))}
            </div>
        </aside>
    )
}
