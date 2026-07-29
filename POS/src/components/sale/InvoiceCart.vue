<!--
  InvoiceCart.vue - Shopping Cart Component for POS System

  ============================================================================
  OVERVIEW
  ============================================================================
  This component displays the shopping cart in the POS interface, including:
  - Customer selection/search with instant in-memory filtering
  - Cart items list with quantity controls, UOM selection, and pricing
  - Offers and coupon application buttons
  - Order totals (subtotal, discount, tax, grand total)
  - Checkout and Hold order actions
  - Quick action buttons when cart is empty

  ============================================================================
  COMPONENT STRUCTURE
  ============================================================================

  1. HEADER SECTION (Customer Selection)
     - Shows selected customer info with edit/remove options
     - Search input with instant filtering from cached customer list
     - Dropdown with search results and "Create New Customer" option
     - Works offline using cached customer data

  2. ACTION BUTTONS SECTION (Offers & Coupons)
     - "Offers" button - Shows available promotional offers
     - "Coupon" button - Apply coupon/gift card codes
     - Badge indicators show count of available/applied offers

  3. CART ITEMS SECTION
     - Scrollable list of cart items
     - Each item shows: thumbnail, name, badges (free/discount), price, quantity controls
     - Quantity controls: increment/decrement buttons + manual input
     - UOM (Unit of Measure) dropdown selector
     - Serial item support with edit dialog
     - Empty cart state with quick action buttons

  4. TOTALS SECTION
     - Total Quantity
     - Subtotal
     - Discount (highlighted when applied)
     - Tax
     - Grand Total (emphasized)

  5. ACTION BUTTONS
     - Checkout - Proceed to payment
     - Hold - Save as draft order

  ============================================================================
  FEATURES
  ============================================================================

  - Offline Support: Customer search works offline using cached data
  - Instant Search: In-memory customer filtering for zero-latency results
  - Smart Quantity Steps: Automatically detects decimal precision for +/- buttons
  - UOM Conversion: Change units with automatic price recalculation
  - Serial Number Support: Special handling for serialized inventory items
  - Responsive Design: Adapts to mobile and desktop layouts
  - Touch Optimized: Large tap targets and touch feedback
  - RTL Support: Fully supports right-to-left languages

  ============================================================================
