import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { streamChat } from '../api.js'

let sessionId = 'session_' + Math.random().toString(36).slice(2)

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function ToolCard({ data }) {
    // Handle backend types
    const type = data.type || data.tool

    if (type === 'jobs' && Array.isArray(data.data)) {
        return (
            <div className="tool-card">
                <div className="tool-card-header">🎯 Top Job Matches</div>
                <div className="job-card-list">
                    {data.data.map((job, i) => (
                        <div className="job-card-item" key={i}>
                            <div className="job-card-title">{job.title}</div>
                            <div className="job-card-meta">{job.company} · {job.location}</div>
                            {job.final_score && (
                                <div className="job-score-badge">{(job.final_score * 100).toFixed(0)}% match</div>
                            )}
                            {job.apply_url && (
                                <a className="job-apply-link" href={job.apply_url} target="_blank" rel="noreferrer">Apply →</a>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        )
    }
    if (type === 'stats' && data.data) {
        const d = data.data
        return (
            <div className="tool-card">
                <div className="tool-card-header">📊 Agent Statistics</div>
                <div style={{ padding: '14px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    {[['JOBS TRACKED', d.total_jobs], ['MATCHED', d.total_matched], ['AVG SCORE', ((d.avg_score || 0) * 100).toFixed(0) + '%'], ['POSTS', d.total_posts]].map(([label, val]) => (
                        <div key={label}>
                            <div style={{ fontSize: 11, color: 'var(--warm-gray)' }}>{label}</div>
                            <div style={{ fontSize: 20, fontWeight: 700 }}>{val}</div>
                        </div>
                    ))}
                </div>
            </div>
        )
    }
    return (
        <div className="tool-card">
            <div className="tool-card-header">🔧 {type}</div>
            <div style={{ padding: 14, fontSize: 13, color: 'var(--warm-gray)' }}>
                {JSON.stringify(data.data, null, 2)}
            </div>
        </div>
    )
}

export default function ChatPanel({ toast }) {
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [sending, setSending] = useState(false)
    const [showWelcome, setShowWelcome] = useState(true)
    const messagesEndRef = useRef(null)
    const textareaRef = useRef(null)

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }, [])

    useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

    // Listen for clear chat from Topbar
    useEffect(() => {
        const handler = () => {
            setMessages([])
            setShowWelcome(true)
            sessionId = 'session_' + Math.random().toString(36).slice(2)
            toast('Chat cleared', 'success')
        }
        window.addEventListener('clearChat', handler)
        return () => window.removeEventListener('clearChat', handler)
    }, [toast])

    const sendMessage = useCallback(() => {
        const msg = input.trim()
        if (!msg || sending) return
        setShowWelcome(false)
        setInput('')
        if (textareaRef.current) { textareaRef.current.style.height = 'auto' }
        setSending(true)

        const userMsg = { role: 'user', content: msg, id: Date.now() }
        const echoId = Date.now() + 1
        setMessages(prev => [...prev, userMsg, { role: 'echo', content: '', id: echoId, streaming: true }])

        streamChat(
            msg, sessionId,
            (chunk) => {
                setMessages(prev => prev.map(m =>
                    m.id === echoId ? { ...m, content: m.content + chunk } : m
                ))
            },
            (toolResult) => {
                setMessages(prev => [...prev, { role: 'tool', data: toolResult, id: Date.now() }])
            },
            () => {
                setMessages(prev => prev.map(m => m.id === echoId ? { ...m, streaming: false } : m))
                setSending(false)
            },
            (err) => {
                setMessages(prev => prev.map(m =>
                    m.id === echoId
                        ? { ...m, content: '⚠️ No response from Ollama. Make sure a model is installed: run  ollama pull llama3.2  in a terminal, then try again.', streaming: false }
                        : m
                ))
                setSending(false)
            }
        )
    }, [input, sending])

    const sendQuick = (msg) => {
        setInput(msg)
        setTimeout(() => {
            setInput(msg)
            // trigger send via state update trick
            const event = new CustomEvent('quickSend', { detail: msg })
            window.dispatchEvent(event)
        }, 0)
    }

    useEffect(() => {
        const handler = (e) => {
            const msg = e.detail
            if (!msg || sending) return
            setShowWelcome(false)
            setInput('')
            setSending(true)
            const userMsg = { role: 'user', content: msg, id: Date.now() }
            const echoId = Date.now() + 1
            setMessages(prev => [...prev, userMsg, { role: 'echo', content: '', id: echoId, streaming: true }])
            streamChat(msg, sessionId,
                (chunk) => setMessages(prev => prev.map(m => m.id === echoId ? { ...m, content: m.content + chunk } : m)),
                (toolResult) => setMessages(prev => [...prev, { role: 'tool', data: toolResult, id: Date.now() }]),
                () => { setMessages(prev => prev.map(m => m.id === echoId ? { ...m, streaming: false } : m)); setSending(false) },
                () => setSending(false)
            )
        }
        window.addEventListener('quickSend', handler)
        return () => window.removeEventListener('quickSend', handler)
    }, [sending])

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
    }

    const handleInput = (e) => {
        setInput(e.target.value)
        e.target.style.height = 'auto'
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
    }

    return (
        <>
            <div className="chat-messages">
                {showWelcome && (
                    <div className="welcome">
                        <div className="welcome-icon">✦</div>
                        <h2>Hello! I'm Echo ✨</h2>
                        <p>Your personal AI career agent, tuned for India's tech job market. I can find you jobs, analyse skill gaps, and write LinkedIn posts that get recruiter attention.</p>
                        <div className="quick-actions">
                            {[
                                ['🎯', 'Top job matches', 'See best-fit opportunities', 'Show me my top job matches'],
                                ['📈', 'Skill gap analysis', 'What to learn next', 'What skills am I missing?'],
                                ['📢', 'LinkedIn post', 'Attract recruiters', 'Generate a LinkedIn open to work post'],
                                ['⚡', 'Find fresh jobs', 'Scrape all sources', 'Start scraping jobs now'],
                            ].map(([icon, title, desc, msg]) => (
                                <div className="quick-action" key={title} onClick={() => sendQuick(msg)}>
                                    <div className="quick-action-icon">{icon}</div>
                                    <div className="quick-action-title">{title}</div>
                                    <div className="quick-action-desc">{desc}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map(m => {
                    if (m.role === 'tool') return <ToolCard key={m.id} data={m.data} />
                    return (
                        <div key={m.id} className={`msg ${m.role}`}>
                            <div className="msg-avatar">{m.role === 'echo' ? '✦' : '👤'}</div>
                            <div className="msg-bubble">
                                {m.streaming && !m.content ? (
                                    <div className="typing">
                                        <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                                    </div>
                                ) : (
                                    <div className="markdown-content">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {m.content}
                                        </ReactMarkdown>
                                    </div>
                                )}
                            </div>
                        </div>
                    )
                })}
                <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-area">
                <div className="chat-input-box">
                    <textarea
                        ref={textareaRef}
                        rows={1}
                        value={input}
                        onChange={handleInput}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask Echo anything... 'show top jobs', 'what skills am I missing?', 'generate LinkedIn post'"
                    />
                    <button className="send-btn" onClick={sendMessage} disabled={sending}>➤</button>
                </div>
                <div className="input-hint">Echo uses your local Ollama model — completely private, no data leaves your machine.</div>
            </div>
        </>
    )
}
