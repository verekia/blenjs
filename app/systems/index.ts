// Component-attached systems (behaviors).
export { playerController } from './playerController'
export { patrol } from './patrol'
export { pickup } from './pickup'
export { trigger } from './trigger'

// Runtime-only systems (the emergent layer — not tied to a registry component).
export { shootStep, bulletStep } from './shoot'
export { goalStep } from './goal'
