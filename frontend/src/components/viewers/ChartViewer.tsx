import React, { useMemo } from 'react'
import Chart from 'react-apexcharts'
import { Download, RefreshCw } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'
import type { ChartData } from '../../types/workspace'

interface ChartViewerProps {
  tab: WorkspaceTab
}

export function ChartViewer({ tab }: ChartViewerProps) {
  const chartData = tab.data as ChartData | undefined

  const { options, series } = useMemo(() => {
    if (!chartData) {
      return { options: {}, series: [] }
    }

    const defaultOptions = {
      chart: {
        id: `chart-${tab.id}`,
        toolbar: {
          show: true,
          tools: {
            download: true,
            selection: true,
            zoom: true,
            zoomin: true,
            zoomout: true,
            pan: true,
            reset: true,
          },
        },
      },
      xaxis: chartData.options?.xaxis || {},
      yaxis: chartData.options?.yaxis || {},
      ...chartData.options,
    }

    return {
      options: defaultOptions,
      series: chartData.series || [],
    }
  }, [chartData, tab.id])

  const handleDownload = () => {
    // ApexCharts handles download through toolbar, but we can add custom logic here
    console.log('Download chart')
  }

  if (!chartData || !chartData.series || chartData.series.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 dark:text-slate-400">Данные графика не загружены</p>
        </div>
      </div>
    )
  }

  const chartType = chartData.chartType || 'line'

  return (
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {tab.title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            className="p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Скачать"
          >
            <Download className="w-4 h-4 text-slate-600 dark:text-slate-400" />
          </button>
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 p-6 overflow-auto">
        <div className="h-full min-h-[400px]">
          <Chart
            options={options}
            series={series}
            type={chartType}
            height="100%"
            width="100%"
          />
        </div>
      </div>
    </div>
  )
}

