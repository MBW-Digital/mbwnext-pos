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
const CACHE_NAME = "pos-shell-v2";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.add("/pos/").catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("pos-shell-") && k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const path = url.pathname;

  if (event.request.mode === "navigate" && path.startsWith("/pos")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
          return response;
        })
        .catch(() =>
          caches
            .match(event.request)
            .then((cached) => cached || caches.match("/pos/"))
        )
    );
    return;
  }

  if (path.startsWith("/assets/pos_next/pos/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
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

		# workbox-xxx.js — serve from built assets
		app_path = frappe.get_app_path("pos_next", "public", "pos")
		file_path = os.path.join(app_path, path.split("/")[-1])
		if not os.path.isfile(file_path):
			return Response("Not Found", status=404)
		with open(file_path, "rb") as f:
			body = f.read()
		return Response(body, status=200, headers=headers)
