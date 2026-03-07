<template>
	<Dialog v-model="isOpen" :options="{ size: '5xl' }">
		<template #body-title>
			<h3 class="text-lg font-semibold text-gray-900">{{ __('Quét mã vạch bằng camera') }}</h3>
		</template>
		<template #body-content>
			<div v-if="polyfillError" class="py-8 px-4 text-center text-gray-600">
				<p class="text-sm">{{ polyfillError }}</p>
				<button
					@click="close"
					class="mt-4 px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg text-sm font-medium"
				>
					{{ __('Close') }}
				</button>
			</div>
			<div v-else-if="loadingPolyfill" class="py-12 px-4 text-center text-gray-600">
				<div class="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto"></div>
				<p class="mt-4 text-sm">{{ __('Loading scanner...') }}</p>
			</div>
			<div v-else class="flex flex-col items-stretch">
				<div class="relative aspect-[4/3] max-h-[60vh] bg-black rounded-lg overflow-hidden">
					<video
						ref="videoRef"
						autoplay
						playsinline
						muted
						class="w-full h-full object-cover"
					/>
					<div
						v-if="cameraError"
						class="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/90 text-white p-4"
					>
						<p class="text-sm">{{ cameraError }}</p>
						<button
							@click="close"
							class="mt-4 px-4 py-2 bg-white text-gray-800 rounded-lg text-sm font-medium"
						>
							{{ __('Close') }}
						</button>
					</div>
					<div
						v-if="scanning && !cameraError"
						class="absolute bottom-2 left-0 right-0 text-center text-white text-sm drop-shadow-lg"
					>
						{{ __('Đưa mã vạch vào khung hình') }}
					</div>
				</div>
				<div class="mt-4 flex justify-center gap-2">
					<button
						@click="close"
						class="px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
					>
						{{ __('Huỷ') }}
					</button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Dialog } from "frappe-ui"
import { computed, nextTick, onUnmounted, ref, watch } from "vue"

const props = defineProps({
	modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(["update:modelValue", "barcode"])

const isOpen = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
})

const videoRef = ref(null)
const cameraError = ref("")
const scanning = ref(false)
const loadingPolyfill = ref(false)
const polyfillError = ref("")

let stream = null
let animationId = null
let barcodeDetector = null
let BarcodeDetectorClass = null

async function ensureBarcodeDetector() {
	if (typeof window === "undefined") return null
	if (window.BarcodeDetector) {
		return window.BarcodeDetector
	}
	loadingPolyfill.value = true
	polyfillError.value = ""
	try {
		await import("barcode-detector/polyfill")
		return window.BarcodeDetector || null
	} catch (err) {
		polyfillError.value =
			__("Camera scan is not supported in this browser. Use Chrome on Android or try again with a stable connection.")
		return null
	} finally {
		loadingPolyfill.value = false
	}
}

async function startCamera() {
	if (!videoRef.value) return
	// Camera requires secure context (HTTPS or localhost); on HTTP navigator.mediaDevices is undefined
	const mediaDevices = typeof navigator !== "undefined" ? navigator.mediaDevices : null
	if (!mediaDevices || typeof mediaDevices.getUserMedia !== "function") {
		const isLocalhost =
			typeof location !== "undefined" &&
			(location.hostname === "localhost" || location.hostname === "127.0.0.1")
		if (isLocalhost) {
			cameraError.value =
				__("Trình duyệt không hỗ trợ camera ở địa chỉ này. Thử mở bằng https://localhost hoặc dùng Chrome trên máy tính.")
		} else {
			cameraError.value =
				__("Camera chỉ hoạt động trên kết nối bảo mật (HTTPS). Cách test trên mạng nội bộ: dùng HTTPS (cert tự ký) hoặc tunnel như ngrok (https) trỏ vào máy chạy POS.")
		}
		return
	}
	BarcodeDetectorClass = BarcodeDetectorClass || (await ensureBarcodeDetector())
	if (!BarcodeDetectorClass || polyfillError.value) return
	cameraError.value = ""
	try {
		stream = await mediaDevices.getUserMedia({
			video: {
				facingMode: "environment",
				width: { ideal: 1280 },
				height: { ideal: 720 },
			},
			audio: false,
		})
		videoRef.value.srcObject = stream
		await videoRef.value.play()
		scanning.value = true
		barcodeDetector = new BarcodeDetectorClass({
			formats: ["ean_13", "ean_8", "code_128", "code_39", "codabar", "upc_a", "upc_e", "qr_code"],
		})
		detectLoop()
	} catch (err) {
		scanning.value = false
		if (err.name === "NotAllowedError") {
			cameraError.value = "Quyền truy cập camera bị từ chối. Vui lòng bật camera trong cài đặt trình duyệt."
		} else if (err.name === "NotFoundError") {
			cameraError.value = "Không tìm thấy camera."
		} else {
			cameraError.value = err.message || "Không thể mở camera."
		}
	}
}

function stopCamera() {
	scanning.value = false
	if (animationId != null) {
		cancelAnimationFrame(animationId)
		animationId = null
	}
	if (stream) {
		stream.getTracks().forEach((t) => t.stop())
		stream = null
	}
	if (videoRef.value && videoRef.value.srcObject) {
		videoRef.value.srcObject = null
	}
	barcodeDetector = null
}

async function detectLoop() {
	if (!videoRef.value || !barcodeDetector || !stream || !scanning.value) return
	const video = videoRef.value
	if (video.readyState < 2) {
		animationId = requestAnimationFrame(detectLoop)
		return
	}
	try {
		const barcodes = await barcodeDetector.detect(video)
		if (barcodes.length > 0 && barcodes[0].rawValue) {
			const value = barcodes[0].rawValue.trim()
			if (value) {
				stopCamera()
				emit("barcode", value)
				isOpen.value = false
				return
			}
		}
	} catch (_) {
		// ignore single frame errors
	}
	animationId = requestAnimationFrame(detectLoop)
}

function close() {
	stopCamera()
	isOpen.value = false
}

watch(
	() => props.modelValue,
	async (open) => {
		if (open) {
			polyfillError.value = ""
			BarcodeDetectorClass = null
			const cls = await ensureBarcodeDetector()
			if (!cls && polyfillError.value) return
			BarcodeDetectorClass = cls
			await nextTick()
			setTimeout(startCamera, 150)
		} else {
			stopCamera()
		}
	},
)

onUnmounted(stopCamera)
</script>
