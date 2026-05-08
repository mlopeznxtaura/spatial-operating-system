/**
 * client/src/App.jsx
 * React Three Fiber spatial shell.
 * The room IS the UI — panels float in physical space.
 */

import { Canvas } from '@react-three/fiber'
import { XR, createXRStore } from '@react-three/xr'
import { Environment, Grid, OrbitControls } from '@react-three/drei'
import { Physics } from '@react-three/rapier'
import { Suspense } from 'react'
import PanelManager from './panels/PanelManager'
import HandTracking from './xr/HandTracking'
import XRSession from './xr/XRSession'
import VoiceRoom from './voice/VoiceRoom'
import useSceneStore from './store/sceneStore'

const xrStore = createXRStore()

function Room() {
  return (
    <>
      {/* Floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[20, 20]} />
        <meshStandardMaterial color="#1a1a2e" roughness={0.8} metalness={0.1} />
      </mesh>

      {/* Spatial grid overlay */}
      <Grid
        position={[0, 0.001, 0]}
        args={[20, 20]}
        cellSize={0.5}
        cellThickness={0.5}
        cellColor="#3a3a5c"
        sectionSize={2}
        sectionThickness={1}
        sectionColor="#5a5a9c"
        fadeDistance={10}
        fadeStrength={1}
        followCamera={false}
        infiniteGrid={false}
      />

      {/* Ambient environment */}
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 8, 5]} intensity={0.8} castShadow />
      <Environment preset="city" background={false} />
    </>
  )
}

function SpatialScene() {
  return (
    <Physics gravity={[0, -9.81, 0]}>
      <Room />
      <PanelManager />
      <HandTracking />
    </Physics>
  )
}

export default function App() {
  const { streamState } = useSceneStore()

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#0a0a1a' }}>
      {/* XR entry button */}
      <XRSession xrStore={xrStore} />

      {/* Stream status indicator */}
      {streamState !== 'running' && (
        <div style={{
          position: 'absolute',
          top: 16,
          left: 16,
          color: '#888',
          fontSize: 12,
          fontFamily: 'monospace',
          zIndex: 10,
        }}>
          stream: {streamState}
        </div>
      )}

      {/* Spatial voice */}
      <VoiceRoom />

      {/* Main 3D canvas */}
      <Canvas
        shadows
        camera={{ position: [0, 1.6, 3], fov: 75, near: 0.01, far: 100 }}
        gl={{ antialias: true, alpha: false }}
      >
        <XR store={xrStore}>
          <Suspense fallback={null}>
            <SpatialScene />
          </Suspense>
        </XR>
        <OrbitControls
          target={[0, 1.0, 0]}
          maxPolarAngle={Math.PI / 2}
          enableDamping
          dampingFactor={0.05}
        />
      </Canvas>
    </div>
  )
}

