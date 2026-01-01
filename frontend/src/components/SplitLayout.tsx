import React, { useEffect } from 'react'
import { PanelGroup, Panel, PanelResizeHandle } from 'react-resizable-panels'
import { useWorkspaceStore } from '../store/workspaceStore'
import { ChatInterface } from './ChatInterface'
import { WorkspacePanel } from './WorkspacePanel'

export function SplitLayout() {
  const { panelSize, setPanelSize, loadFromLocalStorage } = useWorkspaceStore()

  useEffect(() => {
    loadFromLocalStorage()
  }, [loadFromLocalStorage])

  // Always show split layout: left panel 33% (1/3) by default, right panel 67% (2/3)
  // Use saved panelSize if available, otherwise default to 33
  return (
    <PanelGroup direction="horizontal" className="h-full w-full">
      <Panel
        defaultSize={panelSize || 33}
        minSize={25}
        maxSize={50}
        onResize={(size) => setPanelSize(size)}
      >
        <ChatInterface />
      </Panel>
      <PanelResizeHandle 
        className="bg-slate-300 dark:bg-slate-600 hover:bg-blue-500 transition-colors cursor-col-resize"
        style={{ minWidth: '2px', width: '2px' }}
      />
      <Panel minSize={50}>
        <WorkspacePanel />
      </Panel>
    </PanelGroup>
  )
}

