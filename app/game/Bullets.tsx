import { useFrame } from '@react-three/fiber/webgpu'
import { useRef } from 'react'
import type { Mesh } from 'three'
import { useGame } from './store'
import type { Bullet } from './types'

// Bullets are the emergent layer: spawned at runtime, rendered as declarative R3F
// objects, moved in place by the bullet system and synced here each frame.
const BulletMesh = ({ bullet }: { bullet: Bullet }) => {
  const ref = useRef<Mesh>(null)
  useFrame(() => {
    if (ref.current) ref.current.position.set(bullet.pos[0], bullet.pos[1], bullet.pos[2])
  })
  return (
    <mesh ref={ref} position={[bullet.pos[0], bullet.pos[1], bullet.pos[2]]} scale={0.16}>
      <sphereGeometry />
      <meshBasicMaterial color="#fde047" />
    </mesh>
  )
}

export const Bullets = () => {
  const bullets = useGame(s => s.bullets)
  return (
    <>
      {bullets.map(b => (
        <BulletMesh key={b.id} bullet={b} />
      ))}
    </>
  )
}
