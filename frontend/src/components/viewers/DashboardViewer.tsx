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

  // #region agent log
  React.useEffect(() => {
    fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DashboardViewer.tsx:charts_received',message:'Charts data received',data:{chartsCount: charts.length, chartsPreview: charts.map((c,i) => ({index: i, title: c.title, chartType: c.chartType, seriesLen: c.series?.length, seriesType: typeof c.series, firstSeries: JSON.stringify(c.series?.[0]).slice(0,100)}))},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'DASH1'})}).catch(()=>{});
    // Listen for ApexCharts errors
    const errorHandler = (e: ErrorEvent) => {
      if (e.message?.includes('apex') || e.message?.includes('Cannot read properties')) {
        fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DashboardViewer.tsx:apex_error',message:'ApexCharts error caught',data:{error: e.message, filename: e.filename, lineno: e.lineno},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H2'})}).catch(()=>{});
      }
    };
    window.addEventListener('error', errorHandler);
    return () => window.removeEventListener('error', errorHandler);
  }, [charts])
  // #endregion

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

      // #region agent log
      fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DashboardViewer.tsx:chart_config_'+index,message:'Chart '+index+' final config',data:{index,title:chart.title,chartType,safeSeries:JSON.stringify(safeSeries).slice(0,200),finalXaxis:JSON.stringify(defaultOptions.xaxis),hasCategories:!!defaultOptions.xaxis?.categories,labels:defaultOptions.labels,seriesLen:safeSeries?.length},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H_FIX'})}).catch(()=>{});
      // #endregion

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
        ref={(el) => {
          // #region agent log
          if (el) {
            fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DashboardViewer.tsx:scrollContainer',message:'Scroll container dimensions',data:{clientHeight: el.clientHeight, scrollHeight: el.scrollHeight, offsetHeight: el.offsetHeight, hasOverflow: el.scrollHeight > el.clientHeight},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'DASH3'})}).catch(()=>{});
          }
          // #endregion
        }}
      >
        <div className="grid grid-cols-2 gap-4" style={{ minHeight: 'min-content' }}>
          {chartConfigs.map((config, index) => {
            // #region agent log
            fetch('http://127.0.0.1:7244/ingest/b733f86e-10e8-4a42-b8ba-7cfb96fa3c70',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'DashboardViewer.tsx:render_chart_'+index,message:'Rendering chart '+index,data:{index,chartType:config.chartType,seriesJSON:JSON.stringify(config.series),optionsXaxis:JSON.stringify(config.options?.xaxis),optionsLabels:config.options?.labels,optionsChart:JSON.stringify(config.options?.chart)},timestamp:Date.now(),sessionId:'debug-session',hypothesisId:'H_RENDER2'})}).catch(()=>{});
            // #endregion
            return (
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
            )
          })}
        </div>
      </div>
    </div>
  )
}
