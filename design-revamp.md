# Bench directory UI revamp

## Problem

Visitors currently have to scroll past a large introductory section before they can see which benches are available. The main action, adopting an available bench, is too far down the page.

## Proposed page flow

1. **Top summary:** Show the number of benches adopted or reserved and the number available. Keep this section compact enough that availability is visible when the page opens, including on mobile.
2. **Next available bench:** Highlight the first bench that is currently available to adopt, including its bench number, location, and a direct link to begin adoption.
3. **Bench availability map:** Below the summary, show roughly ten benches at a time in a vertically scrollable, Gantt-style view. Put benches in rows and dates along the horizontal axis, with bars for adopted or reserved periods and visible gaps for availability. Let visitors scroll down to see more benches and open a bench's detail page from its row.
4. **Full directory:** Keep search, status filters, and the complete bench listing below the new overview for visitors who want to choose a different bench.

## Goals

- Make the available inventory and primary adoption action visible without scrolling through the introduction.
- Let visitors understand the collection's progress at a glance.
- Preserve a clear path to browse every bench.
- Make the same information and actions easy to use on a small screen.

## Implementation decisions

1. The map covers the next 90 days, matching the booking horizon.
2. Benches stay in number order so the map does not unexpectedly rearrange itself.
3. The map focuses on current and upcoming reservations; completed periods are omitted.
4. The map shows bench numbers, locations, dates, and availability without public adopter names.
5. The overview represents the whole collection while directory search and filters only change the directory below it.

The revamp is implemented in the home directory page.