-->
<template>
	<div class="flex flex-col h-full bg-white">
		<!-- Customer + Offers/Coupon header -->
		<div class="border-b border-gray-200 bg-gray-50">
			<div
				v-if="items.length > 0"
				class="flex items-center justify-between px-2 pt-2"
			>
				<h2 class="text-xs font-bold text-gray-900">
					{{ __("Total Quantity") }} : {{ formatQuantity(totalQuantity) }}
				</h2>
				<button
					@click="$emit('clear-cart')"
					class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 transition-colors touch-manipulation"
					type="button"
					:title="__('Clear all items')"
				>
					<svg
						class="w-4 h-4"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V5a2 2 0 00-2-2h-2a2 2 0 00-2 2v2M4 7h16"
						/>
					</svg>
					<span>{{ __("Clear") }}</span>
				</button>
			</div>

			<div
				class="px-2.5 py-2"
				:class="items.length > 0 ? 'flex gap-2 items-stretch px-2 pb-2' : ''"
			>
				<!-- Inline Customer Search/Selection -->
				<div
					ref="customerSearchContainer"
					class="relative min-w-0"
					:class="items.length > 0 ? 'flex-[2]' : ''"
				>
				<div v-if="customer">
					<!-- Two Cards Layout: Customer Card + Document Type Card -->
					<div class="flex items-stretch gap-2">
						<!-- Customer Card -->
						<div
							class="flex-1 flex items-center gap-1.5 bg-white border border-gray-200 rounded-xl shadow-sm min-w-0"
							:class="items.length > 0 ? 'p-1' : 'p-1.5'"
						>
							<!-- Customer Avatar & Info -->
							<div
								class="flex items-center gap-2 min-w-0 flex-1"
								:class="items.length > 0 ? 'px-1 py-0.5' : 'px-1.5 py-1'"
							>
								<div
									class="bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center flex-shrink-0"
									:class="items.length > 0 ? 'w-7 h-7' : 'w-8 h-8'"
								>
									<svg
										class="text-white"
										:class="items.length > 0 ? 'w-3.5 h-3.5' : 'w-4 h-4'"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
									</svg>
								</div>
								<div class="min-w-0 flex-1">
									<p
										class="font-semibold text-gray-900 truncate leading-tight"
										:class="items.length > 0 ? 'text-[11px]' : 'text-xs'"
									>
										{{ customer.customer_name || customer.name }}
									</p>
									<p
										v-if="customer.mobile_no && items.length === 0"
										class="text-[10px] text-gray-500 truncate leading-tight"
									>
										{{ customer.mobile_no }}
									</p>
								</div>
							</div>

							<!-- Action Buttons -->
							<div class="flex items-center gap-0.5 flex-shrink-0" @click.stop>
								<button
									type="button"
									@click.stop="$emit('edit-customer', customer)"
									class="flex items-center justify-center text-blue-500 hover:bg-blue-50 active:bg-blue-100 rounded-lg transition-colors touch-manipulation"
									:class="items.length > 0 ? 'w-6 h-6' : 'w-7 h-7'"
									:title="__('Edit customer details')"
								>
									<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
										<path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
									</svg>
								</button>
								<button
									v-if="items.length === 0"
									type="button"
									@click.stop="$emit('create-customer', '')"
									class="w-7 h-7 flex items-center justify-center text-green-600 hover:bg-green-50 active:bg-green-100 rounded-lg transition-colors touch-manipulation"
									:title="__('Create new customer')"
								>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
										<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
									</svg>
								</button>
								<button
									type="button"
									@click.stop="removeCustomer"
									class="flex items-center justify-center text-red-500 hover:bg-red-50 active:bg-red-100 rounded-lg transition-colors touch-manipulation"
									:class="items.length > 0 ? 'w-6 h-6' : 'w-7 h-7'"
									:title="__('Remove customer')"
								>
									<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
										<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
									</svg>
								</button>
							</div>
						</div>

						<!-- Document Type Card -->
						<div
							v-if="settingsStore.allowSalesOrder && items.length === 0"
							class="flex items-center bg-white border border-gray-200 rounded-xl p-1.5 shadow-sm flex-shrink-0"
						>
							<div class="flex items-center bg-gray-100 rounded-lg p-0.5">
								<button
									type="button"
									@click="selectDocType('Sales Invoice')"
									class="px-2.5 py-1.5 text-[11px] font-semibold rounded-md transition-all duration-200 flex items-center gap-1"
									:class="cartStore.targetDoctype === 'Sales Invoice'
										? 'bg-white text-blue-600 shadow-sm'
										: 'text-gray-500 hover:text-gray-700'"
									:title="__('Sales Invoice')"
								>
									<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
									</svg>
									<span>{{ __("Invoice") }}</span>
								</button>
								<button
									type="button"
									@click="selectDocType('Sales Order')"
									class="px-2.5 py-1.5 text-[11px] font-semibold rounded-md transition-all duration-200 flex items-center gap-1"
									:class="cartStore.targetDoctype === 'Sales Order'
										? 'bg-white text-orange-600 shadow-sm'
										: 'text-gray-500 hover:text-gray-700'"
									:title="__('Sales Order')"
								>
									<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
									</svg>
									<span>{{ __("Order") }}</span>
								</button>
							</div>
						</div>
					</div>
				</div>
				<div v-else>
					<div class="flex gap-1.5">
						<!-- Search Input -->
						<div class="relative flex-1">
							<!-- Search Icon Prefix -->
							<div
								class="absolute inset-y-0 start-0 ps-3 flex items-center pointer-events-none"
							>
								<div
									v-if="customerSearching || (!customersLoaded && customerSearchStore.loading)"
									class="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-blue-500"
								></div>
								<svg
									v-else
									class="w-4 h-4 text-gray-400"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
									/>
								</svg>
							</div>

							<!-- Native Input for Instant Search -->
							<input
								id="cart-customer-search"
								name="cart-customer-search"
								:value="customerSearch"
								@input="handleSearchInput"
								@focus="handleSearchFocus"
								@blur="handleSearchBlur"
								type="text"
								:placeholder="items.length > 0 ? __('Customer...') : __('Search or add customer...')"
								class="w-full ps-9 pe-3 border border-gray-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm transition-shadow"
								:class="items.length > 0 ? 'h-9 text-[11px]' : 'h-10 text-xs'"
								:disabled="!customersLoaded"
								@keydown="handleKeydown"
								autocomplete="off"
								:aria-label="__('Search customer in cart')"
							/>
						</div>

						<!-- Quick Create Customer Button -->
						<button
							type="button"
							@click="createNewCustomer"
							class="flex items-center justify-center bg-green-500 hover:bg-green-600 active:bg-green-700 rounded-xl text-white transition-colors shadow-sm hover:shadow touch-manipulation flex-shrink-0"
							:class="items.length > 0 ? 'w-9 h-9' : 'w-10 h-10'"
							:title="__('Create new customer')"
							:aria-label="__('Create new customer')"
						>
							<svg
								class="w-4 h-4"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
								stroke-width="2"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"
								/>
							</svg>
						</button>

						<!-- Document Type Toggle (Sales Invoice / Sales Order) -->
						<div
							v-if="settingsStore.allowSalesOrder && items.length === 0"
							class="flex items-center bg-gray-100 rounded-xl p-0.5 h-10"
						>
							<button
								type="button"
								@click="selectDocType('Sales Invoice')"
								class="h-full px-2.5 text-xs font-semibold rounded-lg transition-all duration-200 flex items-center gap-1.5"
								:class="cartStore.targetDoctype === 'Sales Invoice'
									? 'bg-white text-blue-600 shadow-sm'
									: 'text-gray-500 hover:text-gray-700'"
								:title="__('Sales Invoice')"
							>
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
								</svg>
								<span class="hidden sm:inline">{{ __("Invoice") }}</span>
							</button>
							<button
								type="button"
								@click="selectDocType('Sales Order')"
								class="h-full px-2.5 text-xs font-semibold rounded-lg transition-all duration-200 flex items-center gap-1.5"
								:class="cartStore.targetDoctype === 'Sales Order'
									? 'bg-white text-orange-600 shadow-sm'
									: 'text-gray-500 hover:text-gray-700'"
								:title="__('Sales Order')"
							>
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
								</svg>
								<span class="hidden sm:inline">{{ __("Order") }}</span>
							</button>
						</div>
					</div>
				</div>

				<!-- Customer Dropdown -->
				<div
					v-if="customerSearchFocused || customerSearch.trim().length >= 2"
					class="absolute z-50 mt-0.5 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-48 overflow-hidden will-change-transform"
				>
					<!-- Frequent Customers Header (when showing suggestions) -->
					<div
						v-if="customerSearchFocused && customerSearch.trim().length < 2 && customerResults.length > 0"
						class="px-2 py-1 bg-gray-50 border-b border-gray-200"
					>
						<span class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
							{{ __('Frequent Customers') }}
						</span>
					</div>

					<!-- Customer Results -->
					<div v-if="customerResults.length > 0" class="max-h-48 overflow-y-auto overscroll-contain">
						<button
							type="button"
							v-for="(cust, index) in customerResults"
							:key="cust.name"
							@mousedown.prevent="selectCustomer(cust)"
							:class="[
								'w-full text-start px-2 py-1.5 flex items-center gap-1.5 border-b border-gray-100 last:border-0 touch-manipulation select-none cursor-pointer active:bg-blue-200',
								index === selectedIndex ? 'bg-blue-100' : 'hover:bg-blue-50 active:bg-blue-100',
							]"
						>
							<div
								class="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 pointer-events-none"
							>
								<span class="text-[10px] font-bold text-blue-600">{{
									getInitials(cust.customer_name)
								}}</span>
							</div>
							<div class="flex-1 min-w-0 pointer-events-none">
								<p class="text-[11px] font-semibold text-gray-900 truncate">
									{{ cust.customer_name }}
								</p>
								<p v-if="cust.mobile_no" class="text-[9px] text-gray-600">
									{{ cust.mobile_no }}
								</p>
							</div>
						</button>
					</div>

					<!-- No Results + Create New Option -->
					<div v-else-if="customerSearch.trim().length >= 2 && !customerSearching">
						<div
							class="px-2 py-1.5 text-center text-[11px] font-medium text-gray-700 border-b border-gray-100"
						>
							{{ __('No results for "{0}"', [customerSearch]) }}
						</div>
					</div>
					<div
						v-else-if="customerSearch.trim().length >= 2 && customerSearching"
						class="px-2 py-1.5 text-center text-[11px] text-gray-500 border-b border-gray-100"
					>
						{{ __('Searching...') }}
					</div>

					<!-- Create New Customer Option -->
					<button
						type="button"
						v-if="customerSearch.trim().length >= 2"
						@mousedown.prevent="createNewCustomer"
						class="w-full text-start px-2 py-1.5 hover:bg-green-50 active:bg-green-100 flex items-center gap-1.5 border-t border-gray-200 touch-manipulation select-none cursor-pointer"
					>
						<div
							class="w-5 h-5 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0 pointer-events-none"
						>
							<svg
								class="w-3 h-3 text-green-600"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M12 4v16m8-8H4"
								/>
							</svg>
						</div>
						<div class="flex-1 pointer-events-none">
							<p class="text-[11px] font-medium text-green-700">
								{{ __("Create New Customer") }}
							</p>
							<p class="text-[9px] text-green-600">"{{ customerSearch }}"</p>
						</div>
					</button>
				</div>
				</div>

				<template v-if="items.length > 0">
					<!-- View All Offers Button -->
					<button
						type="button"
						@click="$emit('show-offers')"
						class="relative flex-1 flex items-center justify-center gap-1.5 px-2.5 py-2 rounded-lg bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 hover:border-green-400 hover:from-green-100 hover:to-emerald-100 hover:shadow-sm transition-all min-w-0 touch-manipulation active:scale-[0.98]"
						:aria-label="__('View all available offers')"
					>
						<svg
							class="w-3.5 h-3.5 text-green-600 flex-shrink-0"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							stroke-width="2"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
							/>
						</svg>
						<span class="text-[11px] font-bold text-green-700">{{ __("Offers") }}</span>
						<span
							v-if="appliedOfferCount > 0"
							class="bg-green-600 text-white text-[9px] font-bold rounded-full px-1.5 py-0.5 flex-shrink-0 min-w-[16px] text-center"
						>
							{{ appliedOfferCount }}
						</span>
					</button>

					<!-- Enter Coupon Code Button -->
					<button
						type="button"
						@click="$emit('apply-coupon')"
						class="relative flex-1 flex items-center justify-center gap-1.5 px-2.5 py-2 rounded-lg bg-gradient-to-r from-purple-50 to-violet-50 border border-purple-200 hover:border-purple-400 hover:from-purple-100 hover:to-violet-100 hover:shadow-sm transition-all min-w-0 touch-manipulation active:scale-[0.98]"
						:aria-label="__('Apply coupon code')"
					>
						<svg
							class="w-3.5 h-3.5 text-purple-600 flex-shrink-0"
							fill="currentColor"
							viewBox="0 0 20 20"
						>
							<path
								fill-rule="evenodd"
								d="M4 2a2 2 0 00-2 2v11a3 3 0 106 0V4a2 2 0 00-2-2H4zm1 14a1 1 0 100-2 1 1 0 000 2zm5-1.757l4.9-4.9a2 2 0 000-2.828L13.485 5.1a2 2 0 00-2.828 0L10 5.757v8.486zM16 18H9.071l6-6H16a2 2 0 012 2v2a2 2 0 01-2 2z"
								clip-rule="evenodd"
							/>
						</svg>
						<span class="text-[11px] font-bold text-purple-700">{{ __("Coupon") }}</span>
						<span
							v-if="availableGiftCards.length > 0"
							class="bg-purple-600 text-white text-[9px] font-bold rounded-full px-1.5 py-0.5 flex-shrink-0 min-w-[16px] text-center"
						>
							{{ availableGiftCards.length }}
						</span>
					</button>
				</template>
			</div>

			<!-- Promotion Campaigns (custom dropdown, names only — not a select) -->
			<div
				v-if="promotionCampaigns.length > 0"
				ref="promotionCampaignDropdownRef"
				class="px-2.5 pb-2 border-t border-gray-100 relative"
				:class="items.length > 0 ? 'px-2' : ''"
			>
				<div class="flex items-center gap-1.5 mb-1">
					<svg
						class="w-3.5 h-3.5 text-amber-600 flex-shrink-0"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
						/>
					</svg>
					<span class="text-[9px] font-semibold text-gray-500 uppercase tracking-wide">
						{{ __("Promotion Campaign") }}
					</span>
					<span
						class="min-w-[18px] h-[18px] px-1 rounded-full bg-amber-100 text-amber-800 text-[9px] font-bold flex items-center justify-center normal-case"
					>
						{{ promotionCampaigns.length }}
					</span>
				</div>
				<button
					type="button"
					class="w-full h-8 px-2 rounded-lg border border-amber-200 bg-amber-50 text-[11px] font-medium text-amber-900 flex items-center justify-between gap-2 touch-manipulation focus:outline-none focus:ring-2 focus:ring-amber-200 focus:border-amber-400"
					:aria-expanded="promotionCampaignDropdownOpen"
					:aria-label="__('Promotion Campaign')"
					@click="togglePromotionCampaignDropdown"
				>
					<span class="truncate text-left">
						<template v-if="promotionCampaigns.length === 1">
							{{ promotionCampaigns[0].promotion_name || promotionCampaigns[0].name }}
						</template>
						<template v-else>
							{{ __("{0} promotion campaigns", [promotionCampaigns.length]) }}
						</template>
					</span>
					<svg
						class="w-4 h-4 text-amber-600 flex-shrink-0 transition-transform duration-200"
						:class="promotionCampaignDropdownOpen ? 'rotate-180' : ''"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
					</svg>
				</button>
				<div
					v-show="promotionCampaignDropdownOpen"
					class="absolute z-30 left-2.5 right-2.5 mt-1 rounded-lg border border-amber-200 bg-white shadow-lg max-h-32 overflow-y-auto"
					:class="items.length > 0 ? 'left-2 right-2' : ''"
				>
					<div
						v-for="campaign in promotionCampaigns"
						:key="campaign.name"
						class="px-2 py-1.5 text-[11px] font-medium text-amber-900 leading-snug break-words border-b border-amber-50 last:border-b-0"
					>
						{{ campaign.promotion_name || campaign.name }}
					</div>
				</div>
			</div>
		</div>

		<!-- Cart Items -->
		<div class="flex-1 overflow-y-auto p-0.5 sm:p-1.5 bg-gray-50">
			<div
				v-if="cartStore.bundleSuggestions.length > 0"
				class="mx-1 mb-2 rounded-lg border border-amber-200 bg-amber-50 p-2"
			>
				<p class="text-[11px] font-semibold text-amber-900 mb-1.5">
					{{ __("Product bundle suggestions") }}
					<span class="font-normal text-amber-700">
						({{ cartStore.bundleSuggestions.length }})
					</span>
				</p>
				<div class="max-h-48 overflow-y-auto flex flex-col gap-1.5 pe-0.5">
					<div
						v-for="suggestion in cartStore.bundleSuggestions"
						:key="suggestion.bundle_code"
						class="rounded-md bg-white border border-amber-100 p-2"
					>
					<p class="text-[11px] font-semibold text-gray-900">
						{{ suggestion.bundle_name }}
					</p>
					<p v-if="suggestion.is_ready_to_apply" class="text-[10px] text-gray-600 mt-1">
						{{ __("Cart has enough items to apply this bundle:") }}
					</p>
					<p v-else class="text-[10px] text-gray-600 mt-1">
						{{ __("Add missing items to complete this bundle:") }}
					</p>
					<div class="flex flex-wrap gap-1 mt-1.5">
						<button
							v-if="suggestion.is_ready_to_apply"
							type="button"
							class="inline-flex items-center rounded-full bg-green-100 px-2 py-1 text-[10px] font-semibold text-green-900 hover:bg-green-200"
							@click="cartStore.applyProductBundleMatch(suggestion)"
						>
							{{ __("Apply bundle") }}
						</button>
						<button
							v-for="missing in suggestion.missing_items"
							:key="`${suggestion.bundle_code}-${missing.item_code}`"
							type="button"
							class="inline-flex items-center rounded-full bg-amber-100 px-2 py-1 text-[10px] font-semibold text-amber-900 hover:bg-amber-200"
							@click="cartStore.addBundleSuggestionItem(suggestion, missing)"
						>
							+ {{ formatQuantity(missing.qty) }} {{ missing.item_name }}
						</button>
					</div>
				</div>
				</div>
			</div>
			<div
				v-if="items.length === 0"
				class="flex flex-col items-center justify-center h-full px-3 sm:px-4 py-6"
			>
				<!-- Empty Cart Icon & Message -->
				<div
					class="w-14 h-14 sm:w-16 sm:h-16 bg-gray-100 rounded-full flex items-center justify-center mb-3"
				>
					<svg
						class="h-7 w-7 sm:h-8 sm:w-8 text-gray-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"
						/>
					</svg>
				</div>
				<p class="text-xs sm:text-sm font-semibold text-gray-900 mb-1">
					{{ __("Your cart is empty") }}
				</p>
				<p class="text-[10px] sm:text-xs text-gray-500 mb-5 sm:mb-6">
					{{ __("Select items to start or choose a quick action") }}
				</p>

				<!-- Quick Actions Grid -->
				<div class="grid grid-cols-2 gap-2 sm:gap-2.5 w-full max-w-lg">
					<!-- View Shift -->
					<button
						type="button"
						@click="$emit('view-shift')"
						class="flex flex-col items-center justify-center p-3 sm:p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 active:bg-blue-100 transition-colors shadow-sm hover:shadow touch-manipulation group"
						:title="__('View current shift details')"
					>
						<div
							class="w-9 h-9 sm:w-10 sm:h-10 bg-blue-50 rounded-full flex items-center justify-center mb-2 group-hover:bg-blue-100 transition-colors"
						>
							<svg
								class="w-5 h-5 text-blue-600"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
								/>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
								/>
							</svg>
						</div>
						<span class="text-[11px] sm:text-xs font-semibold text-gray-700">{{
							__("View Shift")
						}}</span>
					</button>

					<!-- Draft Invoices -->
					<button
						type="button"
						@click="$emit('show-drafts')"
						class="flex flex-col items-center justify-center p-3 sm:p-4 bg-white border border-gray-200 rounded-lg hover:border-purple-300 hover:bg-purple-50 active:bg-purple-100 transition-colors shadow-sm hover:shadow touch-manipulation group"
						:title="__('View draft invoices')"
					>
						<div
							class="w-9 h-9 sm:w-10 sm:h-10 bg-purple-50 rounded-full flex items-center justify-center mb-2 group-hover:bg-purple-100 transition-colors"
						>
							<svg
								class="w-5 h-5 text-purple-600"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
								/>
							</svg>
						</div>
						<span class="text-[11px] sm:text-xs font-semibold text-gray-700">{{
							__("Draft Invoices")
						}}</span>
					</button>

					<!-- Invoice History -->
					<button
						type="button"
						@click="$emit('show-history')"
						class="flex flex-col items-center justify-center p-3 sm:p-4 bg-white border border-gray-200 rounded-lg hover:border-gray-300 hover:bg-gray-50 active:bg-gray-100 transition-colors shadow-sm hover:shadow touch-manipulation group"
						:title="__('View invoice history')"
					>
						<div
							class="w-9 h-9 sm:w-10 sm:h-10 bg-gray-50 rounded-full flex items-center justify-center mb-2 group-hover:bg-gray-100 transition-colors"
						>
							<svg
								class="w-5 h-5 text-gray-600"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
								/>
							</svg>
						</div>
						<span class="text-[11px] sm:text-xs font-semibold text-gray-700">{{
							__("Invoice History")
						}}</span>
					</button>

					<!-- Return Invoice -->
					<button
						type="button"
						@click="$emit('show-return')"
						class="flex flex-col items-center justify-center p-3 sm:p-4 bg-white border border-gray-200 rounded-lg hover:border-red-300 hover:bg-red-50 active:bg-red-100 transition-colors shadow-sm hover:shadow touch-manipulation group"
						:title="__('Process return invoice')"
					>
						<div
							class="w-9 h-9 sm:w-10 sm:h-10 bg-red-50 rounded-full flex items-center justify-center mb-2 group-hover:bg-red-100 transition-colors"
						>
							<svg
								class="w-5 h-5 text-red-600"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
								/>
							</svg>
						</div>
						<span class="text-[11px] sm:text-xs font-semibold text-gray-700">{{
							__("Return Invoice")
						}}</span>
					</button>

					<!-- Close Shift -->
					<button
						type="button"
						@click="$emit('close-shift')"
						class="flex flex-col items-center justify-center p-3 sm:p-4 bg-white border border-gray-200 rounded-lg hover:border-orange-300 hover:bg-orange-50 active:bg-orange-100 transition-colors shadow-sm hover:shadow touch-manipulation group"
						:title="__('Close current shift')"
					>
						<div
							class="w-9 h-9 sm:w-10 sm:h-10 bg-orange-50 rounded-full flex items-center justify-center mb-2 group-hover:bg-orange-100 transition-colors"
						>
							<svg
								class="w-5 h-5 text-orange-600"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
								/>
							</svg>
						</div>
						<span class="text-[11px] sm:text-xs font-semibold text-gray-700">{{
							__("Close Shift")
						}}</span>
					</button>

					<!-- Create Customer -->
					<button
						type="button"
						@click="$emit('create-customer', '')"
						class="flex flex-col items-center justify-center p-3 sm:p-4 bg-white border border-gray-200 rounded-lg hover:border-green-300 hover:bg-green-50 active:bg-green-100 transition-colors shadow-sm hover:shadow touch-manipulation group"
						:title="__('Create new customer')"
					>
						<div
							class="w-9 h-9 sm:w-10 sm:h-10 bg-green-50 rounded-full flex items-center justify-center mb-2 group-hover:bg-green-100 transition-colors"
						>
							<svg
								class="w-5 h-5 text-green-600"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"
								/>
							</svg>
						</div>
						<span class="text-[11px] sm:text-xs font-semibold text-gray-700">{{
							__("Create Customer")
						}}</span>
					</button>
				</div>
			</div>

			<div v-else class="flex flex-col gap-0.5 sm:gap-1">
				<div
					v-for="(item, index) in items"
					:key="item._rowKey || index"
					:data-cart-line-index="index"
					@click="!item.is_free_display && openEditDialog(item)"
					:class="[
						'bg-white border rounded-md p-1 hover:border-blue-300 hover:shadow-sm transition-all duration-200 active:scale-[0.99] group',
						item.is_free_display ? 'border-green-200 bg-green-50/40 cursor-default' : 'cursor-pointer',
						focusedLineIndex === index ? 'border-blue-400 ring-1 ring-blue-200' : (item.is_free_display ? 'border-green-200' : 'border-gray-200'),
					]"
				>
					<div class="flex gap-1.5">
						<!-- Item Image Thumbnail -->
						<div
							class="w-8 h-8 bg-gradient-to-br from-gray-50 to-gray-100 rounded-md flex-shrink-0 flex items-center justify-center overflow-hidden border border-gray-200"
						>
							<img
								v-if="item.image"
								:src="item.image"
								:alt="item.item_name"
								loading="lazy"
								width="32"
								height="32"
								decoding="async"
								class="w-full h-full object-cover"
							/>
							<svg
								v-else
								class="h-4 w-4 text-gray-400"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
								/>
							</svg>
						</div>

						<!-- Item Content -->
						<div class="flex-1 min-w-0 flex flex-col justify-center">
							<!-- Single row: Name + Qty + UOM + Price + Total + Remove -->
							<div class="flex items-center gap-1 overflow-x-auto scrollbar-hide">
								<div class="flex flex-col min-w-0 flex-1">
									<div class="flex items-center gap-1 min-w-0">
										<h4
											class="text-[11px] font-bold truncate leading-tight min-w-0"
											:class="item.is_free_display ? 'text-green-800' : 'text-gray-900'"
										>
											{{ item.item_name }}
										</h4>
										<span
											v-if="item.is_free_display"
											class="inline-flex items-center px-1 py-0.5 bg-green-600 text-white rounded-full text-[8px] font-bold flex-shrink-0"
										>
											{{ __("Free gift") }}
										</span>
										<div
											v-if="item.discount_amount && item.discount_amount > 0"
											class="inline-flex items-center px-1 py-0.5 bg-red-50 text-red-700 rounded-full text-[8px] font-bold border border-red-200 flex-shrink-0"
										>
											{{
												__("{0}%", [
													Number(item.discount_percentage).toFixed(0),
												])
											}}
										</div>
									</div>
									<span
										v-if="item.item_code"
										class="text-[9px] font-semibold text-gray-600 truncate leading-tight"
									>
										{{ item.item_code }}
									</span>
								</div>

								<!-- Quantity -->
								<div
									v-if="item.is_free_display"
									class="flex items-center bg-green-50 border border-green-200 rounded px-1.5 h-6 flex-shrink-0"
									@click.stop
								>
									<span class="text-[11px] font-bold text-green-700">{{ formatQuantity(item.quantity) }}</span>
								</div>
								<div
									v-else-if="item.has_serial_no && item.serial_no"
									class="flex items-center gap-0.5 flex-shrink-0"
									@click.stop
								>
									<div
										class="flex items-center bg-blue-50 border border-blue-200 rounded px-1 h-6"
									>
										<FeatherIcon
											name="hash"
											class="w-2.5 h-2.5 text-blue-500 me-0.5"
										/>
										<span class="text-[11px] font-bold text-blue-700">{{
											item.quantity
										}}</span>
									</div>
									<button
										type="button"
										@click="openEditDialog(item)"
										class="flex items-center justify-center w-6 h-6 bg-blue-500 hover:bg-blue-600 text-white rounded transition-colors"
										:title="__('Edit serials')"
									>
										<FeatherIcon name="edit-2" class="w-2.5 h-2.5" />
									</button>
								</div>
								<div
									v-else
									:class="[
										'flex items-center bg-gray-50 border rounded overflow-hidden flex-shrink-0',
										item.is_resolved_barcode ? 'border-amber-300 bg-amber-50' : 'border-gray-200'
									]"
									@click.stop
								>
									<button
										type="button"
										@click.stop="decrementQuantity(item)"
										:disabled="item.is_resolved_barcode"
										:class="[
											'w-5 h-6 flex items-center justify-center font-bold transition-colors touch-manipulation border-e',
											item.is_resolved_barcode
												? 'bg-gray-100 text-gray-400 cursor-not-allowed border-amber-300'
												: 'bg-white hover:bg-gray-100 text-gray-700 border-gray-200'
										]"
										:aria-label="__('Decrease quantity')"
									>
										<svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M20 12H4" />
										</svg>
									</button>
									<input
										:value="formatQuantity(item.quantity)"
										@click.stop
										@input="updateQuantity(item, $event.target.value)"
										@blur="handleQuantityBlur(item)"
										@keydown.enter="$event.target.blur()"
										type="text"
										inputmode="decimal"
										:disabled="item.is_resolved_barcode"
										:class="[
											'w-14 min-w-[3.5rem] h-6 text-center border-0 text-[11px] font-bold focus:outline-none tabular-nums',
											item.is_resolved_barcode
												? 'bg-amber-50 text-amber-700 cursor-not-allowed'
												: 'bg-white text-gray-900 focus:ring-1 focus:ring-blue-500'
										]"
										:aria-label="__('Quantity')"
									/>
									<button
										type="button"
										@click.stop="incrementQuantity(item)"
										:disabled="item.is_resolved_barcode"
										:class="[
											'w-5 h-6 flex items-center justify-center font-bold transition-colors touch-manipulation border-s',
											item.is_resolved_barcode
												? 'bg-gray-100 text-gray-400 cursor-not-allowed border-amber-300'
												: 'bg-white hover:bg-gray-100 text-gray-700 border-gray-200'
										]"
										:aria-label="__('Increase quantity')"
									>
										<svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M12 4v16m8-8H4" />
										</svg>
									</button>
								</div>

								<!-- UOM -->
								<div class="relative group/uom flex-shrink-0" @click.stop>
									<button
										type="button"
										@click="toggleUomDropdown(item.item_code, item.uom)"
										:disabled="
											item.is_resolved_barcode || !item.item_uoms || item.item_uoms.length === 0
										"
										:class="[
											'h-6 text-[10px] font-bold rounded ps-1.5 pe-4 transition-all touch-manipulation flex items-center justify-center min-w-[40px]',
											item.is_resolved_barcode
												? 'bg-amber-100 text-amber-700 border border-amber-300 cursor-not-allowed'
												: item.item_uoms && item.item_uoms.length > 0
													? 'bg-blue-500 text-white border border-blue-400 hover:bg-blue-600 active:scale-95 cursor-pointer'
													: 'bg-gray-100 text-gray-500 border border-gray-200 cursor-not-allowed opacity-60',
										]"
										:title="
											item.is_resolved_barcode
												? __('UOM locked (barcode item)')
												: item.item_uoms && item.item_uoms.length > 0
													? __('Click to change unit')
													: __('Only one unit available')
										"
									>
										{{
											item.uom ||
											item.stock_uom ||
											__("Nos", null, "UOM")
										}}
									</button>
									<svg
										:class="[
											'absolute end-1 top-1/2 -translate-y-1/2 w-2.5 h-2.5 pointer-events-none transition-transform',
											openUomDropdown === `${item.item_code}-${item.uom}`
												? 'rotate-180'
												: '',
											item.is_resolved_barcode
												? 'text-amber-600'
												: item.item_uoms && item.item_uoms.length > 0
													? 'text-white'
													: 'text-gray-400',
										]"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2.5"
											d="M19 9l-7 7-7-7"
										/>
									</svg>
									<div
										v-if="
											openUomDropdown ===
												`${item.item_code}-${item.uom}` &&
											item.item_uoms &&
											item.item_uoms.length > 0
										"
										class="absolute top-full start-0 mt-0.5 bg-white border border-blue-300 rounded shadow-xl z-50 min-w-full overflow-hidden"
									>
										<button
											type="button"
											@click="selectUom(item, item.stock_uom)"
											:class="[
												'w-full text-start px-2 py-1.5 text-[10px] font-semibold transition-colors border-b border-gray-100',
												(item.uom || item.stock_uom) === item.stock_uom
													? 'bg-blue-50 text-blue-700'
													: 'text-gray-700 hover:bg-blue-50',
											]"
										>
											{{ item.stock_uom || __("Nos", null, "UOM") }}
										</button>
										<button
											v-for="uomData in item.item_uoms"
											:key="uomData.uom"
											type="button"
											@click="selectUom(item, uomData.uom)"
											:class="[
												'w-full text-start px-2 py-1.5 text-[10px] font-semibold transition-colors border-b border-gray-100 last:border-0',
												(item.uom || item.stock_uom) === uomData.uom
													? 'bg-blue-50 text-blue-700'
													: 'text-gray-700 hover:bg-blue-50',
											]"
										>
											{{ uomData.uom }}
										</button>
									</div>
								</div>

								<!-- Unit Price -->
								<span
									v-if="!item.is_free_display"
									class="text-[10px] font-medium text-gray-500 whitespace-nowrap flex-shrink-0"
								>
									{{ formatCurrency(item.rate) }}
								</span>

								<!-- Line Total -->
								<span
									class="text-[11px] font-bold whitespace-nowrap flex-shrink-0"
									:class="item.is_free_display ? 'text-green-700' : 'text-red-600'"
								>
									{{
										item.is_free_display
											? __("Free")
											: formatCurrency(item.amount || item.rate * item.quantity)
									}}
								</span>

								<button
									v-if="!item.is_free_display"
									type="button"
									@click.stop="$emit('remove-item', item.item_code, item.uom)"
									class="text-gray-400 hover:text-red-600 transition-colors flex-shrink-0 p-0.5 touch-manipulation"
									:aria-label="__('Remove {0}', [item.item_name])"
									:title="__('Remove item')"
								>
									<svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
									</svg>
								</button>
							</div>

							<!-- Inline Item Discount Controls + DVNL (DVNL chỉ hiện khi có service_surcharge_item) -->
							<div
								v-if="
									!item.is_free_display &&
									(settingsStore.allowItemDiscount || showColdStorageToggle(item))
								"
								class="mt-0.5 flex items-center justify-between gap-1 text-[10px] text-gray-600"
								@click.stop
							>
								<div class="flex items-center gap-1 flex-1 min-w-0">
									<label
										v-if="showColdStorageToggle(item)"
										class="flex items-center gap-1 cursor-pointer select-none flex-shrink-0"
									>
										<input
											type="checkbox"
											:checked="isColdStorageCheckedForItem(item)"
											@change="toggleColdStorageForItem(item, $event.target.checked, item.quantity)"
											class="w-3 h-3 rounded border-gray-300 text-blue-600 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer"
											:aria-label="__('Add hot/cold service for this item')"
										/>
										<span class="font-medium text-gray-500 whitespace-nowrap">
											{{ __('DVNL') }}
										</span>
									</label>

									<template v-if="settingsStore.allowItemDiscount">
									<select
										class="h-6 min-w-[100px] w-[100px] flex-shrink-0 border border-gray-300 rounded pl-1.5 pr-6 py-0 bg-white text-[10px] leading-tight text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
										:value="getInlineDiscountType(item)"
										@change="
											($event) => {
												const type = $event.target.value;
												setInlineDiscountType(item, type);
												const updates =
													type === 'percentage'
														? {
																discount_percentage: item.discount_percentage || 0,
																discount_amount: 0,
														  }
														: {
																discount_percentage: 0,
																discount_amount: item.discount_amount || 0,
														  };
												cartStore.updateItemDetails(
													item.item_code,
													updates,
													item.uom || item.stock_uom
												);
											}
										"
									>
										<option value="percentage">
											{{ __("Percent (%)") }}
										</option>
										<option value="amount">
											{{ __("Amount") }}
										</option>
									</select>

									<div class="relative flex-1 max-w-[80px]">
										<input
											type="number"
											min="0"
											:step="getInlineDiscountType(item) === 'percentage' ? 'any' : '0.01'"
											inputmode="decimal"
											class="w-full h-6 border border-gray-300 rounded ps-1 pe-4 text-[10px] text-right focus:outline-none focus:ring-1 focus:ring-blue-500"
											:value="
												getInlineDiscountType(item) === 'percentage'
													? item.discount_percentage || ''
													: item.discount_amount || ''
											"
											@change="
												($event) => {
													const raw = Number.parseFloat($event.target.value || '0');
													const value = isNaN(raw) || raw < 0 ? 0 : raw;
													const type = getInlineDiscountType(item);
													const updates =
														type === 'percentage'
															? {
																	discount_percentage: value,
																	discount_amount: 0,
															  }
															: {
																	discount_percentage: 0,
																	discount_amount: value,
															  };
													cartStore.updateItemDetails(
														item.item_code,
														updates,
														item.uom || item.stock_uom
													);
												}
											"
										/>
										<span
											class="absolute inset-y-0 end-1.5 flex items-center text-[9px] sm:text-[10px] text-gray-400 pointer-events-none"
										>
											{{
												getInlineDiscountType(item) === 'percentage' ? '%' : ''
											}}
										</span>
									</div>
									</template>
								</div>

								<!-- Discount amount preview -->
								<div
									v-if="settingsStore.allowItemDiscount && item.discount_amount && item.discount_amount > 0"
									class="flex items-center gap-1 text-[10px] sm:text-xs text-red-600 font-semibold"
								>
									<span>-{{ formatCurrency(item.discount_amount) }}</span>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Totals Summary -->
		<div class="p-1.5 sm:p-2 bg-white border-t border-gray-200">
			<!-- Discount, excluding the coupon — the coupon has its own line below -->
			<div
				v-if="items.length > 0 && displayDiscountAmount > 0"
				class="mb-1.5 flex items-center justify-between bg-red-50 rounded px-1.5 py-1"
			>
				<div class="flex items-center gap-1">
					<svg
						class="w-3.5 h-3.5 text-red-600"
						fill="currentColor"
						viewBox="0 0 20 20"
					>
						<path
							fill-rule="evenodd"
							d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9a1 1 0 000 2h6a1 1 0 100-2H7z"
							clip-rule="evenodd"
						/>
					</svg>
					<span class="text-xs font-bold text-red-700">{{ __("Discount") }}</span>
				</div>
				<span class="text-sm font-extrabold text-red-600 text-center min-w-[60px]">{{
					formatCurrency(displayDiscountAmount)
				}}</span>
			</div>

			<!-- Coupon discount: shown separately, with its % when the coupon is percentage-based -->
			<div
				v-if="items.length > 0 && couponDiscountAmount > 0"
				class="mb-1.5 flex items-center justify-between bg-purple-50 rounded px-1.5 py-1"
			>
				<div class="flex items-center gap-1 min-w-0">
					<svg
						class="w-3.5 h-3.5 text-purple-600 flex-shrink-0"
						fill="currentColor"
						viewBox="0 0 20 20"
					>
						<path
							d="M10 2a1 1 0 011 1v1a1 1 0 002 0V3a1 1 0 112 0v1a2 2 0 002 2v2a2 2 0 000 4v2a2 2 0 00-2 2v1a1 1 0 11-2 0v-1a1 1 0 10-2 0v1a1 1 0 11-2 0v-1a1 1 0 10-2 0v1a1 1 0 11-2 0v-1a2 2 0 00-2-2v-2a2 2 0 000-4V6a2 2 0 002-2V3a1 1 0 011-1h4z"
						/>
					</svg>
					<span class="text-xs font-bold text-purple-700 truncate">{{ __("Coupon Discount") }}</span>
					<span
						v-if="couponDiscountPercentage > 0"
						class="text-[10px] font-bold text-purple-700 bg-purple-200 rounded px-1 py-0.5 flex-shrink-0"
					>
						{{ couponDiscountPercentage }}%
					</span>
				</div>
				<span class="text-sm font-extrabold text-purple-600 text-center min-w-[60px]">{{
					formatCurrency(couponDiscountAmount)
				}}</span>
			</div>

			<!-- Grand Total -->
			<div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-2.5 mb-1.5">
				<div class="flex items-center justify-between">
					<span class="text-sm font-extrabold text-gray-900">{{
						__("Grand Total")
					}}</span>
					<span
						class="text-xl sm:text-2xl !font-black text-red-600 text-end min-w-[80px] tabular-nums leading-none"
						style="font-weight: 900"
					>
						{{ formatCurrency(displayGrandTotal) }}
					</span>
				</div>
			</div>

			<!-- Action Buttons -->
			<div class="flex gap-1.5">
				<!-- Checkout Button (Primary - 50% width) -->
				<button
					type="button"
					@click="handleProceedToPayment"
					:disabled="items.length === 0"
					:class="[
						'flex-1 py-2.5 px-3 rounded-lg font-bold text-xs text-white transition-all flex items-center justify-center touch-manipulation',
						items.length === 0
							? 'bg-gray-300 cursor-not-allowed'
							: 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 shadow-lg hover:shadow-xl active:scale-[0.98]',
					]"
					:aria-label="__('Proceed to payment')"
				>
					<svg
						class="w-4 h-4 me-1.5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
						/>
					</svg>
					<span>{{ __("Checkout") }}</span>
				</button>

				<!-- Hold Order Button (Secondary - 50% width) -->
				<button
					type="button"
					v-if="items.length > 0"
					@click="$emit('save-draft')"
					class="flex-1 py-2.5 px-2 rounded-lg font-semibold text-xs text-orange-700 bg-orange-50 hover:bg-orange-100 active:bg-orange-200 transition-all touch-manipulation active:scale-[0.98] flex items-center justify-center"
					:aria-label="__('Hold order as draft')"
				>
					<svg
						class="w-4 h-4 me-1.5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						stroke-width="2"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"
						/>
					</svg>
					<span>{{ __("Hold", null, "order") }}</span>
				</button>
			</div>
		</div>

		<!-- Edit Item Dialog -->
		<EditItemDialog
			v-model="showEditDialog"
			:item="selectedItem"
			:warehouses="warehouses"
			:currency="currency"
			@update-item="handleUpdateItem"
		/>

	</div>
