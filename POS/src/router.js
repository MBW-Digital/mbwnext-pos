import { shiftState } from "@/composables/useShift"
import { userResource } from "@/data/user"
import { createRouter, createWebHistory } from "vue-router"
import { session } from "./data/session"

const routes = [
	{
		path: "/",
		name: "POSSale",
		component: () => import("@/pages/POSSale.vue"),
	},
	{
		name: "Login",
		path: "/account/login",
		component: () => import("@/pages/Login.vue"),
	},
	// Catch-all route
	{
		path: "/:pathMatch(.*)*",
		redirect: "/",
	},
]

const router = createRouter({
	history: createWebHistory("/pos"),
	routes,
})

router.beforeEach((to, from, next) => {
	// Khi đang offline thì không ép người dùng về màn đăng nhập,
	// vì đăng nhập cũng không thực hiện được. Cho phép vào mọi route.
	if (typeof navigator !== "undefined" && !navigator.onLine) {
		return next()
	}

	// Check authentication status (session.user is already set in main.js before app mount)
	const isLoggedIn = session.isLoggedIn

	// Only log during development
	if (import.meta.env.DEV) {
		console.log(
			`[Router] ${to.name} (from: ${from.name || "initial"}), auth: ${isLoggedIn}`,
		)
	}

	// Redirect logic
	if (to.name === "Login" && isLoggedIn) {
		next({ name: "POSSale" })
	} else if (to.name !== "Login" && !isLoggedIn) {
		next({ name: "Login" })
	} else {
		next()
	}
})

export default router
