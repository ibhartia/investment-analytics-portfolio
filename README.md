# Investment Analytics Portfolio: Ishaan Bhartia

Two projects that take a judgment-heavy investment question, make the method explicit, and back every number with a model that can be audited, re-run and reconciled.

| Project | What it does | Built with |
|---|---|---|
| [**Earnings Call Sentiment Analyzer**](earnings-call-sentiment/) | Scores earnings call transcripts on six rubric-anchored dimensions and tracks how management and analyst tone shift quarter to quarter. Developed for a Chicago Booth investment competition (team backtest: 29.94% vs. SPY 18.01%, Sharpe 1.77). | Claude plugin + rubric, Python, Excel |
| [**Venture Portfolio Exit Valuation**](vc-exit-valuation/) | Replaces a hardcoded exit multiple with a comparables-driven, probability-weighted exit value, ownership-adjusted MOIC, PV and follow-on reserves for a 42-company venture portfolio. Built at Cedars-Sinai Technology Ventures; published here on synthetic data. | Excel, Python |

## How the work is put together

- **Method first.** Each project documents its rubric or methodology before the numbers, so a reviewer can disagree with an assumption rather than reverse-engineer it.
- **Excel and Python agree.** Both workbooks are formula-driven, and a Python implementation reproduces them exactly. The test suite checks every company, every transcript and every portfolio total against the recalculated workbooks.
- **Data quality is a deliverable.** The scorecard pipeline validates ranges, dates, duplicates and weights, and logs each correction it required. The valuation model keeps every comp's include/exclude decision and reason.
- **Confidentiality respected.** The valuation framework is shown on generated data, and a test fails if any real portfolio identifier appears in the repository.

## Quick start

```bash
git clone https://github.com/ibhartia/investment-analytics-portfolio.git
cd investment-analytics-portfolio
pip install -r requirements.txt

python earnings-call-sentiment/src/scorecard.py
python vc-exit-valuation/src/exit_valuation.py
pytest -q
```

## About me

MS in Finance candidate at the University of Chicago Booth School of Business (graduating December 2026), with a B.Sc. in Economics, Mathematics and Statistics from St. Xavier's College, Mumbai. Prior work spans venture portfolio valuation (Cedars-Sinai Technology Ventures), IPO execution in India's power distribution sector, equity research (Anand Rathi) and financial due diligence (KPMG India).

[ishaanbhartia@gmail.com](mailto:ishaanbhartia@gmail.com)