</template>

<script setup>
/**
 * ============================================================================
 * IMPORTS
 * ============================================================================
 */
import { usePOSCartStore } from "@/stores/posCart";
import { usePOSSettingsStore } from "@/stores/posSettings";
import { usePOSOffersStore } from "@/stores/posOffers";
import { useCustomerSearchStore } from "@/stores/customerSearch";
import { DEFAULT_CURRENCY, formatCurrency as formatCurrencyUtil } from "@/utils/currency";
import { useFormatters } from "@/composables/useFormatters";
import { isOffline } from "@/utils/offline";
import { offlineWorker } from "@/utils/offline/workerClient";
import { logger } from "@/utils/logger";
import { FeatherIcon } from "frappe-ui";

const log = logger.create("InvoiceCart");
import { createResource } from "frappe-ui";
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from "vue";
import EditItemDialog from "./EditItemDialog.vue";

/**
 * ============================================================================
 * STORES & COMPOSABLES
 * ============================================================================
 */
const cartStore = usePOSCartStore(); // Pinia store for cart state management
const settingsStore = usePOSSettingsStore(); // Pinia store for POS settings
const offersStore = usePOSOffersStore(); // Pinia store for offers/promotions
const customerSearchStore = useCustomerSearchStore(); // Pinia store for customer search
const { formatQuantity } = useFormatters(); // Quantity formatting utilities

