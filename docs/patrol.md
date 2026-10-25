# One patrol

1. Read the project, task state, new user messages and quota schedule.
2. Follow the assistant's active wake condition. Continue the smallest concrete authorized action.
3. Record the before and after remaining ratio, or a labelled quota band, and the reset horizon with scripts/patrol.py.
4. Read schedule.json. Apply the next provider wake with the existing automation or scheduling task ID.
5. Report meaningful results, failures and required user decisions. Keep unchanged states quiet.

For a paused row, hand transferable work to schedule.handoff_to and suppress routine work. User mentions and review-ready deliverables change the local advice. A provider event integration or the user's next assistant session applies that change to a paused provider task.
