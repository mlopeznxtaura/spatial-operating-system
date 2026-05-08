/**
 * client/src/panels/SpatialPanel.jsx
 * A 3D UI panel that floats in room space.
 * Glass-like material, rounded corners, draggable in XR via pinch grab.
 */

import { useRef, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { RoundedBox, Text } from '@react-three/drei'
import { useSpring, animated } from '@react-spring/three'
import * as THREE from 'three'
import useSceneStore from '../store/sceneStore'

const AnimatedGroup = animated.group

export default function SpatialPanel({
  id,
  title = 'Panel',
  position = [0, 1.5, -1.5],
  rotation = [0, 0, 0],
  size = [0.8, 0.6],
  open = true,
  children,
  onClose,
  onPin,
}) {
  const groupRef = useRef()
  const { updatePanel } = useSceneStore()
  const [hovered, setHovered] = useState(false)
  const [dragging, setDragging] = useState(false)
  const dragOffset = useRef(new THREE.Vector3())
  const { camera, raycaster, gl } = useThree()

  const [width, height] = size
  const depth = 0.012

  // Spring animation for open/close
  const springs = useSpring({
    scale: open ? [1, 1, 1] : [0.01, 0.01, 0.01],
    opacity: open ? 0.88 : 0,
    config: { tension: 280, friction: 24 },
  })

  // Glass material params
  const glassMaterial = {
    color: hovered ? '#3a3aff' : '#1a1a4a',
    transparent: true,
    opacity: open ? (hovered ? 0.75 : 0.6) : 0,
    roughness: 0.05,
    metalness: 0.2,
    envMapIntensity: 1.2,
  }

  const borderMaterial = {
    color: hovered ? '#6060ff' : '#3030aa',
    transparent: true,
    opacity: open ? 0.9 : 0,
    roughness: 0.1,
    metalness: 0.5,
  }

  const handlePointerDown = (e) => {
    e.stopPropagation()
    setDragging(true)
    dragOffset.current.copy(groupRef.current.position).sub(e.point)
  }

  const handlePointerMove = (e) => {
    if (!dragging) return
    e.stopPropagation()
    groupRef.current.position.copy(e.point).add(dragOffset.current)
    updatePanel(id, { position: groupRef.current.position.toArray() })
  }

  const handlePointerUp = (e) => {
    e.stopPropagation()
    setDragging(false)
  }

  return (
    <AnimatedGroup
      ref={groupRef}
      position={position}
      rotation={rotation}
      scale={springs.scale}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerEnter={() => setHovered(true)}
      onPointerLeave={() => { setHovered(false); setDragging(false) }}
    >
      {/* Panel body */}
      <RoundedBox args={[width, height, depth]} radius={0.02} smoothness={4}>
        <meshStandardMaterial {...glassMaterial} />
      </RoundedBox>

      {/* Border glow */}
      <RoundedBox args={[width + 0.006, height + 0.006, depth - 0.002]} radius={0.022} smoothness={4}>
        <meshStandardMaterial {...borderMaterial} side={THREE.BackSide} />
      </RoundedBox>

      {/* Title bar */}
      <mesh position={[0, height / 2 - 0.035, depth / 2 + 0.001]}>
        <planeGeometry args={[width - 0.04, 0.05]} />
        <meshStandardMaterial color="#2a2a6a" transparent opacity={0.7} />
      </mesh>

      {/* Title text */}
      <Text
        position={[-(width / 2) + 0.08, height / 2 - 0.035, depth / 2 + 0.003]}
        fontSize={0.022}
        color="#aaaaff"
        anchorX="left"
        anchorY="middle"
        maxWidth={width - 0.12}
      >
        {title}
      </Text>

      {/* Close button */}
      <mesh
        position={[width / 2 - 0.035, height / 2 - 0.035, depth / 2 + 0.003]}
        onClick={(e) => { e.stopPropagation(); onClose?.() }}
        onPointerEnter={() => setHovered(true)}
      >
        <circleGeometry args={[0.014, 16]} />
        <meshStandardMaterial color="#ff4444" />
      </mesh>

      {/* Pin button */}
      <mesh
        position={[width / 2 - 0.065, height / 2 - 0.035, depth / 2 + 0.003]}
        onClick={(e) => { e.stopPropagation(); onPin?.() }}
      >
        <circleGeometry args={[0.014, 16]} />
        <meshStandardMaterial color="#ffaa00" />
      </mesh>

      {/* Content area placeholder */}
      <group position={[0, -0.025, depth / 2 + 0.002]}>
        {children}
      </group>
    </AnimatedGroup>
  )
}

