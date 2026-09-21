import { useState } from 'react'
import { downloadFile } from '../api/client.js'
import { useToast } from '../components/common/ToastProvider.jsx'
import { saveBlob } from '../utils/download.js'

/**
 * 统一的 CSV 导出动作: loading 状态、错误提示、成功回执、文件落盘
 * 在监测数据、查询、超标三处保持完全一致的交互。
 * @param {(params: object) => string} buildUrl 用筛选参数拼导出地址
 */
export function useCsvExport(buildUrl) {
  const toast = useToast()
  const [exporting, setExporting] = useState(false)

  const exportCsv = async (params, fileLabel) => {
    setExporting(true)
    try {
      const blob = await downloadFile(buildUrl(params))
      saveBlob(blob, `${fileLabel}_${Date.now()}.csv`)
      toast.success('导出任务已完成, 请查看下载文件')
    } catch (error) {
      toast.error(error.message)
    } finally {
      setExporting(false)
    }
  }

  return { exporting, exportCsv }
}
