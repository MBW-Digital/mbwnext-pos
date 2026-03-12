import router from "@/router"
import { createResource } from "frappe-ui"
import { computed, reactive } from "vue"

import { ensureCSRFToken } from "@/utils/csrf"
import { userResource, userData } from "./user"
import { setSetting } from "@/utils/offline/db"

const POS_OFFLINE_USER_KEY = "pos_offline_user"

/** Read user from cookie only (sync). Offline fallback is loaded from IndexedDB in main.js */
export function sessionUser() {
	const cookies = new URLSearchParams(document.cookie.split("; ").join("&"))
	let _sessionUser = cookies.get("user_id")
	if (_sessionUser === "Guest") {
		_sessionUser = null
	}
	return _sessionUser
}

export const session = reactive({
	login: createResource({
		url: "login",
		makeParams({ email, password }) {
			return {
				usr: email,
				pwd: password,
			}
		},
		async onSuccess(data) {
			// Initialize CSRF token immediately after successful login
			await ensureCSRFToken()

			await userResource.reload()

			// Refresh userData from cookies after login
			// The auto-refresh interval will also pick this up, but we do it immediately for responsiveness
			userData.refresh()

			session.user = sessionUser()
			try {
				if (session.user) await setSetting(POS_OFFLINE_USER_KEY, session.user)
			} catch (_) {}
			session.login.reset()
			// Don't redirect here - let the Login page watcher handle navigation
			// This prevents conflicts with the shift opening dialog flow
		},
		onError(error) {
			console.error("Login error:", error)
		},
	}),
	logout: createResource({
		url: "logout",
		async onSuccess() {
			try {
				await setSetting(POS_OFFLINE_USER_KEY, null)
			} catch (_) {}
			userResource.reset()
			session.user = sessionUser()
			router.replace({ name: "Login" })
		},
		onError(error) {
			console.error("Logout error:", error)
			setSetting(POS_OFFLINE_USER_KEY, null).catch(() => {})
			// Even if logout fails on server, clear local session
			userResource.reset()
			session.user = null
			router.replace({ name: "Login" })
		},
	}),
	user: sessionUser(),
	isLoggedIn: computed(() => !!session.user),
})
