// MoveMatch interface. The browser calls the API directly (fetch) and builds the HTML here.
// The backend stays the authority for all business rules: this file only shows what the API answers.
"use strict";

const view = document.getElementById("view");
const nav = document.getElementById("nav");
const notice = document.getElementById("notice");
const userSelect = document.getElementById("user");

// Demo users from movematch/seed.json. They replace the login until the security lesson.
const COMPANIES = { 7: "Umzüge Keller GmbH", 8: "Rhein Transport AG", 9: "Zügelprofi Basel" };
const STATUS_TEXT = { open: "open", offers_received: "offers received", assigned: "assigned", completed: "completed",
                      pending: "pending", accepted: "accepted", declined: "declined" };

let user = { role: "customer", id: 1 };
let page = "home";
let furnitureTypes = [];

// ----- API access ---------------------------------------------------------------------------------
// Every call returns { ok, status, data }. Error bodies always have the shape { code, message }.
async function api(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  headers[user.role === "customer" ? "X-Customer-Id" : "X-Company-Id"] = String(user.id);
  try {
    const response = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const data = response.status === 204 ? null : await response.json();
    return { ok: response.ok, status: response.status, data };
  } catch (error) {
    return { ok: false, status: 0, data: { code: "network", message: "The server cannot be reached." } };
  }
}

// ----- small helpers --------------------------------------------------------------------------------
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function showNotice(kind, text) {
  notice.innerHTML = text ? `<p class="${kind}">${escapeHtml(text)}</p>` : "";
}
function errorText(result) {
  return `${result.data.message} (HTTP ${result.status})`;
}
function formatDate(iso) {
  const [year, month, day] = iso.split("-");
  return `${day}.${month}.${year}`;
}
function route(request) {
  return `${escapeHtml(request.fromAddress.postalCode)} ${escapeHtml(request.fromAddress.city)} → ` +
         `${escapeHtml(request.toAddress.postalCode)} ${escapeHtml(request.toAddress.city)}`;
}
function statusBadge(status) {
  return `<span class="status ${status}">${STATUS_TEXT[status] || status}</span>`;
}
function priceRange(request) {
  return `<span class="range">CHF ${request.priceMin} – ${request.priceMax}</span>`;
}
function furnitureName(id) {
  const found = furnitureTypes.find((f) => f.id === id);
  return found ? found.name : `Type ${id}`;
}
function requestSummary(request) {
  const items = request.items.filter((i) => i.quantity > 0)
    .map((i) => `${i.quantity} × ${escapeHtml(furnitureName(i.furnitureTypeId))}`).join(", ");
  const floor = (a) => `floor ${a.floor}, ${a.hasLift ? "lift" : "no lift"}`;
  return `<p><strong>${route(request)}</strong> ${statusBadge(request.status)}</p>
    <p class="muted">Moving date ${formatDate(request.movingDate)} · ${request.distanceKm} km ·
      ${request.volumeM3} m³ · from ${floor(request.fromAddress)} · to ${floor(request.toAddress)}</p>
    <p class="muted">${items}</p>
    <p>Price range ${priceRange(request)}</p>`;
}

// ----- navigation -----------------------------------------------------------------------------------
const PAGES = {
  customer: [["home", "My requests"], ["new", "New request"]],
  company: [["home", "Marketplace"], ["offers", "My offers"]],
};
function renderNav() {
  nav.innerHTML = PAGES[user.role].map(([key, label]) =>
    `<button class="${page === key ? "current" : "secondary"}" data-page="${key}">${label}</button>`).join("");
}
nav.addEventListener("click", (event) => {
  if (event.target.dataset.page) { showNotice(); go(event.target.dataset.page); }
});
userSelect.addEventListener("change", () => {
  const [role, id] = userSelect.value.split(":");
  user = { role, id: Number(id) };
  showNotice();
  go("home");
});

async function go(nextPage, argument) {
  page = nextPage;
  renderNav();
  if (!furnitureTypes.length) {
    const result = await api("GET", "/furniture-types");
    if (result.ok) furnitureTypes = result.data;
  }
  if (user.role === "customer") {
    if (page === "new") return renderRequestForm(null);
    if (page === "edit") return renderRequestForm(argument);
    if (page === "detail") return renderCustomerDetail(argument);
    return renderMyRequests();
  }
  if (page === "offers") return renderMyOffers();
  if (page === "detail") return renderCompanyDetail(argument);
  return renderMarketplace();
}

