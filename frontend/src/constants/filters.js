/**
 * 统一的筛选口径 (前端): 各页面共用的下拉选项、初始筛选状态。
 *
 * 这些取值与后端 domain/constants.py 的枚举一一对应; 任何页面新增筛选项
 * 都应在这里定义, 避免 PERIODS / 超标选项等常量在四个页面各抄一份。
 */

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

export const STATION_STATUS_OPTIONS = [
  { value: 'active', label: '运行中' },
  { value: 'maintenance', label: '维护中' },
  { value: 'offline', label: '停用' }
]

export const STATION_TYPE_OPTIONS = [
  { value: 'ambient', label: '环境空气' },
  { value: 'traffic', label: '道路交通' },
  { value: 'background', label: '区域背景' },
  { value: 'industrial', label: '工业园区' },
  { value: 'rural', label: '农村站点' }
]

/** 空筛选的统一工厂: 重置即回到该对象, 保证字段集合稳定、不丢键。 */
export function emptyFilters(keys) {
  return Object.fromEntries(keys.map((key) => [key, '']))
}

export const MEASUREMENT_FILTER_KEYS = [
  'station_id', 'pollutant', 'period', 'is_exceeded', 'date_from', 'date_to'
]

export const QUERY_FILTER_KEYS = [
  'keyword', 'station_id', 'area', 'pollutant', 'period', 'is_exceeded',
  'exceedance_status', 'data_source', 'date_from', 'date_to', 'min_value', 'max_value'
]

export const EXCEEDANCE_FILTER_KEYS = [
  'status', 'level', 'pollutant', 'station_id', 'date_from', 'date_to', 'keyword'
]

export const STATION_FILTER_KEYS = ['keyword', 'area', 'status', 'station_type']

export const INITIAL_MEASUREMENT_FILTERS = emptyFilters(MEASUREMENT_FILTER_KEYS)
export const INITIAL_QUERY_FILTERS = emptyFilters(QUERY_FILTER_KEYS)
export const INITIAL_EXCEEDANCE_FILTERS = emptyFilters(EXCEEDANCE_FILTER_KEYS)
export const INITIAL_STATION_FILTERS = emptyFilters(STATION_FILTER_KEYS)
