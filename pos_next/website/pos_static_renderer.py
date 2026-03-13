# Copyright (c) 2025, pos_next contributors
# Serve pos entry SW at /pos/sw.js and workbox-*.js at /pos/ scope for offline F5.

import os
import re

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

# Inline SW: caches /pos/ navigation so offline F5 works.
# Embedded to avoid dependency on build artifacts being present.
_POS_ENTRY_SW = b"""
const CACHE_NAME = "pos-shell-v7";
const POS_URL = "/pos/";
const OFFLINE_HTML = "<html><head><title>POS</title><meta http-equiv='refresh' content='5'></head><body style='font-family:sans-serif;text-align:center;padding:40px'><h2>Offline</h2><p>Vui long ket noi mang va tai lai trang.</p></body></html>";

function isHtmlResponse(response) {
  const ct = response.headers.get("Content-Type") || "";
  return response.ok && response.type === "basic" && ct.includes("text/html");
}

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    Promise.all([
      caches.keys().then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("pos-shell-") && k !== CACHE_NAME)
            .map((k) => caches.delete(k))
        )
      ),
      fetch(POS_URL, { credentials: "include" })
        .then((res) => {
          if (isHtmlResponse(res)) {
            return caches.open(CACHE_NAME).then((c) => c.put(POS_URL, res));
          }
        })
        .catch(() => {}),
    ]).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const path = url.pathname;

  if (event.request.mode === "navigate" && path.startsWith("/pos")) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        fetch(event.request, { redirect: "follow" })
          .then((response) => {
            if (isHtmlResponse(response)) {
              cache.put(POS_URL, response.clone());
              return response;
            }
            // Server returned non-HTML (wrong redirect, JS, etc.) -- serve from cache
            return cache.match(POS_URL).then(
              (cached) => cached || new Response(OFFLINE_HTML, { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } })
            );
          })
          .catch(() =>
            cache.match(POS_URL).then(
              (cached) => cached || new Response(OFFLINE_HTML, { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } })
            )
          )
      )
    );
    return;
  }

  if (path.startsWith("/assets/pos_next/pos/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const toCache = response.clone();
            caches.open(CACHE_NAME).then((c) => c.put(event.request, toCache));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
  }
});
""".strip()


class POSStaticRenderer(BaseRenderer):
	"""Serves pos_entry_sw (inline) at /pos/sw.js and workbox-*.js so SW scope is /pos/."""

	def can_render(self):
		path = getattr(frappe.local, "path", "") or ""
		if path == "pos/sw.js":
			return True
		if re.match(r"^pos/workbox-[a-zA-Z0-9_-]+\.js$", path):
			return True
		return False

	def render(self):
		path = getattr(frappe.local, "path", "") or ""
		headers = {
			"Content-Type": "application/javascript",
			"Service-Worker-Allowed": "/",
			"Cache-Control": "no-cache",
		}

		if path == "pos/sw.js":
			return Response(_POS_ENTRY_SW, status=200, headers=headers)

		# workbox-xxx.js -- serve from built assets
		app_path = frappe.get_app_path("pos_next", "public", "pos")
		file_path = os.path.join(app_path, path.split("/")[-1])
		if not os.path.isfile(file_path):
			return Response("Not Found", status=404)
		with open(file_path, "rb") as f:
			body = f.read()
		return Response(body, status=200, headers=headers)
