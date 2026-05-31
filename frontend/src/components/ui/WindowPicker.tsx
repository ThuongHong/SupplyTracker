import React from 'react'

export type Window = '7d' | '30d' | '90d'

interface WindowPickerProps {
  options?: Window[]
  value: Window
  onChange: (w: Window) => void
}

export function WindowPicker({ options = ['7d', '30d', '90d'], value, onChange }: WindowPickerProps) {
  return (
    <div className="seg">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={['seg__btn focus-ring', opt === value ? 'seg__btn--active' : ''].join(' ')}
        >
          {opt}
        </button>
      ))}
    </div>
  )
}
