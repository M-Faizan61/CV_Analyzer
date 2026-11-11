# Run and test CV Analyzer, step by step

All commands are for Windows PowerShell. You do not need to install anything: the
`.venv` folder already has every package.

## 1. Start the app

Double-click **start.bat**, or run these two commands:

```powershell
cd D:\cv_analyzer
.\.venv\Scripts\python -m streamlit run app.py
```

Open **http://127.0.0.1:8520** in your browser. Keep the black window open while you
use the app. Press `Ctrl+C` in that window to stop it.

## 2. Test the Manual method (no API key)

1. Click **Use Manual**.
2. Click **Upload** and choose `data\job_descriptions\sample_wordpress_developer.txt`.
   The text appears in the box.
3. Click **Read requirements**. Check the table, then click **Next: add CVs**.
4. Open the **Use CV folder** tab and click **Add all 14 files**.
   You should see: `Added 11 CV(s). Skipped 3 duplicate(s).`
5. Click **Analyze 11 CVs**.

Expected result: **3 shortlisted, 0 needs review, 8 not shortlisted**.

| Rank | Name | Match |
|---|---|---|
| 1 | Farhan Iqbal | 80% |
| 2 | Bilal Ahmed | 80% |
| 3 | Ayesha Noor | 70% |

Open the **Not shortlisted** tab and choose Zain Abbas to see why: only 2 years of
WordPress, and no PHP.

Then click **Shortlisted candidates** at the top of the page. All 3 records are in the database.

To try a second job, click **Start a new analysis** and use
`sample_python_developer.txt`. Expected result: **2 shortlisted**, Hamza Tariq and Ali Raza.

There are 28 test job descriptions in `data\job_descriptions`. [docs/test_jobs.md](docs/test_jobs.md)
lists what each one tests and who should be shortlisted.

## 3. Test entering a CV by hand

In step 3, open the **Enter manually** tab, fill in the form, and click **Add this CV**.
For example, enter the name `Hina Khan`, the education `BS Computer Science`, and these skills:

```text
WordPress: 4 years
PHP: 3 years
WooCommerce: 2 years
MySQL: 2 years
```

With the WordPress job, Hina is shortlisted at rank 1 with a 90% match.

## 4. Test the AI method (needs an OpenRouter key)

1. Create a key at https://openrouter.ai/keys
2. In the app, click **Use AI** and paste the key.
3. Leave the model as `openrouter/free`, or enter any model ID from https://openrouter.ai/models
4. Click **Test connection**. You should see `Connected. This key and model work.`
5. Tick the agreement box, click **Next**, and continue as in section 2.

To avoid pasting the key each time, create a `.env` file once:

```powershell
Copy-Item .env.example .env
notepad .env
```

Put your key after `OPENROUTER_API_KEY=`, save the file, and restart the app.

The `openrouter/free` model is limited by OpenRouter and can be busy. If you see a rate
limit message, wait a minute or choose another model. Free models may keep what you send,
so use a paid model for real CVs.

## 5. Add, view, change and delete records (CRUD)

Everything is on the **Shortlisted candidates** page, at the top of the app.

| Action | How |
|---|---|
| **Create** | Run an analysis, and shortlisted candidates are saved automatically. To add someone by hand: open the **Add a record** tab, choose a job or enter a new one, fill in the form, and click **Add record** |
| **Read** | Open the **Records** tab. Use the table, search box and filters, then choose a name under **Open a record** and open **Details** |
| **Update** | Open the record, open the **Edit** tab, change anything, and click **Save changes** |
| **Delete one record** | Open the record, open the **Delete** tab, tick the box, and click **Delete record** |
| **Delete a whole job** | Choose the job in the **Job** filter, click **Delete this job**, and confirm. This removes all of its records |

Good to know:

- You can change the name, email, phone, location, role, education, experience, type, skills, status and notes.
- Match and rank are calculated by the system, so they cannot be typed in. A record you add by hand has no match or rank.
- What you change is kept. If the same CV is analyzed again, the score updates but your corrections stay.
- Delete cannot be undone. If you delete someone and analyze their CV for the same job again, they are saved again.

## 6. Run the automatic tests

```powershell
cd D:\cv_analyzer
.\.venv\Scripts\python -m pytest -q
```

Expected result: `200 passed`. These tests use a temporary database and a fake OpenRouter,
so they need no key and do not touch your data.

## 7. Look inside the database

The records are in `data\cv_analyzer.db`. The file is created the first time you start the app.
The easiest way to read it is the **Shortlisted candidates** page, which also has a CSV download.
To count the records from PowerShell:

```powershell
.\.venv\Scripts\python -c "import sqlite3; print(sqlite3.connect('data/cv_analyzer.db').execute('select count(*) from shortlisted_candidates').fetchone())"
```

To start again with an empty database, stop the app and delete `data\cv_analyzer.db`.
It is created again the next time the app starts.

## If something goes wrong

| Problem | What to do |
|---|---|
| Port 8520 is already in use | The app is already running. Open http://127.0.0.1:8520 |
| An old app or error appears on 8501, 8502, 8505, 8508 or 8509 | Those are old copies. Use 8520, and see the note below |
| `python` is not recognised | Use the `.\.venv\Scripts\python` commands exactly as written |
| OpenRouter rejected this API key | Copy the key again from openrouter.ai/keys |
| A PDF shows under File problem | It is a scanned image. Provide a text PDF, or use Enter manually |

Old copies of the app can be stopped by closing their black windows, or by restarting the computer.
