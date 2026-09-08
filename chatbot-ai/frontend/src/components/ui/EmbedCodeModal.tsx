import { useState } from 'react'
import { Button } from './Button'
import { Modal } from './Modal'

export function EmbedCodeModal({ embedCode, onClose }: { embedCode: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)

  return (
    <Modal title="Agent created successfully" onClose={onClose} width="max-w-lg">
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          Add this snippet to your website's HTML, right before the closing <code>&lt;/body&gt;</code> tag.
        </p>
        <div className="relative rounded-lg bg-slate-900 p-4">
          <pre className="overflow-x-auto text-xs text-slate-100">{embedCode}</pre>
          <button
            className="absolute right-2 top-2 rounded bg-slate-700 px-2 py-1 text-xs text-white hover:bg-slate-600"
            onClick={() => {
              navigator.clipboard.writeText(embedCode)
              setCopied(true)
              setTimeout(() => setCopied(false), 2000)
            }}
          >
            {copied ? 'Copied!' : 'Copy Embed Code'}
          </button>
        </div>
        <Button className="w-full" onClick={onClose}>
          Done
        </Button>
      </div>
    </Modal>
  )
}
