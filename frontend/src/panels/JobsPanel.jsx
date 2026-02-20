import { useState, useEffect, useCallback } from 'react'
import { getJobs } from '../api.js'

export default function JobsPanel({ toast, active }) {
    const [jobs, setJobs] = useState([])
    const [loading, setLoading] = useState(false)
    const [filter, setFilter] = useState({ mode: '', company: '' })

    const load = useCallback(async () => {
        setLoading(true)
        try {
            const res = await getJobs()
            setJobs(res.jobs || [])
        }
        catch { toast('Failed to load jobs', 'error') }
        finally { setLoading(false) }
    }, [toast])

    useEffect(() => { if (active) load() }, [active, load])

    const companies = [...new Set(jobs.map(j => j.company).filter(Boolean))]
    const modes = [...new Set(jobs.map(j => j.work_mode).filter(Boolean))]

    const filtered = jobs.filter(j =>
        (!filter.mode || j.work_mode === filter.mode) &&
        (!filter.company || j.company === filter.company)
    )

    const scoreColor = (s) => {
        if (s >= 0.75) return 'var(--mint)'
        if (s >= 0.55) return 'var(--peach-deep)'
        return 'var(--warm-gray)'
    }

    return (
        <div className="panel-body">
            <div className="filter-bar">
                <select className="filter-select" value={filter.mode} onChange={e => setFilter(f => ({ ...f, mode: e.target.value }))}>
                    <option value="">All modes</option>
                    {modes.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
                <select className="filter-select" value={filter.company} onChange={e => setFilter(f => ({ ...f, company: e.target.value }))}>
                    <option value="">All companies</option>
                    {companies.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <button className="btn-ghost" onClick={load}>↻ Refresh</button>
            </div>

            {loading ? (
                <div className="empty-state">
                    <div className="empty-state-icon">⏳</div>
                    <h3>Loading jobs...</h3>
                </div>
            ) : filtered.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-state-icon">🎯</div>
                    <h3>No jobs yet</h3>
                    <p>Click ⚡ Run Agent to scrape and match jobs to your resume.</p>
                </div>
            ) : (
                <div className="jobs-grid">
                    {filtered.map((job, i) => (
                        <div className="job-card" key={job.id || i}>
                            <div className="job-card-top">
                                <div>
                                    <div className="job-title">{job.title}</div>
                                    <div className="job-company">{job.company} · {job.location}</div>
                                </div>
                                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                    <div className="job-score" style={{ color: scoreColor(job.final_score) }}>
                                        {job.final_score ? (job.final_score * 100).toFixed(0) + '%' : '—'}
                                    </div>
                                    <div className="job-score-label">match</div>
                                </div>
                            </div>
                            <div className="job-tags">
                                {job.work_mode && <span className="job-tag mode">{job.work_mode}</span>}
                                {job.experience_required && <span className="job-tag">{job.experience_required}</span>}
                                {(job.skills_required || []).slice(0, 4).map(s => (
                                    <span className="job-tag" key={s}>{s}</span>
                                ))}
                            </div>
                            <div className="job-footer">
                                <span className="job-source">{job.source}</span>
                                {job.apply_url && (
                                    <a className="job-apply-btn" href={job.apply_url} target="_blank" rel="noreferrer">Apply →</a>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
