/**
 * client/src/panels/PanelManager.jsx
 * Manages layout of all SpatialPanels in the room.
 * Arranges panels in a semicircle around the user at eye level.
 */

import { useMemo, useCallback } from 'react'
import useSceneStore from '../store/sceneStore'
import SpatialPanel from './SpatialPanel'

const SEMICIRCLE_RADIUS = 1.8
const EYE_HEIGHT = 1.5
const ARC_SPREAD = Math.PI * 0.75  // 135 degrees total spread

function computeSemicirclePositions(count, radius = SEMICIRCLE_RADIUS) {
  if (count === 0) return []
  if (count === 1) return [{ position: [0, EYE_HEIGHT, -radius], rotation: [0, 0, 0] }]

  const positions = []
  const startAngle = -ARC_SPREAD / 2
  const step = ARC_SPREAD / (count - 1)

  for (let i = 0; i < count; i++) {
    const angle = startAngle + step * i
    const x = Math.sin(angle) * radius
    const z = -Math.cos(angle) * radius
    const rotY = -angle  // face the user
    positions.push({
      position: [x, EYE_HEIGHT, z],
      rotation: [0, rotY, 0],
    })
  }

  return positions
}

export function usePanelManager() {
  const {
    panels,
    addPanel,
    removePanel,
    updatePanel,
    togglePanel,
    pinPanel,
    getOpenPanels,
  } = useSceneStore()

  const openPanel = useCallback((config) => {
    addPanel(config)
  }, [addPanel])

  const closePanel = useCallback((id) => {
    removePanel(id)
  }, [removePanel])

  const repositionAll = useCallback(() => {
    const unpinned = panels.filter(p => !p.pinned)
    const positions = computeSemicirclePositions(unpinned.length)
    unpinned.forEach((panel, i) => {
      updatePanel(panel.id, {
        position: positions[i].position,
        rotation: positions[i].rotation,
      })
    })
  }, [panels, updatePanel])

  return { panels, openPanel, closePanel, togglePanel, pinPanel, repositionAll }
}

export default function PanelManager() {
  const { panels, removePanel, togglePanel, pinPanel, updatePanel } = useSceneStore()

  const unpinnedOpen = useMemo(() => panels.filter(p => p.open && !p.pinned), [panels])
  const pinned = useMemo(() => panels.filter(p => p.pinned), [panels])

  const semicirclePositions = useMemo(
    () => computeSemicirclePositions(unpinnedOpen.length),
    [unpinnedOpen.length]
  )

  return (
    <group>
      {/* Unpinned panels arranged in semicircle */}
      {unpinnedOpen.map((panel, i) => (
        <SpatialPanel
          key={panel.id}
          id={panel.id}
          title={panel.title}
          position={panel.position || semicirclePositions[i]?.position}
          rotation={panel.rotation || semicirclePositions[i]?.rotation}
          size={panel.size}
          open={panel.open}
          onClose={() => removePanel(panel.id)}
          onPin={() => pinPanel(panel.id, true)}
        >
          {panel.content}
        </SpatialPanel>
      ))}

      {/* Pinned panels stay at their last position */}
      {pinned.map((panel) => (
        <SpatialPanel
          key={panel.id}
          id={panel.id}
          title={panel.title}
          position={panel.position}
          rotation={panel.rotation}
          size={panel.size}
          open={panel.open}
          onClose={() => removePanel(panel.id)}
          onPin={() => pinPanel(panel.id, false)}
        >
          {panel.content}
        </SpatialPanel>
      ))}
    </group>
  )
}

