import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// During development the API runs separately (uvicorn api.main:app on :8000);
// in production FastAPI serves this build, so the same paths work unchanged.
const API = process.env.HEAT_API ?? 'http://127.0.0.1:8000'
const apiPaths = ['/status', '/days', '/wards', '/ward', '/forecast', '/events', '/config', '/priorities', '/cooling', '/allocation']

export default defineConfig({
  plugins: [react()],
  server: { proxy: Object.fromEntries(apiPaths.map((p) => [p, API])) },
})
