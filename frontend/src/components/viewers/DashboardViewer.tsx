import React, { useMemo } from 'react'
import Chart from 'react-apexcharts'
import { Download } from 'lucide-react'
import type { WorkspaceTab } from '../../types/workspace'
import type { ChartData } from '../../types/workspace'

interface DashboardViewerProps {
  tab: WorkspaceTab
}

export function DashboardViewer({ tab }: DashboardViewerProps) {
  const charts = (tab.data?.charts as ChartData[] | undefined) || []

  const chartConfigs = useMemo(() => {
    return charts.map((chart, index) => {
      const defaultOptions = {
        chart: {
          id: `chart-${tab.id}-${index}`,
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
        xaxis: chart.options?.xaxis || {},
        yaxis: chart.options?.yaxis || {},
        title: {
          text: chart.title || `Chart ${index + 1}`,
          align: 'left' as const,
          style: {
            fontSize: '16px',
            fontWeight: 600,
          },
        },
        ...chart.options,
      }

      return {
        options: defaultOptions,
        series: chart.series || [],
        chartType: chart.chartType || 'line',
      }
    })
  }, [charts, tab.id])

  if (charts.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 dark:text-slate-400">Диаграммы не загружены</p>
        </div>
      </div>
    )
  }

  // Calculate grid layout: 2 columns for 2-4 charts, 3 columns for 5+ charts
  const gridCols = charts.length <= 4 ? 2 : 3

  return (
    <div className="h-full w-full flex flex-col bg-white dark:bg-slate-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {tab.title}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            ({charts.length} {charts.length === 1 ? 'диаграмма' : 'диаграмм'})
          </span>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="flex-1 p-6 overflow-auto">
        <div
          className={`grid gap-6 ${
            gridCols === 2 ? 'grid-cols-2' : gridCols === 3 ? 'grid-cols-3' : 'grid-cols-1'
          }`}
        >
          {chartConfigs.map((config, index) => (
            <div
              key={index}
              className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-4"
            >
              <div className="h-[400px] min-h-[400px]">
                <Chart
                  options={config.options}
                  series={config.series}
                  type={config.chartType}
                  height="100%"
                  width="100%"
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
