import { useEffect, useState } from 'react'
import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import {
  DATA_SOURCE_OPTIONS,
  EXCEEDED_OPTIONS,
  EXCEEDANCE_STATUS_OPTIONS,
  PERIOD_OPTIONS,
  QUERY_FILTER_KEYS
} from '../../../constants/filters.js'
import { usePollutantMeta, useStationOptions } from '../../../hooks/useOptions.js'

export default function QueryFilters({ value, loading, onSubmit, onReset }) {
  const [draft, setDraft] = useState(value)
  const { data: stationData } = useStationOptions()
  const { data: pollutantData } = usePollutantMeta()

  useEffect(() => {
    setDraft(value)
  }, [value])

  const update = (key) => (event) => setDraft({ ...draft, [key]: event.target.value })

  return (
    <FilterPanel
      loading={loading}
      onSearch={() => onSubmit(draft)}
      onReset={() => {
        setDraft({ ...QUERY_FILTER_KEYS })
        onReset()
      }}
    >
      <Field label="关键字">
        <Input
          placeholder="监测点名称 / 编码 / 地址"
          value={draft.keyword || ''}
          onChange={update('keyword')}
          onKeyDown={(event) => event.key === 'Enter' && onSubmit(draft)}
        />
      </Field>
      <Field label="监测点">
        <Select
          value={draft.station_id || ''}
          onChange={update('station_id')}
          placeholder="全部监测点"
          options={(stationData?.items ?? []).map((item) => ({ value: String(item.id), label: `${item.code} ${item.name}` }))}
        />
      </Field>
      <Field label="所属区域">
        <Select
          value={draft.area || ''}
          onChange={update('area')}
          placeholder="全部区域"
          options={(stationData?.areas ?? []).map((area) => ({ value: area, label: area }))}
        />
      </Field>
      <Field label="监测因子">
        <Select
          value={draft.pollutant || ''}
          onChange={update('pollutant')}
          placeholder="全部因子"
          options={(pollutantData?.items ?? []).map((item) => ({ value: item.code, label: item.label }))}
        />
      </Field>
      <Field label="数据周期">
        <Select value={draft.period || ''} onChange={update('period')} placeholder="全部周期" options={PERIOD_OPTIONS} />
      </Field>
      <Field label="是否超标">
        <Select value={draft.is_exceeded || ''} onChange={update('is_exceeded')} placeholder="全部" options={EXCEEDED_OPTIONS} />
      </Field>
      <Field label="标注状态">
        <Select
          value={draft.exceedance_status || ''}
          onChange={update('exceedance_status')}
          placeholder="全部 (仅筛选超标记录)"
          options={EXCEEDANCE_STATUS_OPTIONS}
        />
      </Field>
      <Field label="数据来源">
        <Select value={draft.data_source || ''} onChange={update('data_source')} placeholder="全部来源" options={DATA_SOURCE_OPTIONS} />
      </Field>
      <Field label="开始日期">
        <Input type="date" value={draft.date_from || ''} onChange={update('date_from')} />
      </Field>
      <Field label="结束日期">
        <Input type="date" value={draft.date_to || ''} onChange={update('date_to')} />
      </Field>
      <Field label="监测值下限">
        <Input type="number" step="0.01" value={draft.min_value || ''} onChange={update('min_value')} placeholder="不限" />
      </Field>
      <Field label="监测值上限">
        <Input type="number" step="0.01" value={draft.max_value || ''} onChange={update('max_value')} placeholder="不限" />
      </Field>
    </FilterPanel>
  )
}