function handleProceedToPayment() {
	emit("proceed-to-payment");
}

/**
 * ============================================================================
 * PROPS
 * ============================================================================
 * @prop {Array} items - Cart items array with item details (item_code, quantity, rate, etc.)
 * @prop {Object} customer - Selected customer object (name, customer_name, mobile_no)
 * @prop {Number} subtotal - Cart subtotal before tax and discounts
 * @prop {Number} taxAmount - Total tax amount
 * @prop {Number} discountAmount - Total discount amount applied
 * @prop {Number} grandTotal - Final total (subtotal - discount + tax)
 * @prop {String} posProfile - Current POS Profile name
 * @prop {String} currency - Currency code for formatting (e.g., "USD", "EUR")
 * @prop {Array} appliedOffers - List of currently applied promotional offers
 * @prop {Array} warehouses - Available warehouses for item selection
 */
const props = defineProps({
	items: {
		type: Array,
		default: () => [],
	},
	customer: Object,
	subtotal: {
		type: Number,
		default: 0,
	},
	taxAmount: {
		type: Number,
		default: 0,
	},
	discountAmount: {
		type: Number,
		default: 0,
	},
	// Coupon-only portion of discountAmount — displayed on its own line, not lumped
	// into the Discount line above it
	couponDiscount: {
		type: Number,
		default: 0,
	},
	appliedCoupon: {
		type: Object,
		default: null,
	},
	grandTotal: {
		type: Number,
		default: 0,
	},
	posProfile: String,
	currency: {
		type: String,
		default: DEFAULT_CURRENCY,
	},
	appliedOffers: {
		type: Array,
		default: () => [],
	},
	warehouses: {
		type: Array,
		default: () => [],
	},
	/** Item code cho dịch vụ làm nóng/lạnh. Rỗng = ẩn DVNL (chưa cấu hình trên POS Profile). */
	coldStorageFeeItemCode: {
		type: String,
		default: '',
	},
});

