import type { Entity, Vec3 } from '@blenjs/core'
import { useFrame } from '@react-three/fiber/webgpu'
import { useRef, type ReactNode } from 'react'
import type { Mesh, Object3D } from 'three'
import type { PickupData } from '../components'

const transformOf = (e: Entity) => e.components.Transform as { pos: number[]; scale?: number[] } | undefined

/**
 * Smart wrapper for entities that MOVE (player, enemies). Captures the Three.js
 * Object3D on the entity (reference repo's ModelContainer idiom) so the sync step
 * in GameSystems can drive its position. The initial `position` avoids a one-frame
 * flash at the origin before the first sync.
 */
const Dynamic = ({ entity, children }: { entity: Entity; children: ReactNode }) => {
  const pos = transformOf(entity)?.pos ?? [0, 0, 0]
  return (
    <group
      position={[pos[0], pos[1], pos[2]]}
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

// Static blockout platform: positioned + sized directly from the Transform.
const PlatformMesh = ({ pos, scale }: { pos: number[]; scale: number[] }) => (
  <mesh position={[pos[0], pos[1], pos[2]]} scale={[scale[0], scale[1], scale[2]]}>
    <boxGeometry />
    <meshBasicMaterial color="#39424f" />
  </mesh>
)

// Collectible — spins for shimmer (purely visual useFrame, allowed by the
// architecture skill). Gems are cyan octahedra; coins are gold spheres.
const PickupMesh = ({ entity }: { entity: Entity }) => {
  const ref = useRef<Mesh>(null)
  const pos = transformOf(entity)?.pos ?? [0, 0, 0]
  const isGem = (entity.components.Pickup as PickupData).kind === 'gem'
  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.y += dt * 2.2
  })
  return (
    <mesh ref={ref} position={[pos[0], pos[1], pos[2]]}>
      {isGem ? <octahedronGeometry args={[0.32]} /> : <sphereGeometry args={[0.28, 16, 16]} />}
      <meshBasicMaterial color={isGem ? '#22d3ee' : '#ffd23f'} />
    </mesh>
  )
}

const GoalMesh = ({ pos }: { pos: number[] }) => (
  <mesh position={[pos[0], pos[1] + 0.6, pos[2]]} scale={[0.5, 2.4, 0.5]}>
    <boxGeometry />
    <meshBasicMaterial color="#d946ef" />
  </mesh>
)

/**
 * Maps one entity to its R3F object based on which components it carries. This is
 * the application's visual vocabulary; the generic mapping/keying lives in
 * `@blenjs/runtime-r3f`'s <Level>. Waypoints and the spawn marker render nothing.
 */
export const renderEntity = (e: Entity): ReactNode => {
  const t = transformOf(e)
  if (!t) return null
  const pos = t.pos
  const scale = t.scale ?? [1, 1, 1]

  if (e.components.Player) return <DynamicBox entity={e} color="#34d399" size={[0.8, 1, 0.8]} />
  if (e.components.Enemy) return <DynamicBox entity={e} color="#ef4444" size={[0.8, 0.8, 0.8]} />
  if (e.components.Pickup) return <PickupMesh entity={e} />
  if (e.components.Goal) return <GoalMesh pos={pos} />
  if (e.components.Collider) return <PlatformMesh pos={pos} scale={scale} />
  return null
}
