import { useState } from 'react'
import { generatePost } from '../api.js'

const POST_TYPES = [
    { id: 'open_to_work', label: '🟢 Open to Work' },
    { id: 'achievement', label: '🏆 Achievement' },
    { id: 'skill_showcase', label: '💡 Skill Showcase' },
    { id: 'job_search_update', label: '🔍 Job Search Update' },
]

export default function PostsPanel({ toast }) {
    const [type, setType] = useState('open_to_work')
    const [customPrompt, setCustomPrompt] = useState('')
    const [post, setPost] = useState(null)
    const [generating, setGenerating] = useState(false)

    const generate = async () => {
        setGenerating(true)
        try {
            const result = await generatePost(type, customPrompt)
            setPost(result)
        } catch { toast('Failed to generate post', 'error') }
        finally { setGenerating(false) }
    }

    const copy = () => {
        const text = [post.content, post.hashtags].filter(Boolean).join('\n\n')
        navigator.clipboard.writeText(text)
        toast('Copied to clipboard!', 'success')
    }

    return (
        <div className="panel-body">
            <div className="post-type-tabs">
                {POST_TYPES.map(pt => (
                    <button
                        key={pt.id}
                        className={`post-type-btn ${type === pt.id ? 'active' : ''}`}
                        onClick={() => setType(pt.id)}
                    >
                        {pt.label}
                    </button>
                ))}
            </div>

            <div style={{ marginBottom: 16 }}>
                <input
                    className="setting-input"
                    style={{ width: '100%' }}
                    placeholder="Optional: add context (e.g. 'looking for ML roles in Bangalore')"
                    value={customPrompt}
                    onChange={e => setCustomPrompt(e.target.value)}
                />
            </div>

            <button className="btn-primary" onClick={generate} disabled={generating} style={{ marginBottom: 20 }}>
                {generating ? '✨ Generating...' : '✨ Generate Post'}
            </button>

            {post && (
                <div className="post-output">
                    <div className="post-output-header">
                        <span style={{ fontWeight: 600, fontSize: 14 }}>LinkedIn Post</span>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <button className="btn-ghost" onClick={copy} style={{ padding: '5px 12px', fontSize: 12 }}>📋 Copy</button>
                        </div>
                    </div>
                    <div className="post-output-body">{post.content}</div>
                    {post.hashtags && <div className="post-hashtags">{post.hashtags}</div>}
                </div>
            )}

            {!post && !generating && (
                <div className="empty-state">
                    <div className="empty-state-icon">📢</div>
                    <h3>Generate a LinkedIn post</h3>
                    <p>Choose a post type and click Generate. Echo will write a post tailored to your resume and target roles.</p>
                </div>
            )}
        </div>
    )
}