// ----- customer: my requests ------------------------------------------------------------------------
async function renderMyRequests() {
  const result = await api("GET", "/moving-requests");
  if (!result.ok) return showNotice("error", errorText(result));
  const mine = result.data.filter((r) => r.customerId === user.id);
  view.innerHTML = `<h2>My requests</h2>` + (mine.length ? mine.map((r) => `
    <div class="card">
      <h3>${escapeHtml(r.reference)}</h3>
      ${requestSummary(r)}
      <div class="actions"><button data-open="${r.id}">Open and compare offers</button></div>
    </div>`).join("") : `<p class="muted">You have no moving requests yet.</p>`);
  view.onclick = (event) => {
    if (event.target.dataset.open) go("detail", Number(event.target.dataset.open));
  };
}

// ----- customer: create or change a request (Workflow A) ---------------------------------------------
function addressFields(prefix, title, address) {
  return `<fieldset class="card"><legend>${title}</legend><div class="row">
    <label>Postal code <input name="${prefix}PostalCode" required pattern="[0-9]{4}" maxlength="4" size="5"
      value="${escapeHtml(address?.postalCode)}"></label>
    <label>City <input name="${prefix}City" required value="${escapeHtml(address?.city)}"></label>
    <label>Floor <input name="${prefix}Floor" type="number" min="0" step="1" required value="${address?.floor ?? 0}"></label>
    <label class="check"><input name="${prefix}HasLift" type="checkbox" ${address?.hasLift ? "checked" : ""}> Lift</label>
  </div></fieldset>`;
}

function renderRequestForm(existing) {
  const quantity = (id) => existing?.items.find((i) => i.furnitureTypeId === id)?.quantity ?? 0;
  view.innerHTML = `<h2>${existing ? "Change request " + escapeHtml(existing.reference) : "New moving request"}</h2>
    <form id="request-form" novalidate>
      ${addressFields("from", "Moving from", existing?.fromAddress)}
      ${addressFields("to", "Moving to", existing?.toAddress)}
      <fieldset class="card"><legend>Move</legend><div class="row">
        <label>Distance (km) <input name="distanceKm" type="number" min="1" step="1" required value="${existing?.distanceKm ?? ""}"></label>
        <label>Moving date <input name="movingDate" type="date" required value="${existing?.movingDate ?? ""}"></label>
      </div></fieldset>
      <fieldset class="card"><legend>Furniture</legend>
        ${furnitureTypes.map((f) => `<div class="stepper">
          <span class="name">${escapeHtml(f.name)}</span>
          <button type="button" class="secondary" data-step="-1" data-type="${f.id}" aria-label="Less ${escapeHtml(f.name)}">−</button>
          <output id="quantity-${f.id}">${quantity(f.id)}</output>
          <button type="button" class="secondary" data-step="1" data-type="${f.id}" aria-label="More ${escapeHtml(f.name)}">+</button>
          <span class="muted">${f.volumeM3} m³ each</span></div>`).join("")}
      </fieldset>
      <div id="form-error"></div>
      <div class="actions">
        <button type="submit">${existing ? "Save changes" : "Calculate price range and publish"}</button>
        <button type="button" class="secondary" id="cancel">Cancel</button>
      </div>
    </form>`;
  view.onclick = (event) => {
    const { step, type } = event.target.dataset;
    if (step) {
      const output = document.getElementById(`quantity-${type}`);
      output.textContent = Math.max(0, Number(output.textContent) + Number(step));
    }
    if (event.target.id === "cancel") existing ? go("detail", existing.id) : go("home");
  };
  document.getElementById("request-form").onsubmit = async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const address = (prefix) => ({
      postalCode: form.get(prefix + "PostalCode").trim(), city: form.get(prefix + "City").trim(),
      floor: Number(form.get(prefix + "Floor")), hasLift: form.get(prefix + "HasLift") === "on",
    });
    const body = {
      fromAddress: address("from"), toAddress: address("to"),
      distanceKm: Number(form.get("distanceKm")), movingDate: form.get("movingDate"),
      items: furnitureTypes.map((f) => ({ furnitureTypeId: f.id,
        quantity: Number(document.getElementById(`quantity-${f.id}`).textContent) })),
    };
    // The input stays in the form if the API rejects it; the message of the API is shown below the form.
    const result = existing ? await api("PUT", `/moving-requests/${existing.id}`, body)
                            : await api("POST", "/moving-requests", body);
    if (!result.ok) {
      document.getElementById("form-error").innerHTML = `<p class="field-error">${escapeHtml(errorText(result))}</p>`;
      return;
    }
    showNotice("ok", existing ? `Request ${result.data.reference} was changed. New price range: CHF ${result.data.priceMin} – ${result.data.priceMax}.`
      : `Request ${result.data.reference} is published. Price range: CHF ${result.data.priceMin} – ${result.data.priceMax}.`);
    go("detail", result.data.id);
  };
}

