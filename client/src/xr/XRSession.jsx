/**
 * client/src/xr/XRSession.jsx
 * WebXR session manager using @react-three/xr.
 * Handles enter/exit XR, reference space, controller/hand tracking state.
 */

import { useXR, useXRSessionVisibilityState } from '@react-three/xr'
import { useEffect, useCallback } from 'react'
import useSceneStore from '../store/sceneStore'

export function useXRSession() {
  const xr = useXR()
  const { setXrActive } = useSceneStore()
  const visibilityState = useXRSessionVisibilityState()

  useEffect(() => {
    const isActive = xr.isPresenting
    setXrActive(isActive)
  }, [xr.isPresenting, setXrActive])

  const enterXR = useCallback(async (mode = 'immersive-vr') => {
    try {
      if (!navigator.xr) {
        console.warn('WebXR not available in this browser')
        return false
      }
      const supported = await navigator.xr.isSessionSupported(mode)
      if (!supported) {
        console.warn(`XR mode not supported: ${mode}`)
        return false
      }
      await xr.session?.end()
      return true
    } catch (err) {
      console.error('XR session error:', err)
      return false
    }
  }, [xr])

  return {
    isPresenting: xr.isPresenting,
    session: xr.session,
    visibilityState,
    enterXR,
    controllers: xr.controllers,
    hands: xr.hands,
  }
}

export default function XRSession({ xrStore }) {
  const { xrActive } = useSceneStore()

  const handleEnterVR = async () => {
    xrStore.enterVR()
  }

  const handleEnterAR = async () => {
    xrStore.enterAR()
  }

  return (
    <div style={{
      position: 'absolute',
      bottom: 24,
      left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex',
      gap: 12,
      zIndex: 100,
    }}>
      {!xrActive && (
        <>
          <button
            onClick={handleEnterVR}
            style={{
              padding: '10px 24px',
              background: 'rgba(80, 80, 200, 0.85)',
              color: '#fff',
              border: '1px solid rgba(120,120,255,0.4)',
              borderRadius: 8,
              cursor: 'pointer',
              fontFamily: 'monospace',
              fontSize: 13,
              backdropFilter: 'blur(8px)',
            }}
          >
            Enter VR
          </button>
          <button
            onClick={handleEnterAR}
            style={{
              padding: '10px 24px',
              background: 'rgba(40, 160, 100, 0.85)',
              color: '#fff',
              border: '1px solid rgba(60,200,120,0.4)',
              borderRadius: 8,
              cursor: 'pointer',
              fontFamily: 'monospace',
              fontSize: 13,
              backdropFilter: 'blur(8px)',
            }}
          >
            Enter AR
          </button>
        </>
      )}
      {xrActive && (
        <div style={{
          padding: '8px 16px',
          background: 'rgba(80, 200, 80, 0.2)',
          color: '#4f4',
          border: '1px solid rgba(80,200,80,0.3)',
          borderRadius: 8,
          fontFamily: 'monospace',
          fontSize: 12,
        }}>
          XR Active
        </div>
      )}
    </div>
  )
}

