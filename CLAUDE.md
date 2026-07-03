# CLAUDE.md — NS BN Ethnic-Support Analysis

> Living context file. Keep this updated as work progresses — update the "Current
> status" section and add decisions/gotchas as they come up, so any Claude session
> (or teammate) can pick this up cold.

## Project goal

Reproduce **Table 5** from Ong Kian Ming's ISEAS paper *"Scrutinizing the DAP's
Success in the 2023 Malaysian State Elections"* (TRS8/24, April 2024) — but for **BN**
instead of DAP, in **Negeri Sembilan (NS)** only.

The paper's Table 5 shows, for DAP-contested seats: average Malay and Chinese support
in GE2022 vs PRN2023, and the change. Our task: build the equivalent table for the NS
seats **BN contested**, using **BN vote share** as the dependent variable, via the same
ecological-regression method described in the paper's Appendix 3.

**Working hypothesis (boss's framing — do NOT pre-filter analysis on this, just test it):**
BN benefited from PH vote transfers (Chinese support should rise sharply) but likely lost
Malay support to PN as a result (Malay support should fall/stagnate). Analyse all BN NS
seats, then see which ones fit this pattern and which don't (and why — as the paper does
for its own outlier seats).

## People / roles
- **Boss**: commissioned the analysis, wants the final Table 5 replica.
- **Thevesh**: provided access to NS polling station/stream data and ethnic breakdowns
  (per saluran) for both PRN2023 and GE2022.
- **Imran (user of this workspace)**: runs the analysis.

## Agreed working order
1. **PRN2023 (state election) fully built and validated FIRST.**
2. **GE2022 (general election baseline) built and validated SECOND**, once PRN2023 is solid.
3. **Combine into the Table 5 replica LAST.**

Do not skip ahead to filtering by the BN seat list until the full 36-seat pipeline is
built and validated (see "Why full 36, not just BN seats" below).

## Why build all 36 NS seats, not just BN-contested ones
- We need DAP's 11 NS seats anyway, to **validate** the pipeline against the paper's
  already-published Table 5/6 numbers before trusting it on BN (which has no ground
  truth to check against).
- The expensive/error-prone part is parsing inconsistent per-seat files and joining to
  the roll — identical work whether you keep 11 rows or 36 at the end. Filter at the
  very end via a `WHERE seat_code IN (...)` style slice, not during ingestion.

## Methodology (from the paper, Appendix 3)

Malaysian polling data is tabulated by **polling stream (saluran)** — each stream is a
separate room/classroom, and **voters are assigned to streams by age** (oldest → stream
1, progressively younger after). This is what enables ecological analysis by age as well
as ethnicity.

**Ethnic tagging**: voter names are used to algorithmically tag each voter's likely
ethnicity (Malay/Chinese/Indian/Other). Aggregating by stream gives the ethnic
composition of each stream.

**Core regression** (per seat, per year): two separate bivariate OLS regressions across
that seat's streams —
```
vote_share = b0 + b1 * pct_malay      → Malay support = predicted value at pct_malay = 1.0 (100%)
vote_share = g0 + g1 * pct_chinese    → Chinese support = predicted value at pct_chinese = 1.0 (100%)
```
Worked example from the paper (Damansara): `y = -0.6982x + 0.9746` → at x=1, y=0.2764 ≈ 26% Malay support for PH.

**Conventions to match the paper:**
- Cap estimates to [0%, 100%]; the paper caps Chinese support at **99%** specifically
  (visible in its Table 6 — many entries read exactly 99.0).
- Only report a group's support if that group is **≥20%** of the seat's registered voters.
- Vote share denominator = **valid votes** (excludes rejected ballots).
- **Postal and early votes are excluded** from the granular ethnic regression (can't be
  tied to a physical stream/composition) — the paper explicitly drops these.
- BN-transfer metric (secondary, not core): `x / (|x| + |y|)` where x, y are two
  contestants' percentage-point vote share changes.

## Data files — confirmed formats

### 1. PRN2023 results: `ns_prn2023_results.csv` — **UPDATED, supersedes earlier assumption**

> **Correction log:** originally assumed this would arrive as 36 separate per-DUN xlsx
> files (`Data/PRN 2023 Negeri Sembilan/*.xlsx`) with variable, positionally-detected
> party columns. The actual working file is a **single already-combined CSV across all
> 36 DUNs**, and the party columns are **fixed**, not variable. `build_ns_prn2023_long.py`
> was written against the old (wrong) assumption and **needs to be rewritten** — see
> "Code / pipeline status" below.