/**
 * ============================================================================
 * EMITS
 * ============================================================================
 * Events emitted to parent component for cart operations
 */
const emit = defineEmits([
	"update-quantity", // (itemCode, newQty, uom?) - Update item quantity
	"remove-item", // (itemCode, uom?) - Remove item from cart
	"select-customer", // (customer) - Select/change customer
	"edit-customer", // (customer) - Open edit customer dialog
	"create-customer", // (searchText) - Open create customer dialog
	"proceed-to-payment", // () - Navigate to payment screen
	"clear-cart", // () - Clear all items from cart
	"save-draft", // () - Save current cart as draft/hold order
	"apply-coupon", // () - Open coupon application dialog
	"show-coupons", // () - Show available coupons
	"show-offers", // () - Show available offers dialog
	"remove-offer", // (offerId) - Remove applied offer
	"update-uom", // (itemCode, newUom) - Change item's unit of measure
	"edit-item", // (item) - Open item edit dialog
	"view-shift", // () - View current shift details
	"show-drafts", // () - Show draft/held orders
	"show-history", // () - Show invoice history
	"show-return", // () - Open return invoice dialog
	"close-shift", // () - Close current shift
	"add-cold-storage-fee-line", // (count: number) - Add dịch vụ làm nóng/lạnh với số lượng count
	"remove-cold-storage-fee-line", // (count: number) - Giảm bớt dịch vụ làm nóng/lạnh
	// "create-sales-order", // () - Create Sales Order // Removed as per instruction
]);

