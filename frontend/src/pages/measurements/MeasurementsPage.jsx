import { useCallback, useState } from 'react'
import {
  deleteMeasurement,
  exportMeasurementsUrl,
  listMeasurements
} from '../../api/measurements.js'
import ConfirmDialog from '../../components/common/ConfirmDialog.jsx'
import Pagination from '../../components/common/Pagination.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import { Alert } from '../../components/common/Feedback.jsx'
import { useToast } from '../../components/common/ToastProvider.jsx'
import { MEASUREMENT_FILTER_KEYS } from '../../constants/filters.js'
import { useCsvExport } from '../../hooks/useCsvExport.js'
import { useListQuery } from '../../hooks/useListQuery.js'
import EntryForm from './components/EntryForm.jsx'
import EntryResultPanel from './components/EntryResultPanel.jsx'
import MeasurementFilters from './components/MeasurementFilters.jsx'
import MeasurementTable from './components/MeasurementTable.jsx'

export default function MeasurementsPage() {
  const toast = useToast()
  const query = useListQuery(listMeasurements, MEASUREMENT_FILTER_KEYS)
  const [result, setResult] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const { exporting, exportCsv } = useCsvExport(exportMeasurementsUrl)

  const handleSubmitted = useCallback(
    (payload) => {
      setResult({ kind: 'submit', payload })
      query.reload()
    },
    [query]
  )

  const handleDelete = useCallback(async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteMeasurement(pendingDelete.id)
      toast.success('监测数据已删除')
      setPendingDelete(null)
      query.reload()
    } catch (error) {
      toast.error(error.message)
    } finally {
      setDeleting(false)
    }
  }, [pendingDelete, query, toast])

  const handleExport = useCallback(
    () => exportCsv(query.filters, '监测数据'),
    [exportCsv, query.filters]
  )

  return (
    <>
      <div className="grid-2">
        <EntryForm
          onPreview={(payload) => setResult({ kind: 'preview', payload })}
          onSubmitted={handleSubmitted}
        />
        <EntryResultPanel result={result} summary={query.summary} onClose={() => setResult(null)} />
      </div>

      <MeasurementFilters
        value={query.filters}
        loading={query.loading}
        onSubmit={(next) => query.setFilters(next)}
        onReset={() => query.setFilters(MEASUREMENT_FILTER_KEYS)}
      />

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <SectionCard
        title="最近录入的数据"
        hint="按监测时间倒序展示, 便于核对刚提交的记录"
        actions={
          <>
            <button type="button" className="btn btn-sm" onClick={query.reload} disabled={query.loading}>
              刷新
            </button>
            <button type="button" className="btn btn-sm btn-primary" onClick={handleExport} disabled={exporting}>
              {exporting ? '导出中...' : '导出 CSV'}
            </button>
          </>
        }
      >
        <MeasurementTable
          rows={query.items}
          loading={query.loading}
          onDelete={(row) => setPendingDelete(row)}
        />
        <Pagination
          page={query.page}
          pages={query.pages}
          total={query.total}
          pageSize={query.pageSize}
          onPageChange={query.setPage}
          onPageSizeChange={query.setPageSize}
        />
      </SectionCard>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        danger
        busy={deleting}
        title="删除监测数据"
        message={`确认删除 ${pendingDelete?.pollutant_label || ''} 的这条记录吗?`}
        detail="若该记录已产生超标记录, 对应的标注信息也会一并删除。"
        confirmText="确认删除"
        onConfirm={handleDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  )
}
