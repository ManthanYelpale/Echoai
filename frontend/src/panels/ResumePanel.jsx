import { useState, useEffect, useCallback, useRef } from 'react'
import { getResume, uploadResume, getSkillGaps } from '../api.js'

export default function ResumePanel({ toast, active }) {
    const [resume, setResume] = useState(null)
    const [gaps, setGaps] = useState([])
    const [uploading, setUploading] = useState(false)
    const [drag, setDrag] = useState(false)
    const fileRef = useRef()

    const load = useCallback(async () => {
        try {
            const [r, g] = await Promise.all([getResume(), getSkillGaps()])
            setResume(r)
            setGaps(g.gaps || [])
        } catch { }
    }, [])

    useEffect(() => { if (active) load() }, [active, load])

    const handleFile = async (file) => {
        if (!file) return
        setUploading(true)
        try {
            await uploadResume(file)
            toast('Resume uploaded!', 'success')
            await load()
        } catch { toast('Upload failed', 'error') }
        finally { setUploading(false) }
    }

    const onDrop = (e) => {
        e.preventDefault(); setDrag(false)
        handleFile(e.dataTransfer.files[0])
    }

    return (
        <div className="panel-body">
            {/* Upload zone */}
            <div
                className={`upload-zone ${drag ? 'drag' : ''}`}
                style={{ marginBottom: 20 }}
                onClick={() => fileRef.current?.click()}
                onDragOver={e => { e.preventDefault(); setDrag(true) }}
                onDragLeave={() => setDrag(false)}
                onDrop={onDrop}
            >
                <div className="upload-zone-icon">{uploading ? '⏳' : '📄'}</div>
                <p>{uploading ? 'Uploading...' : <><strong>Click to upload</strong> or drag & drop your resume (PDF, DOCX)</>}</p>
                <input ref={fileRef} type="file" accept=".pdf,.docx,.doc" style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />
            </div>

            {resume ? (
                <div className="resume-grid">
                    {/* Profile */}
                    <div className="resume-card">
                        <div className="resume-card-title">👤 Profile</div>
                        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{resume.name || '—'}</div>
                        <div style={{ fontSize: 13, color: 'var(--warm-gray)', marginBottom: 8 }}>{resume.email}</div>
                        <div style={{ fontSize: 13, color: 'var(--warm-gray)' }}>{resume.experience_level} · {resume.experience_years} yrs exp</div>
                        {resume.summary && <div style={{ fontSize: 13, marginTop: 12, lineHeight: 1.6, color: 'var(--charcoal)' }}>{resume.summary}</div>}
                    </div>

                    {/* Skills */}
                    <div className="resume-card">
                        <div className="resume-card-title">🛠 Skills ({(resume.skills || []).length})</div>
                        <div className="skill-tags">
                            {(resume.skills || []).map(s => <span className="skill-tag" key={s}>{s}</span>)}
                        </div>
                    </div>

                    {/* Tech Stack */}
                    <div className="resume-card">
                        <div className="resume-card-title">💻 Tech Stack</div>
                        <div className="skill-tags">
                            {(resume.tech_stack || []).map(s => <span className="skill-tag" key={s}>{s}</span>)}
                        </div>
                    </div>

                    {/* Education */}
                    {resume.education && (
                        <div className="resume-card">
                            <div className="resume-card-title">🎓 Education</div>
                            <div style={{ fontSize: 14, fontWeight: 600 }}>{resume.education.degree} — {resume.education.branch}</div>
                            <div style={{ fontSize: 13, color: 'var(--warm-gray)', marginTop: 4 }}>{resume.education.college}</div>
                            <div style={{ fontSize: 13, color: 'var(--warm-gray)' }}>Class of {resume.education.graduation_year} · CGPA {resume.education.cgpa}</div>
                        </div>
                    )}

                    {/* Skill Gaps */}
                    {gaps.length > 0 && (
                        <div className="resume-card" style={{ gridColumn: '1 / -1' }}>
                            <div className="resume-card-title">📈 Skill Gaps to Close</div>
                            {gaps.slice(0, 8).map((g, i) => (
                                <div className="gap-item" key={i}>
                                    <span className={`gap-priority ${g.priority}`}>{g.priority}</span>
                                    <div>
                                        <div className="gap-skill">{g.skill}</div>
                                        <div className="gap-reason">{g.reason}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            ) : (
                <div className="empty-state">
                    <div className="empty-state-icon">📄</div>
                    <h3>No resume uploaded yet</h3>
                    <p>Upload your resume above to see your profile and skill analysis.</p>
                </div>
            )}
        </div>
    )
}
