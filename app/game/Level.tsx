import type { Entity, Vec3 } from '@blenjs/core'
import { Clone, useGLTF } from '@react-three/drei/webgpu'
import { useFrame } from '@react-three/fiber/webgpu'
import { useRef, type ReactNode } from 'react'
import type { Group, Mesh, Object3D } from 'three'
import prefabsJson from '../../generated/prefabs.json'
import type { ModelData, PickupData } from '../components'

const transformOf = (e: Entity) => e.components.Transform as { pos: number[]; scale?: number[] } | undefined

// A Model's `src` is a bare name (e.g. "coin"); the runtime loads the built glTF at
// /assets/<src>.glb (prefabs/<src>.blend → app/public/assets/<src>.glb via build:models).
// They are exported Z-up (export_yup=False) so they drop straight into the Z-up world
// with no rotation correction.
const assetUrl = (src: string) => `/assets/${src}.glb`

// Warm the loader cache for every prefab model so instances pop in without a waterfall.
for (const def of Object.values(prefabsJson as Record<string, { components?: Record<string, { src?: string }> }>)) {
  const src = def.components?.Model?.src
  if (src) useGLTF.preload(assetUrl(src))
}

/**
 * Smart wrapper for entities that MOVE (player, enemies). Captures the Three.js
 * Object3D on the entity (reference repo's ModelContainer idiom) so the sync step
 * in GameSystems can drive its position. The initial `position` avoids a one-frame
 * flash at the origin before the first sync. `scale` is set once (the sync step only
 * writes position/rotation, never scale) so a scaled model keeps its size.
 */
const Dynamic = ({ entity, scale, children }: { entity: Entity; scale?: number[]; children: ReactNode }) => {
  const pos = transformOf(entity)?.pos ?? [0, 0, 0]
  return (
    <group
      position={[pos[0], pos[1], pos[2]]}
      scale={scale ? [scale[0], scale[1], scale[2]] : undefined}
      ref={(ref: Object3D | null) => {
        if (!ref) return
        entity.three = ref
        return () => {
          entity.three = undefined
        }
      }}
    >
      {children}
    </group>
  )
}

const DynamicBox = ({ entity, color, size }: { entity: Entity; color: string; size: Vec3 }) => (
  <Dynamic entity={entity}>
    <mesh scale={size}>
      <boxGeometry />
      <meshBasicMaterial color={color} />
    </mesh>
  </Dynamic>
)

// Loads a built glTF and clones it so many instances of one asset share a single
// loaded scene graph. `useGLTF` suspends until loaded (handled by <Suspense> in Game).
const ModelView = ({ src }: { src: string }) => {
  const { scene } = useGLTF(assetUrl(src))
  return <Clone object={scene} />
}

// Moving model-backed entity (player, patrolling enemy): the model under a Dynamic
// capture group the systems drive.
const DynamicModel = ({ entity, src, scale }: { entity: Entity; src: string; scale: number[] }) => (
  <Dynamic entity={entity} scale={scale}>
    <ModelView src={src} />
  </Dynamic>
)

// Collectible model (coin, gem): positioned + scaled from the Transform, spinning on
// the up axis for shimmer (the visual-only useFrame the architecture allows).
const SpinModel = ({ src, pos, scale }: { src: string; pos: number[]; scale: number[] }) => {
  const ref = useRef<Group>(null)
  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.z += dt * 2.2 // spin around the up axis (Z-up)
  })
  return (
    <group ref={ref} position={[pos[0], pos[1], pos[2]]} scale={[scale[0], scale[1], scale[2]]}>
      <ModelView src={src} />
    </group>
  )
}

// Static model-backed entity (a single-use external prop with no behavior).
const StaticModel = ({ src, pos, scale }: { src: string; pos: number[]; scale: number[] }) => (
  <group position={[pos[0], pos[1], pos[2]]} scale={[scale[0], scale[1], scale[2]]}>
    <ModelView src={src} />
  </group>
)

// Static blockout platform: positioned + sized directly from the Transform.
const PlatformMesh = ({ pos, scale }: { pos: number[]; scale: number[] }) => (
  <mesh position={[pos[0], pos[1], pos[2]]} scale={[scale[0], scale[1], scale[2]]}>
    <boxGeometry />
    <meshBasicMaterial color="#39424f" />
  </mesh>
)

// Collectible primitive — fallback for a Pickup with no model. Gems are cyan
// octahedra; coins are gold spheres.
const PickupMesh = ({ entity }: { entity: Entity }) => {
  const ref = useRef<Mesh>(null)
  const pos = transformOf(entity)?.pos ?? [0, 0, 0]
  const isGem = (entity.components.Pickup as PickupData).kind === 'gem'
  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.z += dt * 2.2 // spin around the up axis (Z-up)
  })
  return (
    <mesh ref={ref} position={[pos[0], pos[1], pos[2]]}>
      {isGem ? <octahedronGeometry args={[0.32]} /> : <sphereGeometry args={[0.28, 16, 16]} />}
      <meshBasicMaterial color={isGem ? '#22d3ee' : '#ffd23f'} />
    </mesh>
  )
}

const GoalMesh = ({ pos }: { pos: number[] }) => (
  <mesh position={[pos[0], pos[1], pos[2] + 0.6]} scale={[0.5, 0.5, 2.4]}>
    <boxGeometry />
    <meshBasicMaterial color="#d946ef" />
  </mesh>
)

/**
 * Maps one entity to its R3F object. A `Model` component (from a prefab or a
 * single-use external mesh) renders the loaded glTF, wrapped by behavior:
 * moving (Player/Enemy/Patrol) → Dynamic, Pickup → spinning, else static. Entities
 * without a model fall back to the parametric primitives (platforms, goal, and
 * un-modelled player/enemy/pickup). Waypoints and the spawn marker render nothing.
 */
export const renderEntity = (e: Entity): ReactNode => {
  const t = transformOf(e)
  if (!t) return null
  const pos = t.pos
  const scale = t.scale ?? [1, 1, 1]

  if (e.components.Model) {
    const src = (e.components.Model as ModelData).src
    if (src) {
      if (e.components.Player || e.components.Enemy || e.components.Patrol) {
        return <DynamicModel entity={e} src={src} scale={scale} />
      }
      if (e.components.Pickup) return <SpinModel src={src} pos={pos} scale={scale} />
      return <StaticModel src={src} pos={pos} scale={scale} />
    }
  }

  if (e.components.Player) return <DynamicBox entity={e} color="#34d399" size={[0.8, 0.8, 1]} />
  if (e.components.Enemy) return <DynamicBox entity={e} color="#ef4444" size={[0.8, 0.8, 0.8]} />
  if (e.components.Pickup) return <PickupMesh entity={e} />
  if (e.components.Goal) return <GoalMesh pos={pos} />
  if (e.components.Collider) return <PlatformMesh pos={pos} scale={scale} />
  return null
}
