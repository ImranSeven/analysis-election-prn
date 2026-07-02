# NS BN Ethnic-Support Analysis — Consolidated Plan (v2)

Reproduce Table 5 (ISEAS TRS8/24) for the Negeri Sembilan seats **BN contested** in
PRN2023, estimating BN's Malay and Chinese support in GE2022 vs PRN2023 using the same
ecological-regression method as the paper (Appendix 3).

Order of work, as agreed: **PRN2023 fully built and validated first → then GE2022 →
only then combine into the Table 5 replica.**

Status markers: ✅ done · 🔶 in progress · ⬜ not started

---

## PART A — PRN2023 (Negeri Sembilan state election)

### A1. Confirm inputs ✅
- `Data/PRN 2023 Negeri Sembilan/*.xlsx` — one official EC scoresheet per DUN, all 36 seats.
  Sheet "Main": station/saluran-level results, party columns vary by seat (2-way, or
  3-way with an independent labelled by candidate name, not "IND").
- `nsn_se15_2023.csv` — voter-level roll, all 36 NS DUNs, columns
  `uid, birth_year, sex, ethnicity, state, parlimen, dun, dm_vr, dm, pm, saluran`.
  Confirmed this is the **2023 roll**: Chennah's row count (14,554) matches the
  scoresheet's printed `JUMLAH PEMILIH`, and `dm`/`pm`/`saluran` values match the
  scoresheet exactly, including postal (`.../UP Undi Pos`) and early (`.../00 Undi Awal`)
  tagging.
- Not yet in hand: **the BN-contested seat list** — deliberately not applied yet (see A5).

### A2. Ingest all 36 scoresheets into one tidy long table ✅ (script written, validated on 1/36 files — rerun on your full folder)
Script: `build_ns_prn2023_long.py`.
- Long format: one row per (seat, station, saluran, party). Handles 2-way and 3-way
  fights without schema drift.
- Party columns detected **positionally** (between the fixed `KERTAS UNDI DALAM PETI
  UNDI (A)` and `JUMLAH UNDI` anchor columns) — not by name, since independents are
  labelled by candidate name.
- Postal/early rows tagged via `vote_type`, not dropped.
- Seat-total `JUMLAH` row pulled out into a separate totals table for later integrity checks.
- Outputs: `data/interim/ns_prn2023_results_long.csv`, `data/interim/ns_prn2023_seat_totals.csv`.

**Your action:** run this against the real 36-file folder. Check:
- exactly 36 seats parsed, 0 duplicate rows, 0 `[ERROR]` lines
- eyeball the printed party-column list per seat — flag anything unexpected

### A3. Aggregate the roll into ethnic composition per saluran ⬜ (next step)
From `nsn_se15_2023.csv`:
1. Group by `(dun, dm, pm, saluran)` and count voters by `ethnicity`.
2. Pivot to wide: `pct_malay, pct_chinese, pct_indian, pct_other` (fractions, sum ≈ 1).
3. Also keep `n_registered` (total voters in that stream) — useful as a weight later.
4. Extract a clean `dm_code` from `dm` (e.g. `"126/01/01 Kampong Sungai Buloh"` →
   `"126/01/01"`) using the same regex approach as the results parser, so it joins
   cleanly on `dm_code` + `saluran`.
5. Sanity check: ethnic shares sum to 1.0 (±0.02) for every stream; flag violators.

### A4. Merge results (A2) with ethnic composition (A3) ⬜
1. Join on `dm_code` + `saluran` (not on `pm_name`/station name — those strings differ
   in abbreviation between the two files, e.g. `SK Sungai Buloh` vs
   `SEKOLAH KEBANGSAAN SUNGAI BULOH`; the numeric code is the reliable key).
2. Assert: every **ordinary** stream-level result row finds a matching ethnic-composition
   row. Print and investigate any that don't — a silent join failure here corrupts
   everything downstream.
3. Postal (`vote_type == "postal"`) rows have no `dm_code`/station and therefore **can't**
   be joined to ethnic composition — this is expected and matches the paper (postal/early
   votes are excluded from the granular ethnic analysis; keep them aside for turnout/
   total-vote checks only, not for the regression).
4. Compute `vote_share = votes / valid_votes` (fraction) per row.
5. Save: `data/interim/ns_prn2023_streams_full.csv` — one row per
   (seat, station, saluran, party) with vote share + ethnic composition attached.

### A5. Apply the BN seat filter ⬜
Only now — after A2–A4 are built and validated across all 36 seats — load the BN-contested
seat list and slice. Keep the full 36-seat table around; don't discard it, because:

### A6. Validation harness — reproduce the paper's published DAP numbers ⬜
Before trusting the pipeline on BN seats, prove it on seats we can check:
1. Filter the full table (A4) to DAP's 11 NS seats, dependent variable = DAP/PH vote share.
2. Run the regression engine (A7) on them.
3. Compare to the paper: Table 5 NS row (Malay 18%→31%, Chinese 97%→98%); Table 6 NS
   seats (e.g. Chennah 6.8%→31.3% Malay, Bahau 14.7%→36.3%, Repah 9.5%→29.8%).
