import http, { exportUrl, toParams } from './client.js'

export const queryMeasurements = (params) => http.get('/query/measurements', { params: toParams(params) })
export const queryStatistics = (params) => http.get('/query/statistics', { params: toParams(params) })
export const queryOptions = () => http.get('/query/options')
export const exportQueryUrl = (params) => exportUrl('/query/export', params)
