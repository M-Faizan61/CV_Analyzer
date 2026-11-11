# Test job descriptions

There are 28 job descriptions in `data\job_descriptions`. Between them they hold 98 requirements
that take part in decisions, plus 4 personal conditions that must be ignored.

These results are for the **Manual** method with **Use CV folder** (11 unique CVs). They were worked
out by hand from the CVs first, then checked by `tests/test_sample_jobs.py`, so they are a real test.
Results will change if you add or remove CVs in `data\cvs`.

## How to test one

1. Click **Use Manual**.
2. Upload a file from `data\job_descriptions`, then click **Read requirements** and **Next: add CVs**.
3. Open **Use CV folder**, click **Add all 14 files**, then **Analyze 11 CVs**.
4. Compare the result with the table below. Names are in rank order.

## Expected results

Anyone not listed is Not shortlisted.

| File (`.txt`) | What it tests | Shortlisted | Needs review |
|---|---|---|---|
| `sample_wordpress_developer` | Headings, duties and an age condition are ignored | Farhan Iqbal, Bilal Ahmed, Ayesha Noor | |
| `sample_python_developer` | An "or" group, years and a related degree | Hamza Tariq, Ali Raza | |
| `job_01_junior_python_developer` | A low years limit. Ahmed's CV shows Python but no years | Ali Raza, Hamza Tariq, Usman Khalid, Sana Malik | Ahmed Ali |
| `job_02_senior_python_developer` | A high years limit, numbered list | Hamza Tariq | |
| `job_03_django_developer` | Flask does not count as Django | Ali Raza | |
| `job_04_backend_developer` | "Python or PHP" and total experience | Hamza Tariq, Usman Khalid, Ali Raza, Sana Malik | |
| `job_05_full_stack_developer` | Nobody qualifies, and the rules are not relaxed | Nobody | |
| `job_06_java_developer` | JavaScript does not prove Java | Nobody | |
| `job_07_nodejs_developer` | JavaScript does not prove Node.js | Nobody | |
| `job_08_front_end_developer` | One line that needs three skills, each with years | Zain Abbas | |
| `job_09_data_analyst` | Several accepted degree subjects | Sana Malik | |
| `job_10_data_scientist` | A master's degree is required | Usman Khalid | |
| `job_11_bi_analyst` | A near miss: Sana has 2 years, and 3 are needed | Nobody | |
| `job_12_mysql_database_developer` | SQL does not prove MySQL | Nobody | |
| `job_13_senior_wordpress_developer` | 5+ years filters out Ayesha and Bilal | Farhan Iqbal | |
| `job_14_wordpress_plugin_developer` | The rules cannot confirm plugin work, so a person must check | Nobody | Ayesha Noor, Bilal Ahmed, Farhan Iqbal |
| `job_15_woocommerce_developer` | Farhan has no CSS on his CV | Bilal Ahmed | |
| `job_16_elementor_web_designer` | One rare skill | Ayesha Noor | |
| `job_17_cms_developer` | WordPress proves CMS | Farhan Iqbal, Ayesha Noor, Bilal Ahmed, Zain Abbas | |
| `job_18_seo_specialist` | Hassan has no keyword research on his CV | Maryam Sheikh | |
| `job_19_technical_seo_lead` | SEO does not prove Technical SEO | Hassan Javed | |
| `job_20_content_writer` | Nice-to-haves do not block anyone | Maryam Sheikh | |
| `job_21_digital_marketing_executive` | Ayesha has SEO, but a computer science degree | Hassan Javed, Maryam Sheikh | |
| `job_22_python_intern` | A short job with one requirement | Hamza Tariq, Usman Khalid, Ali Raza, Sana Malik, Ahmed Ali | |
| `job_23_data_entry_operator` | Gender, age and domicile are ignored | Sana Malik | |
| `job_24_data_analyst_paragraph` | One paragraph with no headings or bullets | Sana Malik | |
| `job_25_team_lead` | No skills, only years and a degree. Hamza and Hassan tie at rank 2 | Farhan Iqbal, Hamza Tariq, Hassan Javed | |
| `job_26_crm_executive` | Tools the system does not know | Nobody | |

Ahmed Ali comes from two old test files in `data\cvs` (`ui_test_*.txt`). If you delete them, remove him
from these results too.

## What the sample CVs cannot test

All sample CVs are employees, or "Not clear" for Ahmed Ali, so none of these jobs shows a **Student** result.
To test one, use **Enter manually** in step 3 and paste a CV containing a phrase such as "final year student",
or add a record by hand with the type set to Student.

## Run all of them at once

```powershell
.\.venv\Scripts\python -m pytest tests/test_sample_jobs.py -q
```