/**
 * ============================================================================
 * REACTIVE STATE
 * ============================================================================
 */
// Customer search state
const customerSearch = ref(""); // Current search query
const customerSearchContainer = ref(null); // Ref to search container for click-outside detection
const customerSearchFocused = ref(false); // Track if search input is focused
const customerResults = ref([]); // Debounced search results (server / IndexedDB)
const allCustomers = computed(() => customerSearchStore.allCustomers);
// Online: ready immediately. Offline: wait until cache is available.
const customersLoaded = computed(
	() =>
		!isOffline() ||
		customerSearchStore.searchReady ||
		customerSearchStore.allCustomers.length > 0,
);
const customerSearching = computed(() => customerSearchStore.searching);
const selectedIndex = ref(-1); // Keyboard navigation index for search results
const availableGiftCards = ref([]); // Available gift cards for current customer
const previousCustomer = ref(null); // Store previous customer for restore on blur
let customerSearchTimer = null;

// Edit item dialog state
const showEditDialog = ref(false); // Controls edit dialog visibility
const selectedItem = ref(null); // Item being edited

// UOM dropdown state - tracks which item's UOM dropdown is open (by item_code)
const openUomDropdown = ref(null);

// Inline discount type state per item (percentage/amount)
const inlineDiscountTypes = ref({});

/**
 * ============================================================================
 * API RESOURCES
 * ============================================================================
 * These resources handle data fetching from the server with offline support.
 * Data is cached in the service worker for offline access.
 */

/**
 * Customer Loading
 *
 * Uses the shared customerSearchStore for customer data.
 * This ensures customers are synced across all components (InvoiceCart, CustomerDialog).
 * New customers are immediately available after creation without page refresh.
 */
// Load customers via the shared Pinia store (if not already loaded)
if (props.posProfile) {
	customerSearchStore.loadAllCustomers(props.posProfile);
}

// Load offers on component init (uses shared store method to prevent duplicate fetches)
// ensureOffersFetched handles both online/offline cases and caching
if (props.posProfile) {
	offersStore.ensureOffersFetched(props.posProfile);
}

const promotionCampaigns = ref([]);
const promotionCampaignDropdownOpen = ref(false);
const promotionCampaignDropdownRef = ref(null);

function togglePromotionCampaignDropdown() {
	promotionCampaignDropdownOpen.value = !promotionCampaignDropdownOpen.value;
}

const promotionCampaignsResource = createResource({
	url: "pos_next.api.offers.get_promotion_campaigns_for_pos",
	makeParams() {
		return { pos_profile: props.posProfile };
	},
	auto: false,
	onSuccess(data) {
		promotionCampaigns.value = data?.message || data || [];
		promotionCampaignDropdownOpen.value = false;
	},
	onError(error) {
		log.warn("Failed to load promotion campaigns:", error);
		promotionCampaigns.value = [];
	},
});

watch(
	() => props.posProfile,
	(profile) => {
		if (profile) {
			promotionCampaignsResource.reload();
		} else {
			promotionCampaigns.value = [];
			promotionCampaignDropdownOpen.value = false;
		}
	},
	{ immediate: true },
);

/**
 * Gift Cards Resource
 *
 * Fetches active coupon codes and gift cards for the selected customer.
 * - Only fetches when a customer is selected and online
 * - Reloads when customer changes (via watcher)
 * - Used for the "Coupon" button badge count
 *
 * @endpoint pos_next.api.offers.get_active_coupons
 */
const giftCardsResource = createResource({
	url: "pos_next.api.offers.get_active_coupons",
	makeParams() {
		return {
			customer: props.customer?.name || props.customer,
			company: props.posProfile, // Will get company from profile
		};
	},
	auto: false,
	onSuccess(data) {
		availableGiftCards.value = data?.message || data || [];
	},
});

/**
 * Watch for customer changes to load their gift cards.
 * Reloads gift cards resource when customer is selected (and online).
 * Clears gift cards when customer is removed or offline.
 */
watch(
	() => props.customer,
	(newCustomer) => {
		if (newCustomer && props.posProfile && !isOffline()) {
			giftCardsResource.reload();
		} else {
			availableGiftCards.value = [];
		}
	}
);

/**
 * ============================================================================
 * COMPUTED PROPERTIES
 * ============================================================================
 */

/**
 * Count of currently applied promotional offers.
 * Used for the badge on the "Offers" button.
 * @returns {Number} Count of applied offers
 */
const appliedOfferCount = computed(() => (props.appliedOffers || []).length);

function showFrequentCustomers() {
	const frequent = customerSearchStore.getFrequentCustomerObjects(5);
	if (frequent.length) {
		customerResults.value = frequent;
		return;
	}
	customerResults.value = allCustomers.value.slice(0, 5);
}

async function runCustomerSearch(term) {
	const q = term.trim();
	if (q.length < 2) {
		if (customerSearchFocused.value) showFrequentCustomers();
		else customerResults.value = [];
		return;
	}
	const results = await customerSearchStore.searchCustomers(q, props.posProfile, 20);
	// Ignore stale responses if the input changed
	if (customerSearch.value.trim() !== q) return;
	customerResults.value = results;
}

/**
 * Reset keyboard selection index when search results change.
 */
watch(customerResults, () => {
	selectedIndex.value = -1;
});

/**
 * Total quantity shown in cart header (paid + free gift lines).
 */
const totalQuantity = computed(() => {
	return props.items.reduce((sum, item) => sum + (item.quantity || 0), 0);
});

/**
 * Dịch vụ làm nóng/lạnh: lưu per-item (item_code + uom) thay vì phân bổ theo thứ tự.
 * Chỉ bật khi POS Profile có service_surcharge_item.
 */
const coldStorageFeeItemCode = computed(
	() => props.coldStorageFeeItemCode || ''
);

function showColdStorageToggle(item) {
	const code = coldStorageFeeItemCode.value;
	return Boolean(code) && item.item_code !== code;
}

// Map: key (item_code|uom) -> quantity đã chọn dịch vụ cho dòng đó
const coldStorageItems = ref({});

function getItemKey(item) {
	return `${item.item_code}|${item.uom || item.stock_uom || ''}`;
}

// Sync coldStorageItems khi có fee lines sẵn (load từ cart cũ) - phân bổ theo thứ tự
function syncColdStorageFromCart() {
	const code = coldStorageFeeItemCode.value;
	if (!code) {
		coldStorageItems.value = {};
		return;
	}
	const items = (props.items || []).filter((i) => i.item_code !== code && !i.is_free_display);
	const totalFee = (props.items || [])
		.filter((i) => i.item_code === code)
		.reduce((sum, i) => sum + (Number(i.quantity) || 0), 0);
	let remaining = totalFee;
	const next = {};
	for (const item of items) {
		const qty = Math.max(0, Math.floor(Number(item.quantity) || 0));
		const share = Math.min(qty, remaining);
		remaining -= share;
		if (share > 0) next[getItemKey(item)] = share;
	}
	coldStorageItems.value = next;
}

