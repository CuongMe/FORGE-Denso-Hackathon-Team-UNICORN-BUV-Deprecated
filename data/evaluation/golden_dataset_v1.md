# Golden Dataset v1

Human-review checklist for the evaluation cases in [golden_dataset_v1.jsonl](./golden_dataset_v1.jsonl).

- **Cases:** 30
- **Sign-off rule:** check a case only after the expected answer and supporting evidence have been verified by a human reviewer.
- **Ground truth:** the expected answer is part of each evaluated test case.

| Check | ID | Question | Type | Lang | Answerable | Expected answer | Gold evidence | Sign-off |
|---|---|---|---|---|---|---|---|---|
| [ ] | G001 | What is the target torque for the M6 bolts? | numeric_lookup | EN | Yes | 9.5 Â± 0.5 NÂ·m | WI-ASSY-001 · p.1 · Critical specifications - M6 bolt torque | Pending |
| [ ] | G002 | Which tightening sequence is required? | ordered_procedure | EN | Yes | 1-3-2-4 | WI-ASSY-001 · p.1 · Critical specifications - Bolt sequence | Pending |
| [ ] | G003 | What happens if a torque is outside range? | procedure | EN | Yes | Place the unit in the red quarantine tray and notify the team leader. | WI-ASSY-001 · p.1 · Procedure - Step 6 | Pending |
| [ ] | G004 | Trong bao lÃ¢u pháº£i thÃ´ng bÃ¡o trÆ°á»Ÿng nhÃ³m? | bilingual_retrieval | VI | Yes | Trong vÃ²ng 10 phÃºt. | SOP-QLT-014 · p.1 · Procedure - Step 4 | Pending |
| [ ] | G005 | When must an NCR be created? | conditional_procedure | EN | Yes | Within 30 minutes for a Critical defect or when defect quantity is 3 or more. | SOP-QLT-014 · p.1 · Procedure - Step 5 | Pending |
| [ ] | G006 | What is defect code D07? | bilingual_table_lookup | EN | Yes | Bent terminal / ChÃ¢n terminal cong. | SOP-QLT-014 · p.1 · Defect criteria table - D07 | Pending |
| [ ] | G007 | What is the acceptable air pressure? | numeric_lookup | EN | Yes | 0.50-0.60 MPa | MAINT-CHK-007 · p.1 · Preventive maintenance checklist - Air pressure | Pending |
| [ ] | G009 | Ãp suáº¥t khÃ­ pháº£i báº±ng bao nhiÃªu trÆ°á»›c khi xÃ¡c nháº­n zero energy? | bilingual_numeric_lookup | VI | Yes | 0 MPa | EHS-ALERT-003 · p.1 · LOTO steps - Step 5 | Pending |
| [ ] | G010 | Who may perform LOTO? | policy_lookup | EN | Yes | Only trained and authorized personnel. | EHS-ALERT-003 · p.1 · Warning | Pending |
| [ ] | G011 | What lot is affected? | field_extraction | EN | Yes | L260915-B | QMS-NCR-011 · p.1 · Nonconformance details - Lot | Pending |
| [ ] | G012 | How many pieces are affected? | numeric_field_extraction | EN | Yes | 24 pieces | QMS-NCR-011 · p.1 · Nonconformance details - Affected quantity | Pending |
| [ ] | G013 | What is the terminal height specification? | numeric_range_lookup | EN | Yes | 1.80-1.90 mm | QMS-NCR-011 · p.1 · Nonconformance details - Specification | Pending |
| [ ] | G015 | What caused the downtime? | causal_lookup | EN | Yes | Sensor S12 false trigger. | PROD-HO-20260915 · p.1 · Shift 1 performance - Downtime | Pending |
| [ ] | G016 | When is the next maintenance window for SP-04? | date_time_lookup | EN | Yes | 2026-09-16 09:30 for 20 minutes. | PROD-HO-20260915 · p.1 · Open items for Shift 2 - Maintenance window | Pending |
| [ ] | G018 | Which box IDs contain TM-1552? | table_lookup | EN | Yes | BX007-BX010 | SUP-PACK-20260915 · p.1 · Package contents - TM-1552 | Pending |
| [ ] | G019 | Which Andon fault had the longest unplanned downtime? | ranking_reasoning | EN | Yes | A-214 at Station S40 with 8 minutes. | ANDON-DAILY-20260915 · p.1 · Andon events and summary | Pending |
| [ ] | G020 | What was the measured air pressure on the start-up check sheet? | visual_ocr_numeric | EN | Yes | 0.54 MPa | IMG-CHECK-001 · p.1 · Daily start-up check sheet - Air pressure row | Pending |
| [ ] | G021 | What is alarm E-214? | visual_ocr_lookup | EN | Yes | Vision camera no trigger. | IMG-HMI-001 · p.1 · HMI alarm banner | Pending |
| [ ] | G022 | What is the pallet quantity? | visual_layout_lookup | EN | Yes | 600 pcs | IMG-LABEL-001 · p.1 · Traceability / pallet label - Quantity field | Pending |
| [ ] | G023 | Tá»‘c Ä‘á»™ giá»›i háº¡n cá»§a xe nÃ¢ng trong xÆ°á»Ÿng lÃ  bao nhiÃªu? | visual_bilingual_numeric | VI | Yes | 8 km/h | IMG-SAFE-001 · p.1 · Forklift safety poster - Rule 1 | Pending |
| [ ] | G024 | What was the actual output in the 10:00-11:00 hour? | spreadsheet_row_lookup | EN | Yes | 655 pcs | TBL-PROD-001 · p.? · Production log row: 2026-09-15, Shift 1, Line A3, 10:00-11:00 | Pending |
| [ ] | G025 | Which hour had the highest scrap percentage? | spreadsheet_derived_ranking | EN | Yes | 10:00-11:00, at approximately 1.07% (7 scrap pieces out of 655 actual pieces). | TBL-PROD-001 · p.? · Production log scrap percentage comparison | Pending |
| [ ] | G026 | What action closed the barcode read retries issue? | spreadsheet_row_lookup | EN | Yes | Cleaned the scanner window and retaught focus. | TBL-MNT-001 · p.? · Maintenance history row: 2026-08-29, VIS-A3-02 | Pending |
| [ ] | G027 | Which asset is under monitoring after the September 15 corrective work? | spreadsheet_filtered_lookup | EN | Yes | VIS-A3-02, the Vision Inspector V2. | TBL-MNT-001 · p.? · Maintenance history row: 2026-09-15, Sensor S12 false trigger | Pending |
| [ ] | G028 | Which samples failed terminal height inspection? | spreadsheet_filtered_lookup | EN | Yes | S04 at 1.79 mm, S05 at 1.72 mm, and S09 at 1.76 mm. | TBL-QLT-001 · p.? · Quality inspection row: Sample S04 | Pending |
| [ ] | G029 | What is the acceptance criterion for defect code D21? | csv_row_lookup | EN | Yes | Barcode/QR not readable after 2 attempts. | TBL-DEF-001 · p.? · Defect catalog row: D21 | Pending |
| [ ] | G030 | What is the Vietnamese term for torque? | bilingual_dictionary_lookup | EN | Yes | mÃ´-men siáº¿t | TBL-DICT-001 · p.? · Bilingual term dictionary row: T003 | Pending |
| [ ] | G032 | What was the total actual output recorded in the hourly production log? | spreadsheet_aggregation | EN | Yes | 4,820 pcs | TBL-PROD-001 · p.? · Production log rows for Shift 1, Line A3 | Pending |
| [ ] | G033 | What was the total downtime recorded in the hourly production log? | spreadsheet_aggregation | EN | Yes | 18 minutes | TBL-PROD-001 · p.? · Production log rows for Shift 1, Line A3 | Pending |
| [ ] | G034 | What equipment issue appears in both the shift handover and maintenance history, and what was the immediate action? | cross_document_reasoning | EN | Yes | The Sensor S12 false trigger on Vision Inspector V2 / VIS-A3-02; the connector was reseated and the next shift was asked to monitor it. | PROD-HO-20260915 · p.1 · Open items for Shift 2 | Pending |

