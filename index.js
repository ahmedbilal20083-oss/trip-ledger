const categories = ["food", "groceries", "rent", "fuel", "tickets"];
const currencyNames = { USD: "Dollars", PKR: "Pakistani Rupees" };

const elements = {
	setupView: document.querySelector("#setup-view"),
	appView: document.querySelector("#app-view"),
	setupForm: document.querySelector("#setup-form"),
	tripName: document.querySelector("#trip-name"),
	archiveList: document.querySelector("#archive-list"),
	expenseForm: document.querySelector("#expense-form"),
	friendNames: document.querySelector("#friend-names"),
	paidBy: document.querySelector("#paid-by"),
	totalSpent: document.querySelector("#total-spent"),
	eachShare: document.querySelector("#each-share"),
	friendCount: document.querySelector("#friend-count"),
	expenseCount: document.querySelector("#expense-count"),
	expenseList: document.querySelector("#expense-list"),
	categoryList: document.querySelector("#category-list"),
	peopleList: document.querySelector("#people-list"),
	settlementList: document.querySelector("#settlement-list"),
	formMessage: document.querySelector("#form-message"),
	globalMessage: document.querySelector("#global-message"),
	endTripButton: document.querySelector("#end-trip-button"),
	previewModal: document.querySelector("#preview-modal"),
	previewTitle: document.querySelector("#preview-title"),
	previewMeta: document.querySelector("#preview-meta"),
	previewSummary: document.querySelector("#preview-summary"),
	previewExpenses: document.querySelector("#preview-expenses"),
};

function money(value, code = "PKR") {
	return new Intl.NumberFormat("en-US", { style: "currency", currency: code }).format(value || 0);
}

function moneyLines(totals) {
	return Object.entries(totals || {}).filter(([, value]) => value).map(([code, value]) => `<span>${money(value, code)}</span>`).join(" ") || "-";
}

function currencySummary(totals) {
	return Object.keys(totals || {}).filter((code) => totals[code]).map((code) => currencyNames[code] || code).join(" · ");
}

function expenseTotals(expenses) {
	return expenses.reduce((totals, expense) => {
		const code = expense.currency || "PKR";
		totals[code] = (totals[code] || 0) + Number(expense.amount || 0);
		return totals;
	}, {});
}

function titleCase(value) {
	return value.charAt(0).toUpperCase() + value.slice(1);
}

function showError(message) {
	elements.globalMessage.textContent = message;
}

async function request(path, options = {}) {
	const response = await fetch(path, {
		headers: { "Content-Type": "application/json" },
		...options,
	});
	const responseText = await response.text();
	let data = {};
	if (responseText.trim()) {
		try {
			data = JSON.parse(responseText);
		} catch {
			throw new Error(`The server returned an invalid response (${response.status}).`);
		}
	}
	if (!responseText.trim()) {
		throw new Error("The server returned an empty response. Make sure web_app.py is running.");
	}
	if (!response.ok) throw new Error(data.error || "Something went wrong.");
	return data;
}

function render(state) {
	const hasTrip = state.friends.length > 0;
	elements.setupView.hidden = hasTrip;
	elements.appView.hidden = !hasTrip;
	elements.archiveList.innerHTML = state.archives.length ? state.archives.map((archive) => `<article class="archive-card"><div class="archive-card-top"><span class="archive-icon">↗</span><span class="archive-date">${formatDate(archive.ended_at)}</span></div><h3>${escapeHtml(archive.name)}</h3><div class="archive-meta"><span>${archive.friends} friends</span><span>${archive.expenses} expenses</span><strong>${moneyLines(archive.currency_totals)}</strong></div><div class="archive-actions"><button class="archive-action preview-action" data-trip-folder="${escapeHtml(archive.folder)}" type="button">Preview</button><button class="archive-action delete-action" data-trip-folder="${escapeHtml(archive.folder)}" type="button">Delete</button></div></article>`).join("") : `<div class="empty-archive">No finished trips yet. Your next one will appear here.</div>`;
	if (!hasTrip) return;

	elements.totalSpent.innerHTML = moneyLines(state.currency_totals);
	elements.eachShare.innerHTML = moneyLines(Object.fromEntries(Object.entries(state.currency_totals || {}).map(([code, value]) => [code, value / state.friends.length])));
	elements.friendCount.textContent = state.friends.length;
	elements.expenseCount.textContent = `${state.expenses.length} ${state.expenses.length === 1 ? "entry" : "entries"}`;
	elements.paidBy.innerHTML = state.friends.map((friend) => `<option value="${escapeHtml(friend)}">${escapeHtml(friend)}</option>`).join("");

	const maxCategory = Math.max(...Object.values(state.categories), 1);
	const categoryCurrencyTotals = state.category_currency_totals || Object.fromEntries(categories.map((category) => [category, {}]));
	elements.categoryList.innerHTML = categories.map((category) => {
		const amount = state.categories[category] || 0;
		return `<div class="category-item"><div class="category-line"><span><i class="category-dot ${category}"></i>${titleCase(category)}</span><strong>${moneyLines(categoryCurrencyTotals[category])}</strong></div><div class="bar"><span style="width: ${(amount / maxCategory) * 100}%"></span></div></div>`;
	}).join("");

	elements.peopleList.innerHTML = state.people.map((person) => {
		const lines = Object.entries(person.currencies || {}).map(([code, values]) => `<small>paid ${money(values.paid, code)} · ${values.balance < 0 ? "owes" : "gets back"} ${money(Math.abs(values.balance), code)}</small>`).join("");
		return `<div class="person-row"><span class="avatar">${escapeHtml(person.name.charAt(0).toUpperCase())}</span><div class="person-name"><strong>${escapeHtml(person.name)}</strong>${lines}</div></div>`;
	}).join("");

	elements.expenseList.innerHTML = state.expenses.length ? state.expenses.map((expense) => `<div class="expense-row"><span class="expense-icon ${expense.category}">${titleCase(expense.category).charAt(0)}</span><div class="expense-name"><strong>${escapeHtml(expense.description)}</strong><small>${titleCase(expense.category)} · paid by ${escapeHtml(expense.paid_by)} · ${escapeHtml(expense.currency_description || currencyNames[expense.currency] || expense.currency)}</small></div><strong class="expense-amount">${money(expense.amount, expense.currency)}</strong></div>`).join("") : `<div class="empty-state">Your expenses will appear here.</div>`;
	elements.settlementList.innerHTML = state.settlements.length ? state.settlements.map((settlement) => `<div class="settlement-row"><span>${escapeHtml(settlement.from)}</span><span class="arrow">→</span><span>${escapeHtml(settlement.to)}</span><strong>${money(settlement.amount, settlement.currency)}</strong></div>`).join("") : `<div class="empty-state">Everyone is settled up.</div>`;
}

