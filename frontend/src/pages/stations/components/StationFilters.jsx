import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { useFilterDraft } from '../../../hooks/useFilterDraft.js'
import { STATION_FILTER_KEYS, STATION_STATUS_OPTIONS, STATION_TYPE_OPTIONS } from '../../../constants/filters.js'

export default function StationFilters({ value, areas = [], loading, onSubmit, onReset }) {
  const { draft, update, submit, reset, onKeyDownSubmit } = useFilterDraft(
    value, STATION_FILTER_KEYS, { onSubmit, onReset }
  )

  return (
    <FilterPanel loading={loading} onSearch={submit} onReset={reset}>
      <Field label="关键字">
        <Input
          placeholder="监测点名称 / 编码 / 地址"
          value={draft.keyword || ''}
          onChange={update('keyword')}
          onKeyDown={onKeyDownSubmit}
        />
      </Field>
      <Field label="所属区域">
        <Select
          value={draft.area || ''}
          onChange={update('area')}
          placeholder="全部区域"
          options={areas.map((area) => ({ value: area, label: area }))}
        />
      </Field>
      <Field label="监测点类型">
        <Select value={draft.station_type || ''} onChange={update('station_type')} placeholder="全部类型" options={STATION_TYPE_OPTIONS} />
      </Field>
      <Field label="运行状态">
        <Select value={draft.status || ''} onChange={update('status')} placeholder="全部状态" options={STATION_STATUS_OPTIONS} />
      </Field>
    </FilterPanel>
  )
}
