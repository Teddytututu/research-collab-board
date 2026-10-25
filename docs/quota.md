# Quota and workload algorithm

For each assistant, remaining ratio is r and reset horizon in hours is T. Hourly budget B = r / max(T, 0.5). The initial patrol cost is 0.01; update cost with an exponential average using alpha 0.3 over up to twenty recent valid before/after drops. A quota reset contributes no negative cost. Smooth remaining ratio and reset horizon with the same alpha; reset events use their current values immediately. Apply the raw remaining ratio to the low-quota safeguard.

Base interval in minutes = clamp(60 × c / (0.3 × B), 20, 240). An idle assistant multiplies the interval by 1.5, capped at 240. A mention or a deadline within two hours requests twenty minutes. Below r = 0.1, routine work pauses; a mention or review-ready delivery enables a wake. Changes below twenty percent keep the old interval. Identical UI refreshes keep the existing next-wake time.

Transferable work goes to the eligible assistant with maximum B / (1 + w), where w counts active and review tasks. Suggested long-term shares are clamped between 20% and 80%. A paused assistant's work is handed to the eligible assistant even when the displayed long-term share remains at the floor.

The scenario table is in [quota-scenarios.md](quota-scenarios.md). Inputs are supplied by assistants or the manual band selector. The application keeps advice in data/attachments/schedule.json; provider scheduling is performed by the assistants.

The planning defaults and the reported facts have separate presentation. A new project keeps its initial planning band and displays pending report. Manual choices carry a manual-estimate source, configured fallbacks carry a configured-estimate source, and actual provider percentages carry their source, precision and observation time. Historical band reports with a missing source display as reported estimates. Patrol times in the panel are suggestions; actual provider-native timers belong to the responsible session. These provenance fields leave the six-scenario budget equations intact.
