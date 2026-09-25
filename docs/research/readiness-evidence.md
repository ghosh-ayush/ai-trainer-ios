# Readiness evidence: HRV, resting heart rate and sleep as triggers for a lighter-session proposal

Date: 2026-09-24

## Scope

Question: the app returns `unassessed` for recovery and readiness because no cited policy exists.
Can a research-backed rule propose a lighter session, or keeping the plan, from overnight HRV,
resting heart rate (RHR) and sleep read from HealthKit? Whatever the answer, such a rule could only
ever emit a `Recommendation` that the athlete accepts. It could never write a `SetLog`, stand in for
logged effort, or change a plan by itself (AGENTS.md rules 2–4).

- **Format and grading** follow `training-frequency-evidence.md`. No source key from that file is
  reused here, because none of its sources addresses readiness.
- **Qualifying sources only.** Every source below is a peer-reviewed human study or official
  consensus statement with a DOI or PMID and one of the qualifying designs (position stand or
  consensus statement, guideline, meta-analysis, systematic review, randomised, crossover or
  non-randomised trial, cohort or cross-sectional study, narrative review). No preprint, vendor page
  (Apple, WHOOP, Oura, Garmin, Polar, Bevel, HRV4Training), video, blog or AI text is cited. Where a
  paper itself leans on a vendor document, I say so and do not rely on that part.
- **Certainty** is my own appraisal on the repository scale:
  - **High:** two or more independent syntheses agree, the pooled sample is large (>1,000) and most
    studies are randomised.
  - **Moderate:** at least one meta-analysis or systematic review agrees, but it has few studies
    (<15), a narrow population or some inconsistency.
  - **Low:** one small synthesis, a narrative review, panel opinion, a single trial, an
    observational or validation study, or a claim I could verify only at abstract level.

  Only a synthesis (meta-analysis, systematic or umbrella review, position stand, guideline) can be
  graded above Low. A single RCT, crossover trial, cohort, validation study or narrative review is
  Low at most. A statement its authors call expert consensus counts as panel opinion and is Low.
- **Identifiers and retractions.** Every PMID below was fetched from PubMed on 2026-09-24 and its
  record checked for publication type. I then searched PubMed for all cited PMIDs restricted to
  publication type "Retracted Publication", in batches of 16, with a known retracted paper (PMID
  31188644) as a positive control; the control was returned and no cited paper was. A search for
  "Expression of Concern" notices on HRV, sleep-loss and wearable topics returned one notice, about an
  unrelated PPG arrhythmia paper. DOIs are those in the PubMed records. I did not resolve each DOI
  separately; the independent verification (end of file) resolved all 43 at doi.org and matched
  each to its PubMed record.
- **What I read.** "Full text" means I read the PMC full text returned by the PubMed tool (tables
  arrive flattened, and figures are not visible). "Abstract only" means exactly that. Europe PMC
  (queried with PMIDs only) flags none of the abstract-only papers below as open access. Two
  publisher pages (Taylor & Francis for DEOLIVEIRA19; AHA for the 1996 HRV Task Force guideline)
  refused access (HTTP 403).
- **Locators** are section names, table numbers or "Abstract". A number I could not see in text I
  opened is marked **unverified**.
- **Quotations.** None. Every row is a paraphrase with exact numbers.
- **"Owner decision"** means the literature gives no number. The rationale is then built only from
  findings cited here.
- **Personal data.** No name, email or other personal data was sent to any site or API. No
  Unpaywall or Crossref "mailto" parameter was used.
- **Population caveat.** Almost all HRV-guided training trials are endurance trials. The three
  resistance-type trials together randomised 96 people (20 + 21 + 55). The two that report their
  length trained for 6–7 weeks; DEOLIVEIRA19's length is not in its abstract.

## Summary

1. **No synthesis has tested HRV-guided resistance training.** Three small RCTs (young men, older
   women, recreationally active adults doing high-intensity functional training) found HRV-guided
   and fixed programmes produced similar strength gains; muscle CSA was measured only in
   DEOLIVEIRA19 and BITTENCOURT24 (DEBLAUW21 did not assess it), with similar gains. None found an
   advantage for strength, muscle size or function in healthy adults.
   In endurance training, two meta-analyses found at most small, non-significant performance
   advantages (§1).
2. **What the trials measured:** a morning, supine or standing recording of RMSSD (1–10 min),
   compared with an individual baseline of 5 days to 4 weeks, using a band of mean ± 0.5 SD or a
   floor of mean − 1 SD. One endurance trial used nocturnal wrist-PPG RMSSD. **No trial used SDNN,
   an Apple Watch or HealthKit** (§2).
3. **Resting HR and sleep:** no trial used either one to adjust sessions (§3). Acute sleep loss
   (a night without sleep, or ≤6 h in 24 h) lowered strength by 2.85% on average (CRAVEN22). Only
   total deprivation was significant (−3.00%). For restricted nights alone the estimate was −2.77%
   (95% CI −6.75 to 1.21) and not significant. That is an effect size, not a tested trigger.
4. **Apple Watch:** heart rate and resting HR agree well with ECG at rest. Its HRV (SDNN) runs about
   8–10 ms low with about 20 ms absolute error and is not equivalent to a chest strap. HealthKit HRV
   comes from sporadic ~60-second SDNN windows. Sleep versus wake is good; sleep stages are poor
   (§4).
5. **Verdict (§5):** the evidence does **not** support a readiness rule for resistance training built
   from HealthKit's passive overnight SDNN, resting HR or sleep. The only cited template (DEBLAUW21)
   needs a morning LnRMSSD recording, and even then it promises only similar gains from fewer hard
   sessions, at Low certainty.

## Sources

### Syntheses, guidelines and consensus statements

