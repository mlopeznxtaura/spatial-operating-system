/**
 * client/src/store/sceneStore.js
 * Zustand store for the Spatial OS scene state.
 * Uses immer middleware for immutable state updates.
 */

import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { subscribeWithSelector } from 'zustand/middleware'

const useSceneStore = create(
  subscribeWithSelector(
    immer((set, get) => ({
      // Scene state
      panels: [],
      selectedPrims: [],
      currentTimeCode: 0,
      activeVariants: {},
      streamState: 'stopped', // 'stopped' | 'starting' | 'running' | 'error'
      connectedUsers: [],
      roomScale: 1.0,
      loadedUsdPath: null,

      // XR state
      xrActive: false,
      xrReferenceSpace: 'local-floor',
      dominantHand: 'right',

      // Panel actions
      addPanel: (panel) =>
        set((state) => {
          state.panels.push({
            id: panel.id || crypto.randomUUID(),
            title: panel.title || 'Panel',
            position: panel.position || [0, 1.5, -1.5],
            rotation: panel.rotation || [0, 0, 0],
            size: panel.size || [0.8, 0.6],
            open: true,
            pinned: false,
            content: panel.content || null,
            ...panel,
          })
        }),

      removePanel: (id) =>
        set((state) => {
          state.panels = state.panels.filter((p) => p.id !== id)
        }),

      updatePanel: (id, updates) =>
        set((state) => {
          const panel = state.panels.find((p) => p.id === id)
          if (panel) Object.assign(panel, updates)
        }),

      togglePanel: (id) =>
        set((state) => {
          const panel = state.panels.find((p) => p.id === id)
          if (panel) panel.open = !panel.open
        }),

      pinPanel: (id, pinned) =>
        set((state) => {
          const panel = state.panels.find((p) => p.id === id)
          if (panel) panel.pinned = pinned
        }),

      // Prim selection
      selectPrim: (primPath, multi = false) =>
        set((state) => {
          if (!primPath) {
            state.selectedPrims = []
          } else if (multi) {
            const idx = state.selectedPrims.indexOf(primPath)
            if (idx >= 0) {
              state.selectedPrims.splice(idx, 1)
            } else {
              state.selectedPrims.push(primPath)
            }
          } else {
            state.selectedPrims = [primPath]
          }
        }),

      clearSelection: () =>
        set((state) => {
          state.selectedPrims = []
        }),

      // Timeline
      setTimeCode: (timeCode) =>
        set((state) => {
          state.currentTimeCode = timeCode
        }),

      // Variants
      setVariant: (primPath, variantSet, variant) =>
        set((state) => {
          state.activeVariants[`${primPath}:${variantSet}`] = variant
        }),

      // Stream
      setStreamState: (streamState) =>
        set((state) => {
          state.streamState = streamState
        }),

      setLoadedUsdPath: (path) =>
        set((state) => {
          state.loadedUsdPath = path
        }),

      // Users
      setConnectedUsers: (users) =>
        set((state) => {
          state.connectedUsers = users
        }),

      addUser: (user) =>
        set((state) => {
          if (!state.connectedUsers.find((u) => u.user_id === user.user_id)) {
            state.connectedUsers.push(user)
          }
        }),

      removeUser: (userId) =>
        set((state) => {
          state.connectedUsers = state.connectedUsers.filter(
            (u) => u.user_id !== userId
          )
        }),

      updateUserCamera: (userId, position, target) =>
        set((state) => {
          const user = state.connectedUsers.find((u) => u.user_id === userId)
          if (user) {
            user.camera_position = position
            user.camera_target = target
          }
        }),

      // XR
      setXrActive: (active) =>
        set((state) => {
          state.xrActive = active
        }),

      setDominantHand: (hand) =>
        set((state) => {
          state.dominantHand = hand
        }),

      setRoomScale: (scale) =>
        set((state) => {
          state.roomScale = scale
        }),

      // Derived
      getOpenPanels: () => get().panels.filter((p) => p.open),
      getPinnedPanels: () => get().panels.filter((p) => p.pinned),
      isSelected: (primPath) => get().selectedPrims.includes(primPath),
    }))
  )
)

export default useSceneStore