4. Within ~1–2pp → pipeline is trustworthy. If not, debug here, not after generating
   unverifiable BN numbers.

### A7. Regression engine ⬜
Per seat, per dependent variable (BN vote share for the real analysis, PH for validation):
- Two bivariate OLS regressions across that seat's ordinary streams:
  `share = b0 + b1*pct_malay` → Malay support = predicted value at `pct_malay = 1.0`
  `share = g0 + g1*pct_chinese` → Chinese support = predicted value at `pct_chinese = 1.0`
- Cap estimates to [0, 1] (paper caps Chinese at 0.99).
- Only report a group if it's ≥20% of that seat's voters (paper's threshold).
- Record R², slope, n_streams, and predictor range → flag `low_confidence` if the
  streams don't span a wide enough range to trust the extrapolation to 100%.

### A8. Produce PRN2023-side outputs ⬜
- Per-seat table: BN Malay support %, BN Chinese support % (PRN2023 only — no GE2022
  column yet, that comes in Part B).
- NS-wide average (state both a simple mean and a voter-weighted mean; document which
  you use downstream).
- This is a genuine, presentable intermediate deliverable: "BN's estimated ethnic
  support in PRN2023, NS seats" — useful on its own before GE2022 is added.

---

## PART B — GE2022 (general election baseline)

### B1. Identify and gather the still-missing inputs ⬜
- **GE2022 stream-level results** for NS's parliamentary seats (BN/PH/PN votes per
  polling station/saluran) — not yet in hand. This is the main gap.
- **GE2022 electoral roll with ethnicity**, ideally in the same `uid/ethnicity/parlimen/
  dun/dm/pm/saluran` shape as `nsn_se15_2023.csv`. Check electiondata.my's catalogue
  (or Thevesh directly) for a GE15/2022-dated equivalent file.
- Confirm whether **saluran numbering and `dm` codes changed** between 2022 and 2023 —
  if the same physical station kept the same code/numbering, some of Part A's code
  reuses directly; if not, joins must be re-keyed carefully per election.

### B2. Ingest GE2022 results into the same long format ⬜
Mirror A2's approach: melt into (seat_code, station, saluran, party, votes), keep
postal/early flagged separately. Note the seat_code here will be a **parliamentary**
code (e.g. `P126`), not a DUN code — that's expected, handled in B4.

### B3. Aggregate GE2022 roll into ethnic composition per saluran ⬜
Mirror A3, using the GE2022-dated roll file once obtained.

### B4. Map parliamentary streams to state seats (the hard part) ⬜
Since 2022 only contested Parliament, there's no native state-seat result.
- **Good news given what we found in Part A:** if the roll file already carries a `dun`
  field per voter (as `nsn_se15_2023.csv` does), you may not need a separate
  polling-district → state-seat delineation file at all — the roll itself tells you
  which DUN each stream's voters belong to. Confirm the GE2022 roll has the same `dun`
  column; if so, this step collapses into a simple join, not a separate mapping file.
- If it does NOT have a `dun` field, fall back to sourcing an explicit polling-district
  → DUN delineation table and join on `dm_code`.
- Re-key GE2022 results to `dun`/state-seat codes. Do not sum across streams yet.

### B5. Merge GE2022 results with ethnic composition ⬜
Mirror A4: join on `dm_code` + `saluran`, assert no unmatched rows, compute vote shares.

### B6. Re-run the validation harness on GE2022 ⬜
Same check as A6 but for the 2022 baseline: reproduce the paper's GE2022 columns in
Table 5/6 for DAP's 11 seats before trusting the BN GE2022 numbers.

### B7. Produce GE2022-side outputs ⬜
Same shape as A8 — per-seat and NS-wide BN Malay/Chinese support estimates, GE2022 only.

---

## PART C — Combine into the Table 5 replica

### C1. Join A8 (PRN2023) and B7 (GE2022) outputs on seat_code ⬜
### C2. Compute Δ (PRN2023 − GE2022) per seat, Malay and Chinese ⬜
### C3. Emit Table 5 replica (NS headline row) and Table 6-style per-seat appendix ⬜
### C4. Integrity + narrative checks ⬜
- Reconcile 2023 stream sums against the seat-totals table from A2.
- Check direction: BN Chinese support should rise sharply, Malay support should fall/flat
  (PH lending Chinese votes, Malay votes leaking to PN) — flag seats that don't fit and
  look for a local explanation (candidate, three-corner dynamics), same as the paper does
  for its exceptions.
### C5. Write up caveats ⬜
Ecological-inference limits, parliamentary-vs-state baseline mismatch, ignored
Indian/Other voters in the two separate bivariate regressions, extrapolation confidence
for Malay-majority seats' Chinese estimates.

---

## Where you actually are right now

Part A: **A1–A2 done**, A3 (aggregate the roll into ethnic composition) is the immediate
next step once you confirm A2 ran clean on all 36 files.
