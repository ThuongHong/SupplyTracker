import React from 'react'

interface Props {
  entity: { entity_type: string; entity_id: string; entity_name?: string }
  chart: string
  window: string
  onAsk?: (prompt: string, entityContext: Array<{ entity_type: string; entity_id: string }>) => void
}

export function AskAIButton({ entity, chart, window, onAsk }: Props) {
  const handleClick = () => {
    const entityName = entity.entity_name ?? entity.entity_id
    const prompt = `Why has ${entityName}'s ${chart} moved over the last ${window}?`
    onAsk?.(prompt, [{ entity_type: entity.entity_type, entity_id: entity.entity_id }])
  }
  return (
    <button
      onClick={handleClick}
      title={`Ask AI about ${chart}`}
      className="text-xs text-indigo-500 dark:text-indigo-400 hover:underline focus:outline-none focus:ring-1 focus:ring-indigo-500 rounded"
    >
      Ask AI
    </button>
  )
}
