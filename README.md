# redfolder-ics

Auto-updating calendar feed of Forex Factory **high- and medium-impact** economic events, ready to subscribe to in Apple Calendar (iPhone, iPad, Mac), Google Calendar, or Outlook.

A GitHub Action runs on a schedule, pulls Forex Factory's public weekly feed, keeps only the impact levels and currencies you choose, and publishes a standard `.ics` file. Your calendar app subscribes to that file once and stays in sync on its own.

```
🔴 Non-Farm Employment Change     Fri 17:30 – 17:45
🟠 Unemployment Claims            Thu 17:30 – 17:45
```

> Times are shown in your device's local time zone automatically.

---

## Features

- **Impact filter**: high only (red folder), or high + medium (orange folder), or all.
- **Currency filter**: one currency or several (`USD`, `EUR,GBP,JPY`, …).
- **Reminders**: built-in alerts at configurable lead times (e.g. 30 and 5 minutes before).
- **History**: past weeks stay on the calendar for a configurable number of days.
- **Self-correcting**: rescheduled, cancelled, or downgraded events are updated or removed on the next run, without duplicates.
- **Quiet commits**: the bot only commits when an event actually changes.
- **No dependencies**: one Python file, standard library only. No server, no API key, no cost.

---

## Quick start

### 1. Create the repository

1. Create a new **public** repository on GitHub (e.g. `redfolder-ics`).
   The repository must be public: calendar apps cannot log in to read files from a private repo.
2. Add the files from this project, keeping the folder structure:

   ```
   redfolder-ics/
   ├── .github/
   │   └── workflows/
   │       └── update.yml
   ├── build_calendar.py
   ├── LICENSE
   └── README.md
   ```

   > **Tip:** `.github` is a hidden folder on macOS/iOS. If it doesn't show up after unzipping, create the workflow directly on GitHub: **Add file → Create new file**, type `.github/workflows/update.yml` as the name, and paste the contents in.

### 2. Allow the workflow to write

**Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**

Without this, the workflow cannot save the calendar file.

### 3. Run it once

**Actions → Update red folder calendar → Run workflow.**

After about 15 seconds, the run turns green and a `docs/` folder appears in the repository containing:

| File | Purpose |
|---|---|
| `docs/redfolder.ics` | The calendar feed you subscribe to |
| `docs/events.json` | Stored event history (used internally) |

### 4. Get your feed URL

```
https://raw.githubusercontent.com/<USERNAME>/<REPO>/<BRANCH>/docs/redfolder.ics
```

