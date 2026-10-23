<template>
	<!-- Chọn người bán (nhân viên bán, hoặc người lập đơn khi quầy tắt NV bán) — cùng kiểu với bộ chọn ngày -->
	<div ref="root" class="relative">
		<button
			type="button"
			:class="[
				'h-9 inline-flex items-center gap-2 ps-1.5 pe-3 rounded-lg text-sm font-medium border transition-all max-w-[230px]',
				modelValue ? 'border-orange-400 bg-orange-50 text-orange-700' : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50',
			]"
			@click="toggle"
		>
			<span
				:class="[
					'w-6 h-6 rounded-full grid place-items-center text-[10px] font-bold flex-shrink-0',
					modelValue ? 'bg-orange-500 text-white' : 'bg-gray-100 text-gray-500',
				]"
			>
				<template v-if="selected">{{ initials(selected.label) }}</template>
				<FeatherIcon v-else name="users" class="w-3.5 h-3.5" />
			</span>
			<span class="truncate">{{ selected ? selected.label : allLabel }}</span>
			<FeatherIcon name="chevron-down" :class="['w-4 h-4 opacity-60 flex-shrink-0 transition-transform', open ? 'rotate-180' : '']" />
		</button>

		<Transition name="debt-pop">
			<div v-if="open" class="absolute end-0 mt-1.5 w-64 bg-white border border-gray-200 rounded-xl shadow-xl z-30 overflow-hidden">
				<div class="px-3 pt-3 pb-2">
					<div class="text-[11px] font-semibold text-gray-500 uppercase mb-1.5">{{ title }}</div>
					<div class="relative">
						<FeatherIcon name="search" class="w-4 h-4 text-gray-400 absolute start-2.5 top-1/2 -translate-y-1/2" />
						<input
							ref="searchInput"
							v-model="query"
							class="w-full h-9 ps-8 pe-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
							:placeholder="__('Search...')"
						/>
					</div>
				</div>
				<div class="max-h-64 overflow-y-auto pb-1.5">
					<button
						v-for="opt in visibleOptions"
						:key="opt.value || '__all__'"
						type="button"
						:class="[
							'w-full flex items-center gap-2.5 px-3 py-2 text-sm text-start transition-colors',
							opt.value === modelValue ? 'bg-orange-50 text-orange-700 font-semibold' : 'text-gray-700 hover:bg-gray-50',
						]"
						@click="pick(opt.value)"
					>
						<span
							:class="[
								'w-7 h-7 rounded-full grid place-items-center text-[11px] font-bold flex-shrink-0',
								opt.value ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-500',
							]"
						>
							<template v-if="opt.value">{{ initials(opt.label) }}</template>
							<FeatherIcon v-else name="users" class="w-3.5 h-3.5" />
						</span>
						<span class="flex-1 truncate">{{ opt.label }}</span>
						<FeatherIcon v-if="opt.value === modelValue" name="check" class="w-4 h-4 flex-shrink-0" />
					</button>
					<div v-if="!visibleOptions.length" class="px-3 py-4 text-center text-sm text-gray-400">{{ __("No results found") }}</div>
				</div>
			</div>
		</Transition>
	</div>
</template>

<script setup>
import { initials } from "@/stores/debtCollection"
import { FeatherIcon } from "frappe-ui"
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue"

const props = defineProps({
	modelValue: { type: String, default: "" },
	/** [{ value, label }] */
	options: { type: Array, default: () => [] },
	/** "owner" = người lập đơn, "sales_person" = nhân viên bán */
	sellerType: { type: String, default: "owner" },
	/** Ghi đè nhãn khi dùng ở màn hình khác (vd. Báo cáo kết ngày) */
	allText: { type: String, default: "" },
	titleText: { type: String, default: "" },
})
const emit = defineEmits(["update:modelValue", "change"])

const root = ref(null)
const searchInput = ref(null)
const open = ref(false)
const query = ref("")

const allLabel = computed(() => props.allText || (props.sellerType === "owner" ? __("All creators") : __("All sales persons")))
const title = computed(() => props.titleText || (props.sellerType === "owner" ? __("Created by") : __("Sales Person")))
const selected = computed(() => props.options.find((o) => o.value === props.modelValue) || null)

const visibleOptions = computed(() => {
	const q = query.value.trim().toLowerCase()
	const list = props.options.filter((o) => !q || String(o.label).toLowerCase().includes(q))
	return q ? list : [{ value: "", label: allLabel.value }, ...list]
})

async function toggle() {
	open.value = !open.value
	if (open.value) {
		query.value = ""
		await nextTick()
		searchInput.value?.focus()
	}
}

function pick(value) {
	open.value = false
	if (value === props.modelValue) return
	emit("update:modelValue", value)
	emit("change", value)
}

function onOutside(event) {
	if (open.value && root.value && !root.value.contains(event.target)) open.value = false
}

onMounted(() => document.addEventListener("mousedown", onOutside))
onBeforeUnmount(() => document.removeEventListener("mousedown", onOutside))
</script>

<style scoped>
.debt-pop-enter-active,
.debt-pop-leave-active {
	transition: opacity 0.12s ease, transform 0.12s ease;
}
.debt-pop-enter-from,
.debt-pop-leave-to {
	opacity: 0;
	transform: translateY(-4px);
}
</style>
