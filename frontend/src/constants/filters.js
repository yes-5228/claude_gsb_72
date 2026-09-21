/**
 * 统一的列表筛选口径(前端)。
 *
 * - FILTER_KEYS: 各页面初始筛选 / 重置筛选的唯一来源,
 *   键名与后端查询参数一一对应, 空串由 api/client.toParams 自动剔除;
 * - 下拉选项: 与后端枚举保持一致, 避免多个筛选组件各写一份导致标签漂移。
 */

export const MEASUREMENT_FILTER_KEYS = {
  station_id: '',
  pollutant: '',
  period: '',
  is_exceeded: '',
  date_from: '',
  date_to: ''
}

export const QUERY_FILTER_KEYS = {
  keyword: '',
  station_id: '',
  area: '',
  pollutant: '',
  period: '',
  is_exceeded: '',
  exceedance_status: '',
  data_source: '',
  date_from: '',
  date_to: '',
  min_value: '',
  max_value: ''
}

export const EXCEEDANCE_FILTER_KEYS = {
  status: '',
  level: '',
  pollutant: '',
  station_id: '',
  date_from: '',
  date_to: '',
  keyword: ''
}

export const STATION_FILTER_KEYS = {
  keyword: '',
  area: '',
  status: '',
  station_type: ''
}

export const PERIOD_OPTIONS = [
  { value: 'hourly', label: '小时均值' },
  { value: 'daily', label: '日均值' }
]

export const EXCEEDED_OPTIONS = [
  { value: 'true', label: '仅超标' },
  { value: 'false', label: '仅达标' }
]

export const EXCEEDANCE_STATUS_OPTIONS = [
  { value: 'pending', label: '待标注' },
  { value: 'confirmed', label: '已确认' },
  { value: 'ignored', label: '已忽略' }
]

export const EXCEEDANCE_LEVEL_OPTIONS = [
  { value: 'light', label: '轻度超标' },
  { value: 'moderate', label: '中度超标' },
  { value: 'severe', label: '重度超标' }
]

export const DATA_SOURCE_OPTIONS = [
  { value: 'manual', label: '手工录入' },
  { value: 'device', label: '设备上传' },
  { value: 'import', label: '历史导入' }
]
