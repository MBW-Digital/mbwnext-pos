<template>
	<div ref="dropdownRef" class="relative">
		<button
			@click="toggleDropdown"
			class="flex items-center justify-center p-1 sm:p-1.5 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-500 transition-colors disabled:opacity-60 disabled:cursor-wait"
			:disabled="isChanging"
			:title="localeConfig.nativeName"
			:aria-label="localeConfig.nativeName"
		>
			<template v-if="isChanging">
				<LoadingIndicator class="w-4 h-3" />
			</template>
			<template v-else>
				<img
					:src="localeConfig.flagUrlSvg"
					:alt="localeConfig.name"
					class="w-5 h-3.5 object-cover rounded-sm shadow-sm"
				/>
			</template>
		</button>

		<Transition
			enter-active-class="transition ease-out duration-150"
			enter-from-class="opacity-0 scale-95"
			enter-to-class="opacity-100 scale-100"
			leave-active-class="transition ease-in duration-100"
			leave-from-class="opacity-100 scale-100"
			leave-to-class="opacity-0 scale-95"
		>
			<div
				v-if="isOpen"
				class="absolute z-50 mt-1 w-auto min-w-0 rounded-md bg-white shadow-lg ring-1 ring-black/5"
				:class="isRTL ? 'start-0' : 'end-0'"
				role="menu"
			>
				<div class="py-0.5">
					<button
						v-for="(config, code) in supportedLocales"
						:key="code"
						@click="selectLanguage(code)"
						class="flex items-center gap-1 px-2 py-1.5 transition-colors"
						:class="locale === code ? 'bg-blue-50' : 'hover:bg-gray-100'"
						role="menuitem"
						:aria-label="config.nativeName"
						:title="config.nativeName"
					>
						<img
							:src="config.flagUrlSvg"
							:alt="config.name"
							class="w-5 h-3.5 object-cover rounded-sm shadow-sm"
						/>
						<FeatherIcon
							v-if="locale === code"
							name="check"
							class="w-3 h-3 text-blue-600 flex-shrink-0"
						/>
					</button>
				</div>
			</div>
		</Transition>
	</div>
</template>

<script setup>
/**
 * @component LanguageSwitcher
 * @description Dropdown component for switching application locale.
 *
 * Features:
 * - Displays current locale with flag and native name
 * - Animated dropdown with available locales
 * - RTL-aware layout (adapts direction based on locale)
 * - Loading state during language change
 * - Click-outside to close dropdown
 *
 * @example
 * <LanguageSwitcher />
 */
import { ref, onMounted, onUnmounted } from "vue"
import { FeatherIcon, LoadingIndicator } from "frappe-ui"
import { useLocale } from "@/composables/useLocale"

// Locale state from composable
const { locale, localeConfig, isRTL, supportedLocales, changeLocale } = useLocale()

// Component state
const isOpen = ref(false)        // Dropdown visibility
const isChanging = ref(false)    // Language change in progress
const dropdownRef = ref(null)    // DOM ref for click-outside detection

/** Toggles dropdown (disabled while changing language) */
const toggleDropdown = () => !isChanging.value && (isOpen.value = !isOpen.value)

/**
 * Handles language selection from dropdown.
 * Closes dropdown immediately, then loads new translations.
 * @param {string} code - Locale code to switch to
 */
const selectLanguage = async (code) => {
	isOpen.value = false
	if (code === locale.value || isChanging.value) return

	isChanging.value = true
	try {
		await changeLocale(code)
	} finally {
		isChanging.value = false
	}
}

/** Closes dropdown when clicking outside the component */
const handleClickOutside = (e) => dropdownRef.value?.contains(e.target) || (isOpen.value = false)

// Event listener lifecycle
onMounted(() => document.addEventListener("click", handleClickOutside))
onUnmounted(() => document.removeEventListener("click", handleClickOutside))
</script>
