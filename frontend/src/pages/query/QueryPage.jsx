import { useCallback, useEffect, useState } from 'react'
import { exportQueryUrl, queryMeasurements, queryStatistics } from '../../api/query.js'
import Pagination from '../../components/common/Pagination.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import { Alert } from '../../components/common/Feedback.jsx'
import StatCard from '../../components/common/StatCard.jsx'
import { QUERY_FILTER_KEYS } from '../../constants/filters.js'
import { useAsyncData } from '../../hooks/useAsyncData.js'
import { useCsvExport } from '../../hooks/useCsvExport.js'
import { useListQuery } from '../../hooks/useListQuery.js'
import { formatDateTime, formatNumber, formatPercent } from '../../utils/format.js'
import QueryFilters from './components/QueryFilters.jsx'
import QueryResultTable from './components/QueryResultTable.jsx'
import StatisticsPanel from './components/StatisticsPanel.jsx'

export default function QueryPage() {
  const query = useListQuery(queryMeasurements, QUERY_FILTER_KEYS, { pageSize: 20 })
  const [statsParams, setStatsParams] = useState({ group_by: 'pollutant', metric: 'avg' })
  const { exporting, exportCsv } = useCsvExport(exportQueryUrl)

  const statsLoader = useCallback(
    () => queryStatistics({ ...query.filters, ...statsParams }),
    [query.filters, statsParams]
  )
  const stats = useAsyncData(statsLoader, { immediate: false })

  const summary = query.summary

  // 筛选条件或统计维度变化时自动刷新统计, 便于即时比对
  useEffect(() => {
    stats.reload().catch(() => {})
  }, [stats.reload])

  const handleExport = () =>
    exportCsv({ ...query.filters, sort: 'measured_at', order: 'desc' }, '监测数据查询结果')

  return (
    <>
      <QueryFilters
        value={query.filters}
        loading={query.loading}
        onSubmit={(next) => query.setFilters(next)}
        onReset={() => query.setFilters(QUERY_FILTER_KEYS)}
      />

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <div className="stat-grid">
        <StatCard label="符合条件的数据量" value={summary ? summary.total : '-'} foot={summary ? `涉及 ${summary.station_count} 个监测点` : ''} />
        <StatCard
          label="超标记录"
          value={summary ? summary.exceeded_count : '-'}
          tone={summary?.exceeded_count ? 'danger' : undefined}
          foot={summary ? `超标率 ${formatPercent(summary.exceed_rate)}` : ''}
        />
        <StatCard label="平均浓度" value={summary ? formatNumber(summary.avg_value) : '-'} foot="按当前筛选范围计算" />
        <StatCard
          label="时间范围"
          value={summary ? formatDateTime(summary.first_measured_at).slice(5, 10) : '-'}
          unit={summary ? `~ ${formatDateTime(summary.last_measured_at).slice(5, 10)}` : ''}
          foot={summary ? `${formatDateTime(summary.first_measured_at)} ~ ${formatDateTime(summary.last_measured_at)}` : ''}
        />
      </div>

      <StatisticsPanel
        params={statsParams}
        onChange={(next) => setStatsParams(next)}
        data={stats.data}
        loading={stats.loading}
        error={stats.error}
        onRun={stats.reload}
      />

      <SectionCard
        title="查询结果"
        hint="按监测时间倒序, 单次导出最多 20000 行"
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
        <QueryResultTable rows={query.items} loading={query.loading} />
        <Pagination
          page={query.page}
          pages={query.pages}
          total={query.total}
          pageSize={query.pageSize}
          onPageChange={query.setPage}
          onPageSizeChange={query.setPageSize}
        />
      </SectionCard>
    </>
  )
}