// ----- customer: request detail with offers (Workflow A, step 5) --------------------------------------
async function renderCustomerDetail(requestId) {
  const [request, offers] = await Promise.all([
    api("GET", `/moving-requests/${requestId}`), api("GET", `/offers?movingRequestId=${requestId}`)]);
  if (!request.ok) { showNotice("error", errorText(request)); return go("home"); }
  const r = request.data;
  const list = (offers.ok ? offers.data : []).slice().sort((a, b) => a.price - b.price);
  const canChange = r.status === "open";
  const canDelete = r.status === "open" || r.status === "offers_received";
  view.innerHTML = `<h2>Request ${escapeHtml(r.reference)}</h2>
    <div class="card">${requestSummary(r)}
      <div class="actions">
        ${canChange ? `<button class="secondary" id="edit">Change request</button>` : ""}
        ${canDelete ? `<button class="danger" data-confirm="delete">Delete request</button>` : ""}
      </div>
      ${canChange ? "" : `<p class="muted">A request can only be changed while it is open.</p>`}
    </div>
    <h3>Offers (${list.length})</h3>
    ${list.length ? list.map((o) => `<div class="card">
      <h3>CHF ${o.price} ${statusBadge(o.status)}</h3>
      <p>${escapeHtml(COMPANIES[o.companyId] || "Company " + o.companyId)}</p>
      <p class="muted">${escapeHtml(o.message || "No message")}</p>
      ${o.status === "pending" && canDelete ? `<div class="actions"><button data-confirm="accept" data-offer="${o.id}">Accept offer</button></div>` : ""}
    </div>`).join("") : `<p class="muted">No offers yet.</p>`}`;
  view.onclick = async (event) => {
    const target = event.target;
    if (target.id === "edit") return go("edit", r);
    if (target.dataset.confirm) {
      // Accepting and deleting cannot be undone, so the second click on the same button confirms.
      if (!target.dataset.armed) {
        target.dataset.armed = "yes";
        target.textContent = target.dataset.confirm === "accept" ? "Confirm: accept this offer (binding)" : "Confirm: delete this request";
        return;
      }
      const result = target.dataset.confirm === "accept"
        ? await api("POST", `/offers/${target.dataset.offer}/accept`)
        : await api("DELETE", `/moving-requests/${r.id}`);
      if (!result.ok) {
        showNotice("error", errorText(result));
        return target.dataset.confirm === "accept" ? go("detail", r.id) : null;  // refresh the list of offers
      }
      if (target.dataset.confirm === "delete") {
        showNotice("ok", `Request ${r.reference} was deleted.`);
        return go("home");
      }
      showNotice("ok", `Offer accepted. Your move is booked with ${COMPANIES[result.data.companyId] || "the company"} for CHF ${result.data.price}.`);
      go("detail", r.id);
    }
  };
}

