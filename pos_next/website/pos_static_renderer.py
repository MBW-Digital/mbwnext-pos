# Copyright (c) 2025, pos_next contributors
# Serve sw.js and workbox-*.js at /pos/ scope so offline F5 works.

import os
import re

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response


class POSStaticRenderer(BaseRenderer):
	"""Serves sw.js at /pos/sw.js and workbox-*.js at /pos/workbox-*.js so SW scope can be /pos/."""

	def can_render(self):
		path = getattr(frappe.local, "path", "") or ""
		if path == "pos/sw.js":
			return True
		if re.match(r"^pos/workbox-[a-zA-Z0-9_-]+\.js$", path):
			return True
		return False

	def render(self):
		path = getattr(frappe.local, "path", "") or ""
		app_path = frappe.get_app_path("pos_next", "public", "pos")
		basename = path.split("/")[-1]  # sw.js hoặc workbox-xxx.js
		file_path = os.path.join(app_path, basename)

		if not os.path.isfile(file_path):
			return Response("Not Found", status=404)

		with open(file_path, "rb") as f:
			body = f.read()

		headers = {
			"Content-Type": "application/javascript",
			"Service-Worker-Allowed": "/",
			"Cache-Control": "no-cache",
		}
		return Response(body, status=200, headers=headers)
