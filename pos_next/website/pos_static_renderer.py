# Copyright (c) 2025, pos_next contributors
# Serve /pos/sw.js and /pos/workbox-*.js from app public/pos for offline-first scope.

import os
import re

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response


class POSStaticRenderer(BaseRenderer):
	"""Serves pos_entry_sw.js at /pos/sw.js and workbox-*.js at /pos/workbox-*.js so SW scope can be /pos/."""

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
		if path == "pos/sw.js":
			file_path = os.path.join(app_path, "pos_entry_sw.js")
		else:
			# pos/workbox-xxx.js -> workbox-xxx.js
			basename = path.split("/")[-1]
			file_path = os.path.join(app_path, basename)

		if not os.path.isfile(file_path):
			return Response("Not Found", status=404)

		with open(file_path, "rb") as f:
			body = f.read()
		mimetype = "application/javascript"
		return Response(body, mimetype=mimetype)
