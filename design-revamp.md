# Bench directory UI revamp

## Problem

Visitors currently have to scroll past a large introductory section before they can see which benches are available. The main action, adopting an available bench, is too far down the page.

## Proposed page flow

1. **Top summary:** Show the number of benches adopted or reserved, the number available, and the total. Keep this section compact enough that availability is visible when the page opens, including on mobile.
2. **Next bench to become available:** Highlight the reserved bench whose adoption ends soonest, including its bench number, location, and first available date. Also keep a direct path to benches that can be adopted now.
3. **Bench availability map:** Below the summary, show roughly ten benches at a time in a vertically scrollable, Gantt-style view. Put benches in rows and dates along the horizontal axis, with bars for adopted or reserved periods and visible gaps for availability. Let visitors scroll down to see more benches and open a bench's detail page from its row.
4. **Full directory:** Keep search, status filters, and the complete bench listing below the new overview for visitors who want to choose a different bench.

## Goals

- Make the available inventory and primary adoption action visible without scrolling through the introduction.
- Let visitors understand the collection's progress at a glance.
- Preserve a clear path to browse every bench.
- Make the same information and actions easy to use on a small screen.

## Decisions to make before implementation

1. What date range should the Gantt-style map cover (for example, the next 90 days), and should visitors be able to move backward or forward in time?
2. Which benches should appear first in the map: those becoming available soonest, benches in number order, or benches in the current search/filter results?
3. Should the map include completed adoption periods, or focus on current and upcoming reservations and availability?
4. Should the map show public adopter names, or only bench numbers, dates, and availability?
5. Should the top overview remain the same while visitors search or filter the directory, or should it reflect the filtered results?

This is a design note only. No UI or application behavior is changed here.
