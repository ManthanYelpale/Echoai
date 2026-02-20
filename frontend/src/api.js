// api.js — all FastAPI calls in one place
const BASE = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? '' : 'http://localhost:8000')

export async function checkHealth() {
    const r = await fetch(`${BASE}/health`)
    return r.json()
}

export async function getOllamaModels() {
    const r = await fetch(`${BASE}/api/ollama/models`)
    return r.json()
}

export async function getStats() {
    const r = await fetch(`${BASE}/api/stats`)
    return r.json()
}

export async function getJobs(limit = 30, minScore = 0.4) {
    const r = await fetch(`${BASE}/api/jobs?limit=${limit}&min_score=${minScore}`)
    return r.json()
}

export async function getResume() {
    const r = await fetch(`${BASE}/api/resume`)
    if (r.status === 404) return null
    return r.json()
}

export async function uploadResume(file) {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/api/resume/upload`, { method: 'POST', body: fd })
    return r.json()
}

export async function getSkillGaps() {
    const r = await fetch(`${BASE}/api/skills/gaps`)
    return r.json()
}

export async function runAgent() {
    const r = await fetch(`${BASE}/api/agent/run`, { method: 'POST' })
    return r.json()
}

export async function generatePost(type, customPrompt = '') {
    const r = await fetch(`${BASE}/api/posts/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ post_type: type, custom_prompt: customPrompt })
    })
    return r.json()
}

export async function getSettings() {
    const r = await fetch(`${BASE}/api/settings`)
    return r.json()
}

export async function saveSettings(data) {
    const r = await fetch(`${BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    return r.json()
}

export function streamChat(message, sessionId, onChunk, onToolResult, onDone, onError) {
    const controller = new AbortController()

    fetch(`${BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
        signal: controller.signal,
    }).then(async resp => {
        if (!resp.ok) {
            onError(`Error ${resp.status}: ${resp.statusText}`)
            return
        }
        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop()
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue
                const raw = line.slice(6).trim()
                if (!raw || raw === '[DONE]') continue
                try {
                    const data = JSON.parse(raw)
                    if (data.type === 'text') onChunk(data.chunk)
                    else if (data.type === 'tool') onToolResult(data.result)
                    else if (data.type === 'done') { onDone(); return }
                    else if (data.type === 'error') { onError(data.message); return }
                } catch { }
            }
        }
        onDone()
    }).catch(err => {
        if (err.name !== 'AbortError') onError(err.message)
    })

    return () => controller.abort()
}
