# Auto Safety Check

Look up vehicle safety complaints before you buy. Search 2.2 million consumer complaints submitted to the National Highway Traffic Safety Administration (NHTSA).

**Live:** https://GreatTombProductions.github.io/auto-safety/

## What This Shows

- **Complaint counts** by make, model, and year
- **Crash, fire, injury, and death reports** — consumer-reported, not verified
- **Component breakdown** — which systems are most complained about
- **Timeline** — when complaints were filed
- **Year comparison** — compare model years side by side

## Data

Source: [NHTSA Office of Defects Investigation](https://www.nhtsa.gov/recalls-complaints/complaints)

- 2.2 million consumer complaints
- ~1,200 makes, ~32,000 make/model/year combinations
- 134,000 crash reports, 55,000 fire reports
- 119,000 injuries, 7,400 deaths reported
- Data updated regularly by NHTSA

## Important

These are **consumer-reported complaints**, not verified defects. Higher-selling vehicles naturally receive more complaints. Crash, fire, injury, and death counts are self-reported by consumers and not independently verified by NHTSA.

This tool is not legal or safety advice. Always check [NHTSA.gov](https://www.nhtsa.gov) for official recall information.

## Refreshing the Data

```bash
# Download latest NHTSA flat file and rebuild
python3 pipeline/run.py

# Transform only (reuses existing download)
python3 pipeline/run.py --transform
```

Requires: Python 3.10+

## License

MIT
