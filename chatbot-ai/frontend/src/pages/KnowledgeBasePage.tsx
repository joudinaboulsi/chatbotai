import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { agentsApi, knowledgeApi } from '../api/resources'
import { apiErrorMessage } from '../api/client'
import type { Agent, KnowledgeBase, KnowledgeDocument, ScrapedSite } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Input, Textarea } from '../components/ui/Field'
import { Modal } from '../components/ui/Modal'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { ErrorBanner, LoadingSpinner, EmptyState } from '../components/ui/Feedback'
import { useToast } from '../components/ui/Toast'

interface KbStats {
  docs: number
  sites: number
}

export function KnowledgeBasePage() {
  const { notify } = useToast()
  const [agents, setAgents] = useState<Agent[]>([])
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [kbStats, setKbStats] = useState<Record<string, KbStats>>({})
  const [viewTargetId, setViewTargetId] = useState<string | null>(null)
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [scrapedSites, setScrapedSites] = useState<ScrapedSite[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editTarget, setEditTarget] = useState<KnowledgeBase | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeBase | null>(null)
  const [deleting, setDeleting] = useState(false)

  async function refreshKbStats(kbId: string): Promise<{ docs: KnowledgeDocument[]; sites: ScrapedSite[] }> {
    const [docsRes, sitesRes] = await Promise.all([
      knowledgeApi.listDocuments(kbId),
      knowledgeApi.listScrapedSites(kbId),
    ])
    setKbStats((prev) => ({ ...prev, [kbId]: { docs: docsRes.data.length, sites: sitesRes.data.length } }))
    return { docs: docsRes.data, sites: sitesRes.data }
  }

  useEffect(() => {
    agentsApi.list({ page: 1, page_size: 100 }).then((res) => setAgents(res.data.items))
    knowledgeApi
      .list()
      .then(async (res) => {
        setKnowledgeBases(res.data)
        await Promise.all(res.data.map((kb) => refreshKbStats(kb.id).catch(() => undefined)))
      })
      .catch((err) => setError(apiErrorMessage(err)))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadKbDetail(kbId: string) {
    setError(null)
    try {
      const { docs, sites } = await refreshKbStats(kbId)
      setDocuments(docs)
      setScrapedSites(sites)
    } catch (err) {
      setError(apiErrorMessage(err))
    }
  }

  useEffect(() => {
    if (viewTargetId) loadKbDetail(viewTargetId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewTargetId])

  function handleKbCreated(kb: KnowledgeBase) {
    setKnowledgeBases((prev) => [...prev, kb])
    setViewTargetId(kb.id)
    setShowCreateModal(false)
  }

  function handleKbUpdated(kb: KnowledgeBase) {
    setKnowledgeBases((prev) => prev.map((existing) => (existing.id === kb.id ? kb : existing)))
    refreshKbStats(kb.id).catch(() => undefined)
    if (viewTargetId === kb.id) loadKbDetail(kb.id)
    setEditTarget(null)
  }

  async function handleDeleteKb() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await knowledgeApi.remove(deleteTarget.id)
      const remaining = knowledgeBases.filter((kb) => kb.id !== deleteTarget.id)
      setKnowledgeBases(remaining)
      setKbStats((prev) => {
        const next = { ...prev }
        delete next[deleteTarget.id]
        return next
      })
      if (viewTargetId === deleteTarget.id) {
        setViewTargetId(null)
        setDocuments([])
        setScrapedSites([])
      }
      notify('Knowledge base deleted')
      setDeleteTarget(null)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setDeleting(false)
    }
  }

  async function handleUploadPdf(file: File) {
    if (!viewTargetId) return
    try {
      await knowledgeApi.uploadPdf(viewTargetId, file)
      notify('PDF uploaded — processing in background')
      loadKbDetail(viewTargetId)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleReprocess(docId: string) {
    if (!viewTargetId) return
    await knowledgeApi.reprocessDocument(viewTargetId, docId)
    notify('Reprocessing started')
    loadKbDetail(viewTargetId)
  }

  async function handleDeleteDocument(docId: string) {
    if (!viewTargetId) return
    await knowledgeApi.deleteDocument(viewTargetId, docId)
    loadKbDetail(viewTargetId)
  }

  async function handleRescrape(siteId: string) {
    if (!viewTargetId) return
    await knowledgeApi.rescrape(viewTargetId, siteId)
    notify('Re-scrape started')
    loadKbDetail(viewTargetId)
  }

  async function handleDeleteSite(siteId: string) {
    if (!viewTargetId) return
    await knowledgeApi.deleteScrapedSite(viewTargetId, siteId)
    loadKbDetail(viewTargetId)
  }

  async function handleCreateScrape(url: string) {
    if (!viewTargetId) return
    try {
      await knowledgeApi.createScrape(viewTargetId, {
        url,
        mode: 'single_url',
        max_pages: 20,
        max_depth: 2,
        include_subpages: true,
        exclude_urls: [],
      })
      notify('Scraping started')
      loadKbDetail(viewTargetId)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  async function handleEditSite(siteId: string, url: string) {
    if (!viewTargetId) return
    try {
      await knowledgeApi.deleteScrapedSite(viewTargetId, siteId)
      await knowledgeApi.createScrape(viewTargetId, {
        url,
        mode: 'single_url',
        max_pages: 20,
        max_depth: 2,
        include_subpages: true,
        exclude_urls: [],
      })
      notify('Website URL updated — scraping started')
      loadKbDetail(viewTargetId)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    }
  }

  const viewTarget = knowledgeBases.find((kb) => kb.id === viewTargetId) ?? null

  if (loading) return <LoadingSpinner />

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Knowledge Base</h1>
        <Button onClick={() => setShowCreateModal(true)}><Plus className="h-4 w-4" />New Knowledge Base</Button>
      </div>

      {error && <ErrorBanner message={error} />}

      {knowledgeBases.length === 0 ? (
        <EmptyState
          title="No knowledge bases yet"
          description="Create one and upload a PDF or scrape a website to power your agents' answers."
        />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Assigned Agents</th>
                <th className="px-4 py-3">Created On</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {knowledgeBases.map((kb) => {
                const stats = kbStats[kb.id]
                return (
                  <tr
                    key={kb.id}
                    className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50"
                    onClick={() => setViewTargetId(kb.id)}
                  >
                    <td className="px-4 py-3 font-medium text-slate-900">{kb.name}</td>
                    <td className="px-4 py-3">
                      <Badge status={kb.source_type === 'pdf' ? 'completed' : 'active'} />
                      <span className="ml-1 text-xs text-slate-500">{kb.source_type === 'pdf' ? 'PDF' : 'Website'}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {!stats
                        ? '—'
                        : kb.source_type === 'pdf'
                          ? stats.docs > 0 ? '1 document' : 'no document'
                          : stats.sites > 0 ? '1 URL' : 'no URL'}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {kb.agent_ids.length === 0
                        ? '—'
                        : kb.agent_ids.map((id) => agents.find((a) => a.id === id)?.name ?? id).join(', ')}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{new Date(kb.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-end gap-1.5">
                        <button
                          className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200"
                          onClick={() => setViewTargetId(kb.id)}
                        >
                          View
                        </button>
                        <button
                          className="rounded-md bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 transition-colors hover:bg-brand-100"
                          onClick={() => setEditTarget(kb)}
                        >
                          Edit
                        </button>
                        <button
                          className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-100"
                          onClick={() => setDeleteTarget(kb)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {viewTarget && (
        <ViewKbModal
          key={viewTarget.id}
          kb={viewTarget}
          agents={agents}
          documents={documents}
          scrapedSites={scrapedSites}
          onClose={() => setViewTargetId(null)}
          onUploadPdf={handleUploadPdf}
          onCreateScrape={handleCreateScrape}
          onReprocess={handleReprocess}
          onDeleteDocument={handleDeleteDocument}
          onRescrape={handleRescrape}
          onDeleteSite={handleDeleteSite}
          onEditSite={handleEditSite}
        />
      )}

      {showCreateModal && (
        <CreateKbModal agents={agents} onClose={() => setShowCreateModal(false)} onCreated={handleKbCreated} />
      )}
      {editTarget && (
        <EditKbModal
          kb={editTarget}
          agents={agents}
          onClose={() => setEditTarget(null)}
          onUpdated={handleKbUpdated}
        />
      )}
      {deleteTarget && (
        <ConfirmDialog
          title="Delete knowledge base"
          message={`Delete "${deleteTarget.name}"? This removes all its uploaded PDFs, scraped sites, and embedded content. This cannot be undone.`}
          confirmLabel={deleting ? 'Deleting…' : 'Delete'}
          danger
          onConfirm={handleDeleteKb}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(3)} MB`
  return `${(bytes / 1024).toFixed(1)} KB`
}

function ViewKbModal({
  kb,
  agents,
  documents,
  scrapedSites,
  onClose,
  onUploadPdf,
  onCreateScrape,
  onReprocess,
  onDeleteDocument,
  onRescrape,
  onDeleteSite,
  onEditSite,
}: {
  kb: KnowledgeBase
  agents: Agent[]
  documents: KnowledgeDocument[]
  scrapedSites: ScrapedSite[]
  onClose: () => void
  onUploadPdf: (file: File) => void
  onCreateScrape: (url: string) => void
  onReprocess: (docId: string) => void
  onDeleteDocument: (docId: string) => void
  onRescrape: (siteId: string) => void
  onDeleteSite: (siteId: string) => void
  onEditSite: (siteId: string, url: string) => void
}) {
  const [showAddSite, setShowAddSite] = useState(false)
  const [editingSite, setEditingSite] = useState<ScrapedSite | null>(null)

  const isPdf = kb.source_type === 'pdf'
  const doc = isPdf ? (documents[0] ?? null) : null
  const site = !isPdf ? (scrapedSites[0] ?? null) : null
  const trained = isPdf ? doc?.status === 'completed' : site?.status === 'completed'

  return (
    <Modal title={kb.name} onClose={onClose} width="max-w-2xl">
      <div className="space-y-4">
        {kb.description && <p className="text-sm text-slate-500">{kb.description}</p>}
        <p className="text-sm text-slate-500">
          Assigned to:{' '}
          {kb.agent_ids.length === 0
            ? 'no agents'
            : kb.agent_ids.map((id) => agents.find((a) => a.id === id)?.name ?? id).join(', ')}
        </p>
        <p className="text-xs text-slate-400">Created {new Date(kb.created_at).toLocaleString()}</p>

        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">
          Training status:{' '}
          <span className="font-semibold text-slate-900">{trained ? 'Trained' : 'Not trained'}</span>
        </div>

        {isPdf ? (
          doc ? (
            <div className="rounded-lg border border-slate-200 px-4 py-3">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium text-slate-900">{doc.file_name}</span>
                <Badge status={doc.status} />
              </div>
              {doc.error_message && <p className="mt-1 text-xs text-red-600">{doc.error_message}</p>}
              <p className="mt-1 text-xs text-slate-500">
                {formatBytes(doc.file_size_bytes)} · trained on{' '}
                {doc.processed_at ? new Date(doc.processed_at).toLocaleString() : '—'} · uploaded{' '}
                {new Date(doc.created_at).toLocaleString()}
              </p>
              <div className="mt-3 flex gap-1.5">
                <button
                  className="rounded-md bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 transition-colors hover:bg-brand-100"
                  onClick={() => onReprocess(doc.id)}
                >
                  Re-process
                </button>
                <button
                  className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-100"
                  onClick={() => onDeleteDocument(doc.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center">
              <p className="mb-3 text-sm text-slate-500">No document uploaded yet.</p>
              <label className="mx-auto inline-block cursor-pointer rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700">
                Upload PDF
                <input
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && onUploadPdf(e.target.files[0])}
                />
              </label>
            </div>
          )
        ) : site ? (
          <div className="rounded-lg border border-slate-200 px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-medium text-slate-900">{site.base_url}</span>
              <Badge status={site.status} />
            </div>
            {site.error_message && <p className="mt-1 text-xs text-red-600">{site.error_message}</p>}
            <p className="mt-1 text-xs text-slate-500">
              {site.pages_processed}/{site.pages_discovered} page(s) trained · last scraped{' '}
              {site.last_scraped_at ? new Date(site.last_scraped_at).toLocaleString() : 'never'}
            </p>
            <div className="mt-3 flex gap-1.5">
              <button
                className="rounded-md bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700 transition-colors hover:bg-brand-100"
                onClick={() => onRescrape(site.id)}
              >
                Re-scrape
              </button>
              <button
                className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200"
                onClick={() => setEditingSite(site)}
              >
                Edit URL
              </button>
              <button
                className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-100"
                onClick={() => onDeleteSite(site.id)}
              >
                Delete
              </button>
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center">
            <p className="mb-3 text-sm text-slate-500">No website URL added yet.</p>
            <Button onClick={() => setShowAddSite(true)}><Plus className="h-4 w-4" />Add Website URL</Button>
          </div>
        )}
      </div>

      {showAddSite && (
        <ScrapeModal
          title="Add Website URL"
          submitLabel="Add URL"
          onClose={() => setShowAddSite(false)}
          onCreate={(url) => {
            onCreateScrape(url)
            setShowAddSite(false)
          }}
        />
      )}
      {editingSite && (
        <ScrapeModal
          title="Edit Website URL"
          submitLabel="Save"
          initialUrl={editingSite.base_url}
          onClose={() => setEditingSite(null)}
          onCreate={(url) => {
            onEditSite(editingSite.id, url)
            setEditingSite(null)
          }}
        />
      )}
    </Modal>
  )
}

function CreateKbModal({
  agents,
  onClose,
  onCreated,
}: {
  agents: Agent[]
  onClose: () => void
  onCreated: (kb: KnowledgeBase) => void
}) {
  const { notify } = useToast()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [agentIds, setAgentIds] = useState<string[]>([])
  const [sourceType, setSourceType] = useState<'pdf' | 'website'>('pdf')
  const [queuedFiles, setQueuedFiles] = useState<File[]>([])
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [saving, setSaving] = useState(false)

  function addFiles(files: FileList) {
    setQueuedFiles((prev) => [...prev, ...Array.from(files)])
  }

  async function handleSubmit() {
    setSaving(true)
    try {
      const { data: kb } = await knowledgeApi.create({
        name,
        description: description || undefined,
        source_type: sourceType,
        agent_ids: agentIds,
      })

      let failures = 0
      if (sourceType === 'pdf') {
        for (const file of queuedFiles) {
          try {
            await knowledgeApi.uploadPdf(kb.id, file)
          } catch (err) {
            failures++
            notify(`Failed to upload ${file.name}: ${apiErrorMessage(err)}`, 'error')
          }
        }
      } else if (websiteUrl.trim()) {
        try {
          await knowledgeApi.createScrape(kb.id, {
            url: websiteUrl.trim(),
            mode: 'single_url',
            max_pages: 20,
            max_depth: 2,
            include_subpages: true,
            exclude_urls: [],
          })
        } catch (err) {
          failures = 1
          notify(`Failed to start scraping ${websiteUrl.trim()}: ${apiErrorMessage(err)}`, 'error')
        }
      }

      const sourceCount = sourceType === 'pdf' ? queuedFiles.length : websiteUrl.trim() ? 1 : 0
      if (sourceCount === 0) {
        notify('Knowledge base created')
      } else if (failures === 0) {
        notify(`Knowledge base created with ${sourceCount} source(s) processing in the background`)
      } else {
        notify(`Knowledge base created — ${sourceCount - failures}/${sourceCount} source(s) started successfully`)
      }
      onCreated(kb)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="New Knowledge Base" onClose={onClose} width="max-w-2xl">
      <div className="space-y-6">
        <div className="space-y-4">
          <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Textarea label="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
          <div>
            <span className="mb-1 block text-sm font-medium text-slate-700">Assign to Agents</span>
            <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
              {agents.map((agent) => (
                <label key={agent.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={agentIds.includes(agent.id)}
                    onChange={(e) =>
                      setAgentIds((prev) =>
                        e.target.checked ? [...prev, agent.id] : prev.filter((id) => id !== agent.id),
                      )
                    }
                  />
                  {agent.name}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-3 border-t border-slate-200 pt-4">
          <span className="mb-1 block text-sm font-medium text-slate-700">Source Type</span>
          <p className="text-xs text-slate-400">
            Each knowledge base holds one type of source. Need both a PDF and a website? Create a second knowledge
            base for the other type.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setSourceType('pdf')}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium ${
                sourceType === 'pdf' ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-slate-300 text-slate-600'
              }`}
            >
              PDF Documents
            </button>
            <button
              type="button"
              onClick={() => setSourceType('website')}
              className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium ${
                sourceType === 'website' ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-slate-300 text-slate-600'
              }`}
            >
              Website
            </button>
          </div>
        </div>

        {sourceType === 'pdf' ? (
          <div className="space-y-2 border-t border-slate-200 pt-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">PDF Documents</h3>
              <label className="cursor-pointer text-sm font-medium text-brand-600 hover:underline">
                + Add PDF(s)
                <input
                  type="file"
                  accept="application/pdf"
                  multiple
                  className="hidden"
                  onChange={(e) => e.target.files && addFiles(e.target.files)}
                />
              </label>
            </div>
            {queuedFiles.length === 0 ? (
              <p className="text-xs text-slate-400">No PDFs queued yet — optional, you can add these later too.</p>
            ) : (
              <ul className="space-y-1">
                {queuedFiles.map((file, i) => (
                  <li key={i} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 text-sm">
                    <span className="truncate">{file.name}</span>
                    <button
                      className="ml-2 text-slate-400 hover:text-red-600"
                      onClick={() => setQueuedFiles((prev) => prev.filter((_, idx) => idx !== i))}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="space-y-2 border-t border-slate-200 pt-4">
            <Input
              label="Website URL"
              placeholder="https://example.com"
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
            />
            <p className="text-xs text-slate-400">
              Scrapes this exact page and embeds its content — optional, you can add it later too.
            </p>
          </div>
        )}

        <Button className="w-full" disabled={!name.trim() || saving} onClick={handleSubmit}>
          {saving ? 'Creating…' : 'Create Knowledge Base'}
        </Button>
      </div>
    </Modal>
  )
}

function EditKbModal({
  kb,
  agents,
  onClose,
  onUpdated,
}: {
  kb: KnowledgeBase
  agents: Agent[]
  onClose: () => void
  onUpdated: (kb: KnowledgeBase) => void
}) {
  const { notify } = useToast()
  const [name, setName] = useState(kb.name)
  const [description, setDescription] = useState(kb.description ?? '')
  const [agentIds, setAgentIds] = useState<string[]>(kb.agent_ids)
  const [saving, setSaving] = useState(false)

  const isPdf = kb.source_type === 'pdf'
  const [loadingSource, setLoadingSource] = useState(true)
  const [existingDoc, setExistingDoc] = useState<KnowledgeDocument | null>(null)
  const [existingSite, setExistingSite] = useState<ScrapedSite | null>(null)
  const [newFile, setNewFile] = useState<File | null>(null)
  const [websiteUrl, setWebsiteUrl] = useState('')

  useEffect(() => {
    if (isPdf) {
      knowledgeApi
        .listDocuments(kb.id)
        .then((res) => setExistingDoc(res.data[0] ?? null))
        .finally(() => setLoadingSource(false))
    } else {
      knowledgeApi
        .listScrapedSites(kb.id)
        .then((res) => {
          const site = res.data[0] ?? null
          setExistingSite(site)
          setWebsiteUrl(site?.base_url ?? '')
        })
        .finally(() => setLoadingSource(false))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleSubmit() {
    setSaving(true)
    try {
      const { data } = await knowledgeApi.update(kb.id, {
        name,
        description: description || undefined,
        agent_ids: agentIds,
      })

      if (isPdf && newFile) {
        if (existingDoc) await knowledgeApi.deleteDocument(kb.id, existingDoc.id)
        await knowledgeApi.uploadPdf(kb.id, newFile)
        notify('Knowledge base updated — new PDF processing in background')
      } else if (!isPdf && websiteUrl.trim() && websiteUrl.trim() !== existingSite?.base_url) {
        if (existingSite) await knowledgeApi.deleteScrapedSite(kb.id, existingSite.id)
        await knowledgeApi.createScrape(kb.id, {
          url: websiteUrl.trim(),
          mode: 'single_url',
          max_pages: 20,
          max_depth: 2,
          include_subpages: true,
          exclude_urls: [],
        })
        notify('Knowledge base updated — new URL scraping started')
      } else {
        notify('Knowledge base updated')
      }
      onUpdated(data)
    } catch (err) {
      notify(apiErrorMessage(err), 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Edit Knowledge Base" onClose={onClose} width="max-w-2xl">
      <div className="space-y-4">
        <Input label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
        <Textarea label="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
        <div>
          <span className="mb-1 block text-sm font-medium text-slate-700">Assign to Agents</span>
          <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
            {agents.map((agent) => (
              <label key={agent.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={agentIds.includes(agent.id)}
                  onChange={(e) =>
                    setAgentIds((prev) =>
                      e.target.checked ? [...prev, agent.id] : prev.filter((id) => id !== agent.id),
                    )
                  }
                />
                {agent.name}
              </label>
            ))}
          </div>
        </div>

        <div className="border-t border-slate-200 pt-4">
          {isPdf ? (
            <>
              <span className="mb-1 block text-sm font-medium text-slate-700">PDF Document</span>
              {loadingSource ? (
                <p className="text-xs text-slate-400">Loading current document…</p>
              ) : (
                <>
                  {existingDoc && !newFile && (
                    <p className="mb-2 text-xs text-slate-500">
                      Current: <span className="font-medium text-slate-700">{existingDoc.file_name}</span>
                    </p>
                  )}
                  {newFile ? (
                    <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 text-sm">
                      <span className="truncate">{newFile.name}</span>
                      <button className="ml-2 text-slate-400 hover:text-red-600" onClick={() => setNewFile(null)}>
                        ✕
                      </button>
                    </div>
                  ) : (
                    <label className="cursor-pointer text-sm font-medium text-brand-600 hover:underline">
                      {existingDoc ? '+ Replace PDF' : '+ Upload PDF'}
                      <input
                        type="file"
                        accept="application/pdf"
                        className="hidden"
                        onChange={(e) => e.target.files?.[0] && setNewFile(e.target.files[0])}
                      />
                    </label>
                  )}
                  {newFile && (
                    <p className="mt-1 text-xs text-slate-400">
                      Replacing the document deletes the current one and starts re-embedding from the new file.
                    </p>
                  )}
                </>
              )}
            </>
          ) : (
            <>
              <Input
                label="Website URL"
                placeholder="https://example.com"
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
              />
              <p className="mt-1 text-xs text-slate-400">
                Changing the URL deletes the current scrape and starts a fresh one.
              </p>
            </>
          )}
        </div>

        <Button className="w-full" disabled={!name.trim() || saving} onClick={handleSubmit}>
          {saving ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </Modal>
  )
}

function ScrapeModal({
  title = 'Scrape Website',
  submitLabel = 'Start Scraping',
  initialUrl = '',
  onClose,
  onCreate,
}: {
  title?: string
  submitLabel?: string
  initialUrl?: string
  onClose: () => void
  onCreate: (url: string) => void
}) {
  const [url, setUrl] = useState(initialUrl)

  return (
    <Modal title={title} onClose={onClose}>
      <div className="space-y-4">
        <Input label="Website URL" required placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
        <p className="text-xs text-slate-400">Scrapes this exact page and embeds its content for the chatbot to answer from.</p>
        <Button className="w-full" disabled={!url.trim()} onClick={() => onCreate(url.trim())}>
          {submitLabel}
        </Button>
      </div>
    </Modal>
  )
}
