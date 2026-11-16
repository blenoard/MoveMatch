# MoveMatch

**Current stage:** Milestone 3 (integration). All 11 operations of the OpenAPI contract are implemented and tested, and a browser interface connects both workflows to the API and the stored data (see [Integration](#integration-milestone-3)). The design from Milestone 1 was revised after the design coaching (see [Changes after the design coaching](#changes-after-the-design-coaching-5-october)). This README is updated throughout the project; we do not start a separate document for each milestone.

The application is **not finished**: there is no login yet (the acting user is chosen in the interface and sent as a header), the data is stored in a JSON file and the marketplace filter runs in the browser. See [Known limitations](#known-limitations).

## Project overview

MoveMatch is a web marketplace for private moves. Today, people who move contact five to ten moving companies one by one, fill in a different form each time and wait for replies. Many companies have no capacity on the requested date, and the quotes are hard to compare because each company asks for different details. Companies, in turn, lose time on incomplete requests.

With MoveMatch, a customer describes the move **once** in a standard form (addresses, distance, date, floor, lift and the number of specific furniture items). The application calculates a price range that leaves room for negotiation and publishes the request on a marketplace. Registered moving companies browse the requests, submit one offer within the range, and the customer accepts the offer that fits best.

**Intended users:** private customers who are planning a move, and dispatchers of small and medium moving companies.

### Team and responsibilities

| Member | Responsibility in Milestone 2 | Files | Next action |
|---|---|---|---|
| Blenoard | README, persistence and seed data | `README.md`, `movematch/storage.py`, `movematch/seed.json` | Submit the repository link in Moodle; join the Teams channel; record the coaching feedback |
| Younes   | Business rules (application logic) and behaviour tests | `movematch/service.py`, `tests/test_api.py` | Add the next rules (7: accept an offer, 8: edit/delete a request) with tests |
| Leutrim  | HTTP interface and project setup | `movematch/api.py`, `movematch/models.py`, `movematch/main.py`, `requirements*.txt`, `pytest.ini`, `.gitignore` | Add the next endpoints (list offers of a request, accept an offer) |
| Salahdin | OpenAPI contract and contract test | `contracts/movematch.openapi.yaml`, `tests/test_contract.py`, `data/*.json` | Keep the contract and the implementation reconciled; set more operations to `implemented` / `tested` |

These are starting responsibilities, not permanent silos. Everyone reviews the whole project and should be able to explain it in coaching. Code was drafted with AI assistance (see References) and is reviewed by the person responsible for the file.

## 1. Analysis

### Scenario, users and goals

- **Situation or problem:** A person moving from Basel to Zürich has to contact many companies, repeat the same information in different forms and compare quotes that are based on different assumptions. Moving companies receive incomplete enquiries and requests for dates on which they are already fully booked.
- **Intended users:**
  - *Customer* (e.g. Lena, private person): wants to describe the move once and receive comparable offers.
  - *Moving company* (e.g. the dispatcher of Umzüge Keller GmbH): wants complete, comparable requests to fill free days in the schedule.
  - *Admin*: optional, later (e.g. company verification).
- **Proposed benefit:** one standard request instead of ten; offers only from companies with capacity; comparable offers within a transparent price range; less time spent on incomplete enquiries.
- **Initial scope:** Workflow A (customer publishes a request) and Workflow B (company submits an offer), plus accepting an offer.
  - *Left out for now:* online payment (needs a payment provider and legal checks), chat or live negotiation (the price range covers negotiation), automatic distance via a maps API (customers enter postal codes and an approximate distance), reviews and ratings (only useful once real moves happened), company verification (we assume registered companies are legitimate).

### User stories and first workflow

**Customer**

- As a customer, I want to describe my move once in a standard form, so that I do not have to fill in a different form for every company.
- As a customer, I want to see an expected price range before publishing, so that I know what the move will roughly cost.
- As a customer, I want to compare offers and accept one, so that my move is booked with a company that has capacity on my date.
- As a customer, I want to delete my request as long as no offer is accepted, so that companies stop sending offers if my plans change.

**Moving company**

- As a dispatcher, I want to filter open requests by date and region, so that I only see jobs that fit our free days.
- As a dispatcher, I want to see all details of a request (floors, lift, furniture), so that I can make a realistic offer without calling back.
- As a dispatcher, I want to submit an offer within the price range, so that the customer can compare it fairly with other offers.
- As a dispatcher, I want to withdraw an offer that is still pending, so that I am not bound to a price if we can no longer do the job.

**Workflow A — customer publishes a moving request (Lena, Basel → Zürich)**

| Step | User / role | Action | Information needed | Expected result or feedback |
|---|---|---|---|---|
| 1 | Customer | Enter the move details | From/to postal code and city, floor, lift, distance (km), moving date, quantity of sofas, beds, wardrobes and boxes | Input is kept ready to submit |
| 2 | Customer | Submit the form ("Calculate price range") | The entered data | Required fields checked; moving date not in the past |
| 3 | Customer | Review the summary | — | Route, date, volume (10.5 m³) and price range (CHF 1,200–1,600) are shown |
| 4 | Customer | Publish the request | Confirmation | Request saved with status `open` and reference MM-1042 (the reference is built from the request ID 1042); listed on the marketplace |
| 5 | Customer | Open the offers and accept one (after confirming) | Chosen offer | Request `assigned`; chosen offer `accepted`; all other offers `declined`; the company sees the result under "My offers" |
| 2a | Customer | Submit with a date in the past (e.g. 06.10.2026) | — | Message explains that the date must not be in the past; other input is kept; no request is created |

**Workflow B — moving company submits an offer (Umzüge Keller GmbH)**

| Step | User / role | Action | Information needed | Expected result or feedback |
|---|---|---|---|---|
| 1 | Company | Open the marketplace | — | Open requests with date, route, volume and price range |
| 2 | Company | Filter by date and region | Date range, cantons | Only matching requests are shown |
| 3 | Company | Open one request | — | All details and the allowed price range |
| 4 | Company | Enter a price and submit the offer | Price (CHF), optional message | Price checked against the range; check that the company has no other offer on this request |
| 5 | Company | Read the confirmation | — | Offer saved as `pending`; request changes to `offers_received` |
| 6 | Company | Withdraw a pending offer (under "My offers") | Confirmation | Offer is deleted; if it was the last pending offer, the request returns to `open` |
| 4a | Company | Enter CHF 1,750 (above the range) | — | Allowed range is shown; input kept; offer not saved |

**Questions and exceptions worth discussing**

- *A company cannot do the job after its offer was accepted (e.g. the truck breaks down a week before).* Draft decision: an accepted offer is binding, and cancelling after the assignment is not part of version 1. If this becomes a problem, a reliability rating of companies (as known from marketplaces) is a possible later extension.
- *The customer clicks "Accept" on an offer that the company withdrew in the meantime.* The application shows an error, nothing changes, and the list of offers is refreshed. Offers cannot be edited, so no customer can accept a price that has silently changed.
- *The customer notices more furniture after offers arrived.* Draft decision: editing is only allowed while the request is `open`; afterwards the customer deletes the request and creates a new one.

## 2. Design

### Screens and navigation

Digital versions of our sketches:

![Workflow A – input, review, success](sketches/01-customer-create-request.png)
*Workflow A on a phone: the form, the review with the price range and the confirmation are states of one "new request" flow.*

![Workflow A – error state, offers, accepted](sketches/02-customer-error-and-offers.png)
*Error state 2a (date in the past, other input kept), the list of offers as cards, and the confirmation after accepting.*

![Workflow B – marketplace and offer form](sketches/03-company-marketplace-offer.png)
*Workflow B on a desktop: the marketplace table with filters, and the request detail with the offer form in error state 4a.*

**Main inputs, actions and feedback**

- Customers mostly use a **phone**: one column, +/− steppers for furniture, a highlighted price range, buttons with clear verbs ("Calculate price range", "Publish request").
- Dispatchers mostly use a **desktop**: a table to compare many requests, filters for date and region, a price field labelled with the allowed range.
- Errors appear directly at the affected field, explain how to fix the problem and keep all other input. Accepting an offer needs a confirmation because it cannot be undone.

**Navigation (draft)**

| View | Role | Main actions |
|---|---|---|
| Start page | Visitor | Explains how MoveMatch works; log in / register (later) |
| My requests | Customer | Open a request; create a new request |
| New request (form → review → confirmation) | Customer | Calculate range; edit; publish |
| Request detail with offers | Customer | Accept an offer; delete the request |
| Marketplace | Company | Filter; open a request |
| Request detail + offer form | Company | Submit an offer |
| My offers | Company | See the status of own offers; withdraw a pending offer |

The interface is now implemented with plain HTML, CSS and JavaScript (see [Integration](#integration-milestone-3)). The planned Bootstrap Studio prototype is not available.

### Domain concepts and example data

All example data is fictional.

| File | Content |
|---|---|
| [`data/furniture-types.json`](data/furniture-types.json) | Catalogue of furniture types with their volume in m³ |
| [`data/create-moving-request.json`](data/create-moving-request.json) | What the customer sends when creating a request |
| [`data/price-estimate.json`](data/price-estimate.json) | How the price range for this request is calculated |
| [`data/moving-request.json`](data/moving-request.json) | The saved request as the app returns it |
| [`data/moving-company.json`](data/moving-company.json) | A registered moving company |
| [`data/create-offer.json`](data/create-offer.json) / [`data/offer.json`](data/offer.json) | An offer as sent by the company and as saved |
| [`data/error-examples.json`](data/error-examples.json) | Planned error responses for the main business rules (each entry names the rule it belongs to) |

![Data model draft](sketches/04-data-model-draft.png)

**Important fields and types**

- `movingDate` is a string in ISO format (`"2026-11-14"`), because JSON has no date type; the backend converts it to check that the date is not in the past.
- `fromAddress` / `toAddress` are objects, because postal code, floor and lift are used separately (region filter, floor surcharge).
- `items` is an array of `{ "furnitureTypeId", "quantity" }`. Each item **refers** to the furniture catalogue by ID instead of a name, so that names can change and the volume is defined in one place. The quantity belongs to the item, not to the furniture type.
- Units are part of the key name (`distanceKm`, `volumeM3`); prices are whole CHF with a separate `currency` field.
- The reference `MM-1042` is only a display format: it is built from the request ID (`"MM-"` + ID) and returned as a read-only field `reference`. It is not stored separately, so it cannot disagree with the ID.
- An offer references its request (`movingRequestId`) and company (`companyId`). There is no `acceptedOfferId` on the request: the accepted offer is the offer of that request with status `accepted` (at most one per request). Storing it in both places would allow the two to disagree.
- `customerId` and `companyId` are not sent in the body. They belong to the logged-in user. Until the security lesson the interface offers a list of demo users, and the choice is sent as the header `X-Customer-Id` or `X-Company-Id`.
- Status values: request `open`, `offers_received`, `assigned`, `completed`; offer `pending`, `accepted`, `declined`. A deleted request or offer is really removed, so there is no `withdrawn` status.

### Business rules and possible operations

**Rules (draft)**
1. The moving date must not lie in the past (today is allowed).
2. Quantities are whole numbers ≥ 0, and at least one item has a quantity ≥ 1.
3. The price range is calculated as estimate ± 15 %, rounded inwards to CHF 50. Draft estimate: base price CHF 350 + CHF 3 per km + CHF 60 per m³ + CHF 50 per floor without lift. Lena's move: 350 + 270 + 630 + 150 = CHF 1,400 → range CHF 1,200–1,600.
4. A company offer must lie within the range of the request (both limits included).
5. A company can have only one offer per request at a time. It can withdraw a pending offer and submit a new one.
6. Offers are only possible while the request is `open` or `offers_received`.
7. A customer can only accept a `pending` offer of a request that is not yet `assigned`. Accepting is one step: the offer becomes `accepted`, all other offers of the request become `declined` and the request becomes `assigned`. A request never has more than one accepted offer.
8. A request can only be edited while it is `open`, and deleted as long as it is not `assigned`. Deleting really removes the request together with its pending offers.
9. An offer cannot be edited. A company can withdraw (delete) its own offer while it is `pending`; if it was the last pending offer, the request returns to `open`. An accepted offer is binding and cannot be withdrawn.
10. An `assigned` request becomes `completed` automatically once its moving date has passed. Nobody sets this status manually in version 1.

The interface does not repeat the rules: it sends the input to the API and shows the message of the API at the form, with all input kept. The backend service logic is the authority, because the API can also be called without our frontend. Where each rule is enforced is documented in [Implementation](#4-implementation).

| User goal | Proposed action | Example input | Expected output | Open question |
|---|---|---|---|---|
| Publish a move | Create a moving request | `data/create-moving-request.json` | Saved request with ID (shown as reference MM-1042), volume, price range, status `open` | Is a manual distance acceptable? |
| Find suitable jobs | Read open requests (with filters) | Date range, region | List of requests with date, route, volume, range | Filter by canton or by postal code range? |
| Inspect a job | Read one request | Request ID 1042 | All details incl. range; no contact data before acceptance | — |
| Correct a mistake | Change a request | Changed furniture list | Updated request and recalculated range — only while `open`, otherwise a conflict error | — (decided: no changes once offers exist) |
| Cancel a move | Remove (delete) a request | Request ID | Request and its pending offers are deleted — only while not `assigned`, otherwise a conflict error | — (decided: real delete) |
| Make an offer | Create an offer | `data/create-offer.json` | Offer `pending` — or error: outside range / already offered / request no longer accepts offers | — (decided: offers cannot be edited) |
| Withdraw an offer | Remove (delete) an offer | Offer ID | Offer deleted — only while `pending`; a conflict error once it is accepted | — |
| Compare offers | Read offers of my request | Request ID | List of offers with company, price, message | Sort by price only? |
| Book a company | Accept an offer | Offer ID 311 | Offer `accepted`, request `assigned`, others `declined` — or error if the offer no longer exists or the request is already assigned | `PATCH` status or explicit action endpoint? |

These are the ideas in plain language. The contract with the concrete endpoints is [`contracts/movematch.openapi.yaml`](contracts/movematch.openapi.yaml); the status of each operation is in [Implementation](#4-implementation). The planned error responses are in [`data/error-examples.json`](data/error-examples.json).

## 3. Project management

### Decisions, open questions and next steps

| Question / decision | Current position | Next step |
|---|---|---|
| Scope of version 1 | Decided: Workflows A and B plus accepting an offer; payment, chat, maps API, reviews and verification are out | Confirm in the backend coaching (26 Oct) |
| Moving date | Decided: the date must not lie in the past (earlier draft: 7 days minimum lead time, dropped) | Done: checked when a request is created or changed (rule 1, `service.calculated_fields`) |
| Request reference | Decided: `MM-<ID>` is built from the request ID and not stored | Done: read-only field `reference` in the contract and the API |
| Deleting a request | Decided: real delete while not `assigned`; its pending offers are deleted with it | Done: `DELETE /moving-requests/{id}` |
| Changing or withdrawing an offer | Decided: offers cannot be edited; a pending offer can be withdrawn (deleted) and replaced by a new one; an accepted offer is binding; accepting an offer that no longer exists gives an error | Done for withdrawing and creating offers (rules 5, 6, 9); accepting follows |
| Accepted offer | Decided: no `acceptedOfferId` on the request; the accepted offer is the offer with status `accepted` | Done in the data model draft |
| Who sets a request to `completed`? | Decided: automatically after the moving date has passed; no manual step | Done: the status is derived when the request is read (`service.present`); it is not stored |
| Company cancels after assignment | Out of scope for version 1; accepted offers are binding. Possible later idea: reliability rating of companies | Revisit after the integration milestone |
| Distance | Customer enters an approximate value in km | Ask in coaching; check a postal-code table as alternative |
| Price formula and rates | Draft (see business rule 3) | Validate rates with one real quote or a moving company website |
| Accepting an offer as an API operation | Decided: explicit action endpoint `POST /offers/{offer_id}/accept` | Done; confirm the choice in the integration coaching (16 Nov) |
| User table(s) and roles | Undecided | Define together in the persistence/security lessons (security class 23 Nov) |
| Frontend technology | Decided: plain HTML, CSS and JavaScript, served by the FastAPI application under `/app`; the browser calls the API with `fetch` | Done for both workflows (see Integration) |
| API testing with Postman | Not used — none of us has worked with Postman so far | We test with automated pytest tests and the Swagger UI (`/docs`) using the sample JSON in `data/` |
| Who is the acting user without login? | Decided for now: the temporary headers `X-Company-Id` and `X-Customer-Id` name the acting user; unknown user → 422 | Replace by real login and access checks in the security lesson (23 Nov) |
| Flat offer endpoint | Decided: `POST /offers` with `movingRequestId` in the body, `GET/DELETE /offers/{offer_id}` | Done: `GET /offers?movingRequestId=` lists the offers of a request |
| Comparing external APIs (e.g. a distance/maps service) | Not done yet | Only relevant if we pursue the distance extension above |

### Changes after the design coaching (5 October)

The feedback in the coaching was brief and we did not take minutes. What we took from it: orient the work on the milestones, start with the simpler workflows and build the more complex ones on top, complete the missing sample JSON files and continue with Milestone 2. One remark concerned the reference to the Pizzeria Reference Project; we did not use it, so the mention was removed from this README.

**Initial implementation workflow:** Workflow B, steps 4–6 — a company submits an offer and withdraws a pending offer. We start with this simpler slice, as advised in the coaching, and build the more complex workflows on top of it. An offer only needs an existing request, which we provide as seed data (like the bar example does with its menu). Creating requests and the price calculation (Workflow A) follow afterwards. The slice already contains a success case, invalid input (price outside the range) and conflicts (a second offer, a request that no longer accepts offers).

**Changes made after the coaching:**

- The sample JSON files in `data/` were empty placeholders. They are now filled and consistent with the sketches and the price formula.
- Moving date: the 7-day minimum lead time was dropped; the date only must not lie in the past. Changed in the workflow, the rules, the field description and sketch 2a.
- The reference `MM-1042` is derived from the request ID instead of being stored.
- `acceptedOfferId` was removed from the data model (the accepted offer is the offer with status `accepted`).
- Offers cannot be edited; a pending offer can be withdrawn. An accepted offer is binding.
- Requests are really deleted (no `withdrawn` status).
- `completed` is set automatically after the moving date.
- The sketches were moved to `sketches/`; sketch 2a and the data model diagram were updated.

### Changes after the backend coaching (26 October)

We did not take minutes. The main feedback we recorded: add all operations of the contract, not only the first slice.

**Changes made after the coaching:**

- All 11 operations of the contract are implemented and set to `tested` (before: 5). New are the furniture catalogue, creating, changing and deleting a moving request, listing the offers of a request and accepting an offer.
- Rules 1, 2, 3, 7, 8 and 10 are now enforced in `movematch/service.py` (see [Where the business rules are enforced](#where-the-business-rules-are-enforced)).
- The acting customer is named by the header `X-Customer-Id`, like the company by `X-Company-Id`.
- Workflow chosen for the frontend integration: Workflow A (publish a request) together with Workflow B (submit an offer), because accepting an offer needs both sides.

### Progress and questions for the integration coaching (16 November)

- **Changed since Milestone 2:** all operations implemented; browser interface added; contract, tests and this README updated.
- **Working now:** a customer publishes, changes and deletes a request and accepts an offer; a company filters the marketplace, submits an offer and withdraws it. Every action goes through the API and is saved in the JSON file.
- **Open issue:** no login and no ownership checks; the marketplace filter runs in the browser; the price range is shown after publishing and not in a separate review step (see [Known limitations](#known-limitations)).
- **Questions:** (1) Is the explicit action endpoint `POST /offers/{id}/accept` the right choice, or would you expect a `PATCH` on the status of the offer? (2) Should the marketplace filter move into the API, or is filtering in the browser acceptable for a project of this size?
- **Next step:** replace the demo headers by a login with roles after the security lesson (23 Nov) and check it with tests that try to change requests and offers of other users. Responsible person: to be agreed in the team.
- **Agreed in the coaching:** to be filled in after the meeting.

### Milestone progress

| Milestone | Available evidence | Status / next step |
|---|---|---|
| 1 — Design draft | Analysis, workflows A and B, sketches in `sketches/`, sample JSON in `data/`, proposed operations, open questions | Committed and revised after coaching (see above) |
| 2 — Contract and available implementation | `contracts/movematch.openapi.yaml` (11 operations, 5 of them implemented and tested at that time), FastAPI backend in `movematch/`, 49 automated tests in `tests/` | Committed; feedback recorded above |
| 3 — Integration | Frontend decision, all 11 operations implemented and tested (83 automated tests), browser interface in `frontend/`, one traced workflow with a success and an error case | Committed for the coaching on 16 Nov; next: login and access checks |

Contributions and decisions are described in this README; commit counts are not a measure of individual effort.

## 4. Implementation

### Responsibilities of the layers

| Layer | File | Responsibility |
|---|---|---|
| HTTP interface | `movematch/api.py`, `movematch/models.py` | Parses and validates input (types, formats), calls the service, maps results and errors to status codes and the common error body `{"code", "message"}` |
| Application logic | `movematch/service.py` | The business rules; no HTTP or FastAPI code. Raises `MoveMatchError` (`invalid_input`, `not_found`, `conflict`) |
| Persistence | `movematch/storage.py`, `movematch/seed.json` | Reads and writes one JSON file (`movematch-data.json`) safely; creates it from the seed data on the first start |
| Contract | `contracts/movematch.openapi.yaml` | Describes every operation with schemas, examples and errors, and its status: `planned`, `implemented` or `tested` |
| Interface | `frontend/index.html`, `frontend/app.js`, `frontend/style.css` | Builds the pages in the browser, calls the API with `fetch` and shows the answers and error messages. Contains no business rules |

The service receives the store and the current date through its constructor (dependency injection), so tests can use a temporary file and a fixed date.

### Operations: planned / implemented / tested

| Operation | Endpoint | Status |
|---|---|---|
| List furniture types | `GET /furniture-types` | tested |
| List moving requests | `GET /moving-requests` | tested (no filters yet) |
| Create moving request | `POST /moving-requests` (header `X-Customer-Id`) | tested |
| Read one moving request | `GET /moving-requests/{id}` | tested |
| Change moving request | `PUT /moving-requests/{id}` | tested |
| Delete moving request | `DELETE /moving-requests/{id}` | tested |
| List offers of a request | `GET /offers?movingRequestId=` | tested |
| Create offer | `POST /offers` (header `X-Company-Id`) | tested |
| Read one offer | `GET /offers/{id}` | tested |
| Withdraw offer | `DELETE /offers/{id}` | tested |
| Accept offer | `POST /offers/{id}/accept` | tested |

### Where the business rules are enforced

| Rule | Status | Where |
|---|---|---|
| 1 Moving date not in the past | implemented | `service.calculated_fields` → 422 |
| 2 Whole quantities ≥ 0, at least one item ≥ 1 | implemented | `models.RequestItem` and `service.calculated_fields` → 422 |
| 3 Price range (estimate ± 15 %, rounded inwards to CHF 50) | implemented | `service.calculated_fields`, `service.price_range` |
| 4 Price within the range | implemented | `service.create_offer` → 422 |
| 5 One offer per company and request | implemented | `service.create_offer` → 409 |
| 6 Request must accept offers | implemented | `service.create_offer` → 409 |
| 7 Accept an offer | implemented | `service.accept_offer` → 404 / 409 |
| 8 Edit only while `open`; delete only while not assigned | implemented | `service.replace_moving_request`, `service.delete_moving_request` → 409 |
| 9 Withdraw only while pending; last pending offer → request `open` | implemented | `service.delete_offer` → 409 |
| 10 `completed` after the moving date | implemented | `service.present` (derived when the request is read, not stored) |

### Known limitations

- No login: the interface offers a list of demo users and sends the choice as `X-Customer-Id` or `X-Company-Id`. There is no ownership check yet, so anyone can change, delete, accept or withdraw on behalf of others (security lesson 23 Nov).
- The price range is calculated when the request is published. The separate review step from sketch 1 (see the range first, then publish) is not built; instead a request can be changed or deleted while it is `open`.
- The marketplace filter (date, city or postal code) runs in the browser; the API returns all requests. A filter by canton is not available.
- "My offers" collects the offers request by request, because the contract has no operation for the offers of one company.
- Error messages are shown as the API returns them, including the field name (for example `movingDate: must not lie in the past.`).
- The seed data (requests 1038, 1042 and 1047; customers 1 and 2; companies 7, 8 and 9) has moving dates in November 2026. Open requests whose date has passed stay listed; only `assigned` requests change to `completed`.
- JSON file instead of a database; the real persistence follows in the persistence lesson.

### Integration (Milestone 3)

**Frontend choice.** Plain HTML, CSS and JavaScript in `frontend/`, served by the same FastAPI application under `/app`. The HTML is produced in the browser (`frontend/app.js`) and the browser calls the API directly with `fetch`; there is no frontend server and no build step. Our reasons: one start command and one port, no second technology to learn before the security lesson, and every request can be followed in the network tab of the browser. FastAPI only delivers the three static files (`app.mount("/app", ...)` at the end of `create_app` in `movematch/api.py`).

**User and goal.** Lena (customer) publishes her move from Basel to Zürich and accepts an offer. The dispatcher of Umzüge Keller GmbH finds the request on the marketplace and submits that offer.

**Compared with the sketches** ([customer](sketches/01-customer-create-request.png), [company](sketches/03-company-marketplace-offer.png)):

- As sketched: one column with +/− steppers and a highlighted price range for the customer, a table with filters and a price field labelled with the allowed range for the dispatcher, errors at the form with all input kept.
- Changed: the new request flow has two states (form, saved request) and not three, because the price range comes from the backend when the request is saved. Confirming an action that cannot be undone is a second click on the same button.
- Not built: the start page for visitors and the login. A list of demo users in the header takes their place.

| View | Role | API calls | State |
|---|---|---|---|
| My requests | Customer | `GET /moving-requests` | connected (own requests selected in the browser) |
| New request, change request | Customer | `GET /furniture-types`, `POST /moving-requests`, `PUT /moving-requests/{id}` | connected |
| Request detail with offers | Customer | `GET /moving-requests/{id}`, `GET /offers?movingRequestId=`, `POST /offers/{id}/accept`, `DELETE /moving-requests/{id}` | connected |
| Marketplace | Company | `GET /moving-requests` | connected; the filter runs in the browser |
| Request detail with offer form | Company | `GET /moving-requests/{id}`, `POST /offers` | connected |
| My offers | Company | `GET /offers?movingRequestId=` per request, `DELETE /offers/{id}` | connected |
| Start page, login | Visitor | none | not built |

**Trace of one interaction: Lena publishes a moving request**

| Step | What happens in our project | Relevant code or data |
|---|---|---|
| User action | Lena fills in both addresses, 90 km, the moving date and the furniture (1 sofa, 1 bed, 2 wardrobes, 20 boxes) and clicks "Calculate price range and publish" | `renderRequestForm` in [`frontend/app.js`](frontend/app.js) |
| Request | `POST /moving-requests` with the header `X-Customer-Id: 1` and a body shaped like [`data/create-moving-request.json`](data/create-moving-request.json) | `onsubmit` handler in `renderRequestForm` and `api()` in `frontend/app.js`; route `create_moving_request` in [`movematch/api.py`](movematch/api.py); shape `MovingRequestInput` in [`movematch/models.py`](movematch/models.py) |
| Processing and storage | The customer must exist; the date must not lie in the past (rule 1); at least one item needs a quantity of 1 or more (rule 2); volume 10.5 m³ and estimate CHF 1,400 give the range CHF 1,200 to 1,600 (rule 3). The request is saved with the next ID and the status `open` in `movematch-data.json` | `create_moving_request`, `calculated_fields` and `price_range` in [`movematch/service.py`](movematch/service.py); `JsonStore.save` in [`movematch/storage.py`](movematch/storage.py) |
| Result | `201` with the saved request and a `Location` header. The interface shows "Request MM-1048 is published. Price range: CHF 1200 – 1600." and opens the request with its (still empty) list of offers | the same `onsubmit` handler, `showNotice` and `renderCustomerDetail` in `frontend/app.js` |

**What we checked.** Clicked through in Chrome on 16 November 2026 against a fresh data file. Every success was confirmed by reading the data back from the API, not only by the confirmation in the interface. The same cases are covered by the automated tests.

| Case | Action or input | Expected result | Observed result / remaining issue |
|---|---|---|---|
| Success | Lena: 4057 Basel, floor 3, no lift → 8004 Zürich, floor 1, lift; 90 km; 05.12.2026; 1 sofa, 1 bed, 2 wardrobes, 20 boxes | Request saved as `open` with 10.5 m³ and CHF 1,200 to 1,600; confirmation in the interface | As expected. `GET /moving-requests` returned request 1048 with status `open`, customer 1 and the range 1200 to 1600 |
| Error | The same input with the moving date 06.10.2026 | `422`, message at the form, input kept, nothing saved | As expected: "movingDate: must not lie in the past. (HTTP 422)" below the form, the input stayed, the API still returned three requests. Remaining issue: the message is the raw text of the API |
| Error | Umzüge Keller GmbH enters CHF 1750 for MM-1048 | `422`, allowed range shown, input kept, no offer saved | As expected: "price: must be between 1200 and 1600 CHF. (HTTP 422)" at the price field; `GET /offers?movingRequestId=1048` returned an empty list |
| Success | Umzüge Keller GmbH offers CHF 1450; Lena accepts the offer and confirms | Offer `pending` and request `offers_received`; after accepting: offer `accepted`, request `assigned` | As expected, read back from the API after each step |
| Limitation | Lena wants to see the price range before she publishes | A review step as in sketch 1 | Not built: the range is shown after saving. Next check once it exists: nothing is saved before the customer confirms |

Also clicked through with the expected result: withdrawing a pending offer under "My offers", changing an open request (the price range is recalculated) and deleting a request.

## 5. Execution

Requires Python 3.13 (earlier 3.x may work).

```
python -m venv .venv
.venv\Scripts\activate          # Windows;  macOS/Linux: source .venv/bin/activate
pip install -r requirements-test.txt
python -m uvicorn main:app --reload
```

The application runs at http://127.0.0.1:8000 and only this one process has to keep running. The browser interface is at http://127.0.0.1:8000/app/ and the interactive API documentation (Swagger UI) at http://127.0.0.1:8000/docs (the start address leads there). The file `movematch-data.json` is created on the first start; delete it (with the server stopped) to reset to the seed data.

### Start in GitHub Codespaces (no local installation)

1. On the repository page click **Code → Codespaces → Create codespace on main**.
2. In the terminal of the Codespace run:
   ```
   pip install -r requirements-test.txt
   python -m uvicorn main:app
   ```
3. Click **Open in Browser** in the "Port 8000" notification. The Swagger UI opens; there, **Try it out → Execute** runs a request. Replace `/docs` by `/app/` in the address to open the interface.
4. Run `python -m pytest` in a second terminal to execute the tests. Stop the server with `Ctrl+C`.

### Demo in the interface

Open http://127.0.0.1:8000/app/. All data is fictional; use a moving date in the future.

1. Acting as **Lena Meier**: **New request**, fill in the form (for example 4057 Basel, floor 3 → 8004 Zürich, floor 1 with lift, 90 km, 1 sofa, 1 bed, 2 wardrobes, 20 boxes) and publish. The request appears with the price range CHF 1200 – 1600.
2. Try the same with a date in the past: the message appears below the form, the input stays and nothing is saved.
3. Acting as **Umzüge Keller GmbH**: **Marketplace**, open the new request, enter 1750 (rejected, range shown), then 1450 (saved, listed under **My offers**).
4. Acting as **Lena Meier** again: open the request, **Accept offer** and confirm. The request is `assigned` and the offer `accepted`.

### Demo (Swagger UI or curl)

1. `GET /moving-requests/1042` → 200, `reference` `MM-1042`, price range 1200–1600.
2. `POST /offers` with header `X-Company-Id: 7` and body from `data/create-offer.json` → 201, `Location: /offers/311`, status `pending`.
3. Repeat step 2 → 409 (company already has an offer, rule 5).
4. `POST /offers` with header `X-Company-Id: 7` and body `{"movingRequestId": 1047, "price": 1750}` → 422 (range of this request is 700–900, rule 4).
5. `POST /offers` for `movingRequestId` 1038 → 409 (request is assigned, rule 6).
6. `DELETE /offers/311` → 204; `GET /offers/311` → 404.
7. `DELETE /offers/305` → 409 (accepted offers are binding, rule 9).

```
curl -X POST http://127.0.0.1:8000/offers -H "Content-Type: application/json" -H "X-Company-Id: 7" -d @data/create-offer.json
```

### Tests

```
python -m pytest
```

`tests/test_api.py` checks the offer operations and `tests/test_requests.py` the operations added in Milestone 3: success, invalid input and conflicts against the planned errors in `data/error-examples.json`. `tests/test_contract.py` checks that the contract and the implementation agree (operations, status codes, data shapes, real responses and all examples). The tests of Milestone 3 run with a fixed date, so their result does not depend on the day.

## 6. References and acknowledgements

- Course material Web-based Applications HS26 (FHNW, Dr. Devid Montecchiari): "Networks, the Web and APIs", "Web engineering and application design", "API design and lifecycle", project assignment and Milestone 1 README template.
- Sketches, the data model diagram and the sample data were created digitally; parts of the text, sketches, sample data and the code (backend, tests, contract) were drafted with AI assistance (Claude) and reviewed and adapted by the team.
- The browser interface and the operations added in Milestone 3 were also drafted with AI assistance (Claude) and are reviewed by the team.
