import { useState, useEffect, useCallback } from 'react'
import { getSettings, saveSettings } from '../api.js'

export default function SettingsPanel({ toast, active }) {
    const [form, setForm] = useState({
        ai_model: '',
        target_roles: '',
        preferred_locations: '',
        max_experience: 2,
        match_threshold: 0.55,
        auto_scrape: true,
        scrape_interval: 6,
    })
    const [saving, setSaving] = useState(false)

    const load = useCallback(async () => {
        try {
            const s = await getSettings()
            setForm(f => ({ ...f, ...s }))
        } catch { }
    }, [])

    useEffect(() => { if (active) load() }, [active, load])

    const set = (key, val) => setForm(f => ({ ...f, [key]: val }))

    const save = async () => {
        setSaving(true)
        try {
            await saveSettings(form)
            toast('Settings saved!', 'success')
        } catch { toast('Failed to save', 'error') }
        finally { setSaving(false) }
    }

    return (
        <div className="panel-body">
            <div className="settings-grid">
                {/* Cloud AI (Groq) */}
                <div className="settings-section">
                    <div className="settings-section-title">☁️ Cloud AI (Groq)</div>
                    <div className="setting-row">
                        <div>
                            <div className="setting-label">AI Model</div>
                            <div className="setting-sublabel">Powered by Groq Cloud</div>
                        </div>
                        <input className="setting-input" value={form.ai_model} onChange={e => set('ai_model', e.target.value)} placeholder="llama-3.3-70b-versatile" />
                    </div>
                </div>

                {/* Job Preferences */}
                <div className="settings-section">
                    <div className="settings-section-title">🎯 Job Preferences</div>
                    <div className="setting-row">
                        <div>
                            <div className="setting-label">Target Roles</div>
                            <div className="setting-sublabel">Comma-separated</div>
                        </div>
                        <input className="setting-input" value={form.target_roles} onChange={e => set('target_roles', e.target.value)} placeholder="AI Engineer, Data Analyst" />
                    </div>
                    <div className="setting-row">
                        <div>
                            <div className="setting-label">Locations</div>
                        </div>
                        <input className="setting-input" value={form.preferred_locations} onChange={e => set('preferred_locations', e.target.value)} placeholder="Bangalore, Remote" />
                    </div>
                    <div className="setting-row">
                        <div>
                            <div className="setting-label">Max Experience (yrs)</div>
                        </div>
                        <input className="setting-input" type="number" min={0} max={10} value={form.max_experience} onChange={e => set('max_experience', +e.target.value)} style={{ minWidth: 80 }} />
                    </div>
                    <div className="setting-row">
                        <div>
                            <div className="setting-label">Match Threshold</div>
                            <div className="setting-sublabel">0.5 = lenient, 0.75 = strict</div>
                        </div>
                        <input className="setting-input" type="number" min={0.3} max={0.9} step={0.05} value={form.match_threshold} onChange={e => set('match_threshold', +e.target.value)} style={{ minWidth: 80 }} />
                    </div>
                </div>

                {/* Agent Schedule */}
                <div className="settings-section">
                    <div className="settings-section-title">🔁 Agent Schedule</div>
                    <div className="setting-row">
                        <div>
                            <div className="setting-label">Auto-scrape enabled</div>
                            <div className="setting-sublabel">Runs every N hours</div>
                        </div>
                        <label className="toggle">
                            <input type="checkbox" checked={form.auto_scrape} onChange={e => set('auto_scrape', e.target.checked)} />
                            <span className="toggle-slider" />
                        </label>
                    </div>
                    <div className="setting-row">
                        <div><div className="setting-label">Scrape interval (hours)</div></div>
                        <input className="setting-input" type="number" min={1} max={24} value={form.scrape_interval} onChange={e => set('scrape_interval', +e.target.value)} style={{ minWidth: 80 }} />
                    </div>
                </div>
            </div>

            <div style={{ marginTop: 24 }}>
                <button className="btn-primary" onClick={save} disabled={saving}>
                    {saving ? 'Saving...' : '💾 Save Settings'}
                </button>
            </div>
        </div>
    )
}
