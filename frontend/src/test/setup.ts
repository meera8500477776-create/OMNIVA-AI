import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
class ResizeObserverMock { observe() {} unobserve() {} disconnect() {} }
vi.stubGlobal('ResizeObserver', ResizeObserverMock)
Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', { value: () => ({ clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, set lineWidth(_value:number) {}, set lineCap(_value:string) {}, set lineJoin(_value:string) {}, set strokeStyle(_value:string) {} }) })
afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear() })
