# MoveMatch

**Current stage:** Milestone 1 — design draft. This README is updated throughout the project; we do not start a separate document for each milestone.

Later sections (implementation, execution) will be added from the fourth theory session onwards. This version documents our design draft: drafts and open questions are expected; there is no running backend, database or complete OpenAPI contract yet.

## Project overview

MoveMatch is a web marketplace for private moves. Today, people who move contact five to ten moving companies one by one, fill in a different form each time and wait for replies. Many companies have no capacity on the requested date, and the quotes are hard to compare because each company asks for different details. Companies, in turn, lose time on incomplete requests.

With MoveMatch, a customer describes the move **once** in a standard form (addresses, distance, date, floor, lift and the number of specific furniture items). The application calculates a price range that leaves room for negotiation and publishes the request on a marketplace. Registered moving companies browse the requests, submit one offer within the range, and the customer accepts the offer that fits best.

**Intended users:** private customers who are planning a move, and dispatchers of small and medium moving companies.

### Team and initial responsibilities

| Member | Initial responsibility | Next action |
|---|---|---|
| [Name] | Coordination and README | Keep decisions, questions and the milestone commit together; submit the repository link in Moodle |
| [Name] | Users and workflow | Refine workflows A–B and the business rules after coaching |
| [Name] | Sketches and interaction | Turn the sketches into a clickable prototype (Exercise 3) |
| [Name] | Data and API exploration | Maintain the sample JSON in `data/`; prepare the first OpenAPI draft for Milestone 2 |

These are starting responsibilities, not permanent silos. Everyone reviews the whole draft and should be able to explain it in coaching.

1. Analysis
Scenario, users and goals
Situation or problem: A person moving from Basel to Zürich has to contact many companies, repeat the same information in different forms and compare quotes that are based on different assumptions. Moving companies receive incomplete enquiries and requests for dates on which they are already fully booked.
Intended users:
Customer (e.g. Lena, private person): wants to describe the move once and receive comparable offers.
Moving company (e.g. the dispatcher of Umzüge Keller GmbH): wants complete, comparable requests to fill free days in the schedule.
Admin: optional, later (e.g. company verification).
Proposed benefit: one standard request instead of ten; offers only from companies with capacity; comparable offers within a transparent price range; less time spent on incomplete enquiries.
Initial scope: Workflow A (customer publishes a request) and Workflow B (company submits an offer), plus accepting an offer.
Left out for now: online payment (needs a payment provider and legal checks), chat or live negotiation (the price range covers negotiation), automatic distance via a maps API (customers enter postal codes and an approximate distance), reviews and ratings (only useful once real moves happened), company verification (we assume registered companies are legitimate).
User stories and first workflow
Customer

As a customer, I want to describe my move once in a standard form, so that I do not have to fill in a different form for every company.
As a customer, I want to see an expected price range before publishing, so that I know what the move will roughly cost.
As a customer, I want to compare offers and accept one, so that my move is booked with a company that has capacity on my date.
As a customer, I want to withdraw my request before accepting an offer, so that companies stop sending offers if my plans change.
Moving company

As a dispatcher, I want to filter open requests by date and region, so that I only see jobs that fit our free days.
As a dispatcher, I want to see all details of a request (floors, lift, furniture), so that I can make a realistic offer without calling back.
As a dispatcher, I want to submit an offer within the price range, so that the customer can compare it fairly with other offers.
Workflow A — customer publishes a moving request (Lena, Basel → Zürich)

Step	User / role	Action	Information needed	Expected result or feedback
1	Customer	Enter the move details	From/to postal code and city, floor, lift, distance (km), moving date, quantity of sofas, beds, wardrobes and boxes	Input is kept ready to submit
2	Customer	Submit the form ("Calculate price range")	The entered data	Required fields checked; moving date at least 7 days ahead
3	Customer	Review the summary	—	Route, date, volume (10.5 m³) and price range (CHF 1,200–1,600) are shown
4	Customer	Publish the request	Confirmation	Request saved with status open and reference MM-1042; listed on the marketplace
5	Customer	Open the offers and accept one (after confirming)	Chosen offer	Request assigned; chosen company notified; all other offers declined
2a	Customer	Submit with a date only 3 days ahead	—	Message explains the 7-day minimum; other input is kept; no request is created
Workflow B — moving company submits an offer (Umzüge Keller GmbH)

Step	User / role	Action	Information needed	Expected result or feedback
1	Company	Open the marketplace	—	Open requests with date, route, volume and price range
2	Company	Filter by date and region	Date range, cantons	Only matching requests are shown
3	Company	Open one request	—	All details and the allowed price range
4	Company	Enter a price and submit the offer	Price (CHF), optional message	Price checked against the range; check that the company has no offer on this request yet
5	Company	Read the confirmation	—	Offer saved as pending; request changes to offers_received
4a	Company	Enter CHF 1,750 (above the range)	—	Allowed range is shown; input kept; offer not saved
Questions and exceptions worth discussing

What happens if a company cannot do the job after its offer was accepted (e.g. the truck breaks down a week before)? Version 1: handled outside the app; later possibly back to offers_received.
What if the customer notices more furniture after offers arrived? Draft decision: editing is only allowed while the request is open; afterwards the customer withdraws and creates a new request.
