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
    return charts.map((chart: any, index: number) => {
      const chartType = chart.chartType || 'line'
      
      // Защита от undefined series для разных типов диаграмм
      let safeSeries: any = chart.series || []
      
      // Для pie/donut series должен быть массивом чисел
      if ((chartType === 'pie' || chartType === 'donut') && Array.isArray(safeSeries)) {
        if (safeSeries.length === 0 || typeof safeSeries[0] === 'object') {
          safeSeries = [1]
        }
      }
      // Для line/bar series должен быть массивом объектов с data
      else if (chartType === 'line' || chartType === 'bar') {
        if (!Array.isArray(safeSeries) || safeSeries.length === 0) {
          safeSeries = [{ name: 'Данные', data: [] }]
        } else if (typeof safeSeries[0] !== 'object' || !('data' in safeSeries[0])) {
          safeSeries = [{ name: 'Данные', data: safeSeries }]
        }
        safeSeries = safeSeries.map((s: any) => ({
          ...s,
          data: Array.isArray(s.data) ? s.data : []
        }))
      }
      
      // Для bar charts - автоматически создать categories если их нет
      let safeXaxis: any = chart.options?.xaxis || {}
      if (chartType === 'bar' && !safeXaxis.categories && Array.isArray(safeSeries) && safeSeries[0]?.data) {
        safeXaxis = {
          ...safeXaxis,
          categories: safeSeries[0].data.map((_: any, i: number) => `${i + 1}`)
        }
      }

      // Default colors for charts
      const defaultColors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16']
      
      const defaultOptions: any = {
        chart: {
          id: `chart-${tab.id}-${index}`,
          toolbar: {
            show: true,
            tools: {
              download: true,
              selection: false,
              zoom: false,
              zoomin: false,
              zoomout: false,
              pan: false,
              reset: false,
            },
          },
        },
        colors: defaultColors,
        // Stroke only for line charts
        ...(chartType === 'line' ? { stroke: { width: 3, curve: 'smooth' as const } } : {}),
        xaxis: safeXaxis,
        ...(chart.options?.yaxis ? { yaxis: chart.options.yaxis } : {}),
        title: {
          text: chart.title || `Chart ${index + 1}`,
          align: 'left' as const,
          style: {
            fontSize: '13px',
            fontWeight: 600,
          },
        },
        legend: {
          fontSize: '11px',
          position: 'bottom' as const,
        },
        dataLabels: {
          enabled: chartType === 'pie' || chartType === 'donut',
          style: {
            fontSize: '10px',
          },
        },
        labels: chart.labels || chart.options?.labels,
        // Add plotOptions for bar charts - minimal config
        ...(chartType === 'bar' ? {
          plotOptions: {
            bar: {
              horizontal: false,
              columnWidth: '55%',
            }
          }
        } : {}),
      }
      
      // Merge chart.options but ensure xaxis.categories is preserved
      if (chart.options) {
        Object.keys(chart.options).forEach(key => {
          if (key === 'xaxis') {
            // Preserve our safeXaxis categories
            defaultOptions.xaxis = { ...chart.options.xaxis, ...safeXaxis }
          } else if (key !== 'labels') {
            defaultOptions[key] = chart.options[key]
          }
        })
      }

      return {
        options: defaultOptions,
        series: safeSeries,
        chartType: chartType,
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

  // Calculate grid layout: always 2 columns for compactness
  const gridCols = 2

  return (
    <div 
      className="w-full bg-white dark:bg-slate-900"
      style={{ position: 'relative', height: '100%' }}
    >
      {/* Toolbar - fixed at top */}
      <div 
        className="flex items-center justify-between px-4 py-2 border-b border-slate-200 dark:border-slate-700"
        style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '41px', zIndex: 10, backgroundColor: 'inherit' }}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {tab.title}
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            ({charts.length} {charts.length === 1 ? 'диаграмма' : 'диаграмм'})
          </span>
        </div>
      </div>

      {/* Charts Grid - scrollable container with absolute positioning */}
      <div 
        className="p-4"
        style={{ position: 'absolute', top: '41px', left: 0, right: 0, bottom: 0, overflow: 'auto' }}
      >
        <div className="grid grid-cols-2 gap-4" style={{ minHeight: 'min-content' }}>
          {chartConfigs.map((config, index) => (
              <div
                key={index}
                className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-3"
                style={{ minHeight: '250px' }}
              >
                <div style={{ height: '220px', minHeight: '220px' }}>
                  <Chart
                    options={config.options}
                    series={config.series}
                    type={config.chartType as any}
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
