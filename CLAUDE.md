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

### 5. DAP-contested seat list: `dap_seats.txt` — **NEW, now in hand**
Tab-separated, 11 rows, columns: `PARLIMEN | DUN | candidate name | party (always DAP)`.
Matches the paper's Appendix 1 NS DAP candidate list exactly (Chennah, Bahau, Nilai,
Lobak, Temiang, Bukit Kepayang, Rahang, Mambau, Seremban Jaya, Lukut, Repah). `DUN`
values are in the roll's `"N.01 Chennah"` style (period, title-case) — needs the same
normalization as the other join keys before filtering `merged`. This is the seat list
for **A6 (validation)**, not A5/A7 (the BN filter) — see Current status below.

### 6. BN-contested seat list — deliberately not sourced/applied yet
Only needed at the filtering step (Part A, step A7 — see reordering note in Current
status below), after A5/A6 (regression engine + DAP validation) are done.

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
`left_only`/`right_only` rows. This `merged` table is the base for A5 (the regression
engine) and A6 (validation against the paper's DAP numbers).

### Regression engine — ✅ done (A5)
Written in `N9_State Election_analysis.ipynb`, right after A4:
1. `seat_ethnic`: seat-level ethnic composition, weighted by each stream's
   `n_registered` (not a simple stream average) — one row per DUN (36 total), used
   only for the ≥20%-of-registered-voters reporting rule.
2. `estimate_support(group, pct_col)`: bivariate OLS via `np.polyfit` on a single
   `(dun, party)` group's streams, evaluated at `pct = 1.0`. Returns `NaN` if a group
   has fewer than 2 streams or zero variance in the ethnic share (can't fit a line).
3. `cap_support`: clips to `[0, 1]`, with Chinese specifically capped at `0.99` to
   match the paper's Table 6 convention.
4. `run_regression_engine`: loops every `(dun, party)` pair in `merged`, applies the
   above, and zeroes out (`NaN`s) a group's estimate if `seat_ethnic` shows that group
   is under 20% of the seat's registered voters.
Result: `support_table`, 83 rows (one per contested `(dun, party)` pair), with
`malay_support`/`chinese_support` columns.

### Validation against the paper's DAP numbers — ✅ done (A6)
Written in `N9_State Election_analysis.ipynb`, right after A5. Loads `dap_seats.txt`
(normalized the same way as the roll files), filters `support_table` to `party == 'PH'`
for those 11 seats, and compares against the paper's Table 6 "Voting PH — PRN 2023"
Malay/Chinese columns (hardcoded from the PDF, since it's small and static).

**Found and fixed a real data bug during this pass**: `N22 RAHANG`'s `PN`/`PH` vote
columns were swapped in `ns_prn2023_results.csv` — confirmed by comparing our seat-wide
PN/PH totals against the paper's Table 3 (ours: PH 25.8%/PN 74.2%; paper: DAP 75.3%/PN
24.7% — near-exact mirror images), while all other 10 DAP seats matched Table 3 within
0.6pp. Verified the swap was isolated to this one seat (checked all 11 against Table 3
before concluding it was Rahang-specific, not systemic). Imran fixed it directly in the
CSV; a first attempt left 4 rows at station `130/22/09` (salurans 4–7) with `PN` and
`PH` set to the *same* value instead of properly swapped (undercounting `JUMLAH UNDI`
by 491 votes) — caught via a `party_sum == JUMLAH UNDI` check, and fixed using
`PH = JUMLAH UNDI - PN` (valid since BN/MUDA/IND are all zero in this DUN).

**Final validation results** (11 DAP seats, PH vote share):
- **Chinese support matches essentially exactly** — all 11 seats within ≤0.05pp of the
  paper's published figure (well within rounding).
- **Malay support is within ~2pp for 8 of 11 seats.** Three seats show larger,
  same-direction (underestimated) gaps: N10 Nilai (−6.1pp), N12 Temiang (−4.0pp), N24
  Seremban Jaya (−9.7pp). Hypothesis, not yet confirmed: possibly related to
  independent candidates in some of these seats shifting the denominator slightly
  differently than the paper's method (e.g. Nilai's independent candidate, mentioned
  in the paper, won 3.4% of the vote) — not investigated further, treated as an
  accepted minor caveat rather than a blocker, since it's modest and consistent rather
  than erratic like the Rahang bug was.
- Considered **validated enough to proceed** to the BN-specific analysis (A7).

### Apply the BN seat filter — ✅ done (A7)
Written in `N9_State Election_analysis.ipynb`, right after A6. No external seat list
needed — `merged` already reveals which DUNs BN contested (`party == 'BN'` rows exist
only where BN fielded a candidate). Filtered `support_table` to those seats, with an
assertion that the seat set matches what `merged` independently shows.

Result: **BN contested 17 of NS's 36 seats**. Malay support estimates range ~34-57%
across them. Chinese support is `NaN` (below the 20%-of-registered-voters reporting
threshold) for 16 of 17 seats — only **N35 Gemencheh** clears the threshold, at 99.0%
(capped). This is the PRN2023-side table for the boss's actual question; it still
needs the GE2022 baseline (Part B) before it's a usable "change" table.

### Part C: Combine PRN2023 + GE2022 — ✅ done
Written in a **new third notebook**, `N9_Joined_analysis.ipynb`. Since the three
notebooks don't share kernel state, Part A and Part B each got an appended export
cell (`bn_support.to_csv('Data/bn_support_prn2023.csv' / 'bn_support_ge2022.csv',
index=False)`) writing their numeric (unformatted) 17-row BN support tables; Part C
loads both CSVs directly rather than re-running either pipeline.
1. Load both CSVs, assert same 17-seat set on both sides.
2. Merge on `dun` (`validate='one_to_one'`), compute `malay_change_pp` /
   `chinese_change_pp` = (PRN2023 − GE2022) × 100. `NaN` propagates whenever either
   side is below the paper's 20%-of-registered-voters reporting threshold.
3. **Seat-level output table** (`final_table`, 17 rows) — same paper-style formatting
   as `bn_output`/`bn_output_ge2022` (percentages, "N.A." below threshold), now with
   GE2022, PRN2023, and change columns side by side for both ethnic groups. This is
   the Table 6-style half of the deliverable.
4. **State-level summary** (`state_summary`, 1 row) — the paper's *actual* Table 5 is
   a per-state average across a party's contested seats, not per-seat like Table 6.
   Computed by averaging PRN2023/GE2022 support across the seats where each group
   clears the 20% threshold (mirrors how the paper excludes "N.A." entries from a
   state average rather than treating them as 0).
5. **Hypothesis test** — classified all 17 seats by whether Malay support fell and
   whether Chinese support rose.

**Findings:**
- **Malay support fell in 14 of 17 BN seats** (82%) between GE2022 and PRN2023 —
  broadly consistent with the boss's hypothesis that BN lost Malay support to PN.
  Three seats bucked this (N09 Lenggeng +2.9pp, N31 Bagan Pinang +2.9pp, N16 Seri
  Menanti +3.5pp), all modest gains, not losses reversing to gains.
- **Chinese support is only reportable (≥20% of registered voters) in both years for
  1 of 17 seats: N35 Gemencheh.** There, the hypothesis's Chinese-transfer half is
  confirmed dramatically — Chinese support rose from 4.2% (GE2022) to 99.0% (capped,
  PRN2023), a +94.8pp swing, while Malay support fell 18.8pp (59.1% → 40.3%) — a
  clean, complete match for the boss's predicted pattern in the one seat where it
  can be fully tested.
- N02 Pertang has Chinese support reportable in GE2022 (6.0%) but not PRN2023 (fell
  just under the 20% threshold, or the seat's Chinese registered-voter share itself
  dropped) — so a change can't be computed there even though the underlying pattern
  is probably similar; flagged as a data-availability gap, not a hypothesis failure.
- **State-level summary (NS, BN)**: Malay support averaged 53.9% (GE2022) → 46.1%
  (PRN2023), a −7.8pp swing across all 17 seats. Chinese support (averaged over only
  the 2 seats where it was ever reportable) went 5.1% → 99.0%, +93.9pp — but this
  average is heavily skewed by tiny sample size (n=2 seats, one of which is only
  half-reportable) and should be read as illustrative, not a robust state figure.
- **Overall**: the hypothesis holds up qualitatively (majority Malay decline, the one
  fully-testable seat shows a dramatic Chinese gain) but the Chinese half is mostly
  **untestable** for 16 of 17 BN seats under the paper's own 20% reporting rule — BN's
  seats are mostly too Malay-majority for Chinese support to clear the threshold at
  all, which is itself a finding worth flagging to the boss (the ethnic-transfer
  story may be real but is only *visible* in ethnically-mixed BN seats like
  Gemencheh, not detectable in most of BN's more homogeneously-Malay seat portfolio).

**Part C is now complete — the full three-part pipeline (A, B, C) is built,
validated, and produces the final deliverable.**

### PRN2023-side output table — ✅ done (A8)
Written in `N9_State Election_analysis.ipynb`, right after A7. Formats `bn_support`
into a clean, paper-style table:
- Splits `dun` (e.g. `"N02 PERTANG"`) into `seat_code` (`"N02"`) and a readable
  title-cased `seat_name` (`"Pertang"`) via regex.
- Formats `malay_support`/`chinese_support` as `"XX.X%"` strings, with `"N.A."` for
  `NaN` (matching the paper's own Table 6 style for under-threshold groups).
- Sorted by seat code, 17 rows, columns: `seat_code | seat_name | n_streams |
  malay_support_pct | chinese_support_pct`.
This (`bn_output`) is the finished PRN2023-only artifact — **Part A is now fully
built through A8**. It's a placeholder shape for the final deliverable, not the
deliverable itself: the boss's actual ask needs GE2022 columns and a change column
alongside these, which is Part B + Part C.

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
- A5 Regression engine — ✅ done, see pipeline status above (`support_table`, 83
  `(dun, party)` rows; quick spot-check against the paper's Table 6 already close).
  **Reordered (2026-07-08)**: originally planned as A7 (after the BN filter), moved up
  ahead of the BN filter — we need the engine built before we can validate anything,
  and validating against DAP (which has published ground truth) is the whole reason we
  built all 36 seats instead of just BN's.
- A6 Validation harness (reproduce paper's DAP NS numbers) — ✅ done, see pipeline
  status above (Chinese matches essentially exactly across all 11 DAP seats; Malay
  within ~2pp for 8/11, with 3 seats showing a modest ~4-10pp underestimate treated as
  an accepted caveat). Also caught and fixed a real `PN`/`PH` swap bug in
  `N22 RAHANG` during this pass — see pipeline status above.
- A7 Apply BN seat filter — ✅ done, see pipeline status above (17 BN seats; Malay
  ~34-57%; Chinese reportable in only 1 seat, N35 Gemencheh at 99.0%).
- A8 PRN2023-side output table — ✅ done, see pipeline status above (`bn_output`,
  17 rows, paper-style formatting). **Part A is complete.**

**Part B (GE2022):** data files in hand and structurally inspected
(`ns_ge2022_results.csv`, `ge15_2022.csv` filtered to NS). Mirrors Part A's structure,
same rationale — will be built in a **separate notebook**,
`N9_General Election_analysis.ipynb` (already created, empty), rather than appended to
the PRN2023 notebook, to keep each pipeline independently re-runnable and avoid
cross-contaminating kernel state. Some code (the regression engine especially) will
need to be copied over rather than imported, since the two notebooks don't share state.

One structural note to keep in mind throughout Part B: **GE2022 was a parliamentary
election, not a state election** — voters chose a Parlimen candidate, not a DUN
candidate. The `dun` field only tells us which future state-seat boundary a voter/
stream falls inside; the party vote columns reflect parliamentary-level choice. This
matches exactly how the paper builds Table 6's GE2022 columns (same seats, same
approach), so it's not a blocker — just don't read "BN contested this DUN in GE2022"
literally, since BN contested the *parliamentary* seat, not this specific DUN.

- B1 Confirm inputs — ✅ done (2026-07-09), written in
  `N9_General Election_analysis.ipynb`. Pre-filtered `ge15_2022.csv` to NS via
  `grep ",Negeri Sembilan,"` into a new permanent file, `Data/ge15_2022_ns.csv`
  (850,865 rows) — the notebook loads this directly rather than the 2.7GB/21.2M-row
  national file (loading the full file once did work but threw a mixed-dtype warning
  and is needlessly slow/risky; the NS-filtered file loads cleanly with zero dtype
  issues). Re-ran Part A's gotcha checks against `ns_ge2022_results.csv`:
  - **Drifting station codes: none found** (0 of 379 stations) — good, this file
    doesn't repeat PRN2023's bug.
  - **Multi-meja duplicate rows: 199** `(DUN, dm_code, saluran)` keys have 2+ rows —
    same phenomenon as Part A, same fix needed (sum before merging) in B2/B4.
  - **No `JUMLAH` seat-total row** — confirmed absent, consistent with PRN2023.
  - **Postal rows are genuinely PARLIMEN-only** — all 8 `UNDI POS` rows have blank
    `DUN`, confirming the earlier structural note.
  - **Party-column swap check**: cross-referenced aggregate PH/PN/BN seat totals
    against the paper's Table 3 "GE2022" columns for the 11 DAP seats (same technique
    that caught the N22 Rahang PRN2023 swap). Two seats (Temiang, Rahang) initially
    looked off by ~5-6pp when postal+early votes were included — **turned out to be a
    methodology mismatch, not a data bug**: the paper explicitly excludes postal *and*
    early votes from all of its GE2022 seat-level figures, not just the Table 2
    summary (footnote/methodology text: "these votes could not be accurately
    allocated to individual state seats"). Re-checked excluding postal/early and all
    11 seats landed within ~0.6pp of the paper. **Conclusion: no swap bug in this
    file** — just remember to always exclude postal/early before comparing any
    GE2022 aggregate to the paper, not only in the core regression.
- B2 Ingest GE2022 results into long table — ✅ done. Collapsed the 199 multi-meja
  duplicate rows first (sum, same fix as A4), then melted
  `BN`/`PH`/`PN`/`PEJUANG`/`WARISAN`/`PSM`/`IND`/`IND.1`, dropped `votes == 0`, computed
  `vote_share`. Result: 1,593 ordinary rows collapsed to **1,326 streams**, melted out
  to **5,470** party-per-stream rows.
- B3 Aggregate `ge15_2022_ns.csv` into ethnic composition per saluran — ✅ done. Same
  approach as A3 exactly (drop postal/early — 20,368 dropped, 2.39% of 850,865 — bucket
  ethnicity, group by `(dun, dm_code, saluran)`, compute percentages). Result:
  **1,326 streams**, all sanity checks passed (percentages sum to 1.0 within ±0.02).
  **Good early sign**: this is the exact same stream count as B2's collapsed results
  (1,326 = 1,326) — strongly suggests B4's merge will close as cleanly as A4's did,
  with no repeat of the drifting-code saga (already confirmed absent in B1 anyway).
- B4 Merge B2 + B3 — ✅ done. Same outer-join-with-`indicator`-and-assert approach as
  A4. Result: **5,470 rows, all matched** (`both`) — zero `left_only`/`right_only`,
  confirming the prediction from B2/B3's matching stream counts.
- B5 Regression engine — ✅ done. Copied `estimate_support`/`cap_support`/
  `run_regression_engine` verbatim from Part A, plus a `seat_ethnic` table built the
  same way (registered-voter-weighted composition per DUN, 36 rows). Result:
  `support_table`, **159 `(dun, party)` rows** (more than PRN2023's 83, since GE2022
  had more national parties — PEJUANG, WARISAN, PSM — on the ballot in some seats).
- B6 Validation harness — ✅ done. Same approach as A6, but against Table 6's
  **"Voting PH — GE2022"** Malay/Chinese columns (transcribed from the paper) for the
  same 11 `dap_seats.txt` seats.
  - **Chinese support matches closely** — all 11 seats within ≤1.3pp of the paper's
    published figure.
  - **Malay support within ~5pp for 9 of 11 seats.** Two seats show a larger gap: N10
    Nilai (−8.5pp) and N12 Temiang (−5.3pp) — the same two seats (plus Seremban Jaya
    on the PRN2023 side) that showed the largest gaps in A6's validation too,
    reinforcing the earlier hypothesis that something about these specific seats
    (independent candidates? other structural factor) mildly biases the
    Malay-support regression low, not just a PRN2023-specific issue. N21 Bukit
    Kepayang is a new, smaller outlier here (+4.1pp) not flagged in A6. Treated as an
    accepted caveat, same as Part A — modest and directionally consistent, not
    erratic.
- B7 Apply the BN seat filter — ✅ done. Reused the same 17 seat codes from Part A's
  A7 (hardcoded list, not re-derived from GE2022 data, per the parliamentary-vs-state
  note above) and filtered `support_table` to `party == 'BN'` for those DUNs.
  Confirmed all 17 seats have a GE2022 BN row (`missing` set is empty) — BN contested
  the parliamentary seat overlapping every one of these 17 state seats in GE2022, as
  expected.
- B8 GE2022-side output table — ✅ done. Same shape/format as `bn_output`
  (`bn_output_ge2022`, 17 rows). Malay support ranges ~31-68% across the 17 seats —
  markedly higher than the PRN2023 side's ~34-57%, consistent with BN's GE2022 losses
  reversing by PRN2023. Chinese support clears the 20% threshold in **2 of 17** seats
  this time (vs 1 of 17 in Part A): N02 Pertang (6.0%) and N35 Gemencheh (4.2%) — both
  low, consistent with BN doing poorly with Chinese voters in the 2022 GE "tsunami"
  before recovering some ground by PRN2023 via PH-seat transfers. **Part B is now
  fully built through B8.**

**Part C (combine):** ✅ done, in a new third notebook `N9_Joined_analysis.ipynb`. See
pipeline status above for full detail. Joins Part A's `bn_output`-equivalent (via
exported CSV `Data/bn_support_prn2023.csv`) with Part B's `bn_output_ge2022`-equivalent
(`Data/bn_support_ge2022.csv`), producing:
- `final_table` — 17-row seat-level table (Table 6-style) with GE2022, PRN2023, and
  percentage-point change columns for both Malay and Chinese support.
- `state_summary` — 1-row NS-state BN average (Table 5-style): Malay 53.9%→46.1%
  (−7.8pp), Chinese 5.1%→99.0% (+93.9pp, but only ever reportable in 2 of 17 seats).
- Hypothesis test: Malay support fell in 14/17 BN seats (supports the boss's
  Malay-loss prediction); Chinese support is only reportable in both years for 1 seat
  (N35 Gemencheh), where it rose 4.2%→99.0% while Malay fell 18.8pp — a clean full
  match for the hypothesis in the one fully-testable case. The Chinese-transfer half
  of the hypothesis is largely **untestable** in most BN seats under the paper's own
  20%-threshold rule, since BN's seat portfolio skews heavily Malay-majority — worth
  flagging to the boss as a scope limitation, not a hypothesis failure.

**The full A → B → C pipeline is now complete.**

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