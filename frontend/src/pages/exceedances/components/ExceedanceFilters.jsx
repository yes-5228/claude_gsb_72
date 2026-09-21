import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { usePollutantMeta, useStationOptions } from '../../../hooks/useOptions.js'
import { useFilterDraft } from '../../../hooks/useFilterDraft.js'
import { EXCEEDANCE_FILTER_KEYS, EXCEEDANCE_STATUS_OPTIONS, EXCEEDANCE_LEVEL_OPTIONS } from '../../../constants/filters.js'

export default function ExceedanceFilters({ value, loading, onSubmit, onReset }) {
  const { data: stationData } = useStationOptions()
  const { data: pollutantData } = usePollutantMeta()
  const { draft, update, submit, reset, onKeyDownSubmit } = useFilterDraft(
    value, EXCEEDANCE_FILTER_KEYS, { onSubmit, onReset }
  )

  return (
    <FilterPanel loading={loading} onSearch={submit} onReset={reset}>
      <Field label="标注状态">
        <Select value={draft.status || ''} onChange={update('status')} placeholder="全部状态" options={EXCEEDANCE_STATUS_OPTIONS} />
      </Field>
      <Field label="超标等级">
        <Select value={draft.level || ''} onChange={update('level')} placeholder="全部等级" options={EXCEEDANCE_LEVEL_OPTIONS} />
      </Field>
      <Field label="监测点">
        <Select
          value={draft.station_id || ''}
          onChange={update('station_id')}
          placeholder="全部监测点"
          options={(stationData?.items ?? []).map((item) => ({ value: String(item.id), label: `${item.code} ${item.name}` }))}
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
      <Field label="开始日期">
        <Input type="date" value={draft.date_from || ''} onChange={update('date_from')} />
      </Field>
      <Field label="结束日期">
        <Input type="date" value={draft.date_to || ''} onChange={update('date_to')} />
      </Field>
      <Field label="关键字">
        <Input
          placeholder="监测点名称 / 编码 / 标注说明"
          value={draft.keyword || ''}
          onChange={update('keyword')}
          onKeyDown={onKeyDownSubmit}
        />
      </Field>
    </FilterPanel>
  )
}
