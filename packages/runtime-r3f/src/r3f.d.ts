// Enables R3F element typings for the WebGPU renderer (per the reference repo's
// r3f-setup skill). Maps R3F's ThreeElements to the `three/webgpu` namespace so
// intrinsic elements like <mesh>/<group> are typed against the WebGPU build.
import type { ThreeToJSXElements } from '@react-three/fiber'
import type * as THREE from 'three/webgpu'

declare module '@react-three/fiber' {
  interface ThreeElements extends ThreeToJSXElements<typeof THREE> {}
}