Confirmed columns (from a real sample, header + 3 rows for N.01 Chennah):
```
DUN | NO. KOD DAERAH MENGUNDI | NAMA PUSAT MENGUNDI | SALURAN | KERTAS UNDI DALAM PETI UNDI (A) | PN | PH | BN | IND | JUMLAH UNDI | UNDI YANG DITOLAK (C) | KERTAS UNDI TIDAK DIMASUKKAN KE DALAM PETI UNDI (D)
```

Key differences from the earlier assumption:
- **Party columns are fixed for every seat**: `PN`, `PH`, `BN`, `IND` always exist as
  columns, with **blank/empty cells** for whichever parties didn't contest that
  particular seat (e.g. Chennah has values in `PN`/`PH`, blank `BN`/`IND`). No need for
  positional anchor-column detection anymore — just melt these 4 named columns and drop
  rows where the value is blank/NaN.
- **`IND` is a generic column**, not a candidate-name column as we'd guessed from the
  single-seat xlsx. (Still worth a name→party lookup later if a seat ever has more than
  one independent — flag if that ever shows up.)
- Confirms **PH and BN never both have values in the same row** — consistent with the
  Unity Government not contesting against each other.
- **`DUN` column format does NOT match the roll file's `dun` column** — CORRECTION to
  the original assumption below. Verified directly against both files:
  - Results files (`ns_prn2023_results.csv` and `ns_ge2022_results.csv`) use
    `"N01 CHENNAH"` style — no period after the seat letter/number, all-caps name.
  - Roll files (`nsn_se15_2023.csv` and `ge15_2022.csv`) use `"N.01 Chennah"` style —
    period after the seat number, title-case name.
  - The join must **normalize both sides** (strip periods, case-fold, strip whitespace)
    rather than key on raw text equality.
  - Also found **stray trailing whitespace** in some `DUN` values in the results files,
    e.g. `'N04 KLAWANG '` and `'N07 JERAM PADANG '` (PRN2023) — `.strip()` both sides as
    part of normalization, not just case/period folding.
  - `ns_ge2022_results.csv` additionally has a **typo**: 45 of 46 rows for the Bahau
    seat are labelled `'NO8 BAHAU'` (letter O, not zero) instead of `'N08 BAHAU'` (only
    1 row is spelled correctly). Must special-case this fix before grouping by seat.
- **A `PARLIMEN` column is also present** in both results files (not previously
  documented) — NS's 36 state seats sit inside 8 parliamentary seats: P.126 Jelebu,
  P.127 Jempol, P.128 Seremban, P.129 Kuala Pilah, P.130 Rasah, P.131 Rembau,
  P.132 Port Dickson, P.133 Tampin. Not needed for the seat-level regression but useful
  context (e.g., GE2022 postal votes are only resolved to this level — see below).
- **There are two `IND` columns** in both results files (`IND` and `IND` again, which
  pandas auto-suffixes to `IND.1` on load) — this is the "more than one independent"
  case flagged as an open question, now **confirmed to occur**: in
  `ns_prn2023_results.csv`, **N10 Nilai and N13 Sikamat both have two simultaneous
  independents** (both IND columns nonzero in the same row). `MUDA` is also a fixed
  column in the PRN2023 file, used only in N12 Temiang (matches the paper's mention of
  a MUDA candidate there). In `ns_ge2022_results.csv`, the second `IND.1` column is
  always zero — no GE2022 NS seat had two independents.
- **Confirmed: no `JUMLAH` (seat-total) row** in either results file — checked
  explicitly, none found. (Resolves the open question below for both years.)
- Polling-station code spacing differs by file: PRN2023 uses spaced style
  (`"KAMPONG SUNGAI BULOH 126 / 01 / 01"`), GE2022 uses unspaced style
  (`"KAMPONG SUNGAI BULOH 126/01/01"`). Regex extraction should tolerate optional
  whitespace around slashes for both years.
- **GE2022 postal votes are only resolved to the `PARLIMEN` level, not to a specific
  `DUN`** — the 8 `UNDI POS` rows in `ns_ge2022_results.csv` (one per parliamentary
  seat) have a blank `DUN`. This differs from PRN2023, where postal-vote rows do carry
  a `DUN`. Doesn't block the core regression (paper excludes postal/early votes from it
  anyway), but means GE2022 postal turnout can't be validated at the state-seat level
  from the results side alone.
- **`NO. KOD DAERAH MENGUNDI` may contain an embedded newline inside a quoted CSV cell**
  for ordinary station rows, e.g. `"KAMPONG SUNGAI BULOH\n126 / 01 / 01"` (name on one
  line, code on the next) — different from the single xlsx we inspected earlier, which
  had it as one line with a space (`"KAMPONG SUNGAI BULOH 126 / 01 / 01"`). Regex
  extraction of the code should still work since `\s` matches newlines too, but the
  "name" portion (text before the code) needs `.strip()`/newline-stripping, and don't
  assume single-line text when doing any manual eyeballing.