- `<BRANCH>` is your default branch, usually `main` or `master` (shown at the top left of the repo's Code tab).
- Paste the URL into a browser first. You should see text starting with `BEGIN:VCALENDAR`. A 404 means the username, repo or branch is wrong, or the first run hasn't finished.

### 5. Subscribe

**iPhone / iPad**

1. Open **Calendar** → **Calendars** → **Add Calendar** → **Add Subscription Calendar**.
2. Paste the feed URL → **Subscribe**.
3. Set **Account** to **iCloud** (syncs to all your Apple devices).
4. Pick a color that doesn't clash with the 🔴/🟠 markers. Purple works well.
5. Keep **Event Alerts** on.
6. Under **Subscription Details**:
   - **Remove Alerts**: **Off** (otherwise reminders are stripped)
   - **Remove Attachments**: On
7. Tap ✓.

**Mac**

**Calendar → File → New Calendar Subscription**, paste the URL, set **Location: iCloud** and **Auto-refresh: Every hour**.

> iPhone has no refresh-interval setting. If you have a Mac on the same Apple ID, set **Auto-refresh** there (right-click the calendar → **Get Info**) and the setting applies to all your devices through iCloud.

**Google Calendar**: **Other calendars → + → From URL**.
**Outlook**: **Add calendar → Subscribe from web**.

---

## Configuration

All settings live in `.github/workflows/update.yml` under `env:`:

```yaml
env:
  CURRENCIES: "USD"        # e.g. "USD,EUR,GBP,JPY,CNY"
  IMPACTS: "High,Medium"   # High, Medium, Low
  ALERT_MINUTES: "15"      # e.g. "30,5"; "" for no reminders
  KEEP_DAYS: "45"          # days of past events to keep
```

| Variable | Default | Description |
|---|---|---|
| `CURRENCIES` | `USD` | Currencies to include, comma-separated. With a single currency, the code is left out of event titles. With several, titles are prefixed (`USD Non-Farm …`). |
| `IMPACTS` | `High` | Impact levels to include: `High`, `Medium`, `Low`. |
| `ALERT_MINUTES` | `15` | Reminder lead times in minutes, comma-separated. Empty disables reminders. |
| `KEEP_DAYS` | `45` | How many days of past events stay on the calendar. |
| `EVENT_MINUTES` | `15` | Length of each calendar block, in minutes. |

Changes take effect on the next run. To apply them immediately, use **Actions → Run workflow**.

### Impact markers

The markers are set in `build_calendar.py`:

```python
ICON = {"High": "🔴", "Medium": "🟠", "Low": "🟡"}
```

Any emoji works, for example `🚨 / ⚠️`, `🟥 / 🟧` or `📕 / 📙`. Calendar titles are plain text, so images (such as Forex Factory's folder icons) are not possible.

---

## How it works

```
Forex Factory weekly feed ──► GitHub Action (scheduled) ──► docs/redfolder.ics ──► Calendar app
                                   filter + merge                (public URL)        (polls URL)
```

1. **Fetch**: downloads Forex Factory's current-week feed (and next week's, if available).
2. **Filter**: keeps only the configured impact levels and currencies; bank holidays are skipped.
3. **Merge**: the feed only covers one week, so events are stored in `docs/events.json`. For the dates the feed covers, the feed is treated as the source of truth: stored events in that range are replaced, which handles reschedules, cancellations, and impact changes.
4. **Write**: each event gets a stable ID (currency + title + date), so updates replace the existing calendar entry instead of creating duplicates. Times are written in UTC; calendar apps convert them to local time.
5. **Commit**: only when the output actually changed.

### Update timing

Updates reach your phone through two independent loops:

| Step | Interval |
|---|---|
| GitHub Action regenerates the file | Hourly (best effort; see below) |
| Calendar app re-downloads the file | Device/iCloud schedule; Mac-configurable |

Expect changes to appear within a few hours. Event times are published days in advance, so this is ample for planning. **For same-day changes, always confirm on [forexfactory.com/calendar](https://www.forexfactory.com/calendar).**

Reminders are scheduled on your device, so they fire on time regardless of when the feed last updated.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Run fails at the **Commit** step | Enable **Read and write permissions** (Quick start, step 2). |
| Feed URL returns 404 | Check username, repo name (case-sensitive) and branch name in the URL. |
| No reminders on iPhone | Subscription settings: **Event Alerts** on, **Remove Alerts** off. |
| Times look wrong | iPhone: **Settings → Apps → Calendar → Time Zone Override** should be off. |
| Scheduled runs are irregular or missing | Normal for new repositories: GitHub delays or skips scheduled runs under load. It usually settles within days. Changing the cron minute in `update.yml` can re-register a stuck schedule. |
| Workflow disabled after a long quiet period | GitHub pauses schedules in inactive public repos. Open **Actions** and click **Enable workflow**. |
| Calendar not updating | Pull down on the **Calendars** list (iPhone) or press **⌘R** (Mac) to refresh. |
| Run fails at **Build ICS** | Open the failed run's log. Usually a Python indentation error after a manual edit, or the Forex Factory feed was temporarily unreachable (the next run retries). |

### Running locally

```bash
python3 build_calendar.py                            # fetch live feed, write docs/
CURRENCIES=USD,EUR IMPACTS=High python3 build_calendar.py
SOURCE_FILE=sample.json OUT_DIR=/tmp/out python3 build_calendar.py   # offline test
```

Requires Python 3.9+. No packages to install.

---

## Limitations

- **No actual values.** The free feed carries forecast and previous figures only. Check Forex Factory for released numbers.
- **No real durations.** Releases are instantaneous; the block length is a fixed placeholder (`EVENT_MINUTES`).
- **One week ahead.** Forex Factory publishes the next week's calendar over the weekend.
- **Unofficial source.** The feed is public but undocumented and may change or be rate-limited without notice. If it breaks, runs fail visibly in the **Actions** tab, and the calendar keeps its last good state.

---

## Disclaimer

This project is not affiliated with or endorsed by Forex Factory or Fair Economy, Inc. Event data belongs to its respective owners and is provided as-is, without warranty of accuracy or timeliness. Do not rely on it as your only source for trading decisions.

## License

[MIT](LICENSE). Applies to the code in this repository, not to the event data.
