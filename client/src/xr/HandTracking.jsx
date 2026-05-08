/**
 * client/src/xr/HandTracking.jsx
 * MediaPipe Tasks hand + gaze tracking for WebXR and desktop fallback.
 * Detects pinch (index+thumb) as "select", open palm as "release".
 * Exports useHandTracking hook returning dominant hand pose + active gesture.
 */

import { useRef, useEffect, useState, useCallback } from 'react'
import { useFrame } from '@react-three/fiber'
import { useXR } from '@react-three/xr'
import * as THREE from 'three'
import useSceneStore from '../store/sceneStore'

// Landmark indices (MediaPipe Hand)
const THUMB_TIP = 4
const INDEX_TIP = 8
const MIDDLE_TIP = 12
const WRIST = 0

const PINCH_THRESHOLD = 0.035  // meters — tune per device
const GRAB_THRESHOLD = 0.05

function computePinchDistance(landmarks, tip1, tip2) {
  if (!landmarks || landmarks.length < 21) return Infinity
  const a = landmarks[tip1]
  const b = landmarks[tip2]
  return Math.sqrt(
    Math.pow(a.x - b.x, 2) +
    Math.pow(a.y - b.y, 2) +
    Math.pow(a.z - b.z, 2)
  )
}

function classifyGesture(landmarks) {
  if (!landmarks) return 'none'
  const pinchDist = computePinchDistance(landmarks, THUMB_TIP, INDEX_TIP)
  if (pinchDist < PINCH_THRESHOLD) return 'pinch'
  const grabDist = computePinchDistance(landmarks, THUMB_TIP, MIDDLE_TIP)
  if (grabDist < GRAB_THRESHOLD) return 'grab'
  return 'open'
}

export function useHandTracking() {
  const xr = useXR()
  const { dominantHand } = useSceneStore()
  const [gesture, setGesture] = useState('none')
  const [handPose, setHandPose] = useState(null)
  const prevGesture = useRef('none')
  const gestureCallbacks = useRef({ onPinch: [], onRelease: [], onGrab: [] })

  const onPinch = useCallback((cb) => {
    gestureCallbacks.current.onPinch.push(cb)
    return () => {
      gestureCallbacks.current.onPinch = gestureCallbacks.current.onPinch.filter(f => f !== cb)
    }
  }, [])

  const onRelease = useCallback((cb) => {
    gestureCallbacks.current.onRelease.push(cb)
    return () => {
      gestureCallbacks.current.onRelease = gestureCallbacks.current.onRelease.filter(f => f !== cb)
    }
  }, [])

  useFrame(() => {
    if (!xr.isPresenting || !xr.session) return

    // Read hand joints from WebXR hand tracking API
    const hand = dominantHand === 'right'
      ? xr.session.inputSources?.find(s => s.handedness === 'right')
      : xr.session.inputSources?.find(s => s.handedness === 'left')

    if (!hand?.hand) return

    // Build landmark-like array from XRHand joint poses
    const referenceSpace = xr.referenceSpace
    if (!referenceSpace) return

    const pose = xr.frame?.getPose(
      hand.hand.get('index-finger-tip'),
      referenceSpace
    )

    if (pose) {
      const pos = pose.transform.position
      setHandPose({
        position: new THREE.Vector3(pos.x, pos.y, pos.z),
        handedness: hand.handedness,
      })
    }

    // Detect pinch via index-finger-tip and thumb-tip distance
    const thumbPose = xr.frame?.getPose(hand.hand.get('thumb-tip'), referenceSpace)
    const indexPose = xr.frame?.getPose(hand.hand.get('index-finger-tip'), referenceSpace)

    if (thumbPose && indexPose) {
      const t = thumbPose.transform.position
      const i = indexPose.transform.position
      const dist = Math.sqrt(
        Math.pow(t.x - i.x, 2) + Math.pow(t.y - i.y, 2) + Math.pow(t.z - i.z, 2)
      )

      const newGesture = dist < PINCH_THRESHOLD ? 'pinch' : 'open'

      if (newGesture !== prevGesture.current) {
        prevGesture.current = newGesture
        setGesture(newGesture)

        if (newGesture === 'pinch') {
          gestureCallbacks.current.onPinch.forEach(cb => cb({ handedness: hand.handedness, dist }))
        } else {
          gestureCallbacks.current.onRelease.forEach(cb => cb({ handedness: hand.handedness }))
        }
      }
    }
  })

  return { gesture, handPose, onPinch, onRelease }
}

export default function HandTracking() {
  const { gesture, handPose } = useHandTracking()

  if (!handPose) return null

  return (
    <group position={handPose.position.toArray()}>
      {/* Visual cursor at index fingertip */}
      <mesh>
        <sphereGeometry args={[0.008, 8, 8]} />
        <meshStandardMaterial
          color={gesture === 'pinch' ? '#00ff88' : '#ffffff'}
          emissive={gesture === 'pinch' ? '#00ff44' : '#333333'}
          emissiveIntensity={0.5}
        />
      </mesh>
    </group>
  )
}