- Postal (`UNDI POS`) and early (`UNDI AWAL 126 / 01 / 00`) rows keep their old shape:
  `UNDI POS` has no station/saluran/code at all; `UNDI AWAL ...` has the code on the same
  line, no embedded newline.
- Still need to confirm: is there a `JUMLAH` (seat total) row per DUN in this combined
  file, same as before? Check when the full file is loaded.

### 2. Ethnic roll: `nsn_se15_2023.csv` (one file, all 36 NS DUNs, ~864k voter rows)
- Voter-level microdata. Columns: `uid, birth_year, sex, ethnicity, state, parlimen,
  dun, dm_vr, dm, pm, saluran`.
- **Confirmed this is the 2023 electoral roll** (used for PRN2023): Chennah's voter
  count in this file (14,554) exactly matches the scoresheet's printed `JUMLAH PEMILIH:
  14,554`. `dm`/`pm`/`saluran` values line up 1:1 with the xlsx scoresheet.
- `dun` field already resolves each voter to their **state seat** directly — e.g. all 36
  NS DUNs are present as `"N.01 Chennah"`, `"N.02 Pertang"`, etc. This is very useful for
  GE2022 later: if the GE2022-era roll also has a `dun` column, we may not need a
  separate polling-district → state-seat delineation file at all.
- `ethnicity` values seen: `Malay, Chinese, Indian, Other, Orang Asli, Bumi Sabah, Bumi
  Sarawak`. CORRECTION: Bumi Sabah/Bumi Sarawak are **not absent** in NS, just small —
  confirmed present in both the 2023 and GE2022 NS rolls (a few hundred to a few
  thousand voters each, well under 1% of NS voters). Bucket these into the paper's
  "Other" category when aggregating.
- **`dm` vs `dm_vr` distinction confirmed**: `dm_vr` is the voter's home/residence
  polling district and stays a normal station code even for postal/early voters; `dm`
  is where the vote is actually cast/tabulated, and shows the special
  `".../UP Undi Pos"` or `".../00 Undi Awal"` codes for postal/early voters. This
  is why postal/early voters can't be assigned a stream-level ethnic composition even
  though we know their home precinct via `dm_vr` — `dm_vr` isn't the room they voted
  in, so it carries no ballot-stream link.
- Key format mismatch to handle at join time: `dm` in this file is
  `"126/01/01 Kampong Sungai Buloh"` (code first) vs the xlsx's `"KAMPONG SUNGAI BULOH
  126 / 01 / 01"` (name first, different spacing) — **join on the extracted numeric code
  (`126/01/01`) + saluran, never on the station name string** (station names are
  abbreviated differently between the two files, e.g. `SK Sungai Buloh` vs `SEKOLAH
  KEBANGSAAN SUNGAI BULOH`).
- Postal/early voters are tagged distinctly in `dm`: postal = `".../UP Undi Pos"`,
  early = `".../00 Undi Awal"` — matches the xlsx's special rows exactly.

