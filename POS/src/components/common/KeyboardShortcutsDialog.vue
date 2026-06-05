<template>
	<Dialog
		v-model="show"
		:options="{ title: dialogTitle, size: 'sm' }"
	>
		<template #body-content>
			<div class="max-h-[70vh] overflow-y-auto -mx-1">
				<div
					v-for="(shortcut, index) in shortcuts"
					:key="shortcut.key + index"
					class="flex items-start justify-between gap-4 px-1 py-2.5 border-b border-gray-100 last:border-b-0"
				>
					<span class="font-bold text-gray-900 whitespace-nowrap min-w-[56px]">
						{{ shortcut.key }}
					</span>
					<span class="text-sm text-gray-700 text-end leading-snug">
						{{ shortcut.label }}
					</span>
				</div>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end w-full">
				<Button variant="subtle" @click="show = false">
					{{ closeLabel }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { useLocale } from "@/composables/useLocale"
import { translationVersion } from "@/utils/translation"
import { Button, Dialog } from "frappe-ui"
import { computed, ref, watch } from "vue"

const VI_LABELS = {
	"Function Shortcuts": "Phím tắt chức năng",
	"Add new invoice": "Thêm hóa đơn mới",
	"Toggle auto-print mode": "Bật/Tắt chế độ in tự động",
	"Search items": "Tìm hàng hóa",
	"Search customers": "Tìm khách hàng",
	"Toggle quantity input mode": "Thay đổi chế độ nhập số lượng",
	"Open cash drawer": "Mở két tiền",
	"Customer payment": "Khách thanh toán",
	Payment: "Thanh toán",
	"Scan electronic scale barcode": "Quét mã vạch cân điện tử",
	"Full screen": "Toàn màn hình",
	"Show keyboard shortcuts": "Xem phím tắt",
	"Edit product quantity": "Thay đổi số lượng sản phẩm",
	"Increase product quantity": "Tăng số lượng sản phẩm",
	"Decrease product quantity": "Giảm số lượng sản phẩm",
	"Move to next product": "Di chuyển xuống sản phẩm tiếp theo",
	"Move to previous product": "Di chuyển lên sản phẩm phía trên",
	"Auto-print enabled": "Đã bật in tự động",
	"Auto-print disabled": "Đã tắt in tự động",
	Close: "Đóng",
}

const props = defineProps({
	modelValue: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits(["update:modelValue"])

const { locale } = useLocale()
const show = ref(props.modelValue)

watch(
	() => props.modelValue,
	(value) => {
		show.value = value
	},
)

watch(show, (value) => {
	emit("update:modelValue", value)
})

function label(key) {
	translationVersion.value
	if (locale.value === "vi" && VI_LABELS[key]) {
		return VI_LABELS[key]
	}
	return __(key)
}

const dialogTitle = computed(() => label("Function Shortcuts"))
const closeLabel = computed(() => label("Close"))

const shortcuts = computed(() => [
	{ key: "F1", label: label("Add new invoice") },
	{ key: "F2", label: label("Toggle auto-print mode") },
	{ key: "F3", label: label("Search items") },
	{ key: "F4", label: label("Search customers") },
	{ key: "F6", label: label("Toggle quantity input mode") },
	{ key: "F7", label: label("Open cash drawer") },
	{ key: "F8", label: label("Customer payment") },
	{ key: "F9", label: label("Payment") },
	{ key: "F10", label: label("Scan electronic scale barcode") },
	{ key: "F11", label: label("Full screen") },
	{ key: "F12", label: label("Show keyboard shortcuts") },
	{ key: "Home", label: label("Edit product quantity") },
	{ key: "↑", label: label("Increase product quantity") },
	{ key: "↓", label: label("Decrease product quantity") },
	{ key: "Enter", label: label("Move to next product") },
	{ key: "Shift", label: label("Move to previous product") },
])
</script>
