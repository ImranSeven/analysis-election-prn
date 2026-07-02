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

### 1. PRN2023 results: `Data/PRN 2023 Negeri Sembilan/*.xlsx` (36 files, one per DUN)
- Official EC scoresheet (Borang SPR 760), sheet **"Main"**.
- Columns (fixed order): `BIL.` | `NO. KOD DAERAH MENGUNDI` | `NAMA PUSAT MENGUNDI` |
  `SALURAN` | `KERTAS UNDI DALAM PETI UNDI (A)` | **[party columns, variable count]** |
  `JUMLAH UNDI` | `UNDI YANG DITOLAK (C)` | `KERTAS UNDI TIDAK DIMASUKKAN KE DALAM PETI UNDI (D)`.
- **Party columns vary by seat** and must be detected **positionally** (between the two
  anchor columns above), not by name — some seats are 2-way (e.g. Chennah: `PN`, `PH`),
  BN seats will show `PN`, `BN`, and 3-corner fights add an **independent labelled by
  candidate name**, not "IND".
- **PH and BN never both appear as separate columns in the same seat** — they're Unity
  Government allies and don't contest against each other. A seat has either a PH
  candidate or a BN candidate, never both.
- First column (`NO. KOD DAERAH MENGUNDI`) is blank on continuation rows (2nd, 3rd...
  saluran of the same station) — needs forward-fill, but done carefully around the
  special rows below.
- Two special non-physical rows per seat: `UNDI POS` (postal — no station/saluran, code
  blank) and `UNDI AWAL 126/01/00` (early voting — has a station/saluran, code ends `/00`).
- A `JUMLAH` (seat total) row appears at the end — this is an aggregate, must be pulled
  out separately, not treated as a stream row.
- Filename pattern: `N01_CHENNAH_PRN_2023_PF.xlsx` → seat_code `N01`, seat_name `Chennah`.

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
  Sarawak` (the last three are negligible/absent in Peninsular NS but worth keeping in
  mind for completeness).
- Key format mismatch to handle at join time: `dm` in this file is
  `"126/01/01 Kampong Sungai Buloh"` (code first) vs the xlsx's `"KAMPONG SUNGAI BULOH
  126 / 01 / 01"` (name first, different spacing) — **join on the extracted numeric code
  (`126/01/01`) + saluran, never on the station name string** (station names are
  abbreviated differently between the two files, e.g. `SK Sungai Buloh` vs `SEKOLAH
  KEBANGSAAN SUNGAI BULOH`).
- Postal/early voters are tagged distinctly in `dm`: postal = `".../UP Undi Pos"`,
  early = `".../00 Undi Awal"` — matches the xlsx's special rows exactly.

### 3. Still needed (not yet in hand)
- **GE2022 stream-level results** for NS (BN/PH/PN votes per parliamentary polling
  station/saluran). This is the main outstanding gap before Part B can start.
- **GE2022-dated roll** with ethnicity — ideally same shape as `nsn_se15_2023.csv`. Need
  to confirm whether it has a `dun` column (see note above) and whether `dm` codes /
  saluran numbering match 2023 or differ (streams can be renumbered between elections —
  must verify, not assume).
- **BN-contested seat list** — deliberately not sourced/applied yet; only needed at the
  filtering step (Part A, step A5), after the full 36-seat pipeline is built.

## Code / pipeline status

### `build_ns_prn2023_long.py` — ✅ written and validated
Parses all 36 PRN2023 xlsx files into one tidy **long-format** table (one row per
seat/station/saluran/party) plus a separate seat-totals table.

- Long format chosen deliberately: seats have different numbers/names of party columns
  (2-way vs 3-way with a named independent), so long format is the only schema that
  stacks cleanly across all 36 without per-seat special-casing downstream.
- Party columns detected positionally between the two fixed anchor column headers.
- `vote_type` column flags `postal` / `early` / `ordinary` — computed **before**
  forward-fill, using the raw (pre-fill) station code text, so postal/early rows are
  never accidentally merged into a neighbouring station's identity.
- Seat-total `JUMLAH` row is excluded from the long table and written to a separate
  totals file for later integrity checks (Part C).
- Outputs: `data/interim/ns_prn2023_results_long.csv`,
  `data/interim/ns_prn2023_seat_totals.csv`.
- **Validated against the one real file we have (N01 Chennah)**: postal (93 valid) and
  early (29 valid) votes parsed correctly, forward-fill correctly scoped per station,
  vote shares sum to exactly 1.0 per saluran, zero duplicate rows, zero null votes.
- **Not yet run against the full 36-file folder** — user needs to run this locally and
  confirm: exactly 36 seats parsed, 0 duplicates, 0 `[ERROR]` lines, and eyeball the
  printed party-column list per seat for anything unexpected.

### Next script to write: aggregate `nsn_se15_2023.csv` into ethnic composition per saluran
Not yet started. Plan:
1. Group by `(dun, dm, pm, saluran)`, count by `ethnicity`.
2. Pivot to `pct_malay, pct_chinese, pct_indian, pct_other` (fractions summing to ~1).
3. Extract clean `dm_code` from `dm` using the same regex approach as the results parser.
4. Keep `n_registered` per stream (useful as a weight later).
5. Assert ethnic shares sum to 1.0 (±0.02); flag violators.

## Current status (update this section as you go)

**Part A (PRN2023):**
- A1 Confirm inputs — ✅
- A2 Ingest 36 scoresheets → long table — ✅ script written & spot-validated; ⬜ user to run on full 36-file folder and confirm clean
- A3 Aggregate roll → ethnic composition per saluran — ⬜ **next step**
- A4 Merge results + ethnic composition — ⬜
- A5 Apply BN seat filter — ⬜ (deliberately deferred)
- A6 Validation harness (reproduce paper's DAP NS numbers) — ⬜
- A7 Regression engine — ⬜
- A8 PRN2023-side output table — ⬜

**Part B (GE2022):** not started — blocked on sourcing GE2022 results + roll files.

**Part C (combine):** not started — blocked on A and B.

## Open questions / things to confirm before proceeding
- Does the GE2022 roll (once obtained) carry a `dun` field the same way the 2023 roll
  does? If yes, skip sourcing a separate polling-district → DUN delineation file.
- Did `dm` codes / saluran numbering change between GE2022 and PRN2023? Must check
  empirically once the GE2022 files are in hand — do not assume stability.
- Confirm party-column detection holds up across all 36 files, especially any seat with
  an independent candidate (column will be a candidate name, not "IND" — may need a
  name→party mapping later using Appendix-1-style candidate lists for narrative writeup).
