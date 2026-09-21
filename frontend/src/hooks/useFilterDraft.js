import { useEffect, useState } from 'react'
import { emptyFilters } from '../constants/filters.js'

/**
 * 筛选面板统一的草稿状态:
 * - 输入只改本地 draft, 点"查询"才 onSubmit(draft), 与旧交互完全一致;
 * - 外部 value 变化 (如重置/路由) 时同步回 draft;
 * - reset() 回到由 keys 生成的空筛选, 并通知父级。
 *
 * 四个筛选面板共用这一份, 取代各自重复的 useState/useEffect/update/reset。
 */
export function useFilterDraft(value, keys, { onSubmit, onReset } = {}) {
  const empty = emptyFilters(keys)
  const [draft, setDraft] = useState(value)

  useEffect(() => {
    setDraft(value)
  }, [value])

  const update = (key) => (event) => setDraft((prev) => ({ ...prev, [key]: event.target.value }))
  const patch = (next) => setDraft((prev) => ({ ...prev, ...next }))

  const submit = () => onSubmit?.(draft)
  const reset = () => {
    setDraft(empty)
    onReset?.(empty)
  }

  const onKeyDownSubmit = (event) => {
    if (event.key === 'Enter') submit()
  }

  return { draft, setDraft, update, patch, submit, reset, onKeyDownSubmit }
}