// ----- company: marketplace (Workflow B, steps 1 to 3) --------------------------------------------------
async function renderMarketplace(filters = { from: "", to: "", place: "" }) {
  const result = await api("GET", "/moving-requests");
  if (!result.ok) return showNotice("error", errorText(result));
  const place = filters.place.trim().toLowerCase();
  // The API has no filters yet, so the list is filtered here in the browser.
  const rows = result.data.filter((r) => ["open", "offers_received"].includes(r.status))
    .filter((r) => (!filters.from || r.movingDate >= filters.from) && (!filters.to || r.movingDate <= filters.to))
    .filter((r) => !place || [r.fromAddress, r.toAddress].some((a) => (a.postalCode + " " + a.city).toLowerCase().includes(place)));
  view.innerHTML = `<h2>Marketplace</h2>
    <form id="filters" class="row">
      <label>Date from <input type="date" name="from" value="${filters.from}"></label>
      <label>Date to <input type="date" name="to" value="${filters.to}"></label>
      <label>City or postal code <input name="place" value="${escapeHtml(filters.place)}"></label>
      <button type="submit" class="secondary">Filter</button>
    </form>
    ${rows.length ? `<table><thead><tr><th>Reference</th><th>Date</th><th>Route</th><th>Volume</th><th>Price range</th><th>Status</th><th></th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${escapeHtml(r.reference)}</td><td>${formatDate(r.movingDate)}</td><td>${route(r)}</td>
        <td>${r.volumeM3} m³</td><td>${priceRange(r)}</td><td>${statusBadge(r.status)}</td>
        <td><button data-open="${r.id}">Open</button></td></tr>`).join("")}</tbody></table>`
      : `<p class="muted">No open requests match the filter.</p>`}`;
  document.getElementById("filters").onsubmit = (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    renderMarketplace({ from: form.get("from"), to: form.get("to"), place: form.get("place") });
  };
  view.onclick = (event) => {
    if (event.target.dataset.open) go("detail", Number(event.target.dataset.open));
  };
}

// ----- company: request detail with the offer form (Workflow B, steps 3 to 5) ---------------------------
async function renderCompanyDetail(requestId) {
  const [request, offers] = await Promise.all([
    api("GET", `/moving-requests/${requestId}`), api("GET", `/offers?movingRequestId=${requestId}`)]);
  if (!request.ok) { showNotice("error", errorText(request)); return go("home"); }
  const r = request.data;
  const own = (offers.ok ? offers.data : []).find((o) => o.companyId === user.id);
  view.innerHTML = `<h2>Request ${escapeHtml(r.reference)}</h2>
    <div class="card">${requestSummary(r)}</div>
    ${own ? `<div class="card"><h3>Your offer: CHF ${own.price} ${statusBadge(own.status)}</h3>
        <p class="muted">${escapeHtml(own.message || "No message")}</p>
        <p class="muted">Offers cannot be edited. Withdraw a pending offer under "My offers" to submit a new one.</p></div>`
      : `<form id="offer-form" class="card" novalidate>
        <h3>Submit an offer</h3>
        <div class="field"><label for="price">Price in CHF (allowed: ${r.priceMin} to ${r.priceMax})</label>
          <input id="price" name="price" type="number" step="1" required></div>
        <div id="price-error"></div>
        <div class="field"><label for="message">Message (optional)</label>
          <textarea id="message" name="message" maxlength="500"></textarea></div>
        <div class="actions"><button type="submit">Submit offer</button>
          <button type="button" class="secondary" id="back">Back to the marketplace</button></div>
      </form>`}`;
  view.onclick = (event) => { if (event.target.id === "back") go("home"); };
  const form = document.getElementById("offer-form");
  if (!form) return;
  form.onsubmit = async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const body = { movingRequestId: r.id, price: Number(data.get("price")) };
    if (data.get("message").trim()) body.message = data.get("message").trim();
    const result = await api("POST", "/offers", body);
    if (!result.ok) {
      // The entered price and message stay in the form; the reason is shown at the price field.
      document.getElementById("price-error").innerHTML = `<p class="field-error">${escapeHtml(errorText(result))}</p>`;
      return;
    }
    showNotice("ok", `Offer of CHF ${result.data.price} for ${r.reference} is saved (status ${result.data.status}).`);
    go("offers");
  };
}

// ----- company: my offers (Workflow B, step 6) -----------------------------------------------------------
async function renderMyOffers() {
  const requests = await api("GET", "/moving-requests");
  if (!requests.ok) return showNotice("error", errorText(requests));
  // There is no "offers of a company" operation in the contract: the offers are collected per request.
  const perRequest = await Promise.all(requests.data.map((r) => api("GET", `/offers?movingRequestId=${r.id}`)));
  const rows = [];
  requests.data.forEach((r, index) => (perRequest[index].ok ? perRequest[index].data : [])
    .filter((o) => o.companyId === user.id).forEach((o) => rows.push({ request: r, offer: o })));
  view.innerHTML = `<h2>My offers</h2>` + (rows.length ? `<table><thead><tr><th>Request</th><th>Date</th><th>Route</th>
      <th>Our price</th><th>Offer</th><th>Request</th><th></th></tr></thead><tbody>
      ${rows.map(({ request: r, offer: o }) => `<tr><td>${escapeHtml(r.reference)}</td><td>${formatDate(r.movingDate)}</td>
        <td>${route(r)}</td><td>CHF ${o.price}</td><td>${statusBadge(o.status)}</td><td>${statusBadge(r.status)}</td>
        <td>${o.status === "pending" ? `<button class="danger" data-withdraw="${o.id}">Withdraw</button>` : ""}</td></tr>`).join("")}
      </tbody></table>` : `<p class="muted">Your company has no offers yet.</p>`);
  view.onclick = async (event) => {
    const target = event.target;
    if (!target.dataset.withdraw) return;
    if (!target.dataset.armed) {
      target.dataset.armed = "yes";
      target.textContent = "Confirm withdraw";
      return;
    }
    const result = await api("DELETE", `/offers/${target.dataset.withdraw}`);
    showNotice(result.ok ? "ok" : "error", result.ok ? "The offer was withdrawn." : errorText(result));
    renderMyOffers();
  };
}

go("home");