function formatDate(value) {
	if (!value) return "Recently finished";
	return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function escapeHtml(value) {
	return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));
}

elements.setupForm.addEventListener("submit", async (event) => {
	event.preventDefault();
	const friends = elements.friendNames.value.split(",").map((friend) => friend.trim()).filter(Boolean);
	try {
		const state = await request("/api/setup", { method: "POST", body: JSON.stringify({ name: elements.tripName.value.trim(), friends }) });
		render(state);
	} catch (error) { showError(error.message); }
});

elements.archiveList.addEventListener("click", async (event) => {
	const previewButton = event.target.closest(".preview-action[data-trip-folder]");
	const deleteButton = event.target.closest(".delete-action[data-trip-folder]");
	if (previewButton) {
		try {
			showPreview(await request(`/api/trips/${encodeURIComponent(previewButton.dataset.tripFolder)}`));
		} catch (error) { showError(error.message); }
	}
	if (deleteButton) {
		if (!window.confirm("Delete this saved trip permanently?")) return;
		try {
			render(await request("/api/delete-trip", { method: "POST", body: JSON.stringify({ folder: deleteButton.dataset.tripFolder }) }));
		} catch (error) { showError(error.message); }
	}
});

function showPreview(trip) {
	elements.previewTitle.textContent = trip.name || "Saved trip";
	elements.previewMeta.textContent = `${formatDate(trip.ended_at)} · ${trip.friends.length} friends · ${trip.expenses.length} expenses`;
	const totals = expenseTotals(trip.expenses);
	const shares = Object.fromEntries(Object.entries(totals).map(([code, value]) => [code, value / trip.friends.length]));
	elements.previewSummary.innerHTML = `<div><span>Total expense</span><strong>${moneyLines(totals)}</strong><small>${currencySummary(totals)}</small></div><div><span>Per person</span><strong>${moneyLines(shares)}</strong><small>${currencySummary(shares)}</small></div>`;
	elements.previewExpenses.innerHTML = trip.expenses.length ? trip.expenses.map((expense) => `<div class="preview-expense"><span class="expense-icon ${expense.category}">${titleCase(expense.category).charAt(0)}</span><div><strong>${escapeHtml(expense.description)}</strong><small>${titleCase(expense.category)} · paid by ${escapeHtml(expense.paid_by)} · ${escapeHtml(expense.currency_description || currencyNames[expense.currency] || expense.currency)}</small></div><strong>${money(expense.amount, expense.currency)}</strong></div>`).join("") : `<p class="empty-state">No expenses were recorded.</p>`;
	elements.previewModal.hidden = false;
}

document.querySelectorAll("[data-close-preview]").forEach((element) => element.addEventListener("click", () => { elements.previewModal.hidden = true; }));
document.addEventListener("keydown", (event) => { if (event.key === "Escape") elements.previewModal.hidden = true; });

elements.endTripButton.addEventListener("click", async () => {
	if (!window.confirm("End this trip and save its complete record? You will not be able to add more expenses to it.")) return;
	try {
		render(await request("/api/end-trip", { method: "POST", body: "{}" }));
	} catch (error) { showError(error.message); }
});

elements.expenseForm.addEventListener("submit", async (event) => {
	event.preventDefault();
	const form = new FormData(elements.expenseForm);
	try {
		const state = await request("/api/expenses", { method: "POST", body: JSON.stringify({
			description: form.get("description"), amount: Number(form.get("amount")), category: form.get("category"), paid_by: form.get("paid_by"),
					 currency: form.get("currency"),
		}) });
		render(state);
		elements.expenseForm.reset();
		elements.formMessage.textContent = "Expense saved.";
		setTimeout(() => { elements.formMessage.textContent = ""; }, 2500);
	} catch (error) { elements.formMessage.textContent = error.message; }
});

request("/api/state").then(render).catch((error) => showError(`Start the Python app to connect: ${error.message}`));