// Khởi tạo khi có fee lines nhưng coldStorageItems rỗng (ví dụ: mở cart đã lưu)
const coldStorageServiceLineCount = computed(() => {
	const code = coldStorageFeeItemCode.value;
	return (props.items || [])
		.filter((i) => i.item_code === code)
		.reduce((sum, i) => sum + (Number(i.quantity) || 0), 0);
});

// Khi items thay đổi: xóa key không còn trong cart, emit remove cho phần dư
watch(
	() => props.items,
	(newItems) => {
		const code = coldStorageFeeItemCode.value;
		const keysInCart = new Set(
			(newItems || [])
				.filter((i) => i.item_code !== code)
				.map((i) => getItemKey(i))
		);
		const map = { ...coldStorageItems.value };
		let changed = false;
		for (const key of Object.keys(map)) {
			if (!keysInCart.has(key)) {
				emit('remove-cold-storage-fee-line', map[key]);
				delete map[key];
				changed = true;
			}
		}
		if (changed) coldStorageItems.value = map;
	},
	{ deep: true }
);

// Sync lần đầu khi có fee lines
watch(
	coldStorageServiceLineCount,
	(count) => {
		if (count > 0 && Object.keys(coldStorageItems.value).length === 0) {
			syncColdStorageFromCart();
		}
	},
	{ immediate: true }
);

function isColdStorageCheckedForItem(item) {
	const key = getItemKey(item);
	return (coldStorageItems.value[key] || 0) > 0;
}

function toggleColdStorageForItem(item, checked, quantity) {
	if (!coldStorageFeeItemCode.value) return;

	const qty = Math.max(0, Math.floor(Number(quantity) || 0));
	if (qty <= 0) return;

	const key = getItemKey(item);
	const map = coldStorageItems.value;

	if (checked) {
		map[key] = (map[key] || 0) + qty;
		emit('add-cold-storage-fee-line', qty);
	} else {
		const current = map[key] || 0;
		const remove = Math.min(current, qty);
		if (remove > 0) {
			map[key] = current - remove;
			if (map[key] <= 0) delete map[key];
			emit('remove-cold-storage-fee-line', remove);
		}
	}
	coldStorageItems.value = { ...map };
}

/**
 * Display subtotal adjusted for tax-inclusive mode.
 *
 * When tax is inclusive, the raw subtotal from the store includes tax.
 * For clear cashier display, we show:
 * - Subtotal: Net amount (before tax) = gross - tax
 * - Tax: The extracted tax amount
 * - Grand Total: gross amount = Subtotal + Tax
 *
 * When tax is exclusive, subtotal is already net (before tax).
 *
 * @returns {Number} Subtotal amount to display (net amount before tax)
 */
const displaySubtotal = computed(() => {
	if (cartStore.taxInclusive) {
		// Tax inclusive: subtotal from store is gross (includes tax)
		// Display the net amount (before tax) for clarity
		return props.subtotal - props.taxAmount;
	}
	// Tax exclusive: subtotal is already net (before tax)
	return props.subtotal;
});

/**
 * Display grand total — dùng thẳng grandTotal từ store (đã tính additional discount).
 * Không tính lại từ subtotal+tax-discount vì sẽ bỏ sót invoice-level discount (pricing rule).
 */
const displayGrandTotal = computed(() => props.grandTotal);

/** Coupon discount shown on its own line, never inside the Discount line. */
const couponDiscountAmount = computed(() =>
	Math.max(0, Number(props.couponDiscount) || 0),
);

/** Discount line excludes the coupon so the two lines don't double-count it. */
const displayDiscountAmount = computed(() =>
	Math.max(0, (Number(props.discountAmount) || 0) - couponDiscountAmount.value),
);

/** Percentage-type coupons show their % next to the label; amount-type show nothing. */
const couponDiscountPercentage = computed(() => {
	const coupon = props.appliedCoupon;
	if (!coupon || coupon.type !== "Percentage") return 0;
	return Number(coupon.percentage) || 0;
});

/**
 * ============================================================================
 * FUNCTIONS
 * ============================================================================
 */

// ─────────────────────────────────────────────────────────────────────────────
// Customer Search Functions
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Debounced customer search — server-side when online (avoids scanning 300k+ in UI).
 */
function handleSearchInput(event) {
	customerSearch.value = event.target.value;
	const term = customerSearch.value;

	if (customerSearchTimer) clearTimeout(customerSearchTimer);

	if (term.trim().length < 2) {
		customerSearchStore.clearSearch();
		if (customerSearchFocused.value) showFrequentCustomers();
		else customerResults.value = [];
		return;
	}

	customerSearchTimer = setTimeout(() => {
		runCustomerSearch(term);
	}, 250);
}

// Track if customer history has been loaded this session
const customerHistoryLoaded = ref(false);

/**
 * Handle search input focus - shows frequent customers dropdown.
 */
function handleSearchFocus() {
	customerSearchFocused.value = true;
	if (!customerHistoryLoaded.value) {
		customerSearchStore.loadCustomerHistory();
		customerHistoryLoaded.value = true;
	}
	if (customerSearch.value.trim().length < 2) {
		showFrequentCustomers();
	}
}

/**
 * Handle search input blur - hides dropdown after a short delay.
 * Short delay as fallback for keyboard/tab navigation (mousedown.prevent handles click cases).
 */
function handleSearchBlur() {
	// Reduced delay - mousedown.prevent handles most cases, this is just for keyboard nav
	setTimeout(() => {
		customerSearchFocused.value = false;
	}, 100);
}

/**
 * Handle keyboard navigation in customer search dropdown.
 * Supports:
 * - ArrowDown/ArrowUp: Navigate through results
 * - Enter: Select current or auto-select single result
 * - Escape: Clear search
 *
 * @param {KeyboardEvent} event - Keyboard event from search input
 */
function handleKeydown(event) {
	if (customerResults.value.length === 0) return;

	if (event.key === "ArrowDown") {
		event.preventDefault();
		selectedIndex.value = Math.min(selectedIndex.value + 1, customerResults.value.length - 1);
	} else if (event.key === "ArrowUp") {
		event.preventDefault();
		selectedIndex.value = Math.max(selectedIndex.value - 1, -1);
	} else if (event.key === "Enter") {
		event.preventDefault();
		if (selectedIndex.value >= 0 && selectedIndex.value < customerResults.value.length) {
			selectCustomer(customerResults.value[selectedIndex.value]);
		} else if (customerResults.value.length === 1) {
			// Auto-select if only one result
			selectCustomer(customerResults.value[0]);
		}
	} else if (event.key === "Escape") {
		customerSearch.value = "";
	}
}

/**
 * Select a customer from search results.
 * Emits select-customer event and resets search state.
 * Tracks customer selection for frequency-based suggestions.
 * @param {Object} cust - Customer object to select
 */
function selectCustomer(cust) {
	// Track selection for frequent customers feature
	customerSearchStore.trackCustomerSelection(cust.name, cust);
	emit("select-customer", cust);
	customerSearch.value = "";
	customerResults.value = [];
	selectedIndex.value = -1;
	customerSearchFocused.value = false;
	previousCustomer.value = null;
}

/**
 * Remove the selected customer.
 * Clears the customer and focuses the search input.
 */
async function removeCustomer() {
	previousCustomer.value = null;
	await clearCustomer();
}

/**
 * Clear the currently selected customer.
 * Emits select-customer with null to deselect.
 */
async function clearCustomer() {
	emit("select-customer", null);
	await nextTick();
	const searchInput = document.getElementById("cart-customer-search");
	if (searchInput) {
		searchInput.focus();
	}
}

/**
 * Open customer creation dialog with current search text.
 * Pre-fills the new customer name with the search query.
 */
function createNewCustomer() {
	const searchValue = customerSearch.value;
	// Close dropdown immediately
	customerSearch.value = "";
	customerSearchFocused.value = false;
	// Emit event to open customer creation dialog
	emit("create-customer", searchValue);
}

// ─────────────────────────────────────────────────────────────────────────────
// Utility Functions
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Get initials from a customer name for avatar display.
 * Returns first letter of first two words, or first two letters if single word.
 *
 * @param {String} name - Customer name
 * @returns {String} 2-letter initials (uppercase)
 */
function getInitials(name) {
	if (!name) return "?";
	const parts = name.split(" ");
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.substring(0, 2).toUpperCase();
}

/**
 * Format a numeric amount as currency string.
 * Uses the component's currency prop for formatting.
 *
 * @param {Number} amount - Amount to format
 * @returns {String} Formatted currency string (e.g., "$1,234.56")
 */
function formatCurrency(amount) {
	return formatCurrencyUtil(Number.parseFloat(amount || 0), props.currency);
}

// ─────────────────────────────────────────────────────────────────────────────
// Quantity Control Functions
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Intelligently determine the step size based on current quantity.
 * - Whole numbers (1, 2, 3): step by 1
 * - Multiples of 0.5 (1.5, 2.5): step by 0.5
 * - Multiples of 0.25 (0.25, 0.75): step by 0.25
 * - Multiples of 0.1 (0.1, 0.3): step by 0.1
 * - Other decimals: step by 0.01
 */
