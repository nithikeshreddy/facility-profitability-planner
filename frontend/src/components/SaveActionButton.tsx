import { useState } from 'react'

interface Props {
  /** Saves the proposed action with the manager note; rejects with the API's message. */
  onSave: (note: string) => Promise<void>
  /** When set, saving is disabled and this reason is shown instead. */
  blockedReason?: string | null
  placeholder?: string
}

/** "Save proposed action" → optional note for the approving manager → confirm. */
export default function SaveActionButton({ onSave, blockedReason = null, placeholder }: Props) {
  const [open, setOpen] = useState(false)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm() {
    setSaving(true)
    setError(null)
    try {
      await onSave(note)
      setOpen(false)
      setNote('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the proposed action.')
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <>
        <button
          type="button"
          onClick={() => setOpen(true)}
          disabled={blockedReason !== null}
          title={blockedReason ?? undefined}
          className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
        >
          Save proposed action
        </button>
        {blockedReason && <p className="mt-2 text-xs text-red-800">Cannot be saved: {blockedReason}</p>}
      </>
    )
  }

  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium text-slate-600">
        Note for the approving manager (optional)
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={2000}
          rows={3}
          className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm font-normal text-slate-900"
          placeholder={placeholder}
        />
      </label>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={confirm}
          disabled={saving}
          className="flex-1 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-wait disabled:opacity-60"
        >
          {saving ? 'Saving…' : 'Confirm save'}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          disabled={saving}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          Cancel
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-red-800">
          {error}
        </p>
      )}
    </div>
  )
}
