# Planka Behavior based script system

**Summary:** Create a scheduled job system for Planka Tools. Jobs are able to carry out any methods in client.py file.

## Job Automation Triggers:

### APScheduler

- On X:XX AM/PM time each day, week, month, etc
- Every specific day(s) of the week
- Every X hours

### Webhooks (Already created for updating points in a list)

- When a <card> is affected in some way. (created, moved, updated, deleted)

### Automation Logic

- Any method in the C:\projects\AppDev\Planka\src\planka_tools\api\client.py
  should be callable in a script.
- Each individual job script should be isolated to its own file and stored in a folder based on its job type.
  - Job types: Scheduled, Webhook
  - Sub folders may need to exist as number of jobs grow.

### Job Examples

### APScheduler

---

#### Example 1

---

##### Trigger:

- Every day at 8:00 am

##### Action:

- Move all the cards in list "Tomorrow" to list "Today" on board "Daily Workflow" in Project "Trello Import"

#### Example 2

---

##### Trigger:

- Every month on the 1st at 4:00 am

##### Action:

- Move all the cards in list "This Month" to list "This Week" on board "Daily Workflow" in Project "Trello Import"

#### Example 3

---

##### Trigger:

- Every day at 11:59 pm

##### Action:

- Move each card due in less than 0 days to list "Past-Due" on board "Daily Workflow" in Project "Trello Import"

#### Example 4

---

##### Trigger:

- Every day at 6:00 am

##### Action:

- Copy each card in list "Daily" on board "Personal" in Project "Trello Import" to list "Today" on board "Daily Workflow" in Project "Trello Import"

#### Webhook

##### Trigger:

- When a card is moved to list "In-Progress" on board "Daily Workflow" in Project "Trello Import"

##### Action:

- Assign me to that card
