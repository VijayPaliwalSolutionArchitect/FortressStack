export const API = '/api/v1'

async function request(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`${res.status}: ${body.slice(0, 200)}`)
  }
  return res.json()
}

export const get = (path) => request(path)
export const post = (path, body) =>
  request(path, { method: 'POST', body: JSON.stringify(body) })
export const put = (path, body) =>
  request(path, { method: 'PUT', body: JSON.stringify(body) })
export const patch = (path, body) =>
  request(path, { method: 'PATCH', body: JSON.stringify(body) })

export async function uploadDocument(corpusId, file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${API}/rag/corpora/${corpusId}/documents`, {
    method: 'POST',
    body: fd,
  })
  if (!res.ok) throw new Error(`${res.status}: ${(await res.text()).slice(0, 200)}`)
  return res.json()
}