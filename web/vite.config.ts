import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the API runs separately (uvicorn on :8000); in production one
// address serves both: `/` is the built web, `/api` is the server (decision 0010).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rolldownOptions: {
      output: {
        // Libraries change less often than the app: a separate chunk stays cached.
        codeSplitting: {
          groups: [
            { name: 'markdown', test: /node_modules[\\/](react-markdown|remark-|mdast-|micromark|unified|hast-|unist-|vfile)/ },
            { name: 'vendor', test: /node_modules/ },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
