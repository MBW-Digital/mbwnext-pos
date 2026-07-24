// vite.config.js
import path from "node:path";
import { promises as fs } from "node:fs";
import vue from "file:///home/mbw12345/ha_vang/apps/pos_next/POS/node_modules/@vitejs/plugin-vue/dist/index.mjs";
import frappeui from "file:///home/mbw12345/ha_vang/apps/pos_next/POS/node_modules/frappe-ui/vite/index.js";
import { defineConfig } from "file:///home/mbw12345/ha_vang/apps/pos_next/POS/node_modules/vite/dist/node/index.js";
import { VitePWA } from "file:///home/mbw12345/ha_vang/apps/pos_next/POS/node_modules/vite-plugin-pwa/dist/index.js";
import { viteStaticCopy } from "file:///home/mbw12345/ha_vang/apps/pos_next/POS/node_modules/vite-plugin-static-copy/dist/index.js";
var __vite_injected_original_dirname = "/home/mbw12345/ha_vang/apps/pos_next/POS";
var buildVersion = process.env.POS_NEXT_BUILD_VERSION || Date.now().toString();
var enableSourceMap = process.env.POS_NEXT_ENABLE_SOURCEMAP === "true";
function posNextBuildVersionPlugin(version) {
  return {
    name: "pos-next-build-version",
    apply: "build",
    async writeBundle() {
      const versionFile = path.resolve(__vite_injected_original_dirname, "../pos_next/public/pos/version.json");
      await fs.mkdir(path.dirname(versionFile), { recursive: true });
      await fs.writeFile(
        versionFile,
        JSON.stringify(
          {
            version,
            timestamp: (/* @__PURE__ */ new Date()).toISOString(),
            buildDate: (/* @__PURE__ */ new Date()).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric"
            })
          },
          null,
          2
        ),
        "utf8"
      );
      console.log(`
\u2713 Build version written: ${version}`);
    }
  };
}
var vite_config_default = defineConfig({
  plugins: [
    posNextBuildVersionPlugin(buildVersion),
    frappeui({
      frappeProxy: true,
      jinjaBootData: true,
      lucideIcons: true,
      buildConfig: {
        indexHtmlPath: "../pos_next/www/pos.html",
        outDir: "../pos_next/public/pos",
        emptyOutDir: true,
        sourcemap: enableSourceMap
      }
    }),
    vue(),
    viteStaticCopy({
      targets: [
        {
          src: "src/workers",
          dest: "."
        }
      ]
    }),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: null,
      includeAssets: ["favicon.png", "icon.svg", "icon-maskable.svg"],
      manifest: {
        id: "/pos/",
        name: "MBW Next POS",
        short_name: "MBW Next POS",
        description: "Point of Sale system with real-time billing, stock management, and offline support",
        theme_color: "#c4161c",
        background_color: "#ffffff",
        display: "standalone",
        scope: "/pos/",
        start_url: "/pos",
        icons: [
          {
            src: "/assets/pos_next/pos/icon.svg",
            sizes: "192x192",
            type: "image/svg+xml",
            purpose: "any"
          },
          {
            src: "/assets/pos_next/pos/icon.svg",
            sizes: "512x512",
            type: "image/svg+xml",
            purpose: "any"
          },
          {
            src: "/assets/pos_next/pos/icon-maskable.svg",
            sizes: "192x192",
            type: "image/svg+xml",
            purpose: "maskable"
          },
          {
            src: "/assets/pos_next/pos/icon-maskable.svg",
            sizes: "512x512",
            type: "image/svg+xml",
            purpose: "maskable"
          }
        ]
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff,woff2}"],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        // 3 MB
        navigateFallback: null,
        navigateFallbackDenylist: [/^\/api/, /^\/app/],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "google-fonts-cache",
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365
                // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200]
              }
            }
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "gstatic-fonts-cache",
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365
                // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200]
              }
            }
          },
          {
            urlPattern: /\/assets\/pos_next\/pos\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "pos-assets-cache",
              expiration: {
                maxEntries: 500,
                maxAgeSeconds: 60 * 60 * 24 * 30
                // 30 days
              }
            }
          },
          // Cache product images with StaleWhileRevalidate for better UX
          {
            urlPattern: /\/files\/.*\.(jpg|jpeg|png|gif|webp|svg)$/i,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "product-images-cache",
              expiration: {
                maxEntries: 200,
                // Cache up to 200 product images
                maxAgeSeconds: 60 * 60 * 24 * 7
                // 7 days
              },
              cacheableResponse: {
                statuses: [0, 200]
              }
            }
          },
          {
            urlPattern: /\/api\/.*/i,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              networkTimeoutSeconds: 10,
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24
                // 24 hours
              },
              cacheableResponse: {
                statuses: [0, 200]
              }
            }
          },
          {
            urlPattern: ({ request, url }) => request.mode === "navigate" && url.pathname.startsWith("/pos"),
            handler: "NetworkFirst",
            options: {
              cacheName: "pos-page-cache",
              networkTimeoutSeconds: 3,
              expiration: {
                maxEntries: 3,
                maxAgeSeconds: 60 * 60 * 24
                // 24 hours
              },
              plugins: [
                {
                  cachedResponseWillBeUsed: async ({ cachedResponse }) => {
                    if (cachedResponse?.redirected) {
                      return new Response(await cachedResponse.clone().arrayBuffer(), {
                        status: cachedResponse.status,
                        statusText: cachedResponse.statusText,
                        headers: cachedResponse.headers
                      });
                    }
                    return cachedResponse;
                  }
                }
              ]
            }
          }
        ],
        cleanupOutdatedCaches: true,
        skipWaiting: true,
        clientsClaim: true
      },
      devOptions: {
        enabled: true,
        type: "module"
      }
    })
  ],
  build: {
    chunkSizeWarningLimit: 1500,
    outDir: "../pos_next/public/pos",
    emptyOutDir: true,
    target: "es2015",
    sourcemap: enableSourceMap
  },
  worker: {
    format: "es",
    rollupOptions: {
      output: {
        format: "es"
      }
    }
  },
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "src"),
      "tailwind.config.js": path.resolve(__vite_injected_original_dirname, "tailwind.config.js")
    }
  },
  define: {
    __BUILD_VERSION__: JSON.stringify(buildVersion)
  },
  optimizeDeps: {
    exclude: ["frappe-ui"],
    include: [
      "feather-icons",
      "showdown",
      "highlight.js/lib/core",
      "interactjs",
      "debug",
      "socket.io-client",
      "engine.io-client"
    ]
  },
  server: {
    allowedHosts: true,
    port: 8080,
    proxy: {
      "^/(app|api|assets|files|printview)": {
        target: "http://127.0.0.1:8045",
        ws: true,
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: "localhost",
        router: (req) => {
          const site_name = (req.headers.host || "").split(":")[0];
          const isLocalhost = site_name === "localhost" || site_name === "127.0.0.1";
          const isNgrok = site_name.endsWith(".ngrok-free.app") || site_name.endsWith(".ngrok.io");
          const isTunnel = site_name.endsWith(".loca.lt") || site_name.includes("localtunnel");
          const targetHost = isLocalhost || isNgrok || isTunnel ? "127.0.0.1" : site_name;
          return `http://${targetHost}:8045`;
        }
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvaG9tZS9tYncxMjM0NS9oYV92YW5nL2FwcHMvcG9zX25leHQvUE9TXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCIvaG9tZS9tYncxMjM0NS9oYV92YW5nL2FwcHMvcG9zX25leHQvUE9TL3ZpdGUuY29uZmlnLmpzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9ob21lL21idzEyMzQ1L2hhX3ZhbmcvYXBwcy9wb3NfbmV4dC9QT1Mvdml0ZS5jb25maWcuanNcIjtpbXBvcnQgcGF0aCBmcm9tIFwibm9kZTpwYXRoXCJcbmltcG9ydCB7IHByb21pc2VzIGFzIGZzIH0gZnJvbSBcIm5vZGU6ZnNcIlxuaW1wb3J0IHZ1ZSBmcm9tIFwiQHZpdGVqcy9wbHVnaW4tdnVlXCJcbmltcG9ydCBmcmFwcGV1aSBmcm9tIFwiZnJhcHBlLXVpL3ZpdGVcIlxuaW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSBcInZpdGVcIlxuaW1wb3J0IHsgVml0ZVBXQSB9IGZyb20gXCJ2aXRlLXBsdWdpbi1wd2FcIlxuaW1wb3J0IHsgdml0ZVN0YXRpY0NvcHkgfSBmcm9tIFwidml0ZS1wbHVnaW4tc3RhdGljLWNvcHlcIlxuXG4vLyBHZXQgYnVpbGQgdmVyc2lvbiBmcm9tIGVudmlyb25tZW50IG9yIHVzZSB0aW1lc3RhbXBcbmNvbnN0IGJ1aWxkVmVyc2lvbiA9IHByb2Nlc3MuZW52LlBPU19ORVhUX0JVSUxEX1ZFUlNJT04gfHwgRGF0ZS5ub3coKS50b1N0cmluZygpXG5jb25zdCBlbmFibGVTb3VyY2VNYXAgPSBwcm9jZXNzLmVudi5QT1NfTkVYVF9FTkFCTEVfU09VUkNFTUFQID09PSBcInRydWVcIlxuXG4vKipcbiAqIFZpdGUgcGx1Z2luIHRvIHdyaXRlIGJ1aWxkIHZlcnNpb24gdG8gdmVyc2lvbi5qc29uIGZpbGVcbiAqIFRoaXMgZW5hYmxlcyBjYWNoZSBidXN0aW5nIGFuZCB2ZXJzaW9uIHRyYWNraW5nXG4gKi9cbmZ1bmN0aW9uIHBvc05leHRCdWlsZFZlcnNpb25QbHVnaW4odmVyc2lvbikge1xuXHRyZXR1cm4ge1xuXHRcdG5hbWU6IFwicG9zLW5leHQtYnVpbGQtdmVyc2lvblwiLFxuXHRcdGFwcGx5OiBcImJ1aWxkXCIsXG5cdFx0YXN5bmMgd3JpdGVCdW5kbGUoKSB7XG5cdFx0XHRjb25zdCB2ZXJzaW9uRmlsZSA9IHBhdGgucmVzb2x2ZShfX2Rpcm5hbWUsIFwiLi4vcG9zX25leHQvcHVibGljL3Bvcy92ZXJzaW9uLmpzb25cIilcblx0XHRcdGF3YWl0IGZzLm1rZGlyKHBhdGguZGlybmFtZSh2ZXJzaW9uRmlsZSksIHsgcmVjdXJzaXZlOiB0cnVlIH0pXG5cdFx0XHRhd2FpdCBmcy53cml0ZUZpbGUoXG5cdFx0XHRcdHZlcnNpb25GaWxlLFxuXHRcdFx0XHRKU09OLnN0cmluZ2lmeShcblx0XHRcdFx0XHR7XG5cdFx0XHRcdFx0XHR2ZXJzaW9uLFxuXHRcdFx0XHRcdFx0dGltZXN0YW1wOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG5cdFx0XHRcdFx0XHRidWlsZERhdGU6IG5ldyBEYXRlKCkudG9Mb2NhbGVEYXRlU3RyaW5nKFwiZW4tVVNcIiwge1xuXHRcdFx0XHRcdFx0XHR5ZWFyOiBcIm51bWVyaWNcIixcblx0XHRcdFx0XHRcdFx0bW9udGg6IFwibG9uZ1wiLFxuXHRcdFx0XHRcdFx0XHRkYXk6IFwibnVtZXJpY1wiLFxuXHRcdFx0XHRcdFx0fSksXG5cdFx0XHRcdFx0fSxcblx0XHRcdFx0XHRudWxsLFxuXHRcdFx0XHRcdDJcblx0XHRcdFx0KSxcblx0XHRcdFx0XCJ1dGY4XCJcblx0XHRcdClcblx0XHRcdGNvbnNvbGUubG9nKGBcXG5cdTI3MTMgQnVpbGQgdmVyc2lvbiB3cml0dGVuOiAke3ZlcnNpb259YClcblx0XHR9LFxuXHR9XG59XG5cbi8vIGh0dHBzOi8vdml0ZWpzLmRldi9jb25maWcvXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuXHRwbHVnaW5zOiBbXG5cdFx0cG9zTmV4dEJ1aWxkVmVyc2lvblBsdWdpbihidWlsZFZlcnNpb24pLFxuXHRcdGZyYXBwZXVpKHtcblx0XHRcdGZyYXBwZVByb3h5OiB0cnVlLFxuXHRcdFx0amluamFCb290RGF0YTogdHJ1ZSxcblx0XHRcdGx1Y2lkZUljb25zOiB0cnVlLFxuXHRcdFx0YnVpbGRDb25maWc6IHtcblx0XHRcdFx0aW5kZXhIdG1sUGF0aDogXCIuLi9wb3NfbmV4dC93d3cvcG9zLmh0bWxcIixcblx0XHRcdFx0b3V0RGlyOiBcIi4uL3Bvc19uZXh0L3B1YmxpYy9wb3NcIixcblx0XHRcdFx0ZW1wdHlPdXREaXI6IHRydWUsXG5cdFx0XHRcdHNvdXJjZW1hcDogZW5hYmxlU291cmNlTWFwLFxuXHRcdFx0fSxcblx0XHR9KSxcblx0XHR2dWUoKSxcblx0XHR2aXRlU3RhdGljQ29weSh7XG5cdFx0XHR0YXJnZXRzOiBbXG5cdFx0XHRcdHtcblx0XHRcdFx0XHRzcmM6IFwic3JjL3dvcmtlcnNcIixcblx0XHRcdFx0XHRkZXN0OiBcIi5cIixcblx0XHRcdFx0fSxcblx0XHRcdF0sXG5cdFx0fSksXG5cdFx0Vml0ZVBXQSh7XG5cdFx0XHRyZWdpc3RlclR5cGU6IFwiYXV0b1VwZGF0ZVwiLFxuXHRcdFx0aW5qZWN0UmVnaXN0ZXI6IG51bGwsXG5cdFx0XHRpbmNsdWRlQXNzZXRzOiBbXCJmYXZpY29uLnBuZ1wiLCBcImljb24uc3ZnXCIsIFwiaWNvbi1tYXNrYWJsZS5zdmdcIl0sXG5cdFx0XHRtYW5pZmVzdDoge1xuXHRcdFx0XHRpZDogXCIvcG9zL1wiLFxuXHRcdFx0XHRuYW1lOiBcIk1CVyBOZXh0IFBPU1wiLFxuXHRcdFx0XHRzaG9ydF9uYW1lOiBcIk1CVyBOZXh0IFBPU1wiLFxuXHRcdFx0XHRkZXNjcmlwdGlvbjpcblx0XHRcdFx0XHRcIlBvaW50IG9mIFNhbGUgc3lzdGVtIHdpdGggcmVhbC10aW1lIGJpbGxpbmcsIHN0b2NrIG1hbmFnZW1lbnQsIGFuZCBvZmZsaW5lIHN1cHBvcnRcIixcblx0XHRcdFx0dGhlbWVfY29sb3I6IFwiI2M0MTYxY1wiLFxuXHRcdFx0XHRiYWNrZ3JvdW5kX2NvbG9yOiBcIiNmZmZmZmZcIixcblx0XHRcdFx0ZGlzcGxheTogXCJzdGFuZGFsb25lXCIsXG5cdFx0XHRcdHNjb3BlOiBcIi9wb3MvXCIsXG5cdFx0XHRcdHN0YXJ0X3VybDogXCIvcG9zXCIsXG5cdFx0XHRcdGljb25zOiBbXG5cdFx0XHRcdFx0e1xuXHRcdFx0XHRcdFx0c3JjOiBcIi9hc3NldHMvcG9zX25leHQvcG9zL2ljb24uc3ZnXCIsXG5cdFx0XHRcdFx0XHRzaXplczogXCIxOTJ4MTkyXCIsXG5cdFx0XHRcdFx0XHR0eXBlOiBcImltYWdlL3N2Zyt4bWxcIixcblx0XHRcdFx0XHRcdHB1cnBvc2U6IFwiYW55XCIsXG5cdFx0XHRcdFx0fSxcblx0XHRcdFx0XHR7XG5cdFx0XHRcdFx0XHRzcmM6IFwiL2Fzc2V0cy9wb3NfbmV4dC9wb3MvaWNvbi5zdmdcIixcblx0XHRcdFx0XHRcdHNpemVzOiBcIjUxMng1MTJcIixcblx0XHRcdFx0XHRcdHR5cGU6IFwiaW1hZ2Uvc3ZnK3htbFwiLFxuXHRcdFx0XHRcdFx0cHVycG9zZTogXCJhbnlcIixcblx0XHRcdFx0XHR9LFxuXHRcdFx0XHRcdHtcblx0XHRcdFx0XHRcdHNyYzogXCIvYXNzZXRzL3Bvc19uZXh0L3Bvcy9pY29uLW1hc2thYmxlLnN2Z1wiLFxuXHRcdFx0XHRcdFx0c2l6ZXM6IFwiMTkyeDE5MlwiLFxuXHRcdFx0XHRcdFx0dHlwZTogXCJpbWFnZS9zdmcreG1sXCIsXG5cdFx0XHRcdFx0XHRwdXJwb3NlOiBcIm1hc2thYmxlXCIsXG5cdFx0XHRcdFx0fSxcblx0XHRcdFx0XHR7XG5cdFx0XHRcdFx0XHRzcmM6IFwiL2Fzc2V0cy9wb3NfbmV4dC9wb3MvaWNvbi1tYXNrYWJsZS5zdmdcIixcblx0XHRcdFx0XHRcdHNpemVzOiBcIjUxMng1MTJcIixcblx0XHRcdFx0XHRcdHR5cGU6IFwiaW1hZ2Uvc3ZnK3htbFwiLFxuXHRcdFx0XHRcdFx0cHVycG9zZTogXCJtYXNrYWJsZVwiLFxuXHRcdFx0XHRcdH0sXG5cdFx0XHRcdF0sXG5cdFx0XHR9LFxuXHRcdFx0d29ya2JveDoge1xuXHRcdFx0XHRnbG9iUGF0dGVybnM6IFtcIioqLyoue2pzLGNzcyxodG1sLGljbyxwbmcsc3ZnLHdvZmYsd29mZjJ9XCJdLFxuXHRcdFx0XHRtYXhpbXVtRmlsZVNpemVUb0NhY2hlSW5CeXRlczogNCAqIDEwMjQgKiAxMDI0LCAvLyAzIE1CXG5cdFx0XHRcdG5hdmlnYXRlRmFsbGJhY2s6IG51bGwsXG5cdFx0XHRcdG5hdmlnYXRlRmFsbGJhY2tEZW55bGlzdDogWy9eXFwvYXBpLywgL15cXC9hcHAvXSxcblx0XHRcdFx0cnVudGltZUNhY2hpbmc6IFtcblx0XHRcdFx0XHR7XG5cdFx0XHRcdFx0XHR1cmxQYXR0ZXJuOiAvXmh0dHBzOlxcL1xcL2ZvbnRzXFwuZ29vZ2xlYXBpc1xcLmNvbVxcLy4qL2ksXG5cdFx0XHRcdFx0XHRoYW5kbGVyOiBcIkNhY2hlRmlyc3RcIixcblx0XHRcdFx0XHRcdG9wdGlvbnM6IHtcblx0XHRcdFx0XHRcdFx0Y2FjaGVOYW1lOiBcImdvb2dsZS1mb250cy1jYWNoZVwiLFxuXHRcdFx0XHRcdFx0XHRleHBpcmF0aW9uOiB7XG5cdFx0XHRcdFx0XHRcdFx0bWF4RW50cmllczogMTAsXG5cdFx0XHRcdFx0XHRcdFx0bWF4QWdlU2Vjb25kczogNjAgKiA2MCAqIDI0ICogMzY1LCAvLyAxIHllYXJcblx0XHRcdFx0XHRcdFx0fSxcblx0XHRcdFx0XHRcdFx0Y2FjaGVhYmxlUmVzcG9uc2U6IHtcblx0XHRcdFx0XHRcdFx0XHRzdGF0dXNlczogWzAsIDIwMF0sXG5cdFx0XHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0XHR9LFxuXHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0e1xuXHRcdFx0XHRcdFx0dXJsUGF0dGVybjogL15odHRwczpcXC9cXC9mb250c1xcLmdzdGF0aWNcXC5jb21cXC8uKi9pLFxuXHRcdFx0XHRcdFx0aGFuZGxlcjogXCJDYWNoZUZpcnN0XCIsXG5cdFx0XHRcdFx0XHRvcHRpb25zOiB7XG5cdFx0XHRcdFx0XHRcdGNhY2hlTmFtZTogXCJnc3RhdGljLWZvbnRzLWNhY2hlXCIsXG5cdFx0XHRcdFx0XHRcdGV4cGlyYXRpb246IHtcblx0XHRcdFx0XHRcdFx0XHRtYXhFbnRyaWVzOiAxMCxcblx0XHRcdFx0XHRcdFx0XHRtYXhBZ2VTZWNvbmRzOiA2MCAqIDYwICogMjQgKiAzNjUsIC8vIDEgeWVhclxuXHRcdFx0XHRcdFx0XHR9LFxuXHRcdFx0XHRcdFx0XHRjYWNoZWFibGVSZXNwb25zZToge1xuXHRcdFx0XHRcdFx0XHRcdHN0YXR1c2VzOiBbMCwgMjAwXSxcblx0XHRcdFx0XHRcdFx0fSxcblx0XHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0fSxcblx0XHRcdFx0XHR7XG5cdFx0XHRcdFx0XHR1cmxQYXR0ZXJuOiAvXFwvYXNzZXRzXFwvcG9zX25leHRcXC9wb3NcXC8uKi9pLFxuXHRcdFx0XHRcdFx0aGFuZGxlcjogXCJDYWNoZUZpcnN0XCIsXG5cdFx0XHRcdFx0XHRvcHRpb25zOiB7XG5cdFx0XHRcdFx0XHRcdGNhY2hlTmFtZTogXCJwb3MtYXNzZXRzLWNhY2hlXCIsXG5cdFx0XHRcdFx0XHRcdGV4cGlyYXRpb246IHtcblx0XHRcdFx0XHRcdFx0XHRtYXhFbnRyaWVzOiA1MDAsXG5cdFx0XHRcdFx0XHRcdFx0bWF4QWdlU2Vjb25kczogNjAgKiA2MCAqIDI0ICogMzAsIC8vIDMwIGRheXNcblx0XHRcdFx0XHRcdFx0fSxcblx0XHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0fSxcblx0XHRcdFx0XHQvLyBDYWNoZSBwcm9kdWN0IGltYWdlcyB3aXRoIFN0YWxlV2hpbGVSZXZhbGlkYXRlIGZvciBiZXR0ZXIgVVhcblx0XHRcdFx0XHR7XG5cdFx0XHRcdFx0XHR1cmxQYXR0ZXJuOiAvXFwvZmlsZXNcXC8uKlxcLihqcGd8anBlZ3xwbmd8Z2lmfHdlYnB8c3ZnKSQvaSxcblx0XHRcdFx0XHRcdGhhbmRsZXI6IFwiU3RhbGVXaGlsZVJldmFsaWRhdGVcIixcblx0XHRcdFx0XHRcdG9wdGlvbnM6IHtcblx0XHRcdFx0XHRcdFx0Y2FjaGVOYW1lOiBcInByb2R1Y3QtaW1hZ2VzLWNhY2hlXCIsXG5cdFx0XHRcdFx0XHRcdGV4cGlyYXRpb246IHtcblx0XHRcdFx0XHRcdFx0XHRtYXhFbnRyaWVzOiAyMDAsIC8vIENhY2hlIHVwIHRvIDIwMCBwcm9kdWN0IGltYWdlc1xuXHRcdFx0XHRcdFx0XHRcdG1heEFnZVNlY29uZHM6IDYwICogNjAgKiAyNCAqIDcsIC8vIDcgZGF5c1xuXHRcdFx0XHRcdFx0XHR9LFxuXHRcdFx0XHRcdFx0XHRjYWNoZWFibGVSZXNwb25zZToge1xuXHRcdFx0XHRcdFx0XHRcdHN0YXR1c2VzOiBbMCwgMjAwXSxcblx0XHRcdFx0XHRcdFx0fSxcblx0XHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0fSxcblx0XHRcdFx0XHR7XG5cdFx0XHRcdFx0XHR1cmxQYXR0ZXJuOiAvXFwvYXBpXFwvLiovaSxcblx0XHRcdFx0XHRcdGhhbmRsZXI6IFwiTmV0d29ya0ZpcnN0XCIsXG5cdFx0XHRcdFx0XHRvcHRpb25zOiB7XG5cdFx0XHRcdFx0XHRcdGNhY2hlTmFtZTogXCJhcGktY2FjaGVcIixcblx0XHRcdFx0XHRcdFx0bmV0d29ya1RpbWVvdXRTZWNvbmRzOiAxMCxcblx0XHRcdFx0XHRcdFx0ZXhwaXJhdGlvbjoge1xuXHRcdFx0XHRcdFx0XHRcdG1heEVudHJpZXM6IDEwMCxcblx0XHRcdFx0XHRcdFx0XHRtYXhBZ2VTZWNvbmRzOiA2MCAqIDYwICogMjQsIC8vIDI0IGhvdXJzXG5cdFx0XHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0XHRcdGNhY2hlYWJsZVJlc3BvbnNlOiB7XG5cdFx0XHRcdFx0XHRcdFx0c3RhdHVzZXM6IFswLCAyMDBdLFxuXHRcdFx0XHRcdFx0XHR9LFxuXHRcdFx0XHRcdFx0fSxcblx0XHRcdFx0XHR9LFxuXHRcdFx0XHRcdHtcblx0XHRcdFx0XHRcdHVybFBhdHRlcm46ICh7IHJlcXVlc3QsIHVybCB9KSA9PlxuXHRcdFx0XHRcdFx0XHRyZXF1ZXN0Lm1vZGUgPT09IFwibmF2aWdhdGVcIiAmJiB1cmwucGF0aG5hbWUuc3RhcnRzV2l0aChcIi9wb3NcIiksXG5cdFx0XHRcdFx0XHRoYW5kbGVyOiBcIk5ldHdvcmtGaXJzdFwiLFxuXHRcdFx0XHRcdFx0b3B0aW9uczoge1xuXHRcdFx0XHRcdFx0XHRjYWNoZU5hbWU6IFwicG9zLXBhZ2UtY2FjaGVcIixcblx0XHRcdFx0XHRcdFx0bmV0d29ya1RpbWVvdXRTZWNvbmRzOiAzLFxuXHRcdFx0XHRcdFx0XHRleHBpcmF0aW9uOiB7XG5cdFx0XHRcdFx0XHRcdFx0bWF4RW50cmllczogMyxcblx0XHRcdFx0XHRcdFx0XHRtYXhBZ2VTZWNvbmRzOiA2MCAqIDYwICogMjQsIC8vIDI0IGhvdXJzXG5cdFx0XHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0XHRcdHBsdWdpbnM6IFtcblx0XHRcdFx0XHRcdFx0XHR7XG5cdFx0XHRcdFx0XHRcdFx0XHRjYWNoZWRSZXNwb25zZVdpbGxCZVVzZWQ6IGFzeW5jICh7IGNhY2hlZFJlc3BvbnNlIH0pID0+IHtcblx0XHRcdFx0XHRcdFx0XHRcdFx0aWYgKGNhY2hlZFJlc3BvbnNlPy5yZWRpcmVjdGVkKSB7XG5cdFx0XHRcdFx0XHRcdFx0XHRcdFx0cmV0dXJuIG5ldyBSZXNwb25zZShhd2FpdCBjYWNoZWRSZXNwb25zZS5jbG9uZSgpLmFycmF5QnVmZmVyKCksIHtcblx0XHRcdFx0XHRcdFx0XHRcdFx0XHRcdHN0YXR1czogY2FjaGVkUmVzcG9uc2Uuc3RhdHVzLFxuXHRcdFx0XHRcdFx0XHRcdFx0XHRcdFx0c3RhdHVzVGV4dDogY2FjaGVkUmVzcG9uc2Uuc3RhdHVzVGV4dCxcblx0XHRcdFx0XHRcdFx0XHRcdFx0XHRcdGhlYWRlcnM6IGNhY2hlZFJlc3BvbnNlLmhlYWRlcnMsXG5cdFx0XHRcdFx0XHRcdFx0XHRcdFx0fSlcblx0XHRcdFx0XHRcdFx0XHRcdFx0fVxuXHRcdFx0XHRcdFx0XHRcdFx0XHRyZXR1cm4gY2FjaGVkUmVzcG9uc2Vcblx0XHRcdFx0XHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0XHRcdFx0fSxcblx0XHRcdFx0XHRcdFx0XSxcblx0XHRcdFx0XHRcdH0sXG5cdFx0XHRcdFx0fSxcblx0XHRcdFx0XSxcblx0XHRcdFx0Y2xlYW51cE91dGRhdGVkQ2FjaGVzOiB0cnVlLFxuXHRcdFx0XHRza2lwV2FpdGluZzogdHJ1ZSxcblx0XHRcdFx0Y2xpZW50c0NsYWltOiB0cnVlLFxuXHRcdFx0fSxcblx0XHRcdGRldk9wdGlvbnM6IHtcblx0XHRcdFx0ZW5hYmxlZDogdHJ1ZSxcblx0XHRcdFx0dHlwZTogXCJtb2R1bGVcIixcblx0XHRcdH0sXG5cdFx0fSksXG5cdF0sXG5cdGJ1aWxkOiB7XG5cdFx0Y2h1bmtTaXplV2FybmluZ0xpbWl0OiAxNTAwLFxuXHRcdG91dERpcjogXCIuLi9wb3NfbmV4dC9wdWJsaWMvcG9zXCIsXG5cdFx0ZW1wdHlPdXREaXI6IHRydWUsXG5cdFx0dGFyZ2V0OiBcImVzMjAxNVwiLFxuXHRcdHNvdXJjZW1hcDogZW5hYmxlU291cmNlTWFwLFxuXHR9LFxuXHR3b3JrZXI6IHtcblx0XHRmb3JtYXQ6IFwiZXNcIixcblx0XHRyb2xsdXBPcHRpb25zOiB7XG5cdFx0XHRvdXRwdXQ6IHtcblx0XHRcdFx0Zm9ybWF0OiBcImVzXCIsXG5cdFx0XHR9LFxuXHRcdH0sXG5cdH0sXG5cdHJlc29sdmU6IHtcblx0XHRhbGlhczoge1xuXHRcdFx0XCJAXCI6IHBhdGgucmVzb2x2ZShfX2Rpcm5hbWUsIFwic3JjXCIpLFxuXHRcdFx0XCJ0YWlsd2luZC5jb25maWcuanNcIjogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgXCJ0YWlsd2luZC5jb25maWcuanNcIiksXG5cdFx0fSxcblx0fSxcblx0ZGVmaW5lOiB7XG5cdFx0X19CVUlMRF9WRVJTSU9OX186IEpTT04uc3RyaW5naWZ5KGJ1aWxkVmVyc2lvbiksXG5cdH0sXG5cdG9wdGltaXplRGVwczoge1xuXHRcdGV4Y2x1ZGU6IFtcImZyYXBwZS11aVwiXSxcblx0XHRpbmNsdWRlOiBbXG5cdFx0XHRcImZlYXRoZXItaWNvbnNcIixcblx0XHRcdFwic2hvd2Rvd25cIixcblx0XHRcdFwiaGlnaGxpZ2h0LmpzL2xpYi9jb3JlXCIsXG5cdFx0XHRcImludGVyYWN0anNcIixcbiAgICAgICAgICAgIFwiZGVidWdcIixcbiAgICAgICAgICAgIFwic29ja2V0LmlvLWNsaWVudFwiLFxuICAgICAgICAgICAgXCJlbmdpbmUuaW8tY2xpZW50XCIsXG5cdFx0XSxcblx0fSxcblx0c2VydmVyOiB7XG5cdFx0YWxsb3dlZEhvc3RzOiB0cnVlLFxuXHRcdHBvcnQ6IDgwODAsXG5cdFx0cHJveHk6IHtcblx0XHRcdFwiXi8oYXBwfGFwaXxhc3NldHN8ZmlsZXN8cHJpbnR2aWV3KVwiOiB7XG5cdFx0XHRcdHRhcmdldDogXCJodHRwOi8vMTI3LjAuMC4xOjgwNDVcIixcblx0XHRcdFx0d3M6IHRydWUsXG5cdFx0XHRcdGNoYW5nZU9yaWdpbjogdHJ1ZSxcblx0XHRcdFx0c2VjdXJlOiBmYWxzZSxcblx0XHRcdFx0Y29va2llRG9tYWluUmV3cml0ZTogXCJsb2NhbGhvc3RcIixcblx0XHRcdFx0cm91dGVyOiAocmVxKSA9PiB7XG5cdFx0XHRcdFx0Y29uc3Qgc2l0ZV9uYW1lID0gKHJlcS5oZWFkZXJzLmhvc3QgfHwgXCJcIikuc3BsaXQoXCI6XCIpWzBdXG5cdFx0XHRcdFx0Ly8gS2hpIHRydXkgY1x1MUVBRHAgcXVhIG5ncm9rL2RvbWFpbiBuZ29cdTAwRTBpLCBBUEkgbHVcdTAwRjRuIGdcdTFFRURpIHZcdTFFQzEgYmFja2VuZCBsb2NhbFxuXHRcdFx0XHRcdGNvbnN0IGlzTG9jYWxob3N0ID1cblx0XHRcdFx0XHRcdHNpdGVfbmFtZSA9PT0gXCJsb2NhbGhvc3RcIiB8fCBzaXRlX25hbWUgPT09IFwiMTI3LjAuMC4xXCJcblx0XHRcdFx0XHRjb25zdCBpc05ncm9rID0gc2l0ZV9uYW1lLmVuZHNXaXRoKFwiLm5ncm9rLWZyZWUuYXBwXCIpIHx8IHNpdGVfbmFtZS5lbmRzV2l0aChcIi5uZ3Jvay5pb1wiKVxuXHRcdFx0XHRcdGNvbnN0IGlzVHVubmVsID0gc2l0ZV9uYW1lLmVuZHNXaXRoKFwiLmxvY2EubHRcIikgfHwgc2l0ZV9uYW1lLmluY2x1ZGVzKFwibG9jYWx0dW5uZWxcIilcblx0XHRcdFx0XHRjb25zdCB0YXJnZXRIb3N0ID0gaXNMb2NhbGhvc3QgfHwgaXNOZ3JvayB8fCBpc1R1bm5lbCA/IFwiMTI3LjAuMC4xXCIgOiBzaXRlX25hbWVcblx0XHRcdFx0XHRyZXR1cm4gYGh0dHA6Ly8ke3RhcmdldEhvc3R9OjgwNDVgXG5cdFx0XHRcdH0sXG5cdFx0XHR9LFxuXHRcdH0sXG5cdH0sXG59KVxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUEwUyxPQUFPLFVBQVU7QUFDM1QsU0FBUyxZQUFZLFVBQVU7QUFDL0IsT0FBTyxTQUFTO0FBQ2hCLE9BQU8sY0FBYztBQUNyQixTQUFTLG9CQUFvQjtBQUM3QixTQUFTLGVBQWU7QUFDeEIsU0FBUyxzQkFBc0I7QUFOL0IsSUFBTSxtQ0FBbUM7QUFTekMsSUFBTSxlQUFlLFFBQVEsSUFBSSwwQkFBMEIsS0FBSyxJQUFJLEVBQUUsU0FBUztBQUMvRSxJQUFNLGtCQUFrQixRQUFRLElBQUksOEJBQThCO0FBTWxFLFNBQVMsMEJBQTBCLFNBQVM7QUFDM0MsU0FBTztBQUFBLElBQ04sTUFBTTtBQUFBLElBQ04sT0FBTztBQUFBLElBQ1AsTUFBTSxjQUFjO0FBQ25CLFlBQU0sY0FBYyxLQUFLLFFBQVEsa0NBQVcscUNBQXFDO0FBQ2pGLFlBQU0sR0FBRyxNQUFNLEtBQUssUUFBUSxXQUFXLEdBQUcsRUFBRSxXQUFXLEtBQUssQ0FBQztBQUM3RCxZQUFNLEdBQUc7QUFBQSxRQUNSO0FBQUEsUUFDQSxLQUFLO0FBQUEsVUFD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
