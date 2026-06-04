import type { Entity, Vec3 } from '@blenjs/core'
import { Clone, useGLTF } from '@react-three/drei/webgpu'
import { useFrame } from '@react-three/fiber/webgpu'
import { useRef, type ReactNode } from 'react'
import { Color, Euler, SRGBColorSpace, Vector3, type Group, type Mesh, type Object3D } from 'three'
import prefabsJson from '../../generated/prefabs.json'
import type { ColliderData, LightData, MaterialData, ModelData, PickupData } from '../components'

const transformOf = (e: Entity) => e.components.Transform as { pos: number[]; scale?: number[] } | undefined

const materialOf = (e: Entity) => e.components.Material as MaterialData | undefined

// Authored RGB (each channel 0–1) is interpreted as sRGB — what you set in a colour
// picker is what you see — so values match the old hex literals (three otherwise treats
// raw Color(r,g,b) as linear and renders them noticeably brighter).
const toColor = (c: readonly number[]) => new Color().setRGB(c[0], c[1], c[2], SRGBColorSpace)

/**
 * Surface material for a parametric primitive. With an authored `Material` it uses
 * that colour/opacity — shaded by the scene lights unless `unlit` — otherwise it
 * falls back to the component's built-in flat colour (the old hardcoded look).
 */
const SurfaceMaterial = ({ mat, fallback }: { mat?: MaterialData; fallback: string }) => {
  if (!mat) return <meshBasicMaterial color={fallback} />
  const color = toColor(mat.color as Vec3)
  const transparent = mat.opacity < 1
  return mat.unlit ? (
    <meshBasicMaterial color={color} transparent={transparent} opacity={mat.opacity} />
  ) : (
    <meshStandardMaterial color={color} transparent={transparent} opacity={mat.opacity} />
  )
}

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
      <SurfaceMaterial mat={materialOf(entity)} fallback={color} />
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
const PlatformMesh = ({ pos, scale, mat }: { pos: number[]; scale: number[]; mat?: MaterialData }) => (
  <mesh position={[pos[0], pos[1], pos[2]]} scale={[scale[0], scale[1], scale[2]]}>
    <boxGeometry />
    <SurfaceMaterial mat={mat} fallback="#39424f" />
  </mesh>
)

// A Collider drawn in its actual shape, so the blockout matches the physics and the Blender
// collider overlay: box → cuboid, sphere → ball (r = ½·max scale), capsule → pill along the
// up axis (r = ½·max(x,y), height = scale.z). Sizing mirrors physics.ts exactly.
const ColliderMesh = ({ e, pos, scale, mat }: { e: Entity; pos: number[]; scale: number[]; mat?: MaterialData }) => {
  const shape = (e.components.Collider as ColliderData).shape
  if (shape === 'sphere') {
    return (
      <mesh position={[pos[0], pos[1], pos[2]]}>
        <sphereGeometry args={[0.5 * Math.max(scale[0], scale[1], scale[2]), 24, 16]} />
        <SurfaceMaterial mat={mat} fallback="#39424f" />
      </mesh>
    )
  }
  if (shape === 'capsule') {
    const r = 0.5 * Math.max(scale[0], scale[1])
    const rot = (e.components.Transform as { rot?: Vec3 } | undefined)?.rot ?? [0, 0, 0]
    return (
      <group position={[pos[0], pos[1], pos[2]]} rotation={[rot[0], rot[1], rot[2]]}>
        {/* three's CapsuleGeometry runs along Y; rotate it onto the Z-up world axis. */}
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <capsuleGeometry args={[r, Math.max(0, scale[2] - 2 * r), 6, 16]} />
          <SurfaceMaterial mat={mat} fallback="#39424f" />
        </mesh>
      </group>
    )
  }
  return <PlatformMesh pos={pos} scale={scale} mat={mat} />
}

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
      <SurfaceMaterial mat={materialOf(entity)} fallback={isGem ? '#22d3ee' : '#ffd23f'} />
    </mesh>
  )
}

const GoalMesh = ({ pos, mat }: { pos: number[]; mat?: MaterialData }) => (
  <mesh position={[pos[0], pos[1], pos[2] + 0.6]} scale={[0.5, 0.5, 2.4]}>
    <boxGeometry />
    <SurfaceMaterial mat={mat} fallback="#d946ef" />
  </mesh>
)

/**
 * Maps one entity to its R3F object. A `Light` is the scene's authored lighting; a
 * `Model` component (from a prefab or a single-use external mesh) renders the loaded
 * glTF, wrapped by behavior: moving (Player/Enemy/Patrol) → Dynamic, Pickup →
 * spinning, else static. Entities without a model fall back to the parametric
 * primitives (platforms, goal, and un-modelled player/enemy/pickup), whose surface
 * colour an authored `Material` overrides. Waypoints, the spawn marker, and the
 * camera render nothing.
 */
export const renderEntity = (e: Entity): ReactNode => {
  const t = transformOf(e)
  if (!t) return null
  const pos = t.pos
  const scale = t.scale ?? [1, 1, 1]

  if (e.components.Light) {
    const l = e.components.Light as LightData
    const color = toColor(l.color as Vec3)
    if (l.type === 'ambient') return <ambientLight color={color} intensity={l.intensity} />
    // A directional light shines along the entity's local -Z (the Blender Sun convention),
    // derived from Transform.rot — so the in-game sun matches the rotated Sun lamp in the
    // viewport, and rotating that lamp in Blender drives the game light. three's directionalLight
    // travels from its position toward the origin, so we place it at -direction.
    const rot = (e.components.Transform as { rot?: Vec3 } | undefined)?.rot ?? [0, 0, 0]
    const dir = new Vector3(0, 0, -1).applyEuler(new Euler(rot[0], rot[1], rot[2], 'XYZ'))
    return <directionalLight color={color} intensity={l.intensity} position={[-dir.x * 10, -dir.y * 10, -dir.z * 10]} />
  }

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
  if (e.components.Goal) return <GoalMesh pos={pos} mat={materialOf(e)} />
  // A Trigger is an invisible logic volume by default; give it a Material to show its box (a
  // visible pad/zone). Kill volumes stay invisible; a "rune" switch can opt into a translucent box.
  if (e.components.Trigger) {
    const mat = materialOf(e)
    return mat ? <PlatformMesh pos={pos} scale={scale} mat={mat} /> : null
  }
  if (e.components.Collider) return <ColliderMesh e={e} pos={pos} scale={scale} mat={materialOf(e)} />
  return null
}
