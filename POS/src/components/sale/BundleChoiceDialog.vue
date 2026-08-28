<template>
	<Dialog
		v-model="show"
		:options="{ title: __('Select Product Bundle'), size: 'md' }"
	>
		<template #body-content>
			<p class="text-sm text-gray-600 mb-4">
				{{ __('Cart matches multiple product bundles. Please choose one to apply.') }}
			</p>
			<div class="flex flex-col gap-3 max-h-[420px] overflow-y-auto">
				<button
					v-for="choice in choices"
					:key="choice.bundle_code"
					type="button"
					class="text-start rounded-xl border-2 border-gray-200 p-4 hover:border-blue-500 hover:bg-blue-50 transition-colors"
					@click="selectChoice(choice)"
				>
					<div class="font-semibold text-gray-900">{{ choice.bundle_name }}</div>
					<div class="text-xs text-gray-500 mt-1">{{ choice.bundle_code }}</div>
					<div class="text-sm text-blue-700 mt-2">
						{{ __('Complete sets: {0}', [choice.complete_sets]) }}
					</div>
				</button>
			</div>
		</template>
		<template #actions>
			<Button variant="subtle" @click="show = false">
				{{ __('Cancel') }}
			</Button>
		</template>
	</Dialog>
</template>

<script setup>
import { Button, Dialog } from "frappe-ui"

const show = defineModel({ type: Boolean, default: false })

defineProps({
	choices: {
		type: Array,
		default: () => [],
	},
})

const emit = defineEmits(["select"])

function selectChoice(choice) {
	emit("select", choice)
	show.value = false
}
</script>
