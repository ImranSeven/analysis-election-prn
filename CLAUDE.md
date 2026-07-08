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
- **Postal and early votes are excluded** from the granular ethnic regression — the
  paper explicitly drops these, but the reason differs by type (verified empirically
  against `nsn_se15_2023.csv`, 2026-07-04):
  - **Postal votes** truly have no physical stream — `dm` is a special
    `".../UP Undi Pos"` code with no room/saluran tied to a real ballot box.
  - **Early votes** *do* get a real `saluran` and physical `dm` location (e.g.
    `"126/01/00 Undi Awal"` at `"Khemah A IPD Jelebu"`), so "no physical stream" is
    **not** the reason for these. The actual reason: early-voting streams are **not
    age-sorted** the way ordinary streams are. At an ordinary station, average birth
    year climbs cleanly from stream 1 (oldest) to the last stream (youngest) — the
    mechanism the whole method depends on. At an early-voting location, average birth
    year bounces around with no ordering, because early voting is reserved for a
    specific occupational group (police/military/election-day duty staff — every early
    voter checked was born 1991–2001, a narrow young band, not a spread across ages).
    An early-voting stream's ethnic composition reflects "which unit got posted there,"
    not "which age cohort of local residents this is" — mixing it into the same
    regression as ordinary streams would contaminate the age/ethnicity relationship the
    method relies on. (Also checked: early-voting locations don't mix multiple state
    seats' voters together either — each of 30 sampled locations served exactly one
    DUN — so that's not an additional confound here, just the age-sorting one.)
  - Early votes are a small but non-trivial share of the roll (~3.0%, 26,079 of 864,425
    NS voters in the 2023 roll) — excluding them is a minor loss of coverage, not a
    major one.
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
- **`DUN`/`dun` format mismatch — ✅ FIXED (2026-07-04)**. Originally, results files
  used `"N01 CHENNAH"` style (no period, all-caps) while roll files used
  `"N.01 Chennah"` style (period, title-case) — raw text equality wouldn't join.
  Imran ran `script.py` (repo root; `normalize_dun`/`normalize_parlimen` functions)
  against **both roll files** (`nsn_se15_2023.csv` and `ge15_2022.csv`, in place,
  overwriting the originals) to strip the period and uppercase `dun` (e.g.
  `"N.01 Chennah"` → `"N01 CHENNAH"`), and uppercase-only `parlimen` (e.g.
  `"P.126 Jelebu"` → `"P.126 JELEBU"`, dot kept). Verified after the fix:
  - `nsn_se15_2023.csv` `dun` values now exactly match `ns_prn2023_results.csv` `DUN`
    values (36/36, no set difference) once the results side is `.strip()`'d.
  - The re-filtered NS slice of `ge15_2022.csv` `dun`/`parlimen` now exactly match
    `ns_ge2022_results.csv` `DUN`/`PARLIMEN` (36/36 and 8/8) once the results side is
    `.strip()`'d.
  - Row counts are unchanged post-normalization (864,426 for the 2023 roll; 850,865 for
    the NS slice of the GE2022 roll) — confirms no rows were dropped or duplicated.
  - **Remaining work**: the results files themselves still have stray trailing
    whitespace on some `DUN`/`PARLIMEN` values (see below) — a plain `.strip()` on the
    results side at ingestion/join time is now the *only* normalization needed (no more
    period-removal or case-folding required, since the roll side already matches).
- **Stray trailing whitespace in results files — mostly ✅ FIXED (2026-07-04)**.
  - `ns_prn2023_results.csv`: **fully fixed** — `DUN` and `PARLIMEN` now have zero
    whitespace-only variants (verified: 36 unique `DUN`, 8 unique `PARLIMEN`, no
    leading/trailing whitespace on any value).
  - `ns_ge2022_results.csv`: `PARLIMEN` is fixed (`'P.129 KUALA PILAH '` → clean, 8
    unique values, no whitespace). **`DUN` still has one straggler**: `'N04 KLAWANG '`
    (1 row) still coexists with the correctly-spaced `'N04 KLAWANG'` (25 rows) — unique
    `DUN` count is 37, not 36. A `.strip()` on the results side still fully closes the
    join (verified: stripped `DUN` set matches the roll's `dun` set exactly, 36/36), so
    this is no longer a blocker, but worth a final cleanup pass on that one row if a
    fully-clean source file is wanted.
- **`NO8 BAHAU` typo in `ns_ge2022_results.csv` — ✅ FIXED (2026-07-04)**. Previously 45
  of 46 Bahau-seat rows were mislabelled `'NO8 BAHAU'` (letter O); confirmed now all 46
  rows correctly read `'N08 BAHAU'`, and the file's unique `DUN` count dropped from 38
  to 37 (36 clean seats + the still-outstanding `'N04 KLAWANG '` whitespace duplicate).
- **Drifting station code — ✅ FIXED (2026-07-08)**. The third segment of
  `NO. KOD DAERAH MENGUNDI` (e.g. the `01` in `126/03/01`) is supposed to identify one
  physical polling station and stay fixed across all of that station's `SALURAN` rows.
  It originally didn't: for 345 of 448 stations (77%), across every NS DUN except
  Chennah, the code **climbed by 1 with each saluran row** instead of staying constant
  (e.g. `"LUI TIMUR 126/03/02"` at saluran 1 through `"LUI TIMUR 126/03/06"` at
  saluran 5) — consistent with a spreadsheet drag-fill error at some point in
  compiling the file, since the pattern wasn't a fixable formula (tested
  `code = station's list position + saluran - 1`, which explained 88% of rows in one
  DUN but only 7% in another). This made the `(dun, dm_code, saluran)` join produce
  ~2,700 mismatched/duplicated rows instead of a clean 1-to-1 match. Imran fixed the
  source file directly; verified after the fix: **0 of 386 stations** now have a
  drifting code, and the file's unique stream-key set now matches the roll's 1,405
  streams exactly (zero set difference either direction).
- **Multiple "meja" (ballot box) rows per stream — confirmed real, not an error.**
  After the drifting-code fix, 224 of the 1,405 streams still had 2+ rows sharing the
  same `(DUN, dm_code, saluran)` — but with genuinely different vote counts, not
  duplicate data. Example: `N05 SERTING`'s `127/05/03` saluran 1 has two rows
  (valid votes 281 and 255). This is a large stream split across multiple physical
  ballot boxes at the same station/saluran — confirmed by checking the roll's
  registered-voter count for that stream (800) against the *summed* valid votes
  (281+255=536, a plausible ~67% turnout), whereas either row alone would imply an
  implausibly low turnout. **Fix: sum the numeric vote columns across duplicate
  `(DUN, dm_code, saluran)` rows before melting/joining.** Verified this collapses
  1,711 ordinary rows to exactly 1,405 — matching `stream_ethnic` 1-to-1 — with sane
  turnout everywhere (mean 66%, max 88%, zero rows over 100%).
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
  NS DUNs are present. **Format note**: originally `"N.01 Chennah"` style; as of
  2026-07-04 this file has been normalized in place via `script.py` to
  `"N01 CHENNAH"` style (matching the results files' `DUN` column — see the join-fix
  note in the PRN2023 results section above). Likewise `parlimen` is now
  `"P.126 JELEBU"` style (uppercased, dot kept). This is very useful for GE2022 later:
  the GE2022-era roll also has a `dun` column (see below), so we don't need a separate
  polling-district → state-seat delineation file at all.
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
  — most of them (join normalization, code spacing) apply equally here. The
  `'NO8 BAHAU'` typo (now fixed) and PARLIMEN-only postal rows are specific to this
  file.

### 4. GE2022 roll: `ge15_2022.csv` — **NEW, now in hand, national file**
2.7GB, all of Malaysia, same schema as `nsn_se15_2023.csv`
(`uid, birth_year, sex, ethnicity, state, parlimen, dun, dm_vr, dm, pm, saluran`).
**Must be filtered to `state == "Negeri Sembilan"` before use** — do not load the full
file into memory. Filtering with `grep ",Negeri Sembilan," ge15_2022.csv` gives
**850,865 NS rows** (verified), a similar order of magnitude to the 864,426-row 2023
roll.
- Confirms the open question below: **yes**, this roll has a `dun` column resolving
  every voter to their NS state seat, all 36 NS seats present — **no separate
  polling-district → DUN delineation file is needed** for GE2022 either.
- **Format note**: originally `"N.01 Chennah"` style (period + title case), same as the
  2023 roll; as of 2026-07-04 this file has been normalized in place via `script.py`
  to `"N01 CHENNAH"` style (matching `ns_ge2022_results.csv`'s `DUN` column) and
  `parlimen` to `"P.126 JELEBU"` style. Re-filtering the normalized file for
  `state == "Negeri Sembilan"` still gives 850,865 rows (unchanged), and the resulting
  `dun`/`parlimen` sets now match `ns_ge2022_results.csv`'s `DUN`/`PARLIMEN` exactly
  (36/36 and 8/8) once the results side is `.strip()`'d.
- `dm` / `dm_vr` / postal / early-vote tagging conventions are identical in style to
  the 2023 roll (unspaced `"126/01/01 Kampong Sungai Buloh"` code-first format,
  `".../UP Undi Pos"`, `".../00 Undi Awal"`) — these columns were not touched by the
  normalization script.
- Still open: whether the **numeric stream (`saluran`) assignments** for a given
  station are stable between GE2022 and PRN2023 — this needs an empirical per-seat
  check at modeling time, not just a structural read (see open questions below).

### 5. BN-contested seat list — deliberately not sourced/applied yet
Only needed at the filtering step (Part A, step A5), after the full 36-seat pipeline is
built.

## Code / pipeline status

### `script.py` (repo root) — ✅ run, normalizes roll `dun`/`parlimen` in place
One-off normalization script (`normalize_dun`/`normalize_parlimen` functions,
`INPUT_PATH` hardcoded at the top and edited per run). Run against both
`Data/nsn_se15_2023.csv` and `Data/ge15_2022.csv` on 2026-07-04, overwriting each file
in place. Converts `dun` from `"N.01 Chennah"` → `"N01 CHENNAH"` and `parlimen` from
`"P.126 Jelebu"` → `"P.126 JELEBU"`, so both roll files now key-match the results
files' `DUN`/`PARLIMEN` columns (modulo the results files' own residual whitespace —
see the PRN2023 results section above). If either roll file needs to be regenerated
from a fresh source export, **re-run this script before doing any join** — the roll
files are not currently normalized at the source, only in our working copies.

### PRN2023 results ingestion — ✅ done, no script needed
`ns_prn2023_results.csv` arrives already combined across all 36 DUNs with fixed
`PN`/`PH`/`BN`/`IND` columns, so `build_ns_prn2023_long.py` (written for the earlier
36-separate-xlsx assumption) is not needed for this file.

### Aggregate `nsn_se15_2023.csv` into ethnic composition per saluran — ✅ done (A3)
Written in `N9_State Election_analysis.ipynb`, runs clean against the full 864,425-row
2023 roll:
1. Drop postal + early voters (`dm` contains `Undi Pos` or `Undi Awal`) — **26,225
   dropped (3.03%)**.
2. Extract a clean `dm_code` from `dm` (e.g. `"126/01/01 Kampong Sungai Buloh"` →
   `"126/01/01"`) via regex; asserted zero extraction failures on the remaining rows.
3. Bucket `ethnicity` into `malay`/`chinese`/`indian`/`other` (Orang Asli, Bumi Sabah,
   Bumi Sarawak, Other → `other`); asserted zero unmapped values.
4. Group by `(dun, dm_code, saluran)`, count by ethnic group, pivot to
   `pct_malay/pct_chinese/pct_indian/pct_other` + `n_registered`.
5. Asserted all rows' four percentages sum to 1.0 within ±0.02 — passed, zero
   violations.
Result: **1,405 distinct polling streams** across the 36 NS seats, each with a clean
ethnic composition. This is the table A4 joins against the melted PRN2023 results.

### Melt PRN2023 results + merge with ethnic composition — ✅ done (A2 melt + A4)
Written in `N9_State Election_analysis.ipynb`, right after the A3 cells:
1. Strip `DUN` whitespace, drop postal/early rows (`NO. KOD DAERAH MENGUNDI` ==
   `UNDI POS` or contains `UNDI AWAL`) — 116 of 1,827 rows dropped.
2. Extract `dm_code` from `NO. KOD DAERAH MENGUNDI` the same way as A3 (regex tolerant
   of the spaced `"NAME 126 / 03 / 01"` format and embedded newlines).
3. **Collapse multi-"meja" rows**: sum `PN`/`PH`/`BN`/`MUDA`/`IND`/`IND.1`/`JUMLAH UNDI`/
   etc. across any rows sharing the same `(DUN, dm_code, saluran)` — see the
   "Multiple meja rows" gotcha above. Asserted this collapses to exactly 1,405 rows,
   matching `stream_ethnic`.
4. Melt `PN`/`PH`/`BN`/`MUDA`/`IND`/`IND.1` into long `party`/`votes` rows, drop
   `votes == 0` (fixed columns use `0` for "didn't contest", not blank/NaN), compute
   `vote_share = votes / valid_votes` (`valid_votes` = `JUMLAH UNDI`, matches the
   paper's "valid votes" denominator convention).
5. Outer-merge with `stream_ethnic` on `(dun, dm_code, saluran)` with `indicator=True`
   and assert zero unmatched rows.
Result: **3,227 rows** (one row per party per stream), all matched cleanly — zero
`left_only`/`right_only` rows. This `merged` table is the base for A6 (validation
against the paper's DAP numbers) and A7 (the regression engine).

## Current status (update this section as you go)

**Part A (PRN2023):**
- A1 Confirm inputs — ✅ done. Structure, join keys, and known data issues (DUN/dun
  format, whitespace, `NO8 BAHAU` typo, drifting station code, multi-meja rows) all
  confirmed and fixed as of 2026-07-08.
- A2 Ingest results into long table — ✅ done, melt written as part of A4 (see pipeline
  status below).
- A3 Aggregate roll → ethnic composition per saluran — ✅ done, see pipeline status
  below for details (1,405 streams, all sanity checks passed).
- A4 Merge results + ethnic composition — ✅ done, see pipeline status below (3,227
  rows, zero unmatched).
- A5 Apply BN seat filter — ⬜ (deliberately deferred, next step)
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
- ~~Does the `DUN`/`dun` format mismatch block the results-to-roll join?~~
  **Resolved: fixed** — `script.py` normalized both roll files' `dun`/`parlimen` in
  place to match the results files' format (2026-07-04). Only a plain `.strip()` on
  the results side is now needed to close the join (see PRN2023 results section).
- ~~Does `ns_ge2022_results.csv` have a Bahau seat typo (`'NO8 BAHAU'`)?~~
  **Resolved: fixed** — all 46 Bahau rows now correctly read `'N08 BAHAU'`.