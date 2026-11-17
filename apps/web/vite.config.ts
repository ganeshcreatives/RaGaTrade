import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:4000", changeOrigin: true },
      "/health": { target: "http://localhost:4000", changeOrigin: true },
    },
  },
  define: { "import.meta.env.VITE_API_URL": JSON.stringify(process.env.VITE_API_URL ?? "") },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const moduleId = id.replace(/\\/g, "/");
          if (moduleId.includes("/node_modules/recharts/")) return "charts";
          if (moduleId.includes("/node_modules/lucide-react/")) return "icons";
          if (moduleId.includes("/node_modules/react/") || moduleId.includes("/node_modules/react-dom/") || moduleId.includes("/node_modules/scheduler/")) return "react-vendor";
        },
      },
    },
  },
});
