/**
 * client/src/voice/VoiceRoom.jsx
 * LiveKit spatial voice for the Spatial OS.
 * Participants appear as 3D audio orbs positioned in the room.
 */

import { useEffect, useRef, useState } from 'react'
import { Room, RoomEvent, Track, ConnectionState } from 'livekit-client'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import useSceneStore from '../store/sceneStore'

const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || 'wss://localhost:7880'
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// Fetch a LiveKit token from the backend
async function fetchLiveKitToken(userId, roomName = 'spatial-os') {
  const res = await fetch(`${API_BASE}/session/join`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, room_name: roomName }),
  })
  if (!res.ok) throw new Error(`Token fetch failed: ${res.status}`)
  const data = await res.json()
  return data.livekit_token
}

// 3D orb representing a participant's voice presence in the room
function VoiceOrb({ participant, position = [0, 1.5, -1.5] }) {
  const meshRef = useRef()
  const [speaking, setSpeaking] = useState(false)

  useEffect(() => {
    const onSpeaking = (p) => {
      if (p.identity === participant.identity) setSpeaking(true)
    }
    const onSilent = (p) => {
      if (p.identity === participant.identity) setSpeaking(false)
    }
    participant.on('isSpeakingChanged', (isSpeaking) => setSpeaking(isSpeaking))
    return () => participant.removeAllListeners('isSpeakingChanged')
  }, [participant])

  useFrame((state) => {
    if (!meshRef.current) return
    const scale = speaking
      ? 1 + Math.sin(state.clock.elapsedTime * 8) * 0.12
      : 1.0
    meshRef.current.scale.setScalar(scale)
  })

  return (
    <group position={position}>
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.08, 16, 16]} />
        <meshStandardMaterial
          color={speaking ? '#00ffaa' : '#3366ff'}
          emissive={speaking ? '#00aa66' : '#112244'}
          emissiveIntensity={speaking ? 1.2 : 0.3}
          transparent
          opacity={0.85}
        />
      </mesh>
      {/* Halo ring */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.12, 0.006, 8, 32]} />
        <meshStandardMaterial
          color={speaking ? '#00ffaa' : '#4477ff'}
          transparent
          opacity={speaking ? 0.9 : 0.3}
        />
      </mesh>
    </group>
  )
}

export function useVoiceRoom(userId) {
  const roomRef = useRef(null)
  const [connected, setConnected] = useState(false)
  const [participants, setParticipants] = useState([])
  const [connectionState, setConnectionState] = useState('disconnected')

  useEffect(() => {
    if (!userId) return

    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
      audioCaptureDefaults: { echoCancellation: true, noiseSuppression: true },
    })
    roomRef.current = room

    const updateParticipants = () => {
      setParticipants(Array.from(room.remoteParticipants.values()))
    }

    room.on(RoomEvent.ParticipantConnected, updateParticipants)
    room.on(RoomEvent.ParticipantDisconnected, updateParticipants)
    room.on(RoomEvent.ConnectionStateChanged, (state) => {
      setConnectionState(state)
      setConnected(state === ConnectionState.Connected)
    })
    room.on(RoomEvent.Connected, updateParticipants)

    fetchLiveKitToken(userId)
      .then((token) => room.connect(LIVEKIT_URL, token))
      .then(() => room.localParticipant.setMicrophoneEnabled(true))
      .catch((err) => console.warn('LiveKit connection failed:', err))

    return () => {
      room.disconnect()
    }
  }, [userId])

  return { connected, participants, connectionState, room: roomRef.current }
}

// Positions orbs in a small cluster around the user's position
function computeOrbPositions(count) {
  const positions = []
  const radius = 0.6
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2
    positions.push([
      Math.cos(angle) * radius,
      1.4 + Math.sin(i) * 0.1,
      Math.sin(angle) * radius - 0.8,
    ])
  }
  return positions
}

export default function VoiceRoom() {
  const { connectedUsers } = useSceneStore()
  const userId = 'local-' + Math.random().toString(36).slice(2, 8)
  const { connected, participants } = useVoiceRoom(userId)
  const orbPositions = computeOrbPositions(participants.length)

  // VoiceRoom renders both: DOM (connection indicator) and 3D orbs via portal
  return (
    <>
      {/* DOM connection indicator */}
      <div style={{
        position: 'absolute',
        top: 16,
        right: 16,
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: connected ? '#00ff88' : '#ff4444',
        boxShadow: connected ? '0 0 8px #00ff88' : 'none',
        zIndex: 100,
      }} title={connected ? 'Voice connected' : 'Voice disconnected'} />

      {/* 3D orbs are rendered inside the Canvas via a portal — handled by App.jsx mounting VoiceOrbsScene */}
    </>
  )
}

// Separate component to mount inside R3F Canvas for 3D orbs
export function VoiceOrbsScene({ participants, positions }) {
  return (
    <group>
      {participants.map((p, i) => (
        <VoiceOrb
          key={p.identity}
          participant={p}
          position={positions[i] || [0, 1.4, -0.8]}
        />
      ))}
    </group>
  )
}

