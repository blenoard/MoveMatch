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