| Key | Citation | Design | DOI · PMID | What I read |
|---|---|---|---|---|
| MANRESA21 | Manresa-Rocamora A, Sarabia JM, Javaloyes A, Flatt AA, et al. Heart Rate Variability-Guided Training for Enhancing Cardiac-Vagal Modulation, Aerobic Fitness, and Endurance Performance: A Methodological Systematic Review with Meta-Analysis. *Int J Environ Res Public Health*. 2021;18(19):10299. | Systematic review and meta-analysis (8 studies, 10 analysis units, 199 participants) | [10.3390/ijerph181910299](https://doi.org/10.3390/ijerph181910299) · PMID 34639599 · PMC8507742 | Full text (PMC8507742): Introduction, Methods 2.2–2.5, Results 3.2 (study and method characteristics), 3.3 (risk of bias), 3.4.1–3.4.2, Discussion, Conclusions. |
| DUKING21 | Düking P, Zinner C, Trabelsi K, Reed JL, et al. Monitoring and adapting endurance training on the basis of heart rate variability monitored by wearable technologies: A systematic review with meta-analysis. *J Sci Med Sport*. 2021;24(11):1180–1192. | Systematic review and meta-analysis (8 studies, 198 participants) | [10.1016/j.jsams.2021.04.012](https://doi.org/10.1016/j.jsams.2021.04.012) · PMID 34489178 | **Abstract only.** |
| GRANERO20 | Granero-Gallegos A, González-Quílez A, Plews D, Carrasco-Poyatos M. HRV-Based Training for Improving VO2max in Endurance Athletes. A Systematic Review with Meta-Analysis. *Int J Environ Res Public Health*. 2020;17(21):7999. | Systematic review and meta-analysis | [10.3390/ijerph17217999](https://doi.org/10.3390/ijerph17217999) · PMID 33143175 · PMC7663087 | **Abstract only**; its method is criticised in MANRESA21 (Introduction; Discussion). |
| BELLENGER16 | Bellenger CR, Fuller JT, Thomson RL, Davison K, Robertson EY, Buckley JD. Monitoring Athletic Training Status Through Autonomic Heart Rate Regulation: A Systematic Review and Meta-Analysis. *Sports Med*. 2016;46(10):1461–1486. | Systematic review (27 studies) and meta-analysis (24 studies); endurance athletes | [10.1007/s40279-016-0484-2](https://doi.org/10.1007/s40279-016-0484-2) · PMID 26888648 | **Abstract only.** |
| BOSQUET08 | Bosquet L, Merkari S, Arvisais D, Aubert AE. Is heart rate a convenient tool to monitor over-reaching? A systematic review of the literature. *Br J Sports Med*. 2008;42(9):709–714. | Systematic review with meta-analysis; competitive athletes | [10.1136/bjsm.2007.042200](https://doi.org/10.1136/bjsm.2007.042200) · PMID 18308872 | **Abstract only.** PubMed links an erratum (*Br J Sports Med*. 2008;42(12):1016), not read (publisher refused access). |
| MARASINGHA22 | Marasingha-Arachchige SU, Rubio-Arias JÁ, Alcaraz PE, Chung LH. Factors that affect heart rate variability following acute resistance exercise: A systematic review and meta-analysis. *J Sport Health Sci*. 2022;11(3):376–392. | Systematic review and meta-analysis (26 studies) | [10.1016/j.jshs.2020.11.008](https://doi.org/10.1016/j.jshs.2020.11.008) · PMID 33246163 · PMC9189698 | **Abstract only.** |
| CRAVEN22 | Craven J, McCartney D, Desbrow B, Sabapathy S, Bellinger P, Roberts L, Irwin C. Effects of Acute Sleep Loss on Physical Performance: A Systematic and Meta-Analytical Review. *Sports Med*. 2022;52(11):2669–2690. | Systematic review and multilevel meta-analysis (69 publications, 77 studies, 959 participants) | [10.1007/s40279-022-01706-y](https://doi.org/10.1007/s40279-022-01706-y) · PMID 35708888 · PMC9584849 | Full text (PMC9584849): Key Points, Methods (inclusion criteria, task classification, statistics), Results "Overall Exercise Performance" and "Strength", Discussion, "Limitations and Future Direction". The subgroup tables did not come through in my read; the independent verification read Tables 2, 3 and 5, and their values are used in §3b and §5. |
| KNOWLES18 | Knowles OE, Drinkwater EJ, Urwin CS, Lamon S, Aisbett B. Inadequate sleep and muscle strength: Implications for resistance training. *J Sci Med Sport*. 2018;21(9):959–968. | Systematic review (17 studies) | [10.1016/j.jsams.2018.01.012](https://doi.org/10.1016/j.jsams.2018.01.012) · PMID 29422383 | **Abstract only.** |
| DOBBS19 | Dobbs WC, Fedewa MV, MacDonald HV, Holmes CJ, et al. The Accuracy of Acquiring Heart Rate Variability from Portable Devices: A Systematic Review and Meta-Analysis. *Sports Med*. 2019;49(3):417–435. | Systematic review and meta-analysis (23 studies, 301 effects; literature to July 2017) | [10.1007/s40279-019-01061-5](https://doi.org/10.1007/s40279-019-01061-5) · PMID 30706234 | **Abstract only.** |
| XU26 | Xu S, Liu H, Liu Z, Su P, Gu Z. Accuracy of Photoplethysmography-Derived Pulse Rate Variability Compared with Electrocardiography-Derived Heart Rate Variability: A Systematic Review and Meta-Analysis. *Sensors (Basel)*. 2026;26(16):5192. | Systematic review (43 studies) and meta-analysis (10 studies) | [10.3390/s26165192](https://doi.org/10.3390/s26165192) · PMID 42655500 · PMC13517957 | **Abstract only.** |
| LAMBE26 | Lambe R, Baldwin M, O'Grady B, Schumann M, et al. The accuracy of Apple Watch measurements: a living systematic review and meta-analysis. *NPJ Digit Med*. 2026;9(1):63. | Living systematic review (82 studies) and meta-analysis | [10.1038/s41746-025-02238-1](https://doi.org/10.1038/s41746-025-02238-1) · PMID 41513748 · PMC12823594 | Full text (PMC12823594): Results (risk of bias, heart rate, sleep), Discussion, Methods. Its HRV synthesis is in Supplementary Note 1, which I did not open. It shares authors with OGRADY24 and includes grey literature, among it an Apple white paper; I cite only its pooled peer-reviewed analyses. |
| CHOE25 | Choe JP, Kang M. Apple watch accuracy in monitoring health metrics: a systematic review and meta-analysis. *Physiol Meas*. 2025;46(4). | Systematic review and meta-analysis (56 studies) | [10.1088/1361-6579/adca82](https://doi.org/10.1088/1361-6579/adca82) · PMID 40199339 | **Abstract only.** |
| FULLER20 | Fuller D, Colwell E, Low J, Orychock K, et al. Reliability and Validity of Commercially Available Wearable Devices for Measuring Steps, Energy Expenditure, and Heart Rate: Systematic Review. *JMIR Mhealth Uhealth*. 2020;8(9):e18694. | Systematic review (158 publications) | [10.2196/18694](https://doi.org/10.2196/18694) · PMID 32897239 · PMC7509623 | **Abstract only.** |
| WALSH21 | Walsh NP, Halson SL, Sargent C, Roach GD, et al. Sleep and the athlete: narrative review and 2021 expert consensus recommendations. *Br J Sports Med*. 2021;55(7):356–368 (published online 2020-11-03). | Narrative review with expert consensus (panel opinion) | [10.1136/bjsports-2020-102025](https://doi.org/10.1136/bjsports-2020-102025) · PMID 33144349 | **Abstract only.** |
| WATSON15 | Watson NF, Badr MS, Belenky G, et al. Recommended Amount of Sleep for a Healthy Adult: A Joint Consensus Statement of the American Academy of Sleep Medicine and Sleep Research Society. *Sleep*. 2015;38(6):843–844. | Joint consensus statement (modified RAND appropriateness process) | [10.5665/sleep.4716](https://doi.org/10.5665/sleep.4716) · PMID 26039963 · PMC4434546 | PMC article page (a two-page statement), read through a fetch tool that returned the "Consensus Statement" section. |

### Narrative reviews

| Key | Citation | Design | DOI · PMID | What I read |
|---|---|---|---|---|
| ADDLEMAN24 | Addleman JS, Lackey NS, DeBlauw JA, Hajduczok AG. Heart Rate Variability Applications in Strength and Conditioning: A Narrative Review. *J Funct Morphol Kinesiol*. 2024;9(2):93. | Narrative review (a co-author also led DEBLAUW21) | [10.3390/jfmk9020093](https://doi.org/10.3390/jfmk9020093) · PMID 38921629 · PMC11204851 | Full text (PMC11204851): §3 "Heart Rate Variability Measurement" and "Measurement Considerations", §4.2, §5.2, §6–6.3, §7, §9. Its guideline table (§8) did not come through. |
| BUCHHEIT14 | Buchheit M. Monitoring training status with HR measures: do all roads lead to Rome? *Front Physiol*. 2014;5:73. | Narrative review | [10.3389/fphys.2014.00073](https://doi.org/10.3389/fphys.2014.00073) · PMID 24578692 · PMC3936188 | Full text (PMC3936188): "Resting measures", Table 1, "Determining the smallest worthwhile change", "Making decisions", "Ideal vs. real". |
| SHAFFER17 | Shaffer F, Ginsberg JP. An Overview of Heart Rate Variability Metrics and Norms. *Front Public Health*. 2017;5:258. | Narrative review | [10.3389/fpubh.2017.00258](https://doi.org/10.3389/fpubh.2017.00258) · PMID 29034226 · PMC5624990 | Full text (PMC5624990): "Time-Domain Measurements" (SDNN, RMSSD), "Contextual Factors: Period Length", "Ultra-Short-Term (UST) Measurement Norms". |
| PLEWS13 | Plews DJ, Laursen PB, Stanley J, Kilding AE, Buchheit M. Training adaptation and heart rate variability in elite endurance athletes: opening the door to effective monitoring. *Sports Med*. 2013;43(9):773–781. | Narrative review | [10.1007/s40279-013-0071-8](https://doi.org/10.1007/s40279-013-0071-8) · PMID 23852425 | **Abstract only.** |
| SCHAFFARCZYK26 | Schaffarczyk M, Sperlich B. Heart rate variability-guided endurance training: evaluating strengths, weaknesses, opportunities, and threats for load prescription and adjustment. *Front Sports Act Living*. 2026;8:1858271. | Narrative review (SWOT analysis) | [10.3389/fspor.2026.1858271](https://doi.org/10.3389/fspor.2026.1858271) · PMID 42724227 · PMC13558445 | **Abstract only.** |

### Trials (each Low at most, whatever its quality)

| Key | Citation | Design | DOI · PMID | What I read |
|---|---|---|---|---|
| DEOLIVEIRA19 | De Oliveira RM, Ugrinowitsch C, Kingsley JD, Da Silva DG, et al. Effect of individualized resistance training prescription with heart rate variability on individual muscle hypertrophy and strength responses. *Eur J Sport Sci*. 2019;19(8):1092–1100. | RCT (n = 20) | [10.1080/17461391.2019.1572227](https://doi.org/10.1080/17461391.2019.1572227) · PMID 30702985 | **Abstract only** (publisher page refused; not in PMC or Europe PMC). Session frequency of the fixed group and participants' training status as described by BITTENCOURT24 (Introduction) and DEBLAUW21 (Discussion), which disagree (§6). |
| BITTENCOURT24 | Bittencourt D, de Oliveira RM, da Silva DG, Bergamasco JGA, et al. Effects of individualized resistance training prescription with heart rate variability on muscle strength, muscle size and functional performance in older women. *Front Physiol*. 2024;15:1472702. | RCT (n = 21; same research group as DEOLIVEIRA19) | [10.3389/fphys.2024.1472702](https://doi.org/10.3389/fphys.2024.1472702) · PMID 39742158 · PMC11685108 | Full text (PMC11685108): Methods (Participants, Study design, Heart rate variability, Resistance training protocol), Results (Individualized recovery, Training frequency and volume load, Table 1, Table 2, variability), Discussion, Conclusion. |
| DEBLAUW21 | DeBlauw JA, Drake NB, Kurtz BK, Crawford DA, et al. High-Intensity Functional Training Guided by Individualized Heart Rate Variability Results in Similar Health and Fitness Improvements as Predetermined Training with Less Effort. *J Funct Morphol Kinesiol*. 2021;6(4):102. | RCT, two sites (n = 55) | [10.3390/jfmk6040102](https://doi.org/10.3390/jfmk6040102) · PMID 34940511 · PMC8705715 | Full text (PMC8705715): §2.1–2.4 (design, HRV method, strength testing, modulation rules), §3.1–3.4, Discussion, Conclusions. |
| NUUTTILA22 | Nuuttila OP, Nummela A, Korhonen E, Häkkinen K, Kyröläinen H. Individualized Endurance Training Based on Recovery and Training Status in Recreational Runners. *Med Sci Sports Exerc*. 2022;54(10):1690–1701. | RCT (pair-matched, then randomised; n = 30) | [10.1249/MSS.0000000000002968](https://doi.org/10.1249/MSS.0000000000002968) · PMID 35975912 · PMC9473708 | Full text (PMC9473708), searched for methods, adjustment rules, results and limitations. The rule combining the markers is in Figure 1, which did not come through: **unverified**. |
| NUUTTILA17 | Nuuttila OP, Nikander A, Polomoshnov D, Laukkanen JA, Häkkinen K. Effects of HRV-Guided vs. Predetermined Block Training on Performance, HRV and Serum Hormones. *Int J Sports Med*. 2017;38(12):909–920. | Controlled trial (allocation method not stated in the abstract; n = 24) | [10.1055/s-0043-115122](https://doi.org/10.1055/s-0043-115122) · PMID 28950399 | **Abstract only.** |
| VESTERINEN16 | Vesterinen V, Nummela A, Heikura I, Laine T, Hynynen E, Botella J, Häkkinen K. Individual Endurance Training Prescription with Heart Rate Variability. *Med Sci Sports Exerc*. 2016;48(7):1347–1354. | RCT (n = 40) | [10.1249/MSS.0000000000000910](https://doi.org/10.1249/MSS.0000000000000910) · PMID 26909534 | **Abstract only.** |
| KIVINIEMI07 | Kiviniemi AM, Hautala AJ, Kinnunen H, Tulppo MP. Endurance training guided individually by daily heart rate variability measurements. *Eur J Appl Physiol*. 2007;101(6):743–751. | RCT (n = 26) | [10.1007/s00421-007-0552-2](https://doi.org/10.1007/s00421-007-0552-2) · PMID 17849143 | **Abstract only.** |
| KIVINIEMI10 | Kiviniemi AM, Hautala AJ, Kinnunen H, Nissilä J, Virtanen P, Karjalainen J, Tulppo MP. Daily exercise prescription on the basis of HR variability among men and women. *Med Sci Sports Exerc*. 2010;42(7):1355–1363. | RCT (n = 53) | [10.1249/mss.0b013e3181cd5f39](https://doi.org/10.1249/mss.0b013e3181cd5f39) · PMID 20575165 | **Abstract only.** |
| FIGUEIREDO23 | Figueiredo DH, Figueiredo DH, Bellenger C, Machado FA. Individually guided training prescription by heart rate variability and self-reported measure of stress tolerance in recreational runners: Effects on endurance performance. *J Sports Sci*. 2022;40(24):2732–2740. | RCT (n = 36) | [10.1080/02640414.2023.2191082](https://doi.org/10.1080/02640414.2023.2191082) · PMID 36940300 | **Abstract only.** The key keeps "23" from the DOI; the issue is dated 2022. |
| LEMEUR13 | Le Meur Y, Pichon A, Schaal K, et al. Evidence of parasympathetic hyperactivity in functionally overreached athletes. *Med Sci Sports Exerc*. 2013;45(11):2061–2071. | RCT (intensified vs normal training; n = 21) | [10.1249/MSS.0b013e3182980125](https://doi.org/10.1249/MSS.0b013e3182980125) · PMID 24136138 | **Abstract only.** |
| SCHNEIDER19 | Schneider C, Wiewelhove T, Raeder C, Flatt AA, et al. Heart Rate Variability Monitoring During Strength and High-Intensity Interval Training Overload Microcycles. *Front Physiol*. 2019;10:582. | Non-randomised, uncontrolled overload trial (strength arm n = 19) | [10.3389/fphys.2019.00582](https://doi.org/10.3389/fphys.2019.00582) · PMID 31178746 · PMC6538885 | Full text (PMC6538885), searched: participants, experimental design, orthostatic test, strength results, individual classification. |
| THAMM19 | Thamm A, Freitag N, Figueiredo P, Doma K, Rottensteiner C, Bloch W, Schumann M. Can Heart Rate Variability Determine Recovery Following Distinct Strength Loadings? A Randomized Cross-Over Trial. *Int J Environ Res Public Health*. 2019;16(22):4353. | Randomised crossover (n = 10) | [10.3390/ijerph16224353](https://doi.org/10.3390/ijerph16224353) · PMID 31703468 · PMC6888606 | Full text (PMC6888606): all sections. One author is employed by an HRV-software firm (affiliation). |
| CHEN11 | Chen JL, Yeh DP, Lee JP, et al. Parasympathetic nervous activity mirrors recovery status in weightlifting performance after training. *J Strength Cond Res*. 2011;25(6):1546–1552. | Non-randomised single-group trial (n = 7) | [10.1519/JSC.0b013e3181da7858](https://doi.org/10.1519/JSC.0b013e3181da7858) · PMID 21273908 | **Abstract only.** |
| KNOWLES22 | Knowles OE, Drinkwater EJ, Roberts SSH, et al. Sustained Sleep Restriction Reduces Resistance Exercise Quality and Quantity in Females. *Med Sci Sports Exerc*. 2022;54(12):2167–2177. | Randomised crossover (n = 10) | [10.1249/MSS.0000000000003000](https://doi.org/10.1249/MSS.0000000000003000) · PMID 36136596 | **Abstract only.** |

### Validation and observational studies (each Low at most)

| Key | Citation | Design | DOI · PMID | What I read |
|---|---|---|---|---|
| MILLER22 | Miller DJ, Sargent C, Roach GD. A Validation of Six Wearable Devices for Estimating Sleep, Heart Rate and Heart Rate Variability in Healthy Adults. *Sensors (Basel)*. 2022;22(16):6317. | Cross-sectional validation (one lab night; n = 53) | [10.3390/s22166317](https://doi.org/10.3390/s22166317) · PMID 36016077 · PMC9412437 | Full text (PMC9412437): §2.2–2.5, §3.1 (Apple Watch S6), §3.5 (WHOOP), §4.2, §4.3. |
| OGRADY24 | O'Grady B, Lambe R, Baldwin M, Acheson T, et al. The Validity of Apple Watch Series 9 and Ultra 2 for Serial Measurements of Heart Rate Variability and Resting Heart Rate. *Sensors (Basel)*. 2024;24(19):6220. | Prospective cohort validation (39 adults, 316 paired recordings) | [10.3390/s24196220](https://doi.org/10.3390/s24196220) · PMID 39409260 · PMC11478500 | Full text (PMC11478500): Introduction, §2.3–2.4, §3.2, Discussion, Conclusions. |
| BONNEVAL25 | Bonneval L, Wing D, Sharp S, Tristao Parra M, et al. Validity of Heart Rate Variability Measured with Apple Watch Series 6 Compared to Laboratory Measures. *Sensors (Basel)*. 2025;25(8):2380. | Cross-sectional validation (n = 78) | [10.3390/s25082380](https://doi.org/10.3390/s25082380) · PMID 40285070 · PMC12031371 | **Abstract only.** |
| HERNANDO18 | Hernando D, Roca S, Sancho J, Alesanco Á, Bailón R. Validation of the Apple Watch for Heart Rate Variability Measurements during Relax and Mental Stress in Healthy Subjects. *Sensors (Basel)*. 2018;18(8):2619. | Cross-sectional validation (n = 20) | [10.3390/s18082619](https://doi.org/10.3390/s18082619) · PMID 30103376 · PMC6111985 | **Abstract only.** |
| HIRTEN21 | Hirten RP, Danieletto M, Tomalin L, et al. Use of Physiological Data From a Wearable Device to Identify SARS-CoV-2 Infection and Symptoms and Predict COVID-19 Diagnosis: Observational Study. *J Med Internet Res*. 2021;23(2):e26107. | Prospective cohort (n = 297) | [10.2196/26107](https://doi.org/10.2196/26107) · PMID 33529156 · PMC7901594 | Full text (PMC7901594): "Wearable Monitoring Device and Autonomic Nervous System Assessment", "HRV Modeling", Results "Participant Demographics", Limitations. Used only for how the Apple Watch samples HRV, not for its COVID findings. |
| ROBBINS24 | Robbins R, Weaver MD, Sullivan JP, et al. Accuracy of Three Commercial Wearable Devices for Sleep Tracking in Healthy Adults. *Sensors (Basel)*. 2024;24(20):6532. | Cross-sectional validation (one inpatient night; n = 35) | [10.3390/s24206532](https://doi.org/10.3390/s24206532) · PMID 39460013 · PMC11511193 | Full text (PMC11511193): §2.2–2.6, §3–3.3, Discussion, limitations. |
| DIAL25 | Dial MB, Hollander ME, Vatne EA, Emerson AM, Edwards NA, Hagen JA. Validation of nocturnal resting heart rate and heart rate variability in consumer wearables. *Physiol Rep*. 2025;13(16):e70527. | Validation study (13 adults, 536 nights; no Apple Watch) | [10.14814/phy2.70527](https://doi.org/10.14814/phy2.70527) · PMID 40834291 · PMC12367097 | **Abstract only.** |
| NUUTTILA22R | Nuuttila OP, Seipäjärvi S, Kyröläinen H, Nummela A. Reliability and Sensitivity of Nocturnal Heart Rate and Heart-Rate Variability in Monitoring Individual Responses to Training Load. *Int J Sports Physiol Perform*. 2022;17(8):1296–1303. | Repeated-measures reliability study (n = 15 and 23) | [10.1123/ijspp.2022-0145](https://doi.org/10.1123/ijspp.2022-0145) · PMID 35894977 | **Abstract only.** The recording device is not named in the abstract. |
| PLEWS14 | Plews DJ, Laursen PB, Le Meur Y, Hausswirth C, Kilding AE, Buchheit M. Monitoring training with heart rate-variability: how much compliance is needed for valid assessment? *Int J Sports Physiol Perform*. 2014;9(5):783–790. | Observational analysis of trained triathletes | [10.1123/ijspp.2013-0455](https://doi.org/10.1123/ijspp.2013-0455) · PMID 24334285 | **Abstract only.** |

Metadata, abstracts and PMC full texts were retrieved through PubMed/PMC (NCBI); open-access flags
through Europe PMC.

### Seen but not cited

| Paper | Why not cited |
|---|---|
| Task Force of the ESC and NASPE. Heart rate variability: standards of measurement, physiological interpretation and clinical use. *Circulation*. 1996;93(5):1043–1065. PMID 8598068 | Official guideline, but the publisher page refused access (HTTP 403), there is no PMC copy and the PubMed record has no abstract or DOI. Not read, so not cited. Its content reaches this file only through SHAFFER17 and BUCHHEIT14. |
| Plews DJ, et al. *Eur J Appl Physiol*. 2012;112(11):3729–3741. PMID 22367011 (7-day rolling LnRMSSD in two elite triathletes) | Case comparison of two athletes, not a qualifying design. It is the origin of the 7-day rolling-mean idea that DEBLAUW21 and others adopted. |
| Nelson BW, Allen NB. *JMIR Mhealth Uhealth*. 2019;7(3):e10828. PMID 30855232 (Apple Watch 3 over 24 h) | One participant (the first author); effectively a case study. |
| Lee T, et al. *JMIR Mhealth Uhealth*. 2023;11:e50983. PMID 37917155 (11 sleep trackers, including Apple Watch 8) | I did not extract its Apple Watch figures. Most authors are employed by a company whose sleep product was among those tested (affiliations). |
| Javaloyes A, et al. *J Strength Cond Res*. 2020;34(6):1511–1518. PMID 31490431 (cycling) | Endurance only, and inside MANRESA21's synthesis. Not needed separately. |
| Di P, et al. *BMC Sports Sci Med Rehabil*. 2025;18:47. PMID 41456014 (autoregulated speed-skating programme) | Mixed HRV and session-RPE readiness in speed skaters, with endurance and power outcomes; retrospectively registered. Not resistance training. |
| Lavín-Pérez AM, et al. *Psycho-oncology*. 2025. PMID 41339114 | Clinical population (breast cancer survivors) with quality-of-life and mental-health outcomes. It reported HRV-guided training better than pre-planned training, so the "matched, never beat" finding below is limited to strength, size and function in healthy adults. |
| Düking P, et al. 2020 systematic review. PMID 32785959 | Running only; superseded for this question by DUKING21 and MANRESA21. |
| Manresa-Rocamora A, et al. 2021 meta-analysis. PMID 33533045 | Weekly-averaged HRV rose in overreached athletes (SMD 0.81), consistent with §6.5. Found by the verifier and not read here, so not cited. |
| Casanova-Lizón A, et al. 2025. PMID 40476188 | HRV-guided training with no fixed-programme arm, so it cannot test guided against fixed and does not change the count of 96. |
| Okuno NM, et al. *J Strength Cond Res*. 2014;28(4):1143–1150. PMID 24077384 | Acute HRV after one leg-press session; covered better by MARASINGHA22 and THAMM19. |
| Medellín Ruiz JP, et al. (HRV-guided vs predefined training meta-analysis, *Applied Sciences* 2020) | Mentioned in MANRESA21's Introduction. Not found in PubMed and not opened. |
| Vendor pages and white papers (Apple, WHOOP, Oura, Garmin, Polar, HRV4Training) | Never sources, by rule. |
| Preprints | None used, by rule. |

---

## 1. HRV-guided training vs predetermined programmes

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| **Endurance: HRV-guided training was not significantly better for fitness or performance.** VO2max SMD 0.13 (95% CI −0.12 to 0.39); maximal aerobic capacity 0.20 (−0.07 to 0.47); capacity at VT2 0.26 (−0.05 to 0.57); endurance performance 0.20 (−0.09 to 0.48); no heterogeneity. | Healthy adults aged about 22–39 (mean 31.8); 8 studies, 199 participants; interventions 2–8 weeks. 2 of the 8 trials combined endurance and strength training, but only aerobic outcomes were pooled (Results 3.2). | MANRESA21, Results 3.4.2; Discussion (age range). | **Moderate** (two meta-analyses agree; few studies; endurance only) | Any group-level advantage over a fixed plan is small at best. |
| HRV-guided training raised vagal HRV (RMSSD/SD1) more than predefined training: SMD 0.50 (0.09 to 0.91). Standing resting HR did not differ: SMD 0.04 (−0.34 to 0.43). | Same | MANRESA21, Results 3.4.1. | Moderate | The clearest effect is on HRV itself, not on performance. |
| Performance g = 0.079 (95% CI −0.050 to 0.393; p = 0.597); VO2peak g = 0.171 (−0.213 to 0.371); submaximal markers g = 0.296 (0.031 to 0.562). Fewer non-responders with HRV guidance. Most HRV-guided arms did **fewer** moderate- and high-intensity sessions. | Endurance; 8 studies, 198 participants, fixed-effect model | DUKING21, Abstract. | Moderate (with MANRESA21) | Similar or slightly better outcomes from less hard training. |
| A larger VO2max effect (ES 0.402) in favour of HRV guidance | Endurance athletes | GRANERO20, Abstract. MANRESA21 (Introduction; Discussion) reports that it used within-group effect sizes and did not compare prescription methods directly. | Low (method criticised by a later synthesis) | An outlier among the syntheses; not relied on. |
| **Resistance training: no synthesis exists.** No study had tested whether HRV relates to maximal strength gains or muscle cross-sectional area after a programme; in the one HRV-guided resistance trial the review cites, individual gains did not differ from fixed programming. | Strength and conditioning | ADDLEMAN24, §4.2; §6.2. My PubMed searches (2026-09-24) found no meta-analysis or systematic review of HRV-guided resistance training. | Low (narrative review) | The literature is too thin to support a rule for lifting outcomes. |
| **Young men, fixed 48 h vs HRV-timed sessions:** 1RM +30% (HRV) vs +42% (fixed); vastus lateralis CSA +15.7% vs +15.8%. No group difference, and no reduction in the spread of individual responses. | 20 young men (21.9 ± 3.3 y) | DEOLIVEIRA19, Abstract. | Low (single small RCT; abstract only) | Timing sessions by HRV did not improve strength or size. |
| **Older women, fixed Mon/Wed/Fri vs HRV-timed:** no group × time interaction for CSA, 1RM, peak torque or function. CSA +8.89% (HRV) vs +9.46% (fixed), ES −0.06 (95% CI −0.92 to 0.79). 1RM knee extension +47.44% (HRV) vs +46.77% (fixed); vertical bench press +35.41% vs +39.11%. The row labels did not come through; the order is inferred from the Table 1 footnote, which lists leg extension first (independent verification). | 21 women aged 66 ± 5; 7 weeks; 8 exercises, 3 × 9–12RM to concentric failure | BITTENCOURT24, Results (Table 1, Table 2, "Variability in adaptations"). | Low (single small RCT) | Similar adaptations. The HRV group actually trained more often (27 vs 21 sessions). |
| **High-intensity functional training, fixed vs HRV-modulated:** squat, overhead press, deadlift and their total all improved in both groups, with no between-group difference. The HRV group did 13.56 ± 0.83 fewer high-intensity days with 25.3–26.7 sessions attended (§3.4). The Discussion says 17 of 30 sessions were modulated; the two do not reconcile, so expect roughly 13–17 of 30 (§6.3). | 55 recreationally active adults aged 18–35; 6 training weeks at 5 d/wk | DEBLAUW21, §3.3–3.4; Discussion. | Low (single RCT) | Similar strength gains with less high-intensity work. The only resistance-type trial that reduced volume and load rather than postponing sessions. It measured lean mass, not muscle CSA (limitations). |
| Endurance-trained men: vMax and countermovement-jump changes were greater with HRV guidance (p < 0.05); HRV rose only in that group. | 24 endurance-trained men; 8 weeks of block high-intensity aerobic training | NUUTTILA17, Abstract. | Low (single trial; allocation not stated in abstract) | A neuromuscular (jump) signal in an endurance trial, not a lifting outcome. |

**Trial structures (resistance-type training).**

| Key | Population, weeks | Readiness measure | Decision rule | Result |
|---|---|---|---|---|
| DEOLIVEIRA19 | 20 young men; programme length **unverified** (abstract) | RMSSD before each session; baseline from 5 days before training | Train only if RMSSD had returned to baseline, otherwise wait 24 h. Fixed group trained every 48 h. | No difference (Abstract). |
| BITTENCOURT24 | 21 older women; 7 weeks | 10-min supine RMSSD, same time of day, Polar S810i chest strap, Kubios; 5-day baseline (Mon–Fri) | Train if RMSSD ≥ baseline mean − 1 SD, otherwise return 24 h later (Friday → Monday). Fixed group trained Mon/Wed/Fri. | No difference. Sessions completed by individuals in the HRV group ranged from 19 to 31 of 35 possible; fixed-group individuals trained 1 to 8 times while below their own threshold (Results, "Individualized recovery"). |
| DEBLAUW21 | 55 adults; 6 training weeks (11 weeks including baseline and testing) | 1-min supine morning recording with a smartphone camera (finger PPG) after waking, bladder emptying and 5 min rest; LnRMSSD; 14-day baseline | 7-day rolling LnRMSSD inside baseline ± 0.5 SD: no change. Between ± 0.5 and ± 1 SD: repetitions and load cut by 25%. Beyond ± 1 SD: 20-min light active recovery instead. Baseline recalculated after 15 sessions. | No difference; fewer hard days (§2.4; §3.4). |

**Not addressed.** No trial of trained lifters measured hypertrophy or strength with an HRV rule
that reduced volume or load, and none that reports its length trained for longer than 7 weeks. No
trial changed inter-set rest intervals.

## 2. How HRV-guided protocols decide

### 2a. Baseline, rolling value and "smallest worthwhile change" band

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| Of 8 guided trials, 4 compared a **single-day** value with a moving reference (3 used a 10-day average, 1 the previous day), and 4 compared a **rolling average** (three 7-day, one 3-day) with a fixed baseline. Fixed baselines came from a 3–4-week baseline period, kept throughout or updated once mid-intervention. | Endurance trials, 2007–2020 | MANRESA21, Results 3.2; Discussion (fixed vs rolling paragraph). | Moderate (descriptive count from one systematic review) | There is no standard. Rolling averages trigger fewer changes than single-day values. |
| The reference band was **mean − 1 SD** in 3 trials, **mean ± 0.5 SD** in 3, 70% of the previous day in 1 and the baseline mean in 1. | Same | MANRESA21, Results 3.2. | Moderate (descriptive) | The two common bands are ±0.5 SD and −1 SD. |
| Which HRV index, recording position and baseline approach work best **still needs study**. | Same | MANRESA21, Abstract (Conclusion); Discussion. | Moderate | No band has been shown to beat another. |
| The SWC for HRV has been set at 0.5 × CV (Le Meur) or 1 × CV (Plews) of the individual's values. There is **no evidence** that any fraction of the CV corresponds to a meaningful change in training status or performance, and the SWC may need to change across training phases. | Athletes | BUCHHEIT14, "Determining the smallest worthwhile change". | Low (narrative review) | The ±0.5 SD band is a convention, not a validated threshold. |
| Typical error (CV) about 12% for LnRMSSD and about 10% for resting HR; SWC about +3% (LnRMSSD) and about −2% (resting HR). These SWCs were back-calculated from group endurance-performance gains. | Endurance athletes | BUCHHEIT14, Table 1 (layout flattened in the text I read). Day-to-day CV of LnRMSSD 10–20% ("Ideal vs. real"). | Low | Day-to-day noise is several times larger than the change that matters. |
| **7-day rolling LnRMSSD** against a **14-day** baseline, with SWC1 = ±0.5 SD and SWC2 = ±1 SD of the baseline mean; recalculated after 3 weeks (15 sessions). | Recreationally active adults; functional training | DEBLAUW21, §2.4. | Low (single RCT) | The only resistance-type template with graded bands. |
| Nocturnal HRV: 4-week rolling average ± 0.5 × SD, with values outside the band in either direction counted as negative. The daily marker was a 3-day HRV value, and load was adjusted twice a week. | Recreational runners | NUUTTILA22, Methods (paragraph setting the markers and their desirable ranges); Statistical analysis (the 3-day HRV marker). | Low | Supports a ±0.5 SD band and bidirectional flags, in endurance only. |
| HRV-guided arms reached an HRV-defined recovered state before resuming hard work. The early rule was below (10-day mean − SD), or a falling trend for 2 days, meaning low intensity or rest. | Moderately fit men; HF-HRV each morning | KIVINIEMI07, Abstract. | Low | The origin of the mean − 1 SD floor. |
| With 1 to 7 days averaged per week, standardised LnRMSSD changes and their correlations with performance plateaued after 3–4 days. A **minimum of 3 valid recordings per week** is advised. | Trained triathletes during functional overreaching | PLEWS14, Abstract. | Low | Sets a floor for missing data. |
| Once-a-week HRV recordings missed changes that weekly averages of daily recordings detected. | 21 triathletes, 3-week overload | LEMEUR13, Abstract. | Low | Daily or near-daily recording is needed. |
| Rolling 2–4-day averages gave more precise group estimates but could harm classification of individual short-term responses. | Strength- and HIIT-trained athletes | SCHNEIDER19, Abstract; Results (rolling averages). | Low | Smoothing can hide the very day a rule would act on. |

### 2b. What the protocols changed on a low day

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| **Intensity:** high or moderate sessions were replaced with low-intensity training or rest when HRV was suppressed. | Endurance | MANRESA21, Introduction; KIVINIEMI07, Abstract; KIVINIEMI10, Abstract; VESTERINEN16, Abstract (moderate or high-intensity sessions only when HRV was within the SWC). | Moderate (consistent across trials in two syntheses) | The standard endurance action is to swap intensity, not cancel the day. |
| **Volume and load −25%** (repetitions and absolute weight) for a moderate deviation; **20 min light active recovery** for a large one. | Functional training | DEBLAUW21, §2.4. The text gives the recovery intensity as ">50% HRR", which looks like a typo for <50%; the true bound is **unverified**. | Low | The only lifting-type "lighter session" definition. |
| **Volume −25%**, and high-intensity sessions dropped during interval blocks; +5% volume, or more high-intensity sessions, when markers were favourable. Across the intervention, 55% of adjustments kept the load, 35% raised it and 10% lowered it. | Recreational runners | NUUTTILA22, Methods (training-load adjustment paragraphs); Results. | Low | Readiness rules can also increase load. |
| **Postpone 24 h** (a frequency rule) | Resistance training | DEOLIVEIRA19, Abstract; BITTENCOURT24, "Resistance training protocol". | Low | The two lifting RCTs changed only when a session happened, not its content. |
| A substantial fall in rMSSD could first be met by shifting a few sessions from intense to low without cutting overall load, escalating to rest if it keeps falling. Practitioners may act at once or wait for 2–3 consecutive days of change. | Athletes | BUCHHEIT14, "Making decisions". | Low (opinion) | A graded response is expert advice, not tested. |

**Not addressed:** no study changed inter-set rest intervals in response to HRV.

### 2c. Measurement timing and metric: is overnight wearable HRV (Apple Watch SDNN) valid for this?

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| **7 of 8 guided trials measured in the morning after waking**, and 1 in the afternoon or evening before training. Positions: standing 3, supine 4, both 1. Lengths 1–5 min. Index: RMSSD 5, SD1 1, HF 2. | Endurance trials | MANRESA21, Results 3.2. | Moderate (descriptive) | The evidence base is morning RMSSD. |
| Night recordings are in theory the most standardised, but sleep pattern and quality confound them. Best practice is 5–10 min on waking. To guide that day's training, the author holds morning resting HRV to be the only appropriate option. | Athletes | BUCHHEIT14, "Resting measures"; "Ideal vs. real". | Low (narrative review) | Expert preference for morning over overnight. |
| **Nocturnal wrist-PPG LnRMSSD** (Polar Vantage V2; a 4-h segment starting 30 min after sleep onset) was used to guide training, and the individualised group improved 10-km time more: −6.2 ± 2.8% vs −2.9 ± 2.4% (p = 0.002). The authors state that all earlier HRV-guided trials used morning or daytime recordings. | Recreational runners (IND 16, PD 14); 15 weeks | NUUTTILA22, Methods ("nocturnal HR and HRV"); Results; Discussion. | Low (single RCT; endurance; HRV combined with other markers) | The only guided trial with overnight wearable HRV. It used RMSSD from a fixed sleep segment, not SDNN. |
| Nocturnal HR and HRV were highly reliable between similar nights (ICC 0.97–0.98 for HR, 0.92–0.97 for LnRMSSD) and responded to a maximal 3000-m run most consistently in the 4-h and full-night segments. | Recreational runners | NUUTTILA22R, Abstract. | Low | Overnight RMSSD over a defined segment is reliable. The device is not named in the abstract. |
| Many wearables measure HRV during slow-wave sleep; others on waking. What matters is a consistent method on the same device. | Strength and conditioning | ADDLEMAN24, §3 "Measurement Considerations". | Low | Consistency matters more than the particular window. |
| **Apple Watch and the Health app report HRV only as SDNN, computed from ultra-short windows of about 60 s** taken several times a day. Sampling was sparse and irregular: a median of 28 HRV samples (range 1–129) per participant over a median follow-up of 42 days. Sleep and wake times were not captured. | Apple Watch Series 4–5 users (health-care workers) | HIRTEN21, "Wearable Monitoring Device…"; "HRV Modeling"; Results; Limitations. The "about 60 s" detail rests on the paper's own cited reference, which I did not open. | Low (cohort; device description) | HealthKit HRV is not an overnight RMSSD. It is a sparse ultra-short SDNN. |
| Apple Watch calculates SDNN every 2–4 hours. | Apple Watch | OGRADY24, Introduction. The claim cites a reference I did not open (possibly vendor material): **unverified**. | Low | Consistent with HIRTEN21; do not rely on the interval. |
| SDNN reflects both sympathetic and parasympathetic activity. RMSSD is the primary time-domain index of vagal HRV. Because HRV grows with recording length, SDNN values from windows of different lengths **must not be compared**. Many ultra-short studies had serious methodological limitations. | General | SHAFFER17, "SDNN"; "RMSSD"; "Contextual Factors: Period Length"; "Ultra-Short-Term (UST) Measurement Norms". | Low (narrative review) | A mix of 60-s SDNN readings taken at different times is a weak basis for day-to-day comparison. |
| Across portable devices, the absolute error against ECG was highest for SDNN (ES 0.44), though no longer significantly different after outliers were removed. Recording position also mattered (p = 0.033). | Portable HRV devices, literature to 2017 | DOBBS19, Abstract. | Low for the SDNN-specific finding (not robust to outliers) | SDNN is the least reliable index to take from a device. |

**Answer to the question.** Every guided trial used RMSSD, or a related vagal index, recorded in
the morning or over a fixed overnight segment. **No trial used SDNN, and none used an Apple Watch or
HealthKit.** Overnight RMSSD from a validated device has Low-certainty support from one endurance
trial. HealthKit's passive SDNN has none.

## 3. Resting heart rate and sleep as readiness signals

### 3a. Resting heart rate

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| Short-term overload (under 2 weeks) moderately raised resting HR (SMD 0.55; p = 0.01). Longer overload left resting values unchanged. The changes are small enough to fall within day-to-day variability, so they need other signs of overreaching to interpret. | Competitive athletes | BOSQUET08, Abstract. | Moderate for the group-level effect; Low for individual use | Resting HR moves with overload on average but is weak for single days. |
| When performance improved, resting RMSSD rose (SMD 0.58). With overreaching, resting RMSSD rose slightly (SMD 0.26) and resting HF and SD1 barely changed. The authors conclude resting HRV is largely unaffected by overreaching. | Endurance athletes; 24 studies | BELLENGER16, Abstract. | Moderate (endurance only) | A rise in HRV is not always good news, and overreaching may not lower it. |
| Overreached triathletes showed **rising** weekly LnRMSSD (parasympathetic hyperactivity), with performance −9.0 ± 2.1%. | Endurance | LEMEUR13, Abstract. | Low | High readings can also signal fatigue. |
| **Strength overload** (11 sessions in 6 days): squat 1RM −4.4 kg (90% CL −7.8 to −1.0) the next day. Supine morning HR rose (d 0.36–0.50) and supine LnRMSSD fell (d −0.43 to −0.51); standing values did not change. Of 10 athletes whose 1RM fell beyond the 4.9% typical error, only 5 had a likely HR rise and 5 a likely LnRMSSD fall on single-day values (6 and 4 with 4-day averages). | 19 strength-trained athletes (≥3 years' training) | SCHNEIDER19, Abstract; Results (strength arm; individual classification). | Low (uncontrolled trial) | HR and HRV track lifting overload for the group but flag only about half the athletes whose strength actually dropped. |
| HRV-guided and predefined training did not differ in their effect on resting HR (SMD 0.04). | Endurance | MANRESA21, Results 3.4.1. | Moderate | No evidence that steering by resting HR adds anything. |
| Resting HR was recorded daily but **not used** in the decision rule. | Functional training | DEBLAUW21, §2.3.2 and §2.4. | Low | The resistance-type trial did not treat resting HR as a trigger. |

**Not addressed.** No trial used resting HR as the trigger for adjusting a session (searches on
2026-09-24: "resting heart rate guided training prescription randomized" and variants).

### 3b. Sleep loss and strength

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| **Acute sleep loss lowers strength: −2.85% (95% CI −4.47 to −1.23; I² 62.2%).** Across all performance categories the loss is −7.56% (−11.9 to −3.13). | Adults; strength 25 studies (n = 289, 74% male, 66 outcomes); all categories 77 studies (n = 959, 89% male) | CRAVEN22, Results "Strength"; "Overall Exercise Performance". | **Moderate** (one large meta-analysis, heterogeneous, mostly men; KNOWLES18 agrees on the direction) | Sleep loss costs a few percent of strength on average, driven mainly by nights without any sleep. |
| "Sleep loss" was **≤6 h of sleep in any 24 h**, against >6 h as control. Only acute (single-episode) protocols were included. About 98% of outcomes rested on sleep quantity only, often time in bed. | Same | CRAVEN22, Methods "Inclusion and Exclusion Criteria"; "Limitations and Future Direction". | Moderate (definition) | The literature's threshold is ≤6 h, and it is time-in-bed based. |
| Within strength, only **total deprivation** was significant (−3.00%; 95% CI −4.52 to −1.48). Restriction −2.77% (−6.75 to 1.21); early restriction −1.16% (−2.57 to 0.25); late restriction −4.45% (−9.30 to 0.41) (Table 2). Afternoon or evening tasks −4.58% (−7.59 to −1.58); morning effects were smaller (−1.78%; −3.22 to −0.33), and after restriction not significant (−0.43%) (Table 3). **Lower body** −3.42% (−5.54 to −1.31) vs upper body −1.63% (−3.30 to 0.04) (Table 5). | Same | CRAVEN22, Results "Strength"; Tables 2, 3 and 5 (read by the independent verification). | Low (subgroup findings) | After a night without sleep, heavy lower-body work later in the day is most affected. A restricted night alone did not reach significance. |
| Performance declined about 0.4% per hour awake after deprivation or late restriction (early waking). For strength after late restriction, −1.07% per hour (95% CI −2.05 to −0.10). | Same | CRAVEN22, Abstract; Results "Strength"; Discussion "Pattern of Sleep Loss". | Low (meta-regression) | Training soon after waking softens the effect. |
| Total deprivation had little effect on strength; **consecutive nights of restriction** could reduce force in multi-joint lifts but not single-joint ones. Motivation strategies may offset it. | 17 studies rated moderate or weak quality | KNOWLES18, Abstract. | Low (disagrees with CRAVEN22 on deprivation; abstract only) | Multi-joint lifts after several short nights are the vulnerable case. |
| Nine nights of 5 h in bed: volume load fell trivially (<1%); lower-body mean concentric velocity fell by up to 15%; squat velocity loss rose by up to 7%; session RPE rose 11%. | 10 resistance-trained women | KNOWLES22, Abstract. | Low (small crossover) | Lifting quality and effort are hit before volume. |
| Habitual short sleep is <7 h a night. A one-size recommendation such as 7–9 h is unlikely to be ideal; the panel recommends an individual approach. The effect of 1–3 nights of partial restriction on performance is unclear. | Elite athletes | WALSH21, Abstract. | Low (expert consensus) | Supports caution, not a numeric trigger. |
| Adults should sleep 7 or more hours a night on a regular basis for health. | Healthy adults | WATSON15, "Consensus Statement". | Low (consensus) | A health target, not a performance or readiness threshold. |

### 3c. Did any study adjust sessions from sleep or resting HR?

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| **No trial found that used sleep duration or resting HR as the trigger.** The closest is a multi-marker rule (nocturnal HRV, perceived fatigue and muscle soreness above 5 on a 1–7 scale, and an HR–running-speed index), used in runners. | Endurance | NUUTTILA22, Methods (paragraph setting the markers and their desirable ranges). Searches on 2026-09-24: "sleep-guided OR sleep-based training adjustment athletes randomized readiness"; "wellness questionnaire guided training readiness autoregulation randomized strength" (no qualifying hits). | Low | Sleep- or RHR-guided training is untested. |
| A self-report stress questionnaire (DALDA) guided one trial arm, against HRV-guided and predefined arms. | 36 male recreational runners; 5 weeks | FIGUEIREDO23, Abstract. The DALDA-guided arm improved most (Vpeak +8.4%, 5-km time trial −12.8%), then HRV-guided (+6.6%, −8.3%), then predefined (+4.9%, −6.0%); between-arm significance is not stated in the abstract. | Low | Subjective questionnaires are a studied alternative input, in endurance only. |

## 4. Validity of consumer wearables against reference methods (Apple Watch first)

### 4a. HRV

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| Portable devices differed from ECG by a small, highly heterogeneous amount: ES 0.23 (95% CI 0.05–0.42; I² 78.6%). Error depended on HRV metric, position and sex, but not on the device. | 23 studies to July 2017 | DOBBS19, Abstract. | Moderate (with XU26) | Small error at rest, larger in some conditions. |
| PPG pulse-rate variability vs ECG: absolute standardised error 0.188 for RMSSD (0.066–0.309) and 0.134 for SDNN (0.014–0.255). The authors say this **must not be generalised to sleep, exercise, stress or free-living use**, nor read as interchangeability. | Resting or controlled conditions; 10 studies | XU26, Abstract. | Moderate (for rest only) | Resting validity does not carry over to overnight readings. |
| **Apple Watch Series 9 and Ultra 2** (5-min morning supine Breathe session vs Polar H10 with Kubios): SDNN −8.31 ms (95% CI −11.04 to −5.59), MAE 20.46 ms, MAPE 28.88% (26.18–31.57%). Not equivalent within ±10 ms. | 39 healthy adults, 316 paired recordings over 7–14 days | OGRADY24, §2.3; §3.2; §3.2.3. | Low | Apple SDNN runs low with large individual error, even in a controlled morning recording. |
| **Apple Watch S6 overnight** (data via a third-party app): HRV −9.6 ms, absolute bias 22.5 ms, ICC 0.67, with proportional bias (from +14.6 ms at low values to −47.6 ms at high values; limits of agreement −123.6 to 28.4 ms at the high end). The sampling period was not specified. WHOOP, which supplied raw RR intervals, reached ICC 0.99. | 53 young adults, one lab night | MILLER22, §2.4.1; §3.1; §3.5; §4.2. The ECG reference was an RMSSD-type index (§2.3.2), so the comparison may mix metrics (my reading). | Low | Overnight Apple HRV is only moderately related to ECG and least accurate in people with high HRV. |
| Apple Watch S6 at rest: RR intervals and BPM near-perfect (MAPE 1.15%), but N-N-interval HRV only moderately concordant (MAPE 31.31%). | 78 adults aged 20–75 | BONNEVAL25, Abstract. | Low | The beat timing is good; the derived variability is not. |
| RR series from Apple Watch agreed with a Polar chest strap (reliability and agreement >0.9), with about 5 gaps per recording lasting 6.5 s on average. Time-domain indices were not significantly affected by the gaps. | 20 healthy volunteers, relax and mild stress | HERNANDO18, Abstract. | Low | RMSSD computed from Apple Watch RR intervals at rest may be usable. Whether HealthKit exposes those intervals for overnight readings is outside this literature. |
| Only one included study validated Apple Watch HRV. | Apple Watch | LAMBE26, Results (opening paragraph). The synthesis itself is in Supplementary Note 1, **not read**. | Low | The evidence on Apple HRV is thin. |
| Nocturnal HRV agreement differs widely by device: CCC 0.97–0.99 for Oura Gen 3 and 4, 0.94 for WHOOP, 0.87 for Garmin and 0.82 for Polar (MAPE 5.96–16.32%). | 13 adults, 536 nights; no Apple Watch | DIAL25, Abstract. | Low | Overnight HRV validity is device-specific and cannot be assumed for Apple Watch. |
| PPG is trustworthy at rest in healthy people but disagrees with ECG under physical or mental stress, above about 160 bpm, with motion and with darker skin tones. | General | ADDLEMAN24, §3 "Measurement Considerations". | Low | Use one device consistently, and only at rest. |

### 4b. Heart rate and resting heart rate

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| Apple Watch heart rate, all conditions: mean bias −0.27 bpm (95% CI −0.72 to 0.17), limits of agreement −7.19 to 6.64. **Resting HR: bias 0.21 bpm (−0.65 to 1.07), limits of agreement −8.14 to 8.56.** Third-generation sensor (Series 6 onward): limits of agreement −3.68 to 2.59. Accuracy is lower with arrhythmia and irregular movement. | 22 studies, n = 1,247 (38 studies reviewed) | LAMBE26, Results "Heart rate"; Discussion. | **Moderate** (one living meta-analysis; CHOE25 agrees on bias) | Resting HR is accurate on average, ±8 bpm per reading across devices. |
| Heart rate bias −0.12 bpm, limits of agreement −11.06 to 10.81; HR MAPE under 10% in every subgroup. | 56 studies | CHOE25, Abstract. LAMBE26 (Discussion) argues that CHOE25 pooled several estimates per study, widening these limits. | Moderate | Same direction, wider limits. |
| Morning resting HR, Apple Watch vs Polar H10: mean difference 0.08 bpm (the abstract says −0.08), MAE 3.73 bpm, MAPE 5.91%. | 39 adults | OGRADY24, §3.2; Abstract. | Low | A typical single-reading error of about 4 bpm. |
| Overnight HR, Apple Watch S6: +0.5 bpm, absolute bias 1.5 bpm, ICC 0.96, limits of agreement −3.5 to 4.6. | 53 adults | MILLER22, §3.1. | Low | Sleep HR is accurate. |
| In laboratory settings, Apple Watch and Garmin were the most accurate for heart rate. | 158 publications | FULLER20, Abstract. | Moderate (systematic review) | Consistent with LAMBE26. |

### 4c. Sleep

| Value | Applies to | Source (locator) | Certainty | Paraphrase |
|---|---|---|---|---|
| Apple Watch sleep: good separation of sleep from wake but poor staging. Its agreement with polysomnography was lower than WHOOP's, Fitbit's and Garmin's. | 3 studies, n = 221 | LAMBE26, Results "Sleep stage classification…"; Discussion. | Low (3 studies) | Sleep duration is usable; stages are not. |
| **Apple Watch S8 (native output):** sleep sensitivity 97%; two-stage agreement 93% (κ 0.60). It overestimated light sleep by 45 min and underestimated deep sleep by 43 min, wake by 7 min and WASO by 10 min. Total sleep time was within about 10 min of PSG for all devices. No Apple data were recorded for 6 of 35 participants. | 35 healthy adults aged 20–50, one 8-h inpatient night | ROBBINS24, §3.1–3.3; Discussion; limitations. | Low | Total sleep time is close in good sleepers under lab conditions; data can go missing. |
| **Apple Watch S6 (third-party app, 5-min epochs):** detected 97% of sleep epochs but only 26% of wake epochs. It overestimated total sleep time by 39.5 min (absolute bias 48.1 min), and the bias grew with poorer sleep (104.7 min down to 10.1 min). | 53 adults, 9 h in bed | MILLER22, §3.1. | Low | Apple Watch S6 sleep time, scored by a third-party app, ran 39.5 min high, more in people with less efficient sleep (one lab night each, so between people, not across one person's nights). Polar, Oura and WHOOP were within about 12 min (Table 4). Native S8 output was within about 10 min in good sleepers (ROBBINS24). |

## 5. What a defensible rule could look like

### Verdict

**The evidence does not support a readiness rule that improves strength or hypertrophy in
resistance training.** No synthesis has tested one. Three small RCTs (§1) found HRV-guided
resistance-type training matched fixed programmes but did not beat them, for strength, muscle size
and function in healthy adults.

**The evidence does not support a rule built from HealthKit's passive inputs.** No trial used SDNN,
an Apple Watch, resting HR alone or sleep duration as the trigger (§2c, §3c). HealthKit's HRV is a
sparse ultra-short SDNN whose error against a chest strap is about 20 ms, and it is not equivalent
(§4a).

**Recommendation:** keep recovery and readiness `unassessed` for passive HealthKit HRV, resting HR
and sleep.

The single cited template is DEBLAUW21. A lighter-session **proposal** can be built from it at Low
certainty, but only if the app obtains a **morning LnRMSSD** measurement comparable to the one
studied. Even then, the only honest promise is **similar gains with fewer hard sessions**, not
better gains.

### If the owner still builds a proposal rule: every number it needs

| # | Parameter | Value | Source (locator) or owner decision | Certainty | Rationale or caveat |
|---|---|---|---|---|---|
| 1 | Who is eligible | Adults 18+ with no medication known to affect cardiac rhythm or HRV and no arrhythmia; otherwise `unassessed` | **Owner decision.** Built from trial exclusions: DEBLAUW21 §2.2 (18–35; no condition or medication altering cardiac rhythm); BITTENCOURT24 "Participants" (medications affecting HRV excluded); ADDLEMAN24 §7 (beta-blockers, ACE inhibitors, contraceptives and antidepressants lower HRV); LAMBE26 (heart-rate accuracy lower with arrhythmia). | Low | Nobody outside the tested populations should get proposals. |
| 2 | Input metric | Natural-log RMSSD (LnRMSSD). **Not** HealthKit SDNN. | MANRESA21 3.2 (RMSSD in 5 of 8 trials); DEBLAUW21 §2.3.1; SHAFFER17 ("RMSSD"; "Period Length"); HIRTEN21 (Apple HRV is SDNN only). | Low | SDNN from windows of different lengths is not comparable, and no trial used it. |
| 3 | When and how measured | On waking, supine, after emptying the bladder and 5 min rest; a 1-min recording (DEBLAUW21), or 5 min as validated for Apple Watch (OGRADY24, which validated SDNN, not RMSSD). | DEBLAUW21 §2.3.1; MANRESA21 3.2 (7 of 8 trials in the morning); BUCHHEIT14 "Resting measures". **Owner decision** on the device path: RMSSD computed from the watch's RR intervals has only resting validation (HERNANDO18). | Low | An athlete-initiated morning recording, not a passive overnight value. |
| 3b | Overnight alternative | LnRMSSD over a fixed 4-h segment starting 30 min after sleep onset | NUUTTILA22 (Methods); NUUTTILA22R (Abstract). **Owner decision** whether the device qualifies: no Apple Watch validation of this exists (§4a). | Low (endurance only) | Allowed only on a device validated for nocturnal RMSSD. |
| 4 | Baseline before any proposal | 14 days | DEBLAUW21 §2.4. BITTENCOURT24 and DEOLIVEIRA19 used 5 days; NUUTTILA22 used a 4-week rolling baseline. | Low | Pick the tested template's value. Until the baseline exists, readiness stays `unassessed`. |
| 5 | Daily comparison value | 7-day rolling mean of LnRMSSD | DEBLAUW21 §2.4; MANRESA21 3.2 (three of 8 trials used a 7-day average). | Low | Smooths noise (day-to-day CV 10–20%, BUCHHEIT14). DEBLAUW21's app displays HRVdaily as 2 × LnRMSSD (§2.3.1); the scale does not affect SD bands. |
| 6 | Minimum data | At least 3 valid recordings in the 7-day window; otherwise no proposal | PLEWS14, Abstract (3 per week). The "otherwise no proposal" part is an **owner decision** under AGENTS.md rule 2. | Low | Missing data stays unknown; never fill it in. |
| 7 | No-change band | Baseline mean ± 0.5 SD | DEBLAUW21 §2.4 (SWC1); MANRESA21 3.2 (3 of 8 trials); ADDLEMAN24 §3. | Low | A convention; BUCHHEIT14 notes that no fraction has been validated. DEBLAUW21 does not state which values the SD is computed from (baseline days or rolling means): **owner decision**. |
| 8 | Moderate deviation | Outside ± 0.5 SD but within ± 1 SD: **propose** the day's session with repetitions and load reduced by 25% | DEBLAUW21 §2.4. **Owner decision** on how "load −25%" is expressed (lighter weight, or fewer reps or sets); the trial cut both reps and absolute weight. | Low | The only tested lifting-type reduction. |
| 9 | Large deviation | Outside ± 1 SD: **propose** replacing the session with 20 min of light activity, or postponing it by 24 h | DEBLAUW21 §2.4 (replace); DEOLIVEIRA19 Abstract and BITTENCOURT24 "Resistance training protocol" (postpone). **Owner decision** which to offer. | Low | Both were tested; neither improved outcomes. |
| 10 | Direction | Both directions, as in DEBLAUW21's ± bands (my reading of its text) and NUUTTILA22 (values outside the range either way counted as negative); or low-side only, as in BITTENCOURT24 (mean − 1 SD) | **Owner decision.** LEMEUR13 and BELLENGER16 show HRV can **rise** with overreaching, while BELLENGER16 also shows it rises with positive adaptation. | Low | The literature cannot say what a high reading means for one person. |
| 11 | Recalibration | Recompute the baseline after 3 weeks (15 sessions), or keep a 4-week rolling baseline | DEBLAUW21 §2.4; NUUTTILA22 (Methods). A 2-week short-term and 8-week long-term pair of limits is suggested in NUUTTILA22's Discussion (untested). | Low | Fitness gains shift HRV; a fixed baseline drifts. |
| 12 | Resting HR | Not used as a trigger | BOSQUET08 (changes within day-to-day variability); SCHNEIDER19 (flagged about half of the athletes whose strength fell); DEBLAUW21 (recorded but not used). **Owner decision.** | Low | No trial used it; no cited threshold exists. |
| 13 | Sleep | Not used as a trigger. An optional information note after a night of ≤6 h, which changes no plan, may say only that studies of acute sleep loss found strength about 3% lower on average, mainly after a night with no sleep, for lower-body lifts and for later sessions. For a short night the pooled change (−2.77%) was not statistically significant. | CRAVEN22 (definition; −2.85% overall; Tables 2, 3 and 5). Whether to show any note is an **owner decision**. Device error: MILLER22 (Apple Watch S6 via a third-party app, +39.5 min, more in people with less efficient sleep); ROBBINS24 (native S8 output within about 10 min in good sleepers). Never use sleep stages (LAMBE26; ROBBINS24; MILLER22). | Moderate (pooled sleep-loss effect); Low (a single short night; device use) | An effect size is not a tested adjustment rule, and the short-night case itself is not significant. |
| 14 | What the proposal may claim | "Similar results with less hard work"; never "better strength or size" | MANRESA21; DUKING21; DEBLAUW21; BITTENCOURT24; DEOLIVEIRA19. | Moderate (endurance); Low (lifting) | The claim has to match the evidence. |
| 15 | Expected proposal frequency | Often: roughly 13–17 of 30 sessions. DEBLAUW21 reports 17 of 30 modulated (Discussion) but 13.56 ± 0.83 fewer high-intensity days with 25.3–26.7 sessions attended (§3.4); these do not reconcile. | DEBLAUW21, Discussion; §3.4. ADDLEMAN24 §7 warns that frequent checking can itself raise anxiety and lower HRV. **Owner decision** on whether that burden is acceptable. | Low | A ±0.5 SD band on either side flags frequently. |
| 16 | Proposal lifetime | The day's session only; acceptance re-evaluates the stored request | **Owner decision** under AGENTS.md rule 3. | n/a | A proposal must not outlive the reading it came from. |

**Always true, whatever is built:** the rule reads sensor data only to *propose*. It never writes
or edits a `SetLog`, never infers RIR, effort or load from HRV, and never changes the plan without
Accept (AGENTS.md rules 2–4).

## 6. Gaps and disagreements

1. **No synthesis of HRV-guided resistance training.** The resistance-type evidence is three RCTs
   (96 people; 6–7 weeks where the length is reported), all showing no difference. Muscle CSA was
   measured only in DEOLIVEIRA19 and BITTENCOURT24. None studied
   trained lifters with a volume- or load-reducing rule.
2. **Who was in DEOLIVEIRA19?** BITTENCOURT24, from the same research group, describes the
   participants as young untrained men training three times a week (Introduction). DEBLAUW21
   describes them as young resistance-trained men (Discussion). The abstract says only "young men".
   Unresolved without the full text.
3. **Internal inconsistencies noted while reading.**
   - BITTENCOURT24 says the HRV group accumulated more volume load, but the figures it gives
     "respectively" (120,833 vs 159,174 kg) put the HRV group lower (Results, "Training frequency
     and volume load").
   - THAMM19's abstract gives the hypertrophy protocol as 70% 1RM; its Methods give 80%. Its abstract
     and conclusions report no association between HRV and force changes, yet its Results report
     pooled acute correlations (r = 0.433, p = 0.056 and r = 0.550, p = 0.012).
   - OGRADY24 gives the resting-HR mean difference as −0.08 bpm (Abstract) and 0.08 bpm (Results).
     It also calls the equivalence failure an upper-bound breach, although its interval (−11.04 to
     −5.59 ms) crosses the lower bound.
   - DEBLAUW21 describes the light session as ">50% HRR".
   - DEBLAUW21 calls its programme 9 weeks (Discussion) but 6 training weeks (Abstract, §2.1). Its
     "17 of 30" modulated sessions does not match its own figures of 13.56 fewer high-intensity days
     with 25.3–26.7 sessions attended (§3.4).
4. **Morning versus overnight.** BUCHHEIT14 treats morning HRV as the only appropriate basis for
   same-day decisions. NUUTTILA22 guided training successfully with nocturnal wrist HRV, and
   ADDLEMAN24 notes that many wearables use slow-wave sleep. No study compares morning and overnight
   guidance head to head (BUCHHEIT14 also calls the night-versus-morning comparisons limited and
   conflicting).
5. **Direction of a "bad" reading.** HRV can fall with acute fatigue (MARASINGHA22; SCHNEIDER19) and
   rise with overreaching (LEMEUR13; BELLENGER16) or with good adaptation (BELLENGER16; MANRESA21).
   PLEWS13 reports that both increases and decreases have accompanied negative adaptation in elite
   athletes. A single-direction rule is not clearly right, and nor is a bidirectional one.
6. **Acute resistance exercise hardly moves next-day HRV.** RMSSD returned to baseline within 30 min
   after heavy leg-press work (THAMM19), and HRV changes did not track neuromuscular recovery
   (THAMM19). CHEN11, with 7 weightlifters, found HF HRV and performance recovering together within
   24 h. MARASINGHA22's pooled effects describe roughly the first 30 min after exercise, not the
   next morning. HRV may therefore be a poor recovery marker for lifting specifically.
7. **Sleep syntheses disagree on total deprivation.** For strength, CRAVEN22 finds it significant
   (−3.00%). KNOWLES18 finds little effect of deprivation and places the problem in multi-night
   restriction of multi-joint lifts. CRAVEN22 excluded multi-night protocols, so its result does not
   cover the common real-world case of several short nights.
8. **Sleep evidence is time-in-bed based, mostly male, and morning-weighted.** About 98% of outcomes
   rested on sleep quantity, about 11% of participants were women, and only 8 of 227 outcomes were
   measured after 18:00 (CRAVEN22, Limitations).
9. **Apple Watch HRV is barely validated.** One HRV study sits inside LAMBE26; OGRADY24, MILLER22 and
   BONNEVAL25 each show large individual error. None validates the passive overnight HealthKit SDNN
   series as a day-to-day training signal. Sampling was sparse in HIRTEN21 (Series 4–5, 2020);
   whether newer hardware samples more often during sleep is **not addressed** by any qualifying
   source I found.
10. **Author overlap.** LAMBE26 and OGRADY24 share authors. ADDLEMAN24 has DEBLAUW21's lead author as
    a co-author. MANRESA21's authors include authors of trials it pooled. BITTENCOURT24 and
    DEOLIVEIRA19 come from the same group. None of this invalidates the work, but the independent
    evidence is thinner than the key count suggests.
11. **Heart-rate syntheses differ on the limits of agreement.** LAMBE26 reports ±7 bpm; CHOE25
    reports ±11 bpm. LAMBE26 attributes the difference to CHOE25's pooling method.
12. **Women and the menstrual cycle.** HRV varies across the cycle (ADDLEMAN24 §7). Only
    BITTENCOURT24 (older women) and part of DEBLAUW21 include women in resistance-type HRV guidance.
13. **Decision frameworks are opaque.** SCHAFFARCZYK26 (Abstract) argues that the main weakness of
    HRV-guided training is the lack of transparent, physiologically grounded rules for turning HRV
    into prescriptions, and warns against reliance on proprietary scores. This supports keeping any
    rule simple and fully cited, or not shipping one.
14. **Not addressed anywhere:**
    - inter-set rest changes;
    - hypertrophy outcomes in trained lifters under an HRV rule;
    - interventions longer than about 15 weeks (NUUTTILA22) in endurance, or 7 weeks in lifting;
    - resting-HR-guided or sleep-guided training;
    - validity of HealthKit sleep or HRV on the nights after hard lifting sessions.

## Design labels for a content bundle

If any value here moves into a bundle, the evidence gate accepts only `content.QUALIFYING_DESIGNS`.
The labels used above map to them as follows. The certainty grades above are unchanged by the
mapping.

| Keys | Label above | Bundle `design` |
|---|---|---|
| MANRESA21, DUKING21, GRANERO20, BELLENGER16, BOSQUET08, MARASINGHA22, CRAVEN22, DOBBS19, XU26, LAMBE26, CHOE25 | Systematic review and meta-analysis | `metaAnalysis` |
| KNOWLES18, FULLER20 | Systematic review | `systematicReview` |
| WATSON15 | Joint consensus statement | `positionStand` (still graded Low: panel opinion) |
| WALSH21, ADDLEMAN24, BUCHHEIT14, SHAFFER17, PLEWS13, SCHAFFARCZYK26 | Narrative review (with or without expert consensus) | `narrativeReview` |
| DEOLIVEIRA19, BITTENCOURT24, DEBLAUW21, NUUTTILA22, VESTERINEN16, KIVINIEMI07, KIVINIEMI10, FIGUEIREDO23, LEMEUR13 | RCT | `randomisedTrial` |
| THAMM19, KNOWLES22 | Randomised crossover | `crossoverTrial` |
| NUUTTILA17, SCHNEIDER19, CHEN11 | Controlled, uncontrolled or single-group trial | `nonRandomisedTrial` |
| OGRADY24, HIRTEN21, DIAL25, PLEWS14, NUUTTILA22R | Cohort, validation, observational or reliability study | `cohortStudy` |
| MILLER22, BONNEVAL25, HERNANDO18, ROBBINS24 | Cross-sectional validation | `crossSectionalStudy` |

## Re-check log

Every number used above was re-read against the source text in this session before being written
down. Sources read in full text were checked against the full text, the rest against the abstract.

| Key | Re-checked against | Rows | Result |
|---|---|---|---|
| MANRESA21 | Full text: Results 3.2, 3.4.1, 3.4.2; Discussion; Conclusions | §1, §2a, §2b, §2c, §3a, §5 | Confirmed: 8 studies, 199 participants; morning in 7 of 8; RMSSD in 5; band counts 3/3/1/1; all SMDs and CIs. |
| DUKING21 | Abstract | §1, §5 | Confirmed: all three g values and CIs; fewer moderate/high sessions. |
| DEBLAUW21 | Full text §2.3.1, §2.4, §3.3, §3.4, Discussion | §1, §2a, §2b, §3a, §5 | Confirmed: 14-day baseline; 7-day LnRMSSD; ±0.5 and ±1 SD; −25% reps and load; 20-min recovery; recalibration after 15 sessions; −13.56 ± 0.83 high-intensity days; "17 of 30 sessions modulated" is in the Discussion but conflicts with §3.4 (§6.3). |
| BITTENCOURT24 | Full text Methods, Results, Table 1 | §1, §2b, §5 | Confirmed: mean − 1 SD; 5-day baseline; 27 vs 21 sessions; CSA ES −0.06; 1RM percentages; row order inferred from the Table 1 footnote by the independent verification. |
| DEOLIVEIRA19 | Abstract | §1, §2b, §6 | Confirmed: n = 20; +30% vs +42% 1RM; +15.7% vs +15.8% CSA; 24 h postponement. |
| NUUTTILA22 | Full text Methods, Results, Discussion | §2a, §2b, §2c, §3c, §5 | Confirmed: 4-week rolling ± 0.5 × SD; Polar Vantage V2 4-h segment; −6.2 vs −2.9% 10-km; 55/35/10% adjustments. The Figure 1 rule is not verified. |
| CRAVEN22 | Full text Results "Strength", Methods, Limitations | §3b, §5, §6 | Confirmed: −2.85% (−4.47 to −1.23), I² 62.2%, n = 289; deprivation −3.00%; −1.07%/h; ≤6 h definition; 98%, 11% and 8/227 figures. |
| SCHNEIDER19 | Full text Results (strength arm) | §2a, §3a, §5, §6 | Confirmed: −4.4 kg; d ranges; 5/5 and 6/4 individual counts; 4.9% typical error. |
| OGRADY24 | Full text §3.2 | §2c, §4a, §4b, §6 | Confirmed: −8.31 ms; MAE 20.46 ms; MAPE 28.88%; resting HR 0.08 vs −0.08 inconsistency. |
| MILLER22 | Full text §3.1 | §4a, §4b, §4c, §5 | Confirmed: HRV −9.6 ms and ICC 0.67; HR +0.5 bpm; TST +39.5 min; 26% wake detection. |
| ROBBINS24 | Full text §3–3.3, Discussion | §4c, §5 | Confirmed: 97%; κ 0.60; −43 and +45 min; 6 of 35 missing. |
| LAMBE26 | Full text Results, Discussion | §4a, §4b, §4c, §6 | Confirmed: −0.27 bpm (−7.19 to 6.64); resting 0.21 bpm (−8.14 to 8.56); third-generation −3.68 to 2.59; one HRV study; 3 sleep studies. |
| HIRTEN21 | Full text Methods, Results, Limitations | §2c, §6 | Confirmed: SDNN only; about 60-s windows; median 28 samples over median 42 days. |
| BUCHHEIT14 | Full text Table 1, SWC and decision sections | §2a, §2b, §2c, §5, §6 | Confirmed as read from flattened Table 1: CV about 12% and about 10%; SWC about +3% and about −2%. |
| SHAFFER17 · ADDLEMAN24 · THAMM19 | Full text, named sections | §2c, §3a, §4a, §5, §6 | Confirmed. |
| All abstract-only keys | Abstracts as fetched on 2026-09-24 | as cited | Confirmed against the abstract text; anything beyond it is marked unverified. |

## Independent verification

A second agent, separate from the one that wrote this file, checked it against the papers on
2026-09-24. It did not edit the file; its corrections were applied afterwards.

- **Read in full text (PMC or Europe PMC):** DEBLAUW21, BITTENCOURT24, CRAVEN22, MILLER22,
  OGRADY24, HIRTEN21, ROBBINS24, LAMBE26, MANRESA21, ADDLEMAN24, NUUTTILA22 and SCHNEIDER19. Sixteen
  more were checked against their PubMed abstracts.
- **Identifiers:** all 43 DOI and PMID pairs match their PubMed records and resolve at doi.org. None
  is a preprint. None is retracted; the positive control (PMID 31188644) was returned by the same
  search. BOSQUET08 has an erratum that could not be read.
- **Certainty and copying:** every Moderate grade rests on a systematic review or meta-analysis, and
  nothing is graded High. An automated check for any 9-word run shared with the sources found only
  titles, author lists, section names and numbers.
- **Verdict:**
  - The conclusion to keep readiness `unassessed` for passive HealthKit inputs is **supported**.
  - DEBLAUW21 as a Low-certainty template is **supported with corrections**: the input, bands,
    actions, recalibration and outcome are confirmed, but its proposal frequency is internally
    inconsistent (§6.3).
  - The former sleep line ("one short night lowers strength by about 3%") was **not supported** and
    has been corrected: the short-night estimate is not significant (§3b, §5 row 13).
- **Corrections applied:**
  - the sleep effect split by deprivation and restriction, with CRAVEN22's Tables 2, 3 and 5;
  - Apple Watch sleep overestimation narrowed to the S6 with a third-party app;
  - muscle CSA limited to the two trials that measured it;
  - DEBLAUW21's "17 of 30" flagged as not matching its own figures;
  - BITTENCOURT24's 1RM rows assigned;
  - FIGUEIREDO23's year and results, WALSH21's volume and pages, and BOSQUET08's erratum;
  - the scope of "matched, never beat" limited to strength, size and function in healthy adults;
  - the bundle design labels above.
- **Absence claims re-searched on PubMed.** No paper contradicts them:
  - HRV-guided or individualised resistance, strength or hypertrophy training, with and without
    systematic-review and meta-analysis filters (0–9 hits each; only DEOLIVEIRA19, BITTENCOURT24 and
    DEBLAUW21 among resistance trials, and endurance-only syntheses);
  - readiness or autoregulation with wearables (Apple Watch, WHOOP, Oura), HealthKit or Apple
    Health (0–5 hits; no trials);
  - resting-HR-guided and sleep-guided training adjustment (0 hits);
  - Apple Watch HRV validation (14 hits; nothing beyond the sources above).
- **Could not access:**
  - DEOLIVEIRA19 full text (publisher returned HTTP 403; not in PMC), so its participants'
    training status stays unresolved;
  - the BOSQUET08 erratum (HTTP 403);
  - DEBLAUW21's tables and figures, which did not come through in the PMC text;
  - LAMBE26's Supplementary Note 1, whose one HRV study is OGRADY24 itself.
