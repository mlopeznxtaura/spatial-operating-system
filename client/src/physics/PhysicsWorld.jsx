/**
 * client/src/physics/PhysicsWorld.jsx
 * Physics layer for the Spatial OS using @react-three/rapier.
 * Panels that are "thrown" by the user obey physics.
 * Floor collider prevents objects falling through.
 */

import { RigidBody, CuboidCollider } from '@react-three/rapier'
import { useRef, forwardRef, useImperativeHandle } from 'react'
import * as THREE from 'three'

// Floor collider — invisible, infinite-ish plane
export function SpatialFloor({ y = 0 }) {
  return (
    <RigidBody type="fixed" position={[0, y, 0]}>
      <CuboidCollider args={[50, 0.05, 50]} />
    </RigidBody>
  )
}

// A physics-enabled panel wrapper — wrap SpatialPanel with this to make it throwable
export const PhysicsPanel = forwardRef(function PhysicsPanel(
  { children, position = [0, 1.5, -1.5], mass = 0.1, restitution = 0.2, friction = 0.8, kinematic = false },
  ref
) {
  const rigidBodyRef = useRef()

  useImperativeHandle(ref, () => ({
    // Throw the panel in a direction (velocity vector)
    throw: (velocity) => {
      rigidBodyRef.current?.setLinvel(
        { x: velocity[0], y: velocity[1], z: velocity[2] },
        true
      )
    },
    // Freeze in place
    freeze: () => {
      rigidBodyRef.current?.setBodyType(1)  // static
    },
    // Unfreeze
    unfreeze: () => {
      rigidBodyRef.current?.setBodyType(0)  // dynamic
    },
    // Teleport to position
    setPosition: (pos) => {
      rigidBodyRef.current?.setTranslation({ x: pos[0], y: pos[1], z: pos[2] }, true)
    },
    getRigidBody: () => rigidBodyRef.current,
  }))

  return (
    <RigidBody
      ref={rigidBodyRef}
      type={kinematic ? 'kinematicPosition' : 'dynamic'}
      position={position}
      mass={mass}
      restitution={restitution}
      friction={friction}
      linearDamping={0.8}
      angularDamping={0.9}
      gravityScale={0}  // panels float by default — set to 1.0 to enable gravity
      colliders={false}
    >
      {/* Collider matches panel size */}
      <CuboidCollider args={[0.4, 0.3, 0.01]} />
      {children}
    </RigidBody>
  )
})

// Wall colliders for room boundaries
export function RoomWalls({ size = [6, 4, 6] }) {
  const [w, h, d] = size
  const t = 0.1  // wall thickness

  return (
    <>
      {/* Left wall */}
      <RigidBody type="fixed" position={[-w / 2, h / 2, 0]}>
        <CuboidCollider args={[t, h / 2, d / 2]} />
      </RigidBody>
      {/* Right wall */}
      <RigidBody type="fixed" position={[w / 2, h / 2, 0]}>
        <CuboidCollider args={[t, h / 2, d / 2]} />
      </RigidBody>
      {/* Back wall */}
      <RigidBody type="fixed" position={[0, h / 2, -d / 2]}>
        <CuboidCollider args={[w / 2, h / 2, t]} />
      </RigidBody>
      {/* Front wall */}
      <RigidBody type="fixed" position={[0, h / 2, d / 2]}>
        <CuboidCollider args={[w / 2, h / 2, t]} />
      </RigidBody>
      {/* Ceiling */}
      <RigidBody type="fixed" position={[0, h, 0]}>
        <CuboidCollider args={[w / 2, t, d / 2]} />
      </RigidBody>
    </>
  )
}

// Hook to apply impulse to a panel (simulate throw from hand tracking release)
export function useThrowPanel(panelRef) {
  const throwPanel = (velocityVector) => {
    panelRef.current?.throw(velocityVector)
  }
  return { throwPanel }
}

// Main PhysicsWorld wrapper (re-export Physics with spatial defaults)
// Usage: wrap <SpatialScene> with this instead of raw <Physics>
export default function PhysicsWorld({ children, debug = false }) {
  return (
    <>
      <SpatialFloor y={0} />
      <RoomWalls />
      {children}
    </>
  )
}