function getSmartStep(quantity) {
	// Check if it's a whole number
	if (quantity === Math.floor(quantity)) {
		return 1;
	}

	// Round to 4 decimal places to avoid floating point errors
	const rounded = Math.round(quantity * 10000) / 10000;

	// Check if it's a multiple of 0.5
	if (Math.abs(rounded % 0.5) < 0.0001) {
		return 0.5;
	}

	// Check if it's a multiple of 0.25
	if (Math.abs(rounded % 0.25) < 0.0001) {
		return 0.25;
	}

	// Check if it's a multiple of 0.1
	if (Math.abs(rounded % 0.1) < 0.0001) {
		return 0.1;
	}

	// For other decimals, use 0.01 for fine control
	return 0.01;
}

/**
 * Increment item quantity using smart step.
 * Uses getSmartStep to determine appropriate increment value.
 *
 * @param {Object} item - Cart item to increment
 */
function incrementQuantity(item) {
	// Prevent editing resolved barcode items
	if (item.is_resolved_barcode) return;

	const step = getSmartStep(item.quantity);
	const newQty = Math.round((item.quantity + step) * 10000) / 10000;
	emit("update-quantity", item.item_code, newQty, item.uom);
}

/**
 * Decrement item quantity using smart step.
 * Removes item if quantity would become zero or negative.
 *
 * @param {Object} item - Cart item to decrement
 */
function decrementQuantity(item) {
	// Prevent editing resolved barcode items
	if (item.is_resolved_barcode) return;

	const step = getSmartStep(item.quantity);
	const newQty = Math.round((item.quantity - step) * 10000) / 10000;

	if (newQty <= 0) {
		// If quantity would be 0 or negative, remove the item
		emit("remove-item", item.item_code, item.uom);
	} else {
		emit("update-quantity", item.item_code, newQty, item.uom);
	}
}

/**
 * Update quantity from direct input (manual typing).
 * Allows any positive number during typing without rounding.
 *
 * @param {Object} item - Cart item to update
 * @param {String} value - New quantity value from input
 */
  
function updateQuantity(item, value) {
	// Prevent editing resolved barcode items
	if (item.is_resolved_barcode) return;

	const qty = Number.parseFloat(value);

	// If the input isn't a valid number (e.g., user cleared the field), do nothing
	if (isNaN(qty)) return;

	// If quantity is zero or negative, remove the item from the cart
	if (qty <= 0) return emit("remove-item", item.item_code, item.uom);

	// For positive numbers, update quantity immediately (no rounding here while typing)
	emit("update-quantity", item.item_code, qty, item.uom);
}

/**
 * Handle quantity input blur - validate and round.
 * Called when user leaves the quantity input field.
 * - Removes item if quantity is 0 or invalid
 * - Rounds to 4 decimal places for consistency
 *
 * @param {Object} item - Cart item that lost focus
 */
function handleQuantityBlur(item) {
	// When user leaves the input field, round and validate
	if (!item.quantity || item.quantity <= 0) {
		// If quantity is 0 or invalid, remove the item
		emit("remove-item", item.item_code, item.uom);
	} else {
		// Round to 4 decimal places for consistency
		const roundedQty = Math.round(item.quantity * 10000) / 10000;
		if (roundedQty !== item.quantity) {
			emit("update-quantity", item.item_code, roundedQty, item.uom);
		}
	}
}

// Helper to build unique key for inline discount state
function getInlineDiscountKey(item) {
	return `${item.item_code}::${item.uom || item.stock_uom || ""}`;
}

// Get inline discount type for an item (percentage/amount)
function getInlineDiscountType(item) {
	const key = getInlineDiscountKey(item);
	const current = inlineDiscountTypes.value[key];
	if (current === "percentage" || current === "amount") {
		return current;
	}

	// Derive from item data when not set
	const derived =
		item.discount_amount && item.discount_amount > 0 ? "amount" : "percentage";
	inlineDiscountTypes.value = {
		...inlineDiscountTypes.value,
		[key]: derived,
	};
	return derived;
}

// Update inline discount type for an item
function setInlineDiscountType(item, type) {
	const key = getInlineDiscountKey(item);
	inlineDiscountTypes.value = {
		...inlineDiscountTypes.value,
		[key]: type === "amount" ? "amount" : "percentage",
	};
}

// ─────────────────────────────────────────────────────────────────────────────
// UOM (Unit of Measure) Functions
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Toggle UOM dropdown visibility for an item.
 * Uses unique key combining item_code + uom to handle same item with different UOMs.
 */
function toggleUomDropdown(itemCode, uom) {
	const key = `${itemCode}-${uom}`;
	openUomDropdown.value = openUomDropdown.value === key ? null : key;
}

/**
 * Select a UOM from dropdown - changes UOM and closes dropdown
 * Handles merging if target UOM already exists in cart
 */
async function selectUom(item, newUom) {
	if (item.uom === newUom) {
		openUomDropdown.value = null;
		return;
	}

	const currentUom = item.uom || item.stock_uom;
	await cartStore.changeItemUOM(item.item_code, newUom, currentUom);
	openUomDropdown.value = null;
	emit("update-uom", item.item_code, newUom);
}

// ─────────────────────────────────────────────────────────────────────────────
// Item Edit Dialog Functions
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Open the edit item dialog for an item.
 * Creates a copy of the item to avoid mutating the original.
 * Used for serial number items and advanced editing.
 *
 * @param {Object} item - Cart item to edit
 */
function openEditDialog(item) {
	selectedItem.value = { ...item };
	showEditDialog.value = true;
}

/**
 * Handle item update from edit dialog.
 * Updates item via cart store and emits for parent compatibility.
 *
 * @param {Object} updatedItem - Updated item data from dialog
 */
async function handleUpdateItem(updatedItem) {
	// Get the original UOM from selectedItem (before any changes)
	const originalUom = selectedItem.value?.uom || selectedItem.value?.stock_uom;
	// Use store method to update item, passing original UOM to identify correct item
	await cartStore.updateItemDetails(updatedItem.item_code, updatedItem, originalUom);
	// Also emit for parent component compatibility
	emit("edit-item", updatedItem);
}

// ─────────────────────────────────────────────────────────────────────────────
// Event Handlers & Lifecycle
// ─────────────────────────────────────────────────────────────────────────────

function selectDocType(type) {
	cartStore.setTargetDoctype(type);
}

/**
 * Handle clicks outside interactive elements.
 * - Closes customer search dropdown when clicking outside
 * - Closes UOM dropdown when clicking outside
 *
 * @param {MouseEvent} event - Click event
 */
function handleOutsideClick(event) {
	const target = event.target;

	// Close customer search if clicking outside
	if (
		customerSearchContainer.value &&
		target instanceof Node &&
		!customerSearchContainer.value.contains(target)
	) {
		customerSearch.value = "";

		// Restore previous customer if set and no customer selected
		if (previousCustomer.value && !props.customer) {
			emit("select-customer", previousCustomer.value);
			previousCustomer.value = null;
		}
	}

	// Close UOM dropdown if clicking outside
	if (openUomDropdown.value !== null) {
		// Check if click is outside all UOM dropdowns
		const clickedInsideUomDropdown =
			target instanceof Element && target.closest(".group\\/uom");
		if (!clickedInsideUomDropdown) {
			openUomDropdown.value = null;
		}
	}

	if (
		promotionCampaignDropdownOpen.value &&
		promotionCampaignDropdownRef.value &&
		target instanceof Node &&
		!promotionCampaignDropdownRef.value.contains(target)
	) {
		promotionCampaignDropdownOpen.value = false;
	}
}

/**
 * Component mounted - register global click listener.
 * Used for click-outside detection on dropdowns.
 */
onMounted(() => {
	if (typeof document === "undefined") return;
	// Use mousedown instead of click to catch events before they are swallowed by other handlers
	document.addEventListener("mousedown", handleOutsideClick);
});

/**
 * Component unmounting - cleanup global click listener.
 * Prevents memory leaks by removing event listener.
 */
onBeforeUnmount(() => {
	if (typeof document === "undefined") return;
	document.removeEventListener("mousedown", handleOutsideClick);
});

const focusedLineIndex = ref(-1);

function getFocusedItem() {
	if (!props.items?.length) {
		focusedLineIndex.value = -1;
		return null;
	}
	if (
		focusedLineIndex.value < 0 ||
		focusedLineIndex.value >= props.items.length
	) {
		focusedLineIndex.value = 0;
	}
	return props.items[focusedLineIndex.value];
}

function moveFocusedLine(delta) {
	if (!props.items?.length) return;
	if (focusedLineIndex.value < 0) {
		focusedLineIndex.value = 0;
		return;
	}
	focusedLineIndex.value = Math.max(
		0,
		Math.min(props.items.length - 1, focusedLineIndex.value + delta),
	);
}

function keyboardIncreaseQuantity() {
	const item = getFocusedItem();
	if (item) incrementQuantity(item);
}

function keyboardDecreaseQuantity() {
	const item = getFocusedItem();
	if (item) decrementQuantity(item);
}

function keyboardNextProduct() {
	moveFocusedLine(1);
}

function keyboardPreviousProduct() {
	moveFocusedLine(-1);
}

function keyboardFocusQuantity() {
	const item = getFocusedItem();
	if (!item) return;
	nextTick(() => {
		const row = document.querySelector(
			`[data-cart-line-index="${focusedLineIndex.value}"]`,
		);
		const input = row?.querySelector('input[type="text"]');
		input?.focus();
		input?.select?.();
	});
}

defineExpose({
	keyboardIncreaseQuantity,
	keyboardDecreaseQuantity,
	keyboardNextProduct,
	keyboardPreviousProduct,
	keyboardFocusQuantity,
});
</script>
```
