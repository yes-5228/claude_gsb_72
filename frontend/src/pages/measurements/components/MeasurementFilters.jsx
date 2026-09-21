import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { usePollutantMeta, useStationOptions } from '../../../hooks/useOptions.js'
import { useFilterDraft } from '../../../hooks/useFilterDraft.js'
import { MEASUREMENT_FILTER_KEYS, PERIOD_OPTIONS, EXCEEDED_OPTIONS } from '../../../constants/filters.js'

export default function MeasurementFilters({ value, loading, onSubmit, onReset }) {
  const { data: stationData } = useStationOptions()
  const { data: pollutantData } = usePollutantMeta()
  const { draft, update, submit, reset } = useFilterDraft(
    value, MEASUREMENT_FILTER_KEYS, { onSubmit, onReset }
  )

  return (
    <FilterPanel loading={loading} onSearch={submit} onReset={reset}>
      <Field label="监测点">
        <Select
          value={draft.station_id || ''}
          onChange={update('station_id')}
          placeholder="全部监测点"
          options={(stationData?.items ?? []).map((item) => ({
            value: String(item.id),
            label: `${item.code} ${item.name}`
          }))}
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
      <Field label="超标情况">
        <Select value={draft.is_exceeded || ''} onChange={update('is_exceeded')} placeholder="全部" options={EXCEEDED_OPTIONS} />
      </Field>
      <Field label="开始日期">
        <Input type="date" value={draft.date_from || ''} onChange={update('date_from')} />
      </Field>
      <Field label="结束日期">
        <Input type="date" value={draft.date_to || ''} onChange={update('date_to')} />
      </Field>
    </FilterPanel>
  )
}
