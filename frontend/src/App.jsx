import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Topbar from './components/Topbar.jsx'
import Toast from './components/Toast.jsx'
import ChatPanel from './panels/ChatPanel.jsx'
import JobsPanel from './panels/JobsPanel.jsx'
import PostsPanel from './panels/PostsPanel.jsx'
import ResumePanel from './panels/ResumePanel.jsx'
import SettingsPanel from './panels/SettingsPanel.jsx'
import { checkHealth, getStats, runAgent } from './api.js'

const PANELS = {
    chat: { title: 'Chat', sub: 'Ask Echo anything about your job search' },
    jobs: { title: 'Job Matches', sub: 'AI-ranked opportunities matched to your profile' },
    posts: { title: 'LinkedIn Posts', sub: 'AI-generated content to attract recruiters' },
    resume: { title: 'Resume & Profile', sub: 'Your skills and analysis' },
    settings: { title: 'Settings', sub: 'Configure Echo to your preferences' },
}

export default function App() {
    const [panel, setPanel] = useState('chat')
    const [health, setHealth] = useState({ ollama: false, model: '' })
    const [stats, setStats] = useState({})
    const [toasts, setToasts] = useState([])
    const [loading, setLoading] = useState(false)
    const [loadingText, setLoadingText] = useState('Processing...')

    const toast = useCallback((msg, type = 'info') => {
        const id = Date.now()
        setToasts(t => [...t, { id, msg, type }])
        setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3500)
    }, [])

    const refreshStats = useCallback(async () => {
        try { setStats(await getStats()) } catch { }
    }, [])

    const handleRunAgent = useCallback(async () => {
        setLoading(true); setLoadingText('Running agent...')
        try {
            await runAgent()
            await refreshStats()
            toast('Agent cycle complete!', 'success')
        } catch { toast('Agent failed', 'error') }
        finally { setLoading(false) }
    }, [refreshStats, toast])

    useEffect(() => {
        async function init() {
            try { setHealth(await checkHealth()) } catch { }
            await refreshStats()
        }
        init()
        const iv = setInterval(refreshStats, 30000)
        return () => clearInterval(iv)
    }, [refreshStats])

    const { title, sub } = PANELS[panel]

    return (
        <div className="app">
            <Sidebar
                panel={panel}
                setPanel={setPanel}
                health={health}
                stats={stats}
                onRunAgent={handleRunAgent}
            />
            <div className="main">
                <Topbar
                    title={title}
                    sub={sub}
                    panel={panel}
                    onRunAgent={handleRunAgent}
                />
                <div className="content">
                    <div className={`panel ${panel === 'chat' ? 'active' : ''}`}>
                        <ChatPanel toast={toast} />
                    </div>
                    <div className={`panel ${panel === 'jobs' ? 'active' : ''}`}>
                        <JobsPanel toast={toast} active={panel === 'jobs'} />
                    </div>
                    <div className={`panel ${panel === 'posts' ? 'active' : ''}`}>
                        <PostsPanel toast={toast} active={panel === 'posts'} />
                    </div>
                    <div className={`panel ${panel === 'resume' ? 'active' : ''}`}>
                        <ResumePanel toast={toast} active={panel === 'resume'} />
                    </div>
                    <div className={`panel ${panel === 'settings' ? 'active' : ''}`}>
                        <SettingsPanel toast={toast} active={panel === 'settings'} />
                    </div>
                </div>
            </div>

            {loading && (
                <div className="loading-overlay">
                    <div className="loading-spinner" />
                    <div className="loading-text">{loadingText}</div>
                </div>
            )}

            <Toast toasts={toasts} />
        </div>
    )
}
