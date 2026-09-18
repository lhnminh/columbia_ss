# Product Requirements Document: Bench Adoption Demo

## 1. Product summary

Build a responsive website demonstrating Van Cortlandt Park's bench adoption program. Visitors can browse benches, see which are adopted and by whom, and book an available bench for a chosen start date, end date, and donation amount. No payment is collected.

## 2. Demo scope

The demo will use a seeded inventory of 500+ fictional benches, labeled Bench1, Bench2, Bench3, and so on. These labels are demo data, not a real park inventory. It will have a public bench directory, bench detail pages, and a booking flow. It will not have staff accounts, an admin interface, or an inventory import workflow.

## 3. User flow

1. Browse or search benches by ID or location.
2. Filter benches by **Available** or **Adopted**.
3. Open a bench to see its status. For an adopted bench, see the donor's public name and adoption dates.
4. For an available bench, choose an adoption start date and end date, enter a public donor name and a specific amount in USD, then review and confirm.
5. See a confirmation with the bench ID, adoption dates, and recorded amount. The confirmation clearly states that no payment was taken.

A confirmed booking immediately marks the bench as adopted.

## 4. Functional requirements

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| BR-01 | Every bench has a unique ID. | The seeded inventory contains no duplicate IDs. |
| BR-02 | Visitors can search and filter benches. | Results show the correct benches and current availability. |
| BR-03 | Adopted bench pages show the donor and date range. | The page shows the public donor name and adoption start and end dates. |
| BR-04 | Visitors can book an available bench for a date range. | The form requires a start date no earlier than today and an end date after the start date; confirmation creates an adoption and immediately changes the bench to Adopted. |
| BR-05 | Visitors can enter a specific amount. | The form accepts a USD amount greater than $0 with no more than two decimal places and saves it exactly. |
| BR-06 | No payment is processed. | There are no card fields or payment integrations; confirmation says no payment was taken. |
| BR-07 | Conflicting bookings are prevented. | If a bench is booked by someone else first, the second booking creates no adoption and shows a clear message. |
| BR-08 | Availability reflects adoption dates. | A confirmed future-dated booking reserves the bench immediately; it becomes available again after the end date while its booking record remains in the demo database. |

## 5. Frontend requirements

The website must work on desktop and mobile. It needs clear status labels, accessible forms and validation messages, a review step before confirmation, and a helpful message when a bench becomes unavailable during booking. The MVP can use Flask templates and CSS.

## 6. Demo data and technical approach

Seed 500+ fictional benches named Bench1, Bench2, Bench3, and so on, with simple demo locations. Include some existing adoptions so both statuses are visible immediately. Store the demo data in SQLite using three tables:

| Table | Purpose | Key fields |
| --- | --- | --- |
| `benches` | Stores information about each bench. | Unique bench ID, location |
| `adopters` | Stores the person who adopts a bench. | Adopter ID, public name |
| `adoptions` | Records each booking and links a bench to an adopter. | Bench ID, adopter ID, start date, end date, amount in cents |

One bench can have multiple adoptions over time, and one adopter can have multiple adoptions. Because the demo collects no reliable identifier beyond a name, it must not assume that two bookings with the same name belong to the same person; each booking can create a new adopter record. Save monetary amounts as exact cents rather than floating-point numbers. Perform booking and availability checks in one database transaction.

The donor chooses both real calendar dates; the system does not calculate the end date from a number of months. "Today" is determined in the park's `America/New_York` time zone. The end date is inclusive: a bench becomes available the following day. A confirmed booking reserves the bench immediately, even if its start date is in the future. The demo labels a bench with a current or future booking as **Adopted** and displays the selected dates so visitors can distinguish a scheduled adoption from one already in progress. New bookings are allowed only when the bench has no current or future booking; overlapping date ranges are never allowed.

## 7. Out of scope

Payments, donor contact details, staff management, CSV import, email, donor accounts, and an interactive map are out of scope for this demo.

## 8. Demo acceptance checklist

The demo is complete when someone can find a bench, book it with chosen start and end dates and an amount, see it change to Adopted, and see its public donor name and dates. A second visitor must not be able to book it for the same period, and no part of the flow should suggest that payment was collected.