### 3. GE2022 results: `ns_ge2022_results.csv` — **NEW, now in hand**
1,669 rows, same "one combined CSV, fixed party columns" shape as the PRN2023 results
file (confirmed fresh, not assumed). Columns:
```
PARLIMEN | DUN | NO. KOD DAERAH MENGUNDI | NAMA PUSAT MENGUNDI | SALURAN | KERTAS UNDI
DALAM PETI UNDI (A) | BN | PH | PN | PEJUANG | WARISAN | PSM | IND | IND | JUMLAH UNDI |
UNDI YANG DITOLAK (C) | KERTAS UNDI TIDAK DIMASUKKAN KE DALAM PETI UNDI (D)
```
- Party columns are the national GE2022 set (`PEJUANG`, `WARISAN`, `PSM` included even
  though they're marginal/absent in most NS seats) — melt all of them, drop
  blank/zero, same approach as PRN2023.
- See the DUN-format, typo, and postal-vote gotchas noted above in the PRN2023 section
  — most of them (join normalization, code spacing) apply equally here, and the
  `'NO8 BAHAU'` typo and PARLIMEN-only postal rows are specific to this file.

### 4. GE2022 roll: `ge15_2022.csv` — **NEW, now in hand, national file**
2.7GB, all of Malaysia, same schema as `nsn_se15_2023.csv`
(`uid, birth_year, sex, ethnicity, state, parlimen, dun, dm_vr, dm, pm, saluran`).
**Must be filtered to `state == "Negeri Sembilan"` before use** — do not load the full
file into memory. Filtering with `grep ",Negeri Sembilan," ge15_2022.csv` gives
**850,865 NS rows** (verified), a similar order of magnitude to the 864,426-row 2023
roll.
- Confirms the open question below: **yes**, this roll has a `dun` column resolving
  every voter to their NS state seat (`"N.01 Chennah"` style, period + title case,
  all 36 NS seats present) — **no separate polling-district → DUN delineation file is
  needed** for GE2022 either.
- `dm` / `dm_vr` / postal / early-vote tagging conventions are identical in style to
  the 2023 roll (unspaced `"126/01/01 Kampong Sungai Buloh"` code-first format,
  `".../UP Undi Pos"`, `".../00 Undi Awal"`).
- Still open: whether the **numeric stream (`saluran`) assignments** for a given
  station are stable between GE2022 and PRN2023 — this needs an empirical per-seat
  check at modeling time, not just a structural read (see open questions below).

### 5. BN-contested seat list — deliberately not sourced/applied yet
Only needed at the filtering step (Part A, step A5), after the full 36-seat pipeline is
built.

## Code / pipeline status

### PRN2023 results ingestion — ✅ done, no script needed
`ns_prn2023_results.csv` arrives already combined across all 36 DUNs with fixed
`PN`/`PH`/`BN`/`IND` columns, so `build_ns_prn2023_long.py` (written for the earlier
36-separate-xlsx assumption) is not needed for this file. A2 is complete.

### Next script to write: aggregate `nsn_se15_2023.csv` into ethnic composition per saluran
Not yet started. Plan:
1. Group by `(dun, dm, pm, saluran)`, count by `ethnicity`.
2. Pivot to `pct_malay, pct_chinese, pct_indian, pct_other` (fractions summing to ~1).
3. Extract clean `dm_code` from `dm` using the same regex approach as the results parser.
4. Keep `n_registered` per stream (useful as a weight later).
5. Assert ethnic shares sum to 1.0 (±0.02); flag violators.

## Current status (update this section as you go)

**Part A (PRN2023):**
- A1 Confirm inputs — 🔶 revised: results file is actually one combined
  `ns_prn2023_results.csv` with fixed PN/PH/BN/IND columns, not 36 xlsx files with
  variable columns. Roll file (`nsn_se15_2023.csv`) understanding unchanged.
- A2 Ingest results into long table — ✅ done (file arrives already combined with fixed
  party columns — no ingestion script needed)
- A3 Aggregate roll → ethnic composition per saluran — ⬜ next step after A2 rewrite
- A4 Merge results + ethnic composition — ⬜
- A5 Apply BN seat filter — ⬜ (deliberately deferred)
- A6 Validation harness (reproduce paper's DAP NS numbers) — ⬜
- A7 Regression engine — ⬜
- A8 PRN2023-side output table — ⬜

**Part B (GE2022):** data files now in hand and structurally inspected
(`ns_ge2022_results.csv`, `ge15_2022.csv` filtered to NS). Ingestion/aggregation
scripts not yet written — next actual coding step once Part A is validated.

**Part C (combine):** not started — blocked on A and B.

## Open questions / things to confirm before proceeding
- ~~Does `ns_prn2023_results.csv` include a `JUMLAH` row per DUN?~~ **Resolved: no**,
  checked both results files directly, no such row in either.
- ~~Does any NS seat have more than one independent?~~ **Resolved: yes** — PRN2023 has
  two simultaneous independents in N10 Nilai and N13 Sikamat (both `IND`/`IND.1`
  columns nonzero). GE2022 has none (`IND.1` always zero).
- ~~Does the GE2022 roll carry a `dun` field like the 2023 roll?~~ **Resolved: yes** —
  `ge15_2022.csv` filtered to NS has all 36 state seats in the `dun` column, same style
  as the 2023 roll. No separate delineation file needed.
- ~~Does the GE2022 results file follow the same "one combined CSV" shape?~~
  **Resolved: yes** — `ns_ge2022_results.csv` confirmed, same shape, different (national)
  party column set.
- **Still open**: did `dm` codes / `saluran` numbering change between GE2022 and
  PRN2023 for the same physical station? Both rolls use the same code *format*, but
  whether the *numbering* is stable per station needs an empirical per-seat check once
  Part B ingestion starts — do not assume stability.
- **New from this pass**: confirm the impact of GE2022 postal votes only being
  resolved to `PARLIMEN` (not `DUN`) in the results file — does this affect any
  aggregate turnout figures we plan to report for Part B/C, given the paper's approach
  already excludes postal/early votes from the core regression?