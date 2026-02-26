from fastapi import APIRouter, UploadFile, Depends, HTTPException, File, BackgroundTasks
from typing import List, Optional
import asyncio
from bson import ObjectId
from datetime import datetime
import logging

from ..auth import get_current_user
from ..database import documents_collection
from ..services.storage_service import StorageService, DuplicateFileError
from ..services.gemini_service import GeminiService
from ..config import settings

router = APIRouter()
gemini = GeminiService()

# =========================
# BRSR SECTION A PROMPT
# =========================

GEMINI_API_KEY = settings.GEMINI_API_KEY  # or paste directly (not recommended)
MODEL_NAME = "gemini-2.5-flash"  # fast + cheap, enough for extraction

PROMPT = """
You are a regulatory document extraction engine.

You are given a full PDF of a SEBI Business Responsibility and Sustainability Report (BRSR).

Your task is to extract ONLY SECTION A – GENERAL DISCLOSURES.

Extract ONLY the exact fields shown in the Annexure II template below.
Ignore everything else.

DO NOT extract Section B or Section C.

### ------------------------------------------
### STRICT EXTRACTION RULES
### ------------------------------------------

1. Extract values exactly as written in the PDF.
2. Do NOT summarize.
3. Do NOT infer.
4. Do NOT calculate derived fields.
5. If a value is explicitly written as:
   * "N/A", "NA", "Not Applicable" -> return "N/A"
   * "0" -> return 0
   * "Nil" -> return 0 (only for numeric fields)
   * "-" -> treat as not available -> return "N/A" (for strings) or 0 (for numbers)
6. If a field is explicitly present but blank in the PDF -> return null for numeric fields and "N/A" for string fields.
7. If a field is genuinely not mentioned anywhere in the PDF:
   * Return null for numeric fields.
   * Return "N/A" for string fields.
8. Preserve numeric values exactly as written (do not reformat commas or decimals).
9. Do NOT change field names.
10. Do NOT add extra keys.
11. Do NOT remove keys.
12. Output ONLY valid JSON.
13. Do NOT leave string fields as empty strings "" unless the PDF explicitly shows it as blank.

---

### ------------------------------------------
### CONFIDENCE SCORE CALCULATION 
### ------------------------------------------

After extraction, calculate confidence_score (0-100) using the following logic:

1. Total required fields in template = 103.
2. Count as "field_with_value" if:
   * Field has an actual extracted value.
   * Field explicitly contains "N/A", "0", "Nil", or null because the PDF explicitly states it or clearly does not provide that data.
3. Do NOT penalize fields that are:
   * Not mentioned in the PDF at all.
   * Clearly not applicable based on the document.
4. Only reduce confidence if:
   * A field should logically exist in Section A but extraction failed.
   * The value was partially extracted or malformed.
5. Formula:
   confidence_score = (fields_correctly_extracted / total_fields) x 100
6. Round to nearest integer.
7. Assign this score to "confidence_score".

Important:
* Do NOT reduce confidence for legitimate null, N/A, or zero values.
* Do NOT reduce confidence for optional subsections not present in the document.

---

### ------------------------------------------
### FIELD VALUE HANDLING SUMMARY
### ------------------------------------------

| PDF Value                     | Return                          |
| ----------------------------- | ------------------------------- |
| N/A / NA / Not Applicable     | "N/A"                           |
| 0                             | 0                               |
| Nil                           | 0 (numeric fields only)         |
| Explicit blank field          | null (numeric) / "N/A" (string) |
| Field not present in document | null (numeric) / "N/A" (string) |
| Actual value found            | Exact extracted value           |
| Not found at all              | "Not found in the pdf"          |

------------------------------------------
FIELDS TO EXTRACT (ONLY THESE)
------------------------------------------

1. Corporate Identity Number (CIN)
2. Name of Listed Entity
3. Year of Incorporation
4. Registered office address
5. Corporate office address
6. Email ID
7. Telephone number
8. Website
9. Financial Year for which reporting is being done
  - If the financial year is written in any of the following formats:
    - 2022-2023
    - 2022-23
    - FY 2022-2023
    - FY22-23
    - FY 22-23
    - Financial Year 2022-23
    - For the year ended 31 March 2023
    - Year ended March 31, 2023
  → Return strictly in this format:
  "2022-23"
---

### 10. Stock Exchange Listing (Normalized Output Required)

Extract stock exchange listing information and normalize the output using the rules below:

#### Normalization Rules:

1. If any variation of BSE is found (including but not limited to):

  * "BSE"
  * "BSE Ltd"
  * "BSE Limited"
  * "Bombay Stock Exchange"
  * "Bombay Stock Exchange Limited"

  → Return exactly: "BSE"

2. If any variation of NSE is found (including but not limited to):

  * "NSE"
  * "NSE Ltd"
  * "NSE Limited"
  * "National Stock Exchange"
  * "National Stock Exchange of India Limited"

  → Return exactly: "NSE"

3. If both NSE and BSE are mentioned in any format:

  → Return exactly: "BSE NSE"

  (Always return in this order: BSE first, then NSE)

4. If other stock exchanges are mentioned (e.g., international exchanges):

  * Include them after BSE/NSE (if present)
  * Separate values using a single space
  * Preserve their original name as written (no reformatting)

  Example:

  * If listed on NSE and London Stock Exchange
    → "NSE London Stock Exchange"

  * If listed on BSE, NSE and NYSE
    → "BSE NSE NYSE"

5. If only other stock exchanges are mentioned (no NSE or BSE):

  * Return them exactly as written, separated by a single space.

6. If explicitly stated as not listed:

  * Return "None"

7. If the field is not mentioned in the document:

  * Return "N/A"

#### Output Type:

* Must be a string.
* Do NOT return arrays.
* Do NOT return null.
* Do NOT return empty string unless explicitly blank in PDF.

---
11. Paid-up Capital
12. Name and contact details of the person who may be contacted in case of any queries on the BRSR report
13. Reporting boundary
14. Name of assurance provider
15. Type of assurance

16. Business Activity
  - Description of main business activity(ies) of the entity
  - Description of Business Activity
  - % of Turnover of the entity

17. Products/Services (90% of turnover)
  - Product/Service
  - NIC code
  - % of Total Turnover Contributed

18. Number of locations
    - No of plants (National)
    - No of offices (National)
    - No of plants (International)
    - No of offices (International)

19. Markets served
  - International markets served (No. of Countries)
  - Contribution of exports (% of total revenue)
  - A brief on types of customers

20. Employees and Workers (including differently abled)
  A. Employees
    - Total permanent employees (D)
    - Permanent male employees
    - Permanent female employees
    - Employees other than permanent (E)
    - Male employees other than permanent
    - Female employees other than permanent
    - Total employees (D + E)
    - Total male employees
    - Total female employees
  B. Workers
    - Permanent workers
    - Permanent male workers
    - Permanent female workers
    - Workers other than permanent
    - Male workers other than permanent
    - Female workers other than permanent
    - Total workers
    - Total male workers
    - Total female workers
  C. Differently abled employees and workers
    Employees
      - Total differently abled permanent employees
      - Differently abled permanent male employees
      - Differently abled permanent female employees
      - Differently abled employees other than permanent
      - Differently abled male employees other than permanent
      - Differently abled female employees other than permanent
      - Total differently abled employees (D + E)
      - Total differently abled male employees
      - Total differently abled female employees
    Workers
      - Permanent differently abled workers (F)
      - Permanent differently abled male workers
      - Permanent differently abled female workers
      - Differently abled workers other than permanent (G)
      - Differently abled male workers other than permanent
      - Differently abled female workers other than permanent
      - Total differently abled workers (F + G)
      - Total differently abled male workers
      - Total differently abled female workers

21. Participation/Representation of women
    - Board of Directors (Total number)
    - Board of Directors (No. of women)
    - Key Managerial Personnel (Total number)
    - Key Managerial Personnel (No. of women)

22. Turnover rate for permanent employees and workers
    - Permanent Employees (Male, Female, Total)
    - Permanent Workers (Male, Female, Total)

23. Names of holding/subsidiary/associate companies/joint ventures
  - Name of entity
  - Type of entity (Holding/Subsidiary/Associate/Joint Venture)
  - % of shares held by listed entity

24. CSR
    - Is CSR applicable?
    - Turnover (INR Cr)
      - If not in Cr then convert to Cr using the financial figures mentioned in the report (e.g. if turnover is given as 5000 lakhs, convert to 500 Cr)
    - Net Worth (INR Cr)
      - If not in Cr then convert to Cr using the financial figures mentioned in the report (e.g. if net worth is given as 2000 lakhs, convert to 200 Cr)
      
25. Grievance Redressal
    - Mechanism in place?
    - Number of complaints filed (by stakeholder)
    - Number of complaints pending (by stakeholder)

26. Identified material risks & opportunities
  For each of Environment, Social, Governance capture an array of items with:
    - Material Issue Identified
    - Risk/Opportunity
    - Rationale
    - Financial Implications (Negative/Positive)

------------------------------------------
REQUIRED OUTPUT FORMAT (STRICT)
------------------------------------------

Return ONLY this JSON structure:

{
  "section": "A",
  "confidence_score": null,

  "entity_details": {
    "cin": "",
    "name": "",
    "year_of_incorporation": null,
    "registered_office_address": "",
    "corporate_office_address": "",
    "email": "",
    "telephone": "",
    "website": "",
    "financial_year": "",
    "stock_exchange_listing": "N/A",
    "paid_up_capital": null,
    "contact_person_details": "",
    "reporting_boundary": "",
    "assurance_provider": "",
    "assurance_type": "",
    "sector": ""
  },

  "business_activity": {
    "main_activity_description": "",
    "description": "",
    "percent_of_turnover": null
  },

  "products_services": [
    {
      "product_service": "",
      "nic_code": "",
      "percent_of_total_turnover": null
    }
  ],

  "locations": {
    "national_plants": null,
    "national_offices": null,
    "international_plants": null,
    "international_offices": null
  },

  "markets_served": {
    "international_countries": null,
    "export_percent": null,
    "customers_brief": ""
  },

  "employees": {
    "employees": {
      "total_permanent": null,
      "permanent_male": null,
      "permanent_female": null,
      "other_than_permanent": null,
      "other_than_permanent_male": null,
      "other_than_permanent_female": null,
      "total_employees": null,
      "total_male": null,
      "total_female": null
    },
    "workers": {
      "total_permanent": null,
      "permanent_male": null,
      "permanent_female": null,
      "other_than_permanent": null,
      "other_than_permanent_male": null,
      "other_than_permanent_female": null,
      "total_workers": null,
      "total_male": null,
      "total_female": null
    },
    "differently_abled_employees": {
      "total_permanent": null,
      "permanent_male": null,
      "permanent_female": null,
      "other_than_permanent": null,
      "other_than_permanent_male": null,
      "other_than_permanent_female": null,
      "total_employees": null,
      "total_male": null,
      "total_female": null
    },
    "differently_abled_workers": {
      "total_permanent": null,
      "permanent_male": null,
      "permanent_female": null,
      "other_than_permanent": null,
      "other_than_permanent_male": null,
      "other_than_permanent_female": null,
      "total_workers": null,
      "total_male": null,
      "total_female": null
    }
  },

  "women_representation": {
    "board_of_directors_total": null,
    "board_of_directors_women": null,
    "kmp_total": null,
    "kmp_women": null
  },

  "turnover_rate": {
    "permanent_employees": {
      "male": null,
      "female": null,
      "total": null
    },
    "permanent_workers": {
      "male": null,
      "female": null,
      "total": null
    }
  },

  "holding_subsidiaries": [
    {
      "name": "",
      "type": "",
      "percent_shares_held": null
    }
  ],

  "csr": {
    "is_applicable": "",
    "turnover_inr_cr": null,
    "net_worth_inr_cr": null
  },

  "grievances": {
    "mechanism_in_place": {
      "communities": "Yes/No",
      "investors_other_than_shareholders": "Yes/No",
      "shareholders": "Yes/No",
      "employees_and_workers": "Yes/No",
      "customers": "Yes/No",
      "value_chain_partners": "Yes/No",
      "other_please_specify": "Yes/No"
    },    
    "filed": {},
    "pending": {}
  },

  "material_risks_opportunities": {
    "environment": [
      {
        "material_issue": "",
        "risk_or_opportunity": "",
        "rationale": "",
        "financial_implications": ""
      }
    ],
    "social": [
      {
        "material_issue": "",
        "risk_or_opportunity": "",
        "rationale": "",
        "financial_implications": ""
      }
    ],
    "governance": [
      {
        "material_issue": "",
        "risk_or_opportunity": "",
        "rationale": "",
        "financial_implications": ""
      }
    ]
  }
}

------------------------------------------
CONFIDENCE SCORE CALCULATION
------------------------------------------

After extraction, calculate a confidence_score (0-100) based on:
- Count total required fields in the template: 103
- Count fields that have actual values from the PDF (not empty strings or null)
- If a field is legitimately not mentioned in the PDF, do NOT count it as missing
- confidence_score = (fields_with_values / total_fields) * 100
- Round to nearest integer
- Assign this score as "confidence_score" in the output

------------------------------------------
SECTOR CLASSIFICATION
------------------------------------------
- Classify the sector from business activity and products/services into one of these exact values only (Agriculture, Auto ancillary, Aviation, Building materials, Chemicals, Consumer durables, Dairy products, Defence, Diversified, Education & training, Energy, Engineering & capital goods, FMCG, Fertilizers, Financial services, Healthcare, IT, Logistics, Media & entertainment, Metals, Miscellaneous, NBFC, Packaging, Plastic pipes, Real estate, Retail, Services, Silver, Software services, Solar panel, Telecom, Textiles, Tourism & hospitality, Trading)
- Include it under "entity_details" as "sector"

------------------------------------------
IMPORTANT:
------------------------------------------
- Do not change key names.
- Do not add keys.
- Do not remove keys.
- Do not nest differently.
- Output ONLY valid JSON.
"""

# =========================
# UPLOAD + PARSE ENDPOINT
# =========================

@router.post("/")
async def upload_pdfs(
  files: Optional[List[UploadFile]] = File(None),
  file: Optional[UploadFile] = File(None),
  background_tasks: BackgroundTasks = None,
  user=Depends(get_current_user)
):
  """Accept multiple PDF files, upload each to Supabase, create a document
  record with status `pending`, return their IDs and file URLs immediately,
  and process each file in background to extract JSON via Gemini and update
  the document status.
  """
  try:
    # Accept both multipart field names:
    # - files: multiple
    # - file: single
    upload_list: List[UploadFile] = list(files or [])
    if file is not None:
      upload_list.append(file)

    if not upload_list:
      raise HTTPException(status_code=400, detail="No files uploaded")

    coll = documents_collection()
    created = []
    skipped_duplicates = []
    skipped_invalid = []

    async def _process_and_update(doc_id, file_bytes):
      try:
        parsed = await gemini.extract_section_a(file_bytes, PROMPT)
        update = {
          "status": "completed",
          "extracted_json": parsed,
          "parsed_at": datetime.utcnow()
        }
      except Exception as e:
        logging.exception("Gemini extraction failed for %s", doc_id)
        update = {
          "status": "failed",
          "error_message": str(e),
          "parsed_at": datetime.utcnow()
        }
      try:
        await coll.update_one({"_id": ObjectId(doc_id)}, {"$set": update})
      except Exception:
        logging.exception("Failed to update document %s", doc_id)

    for uploaded_file in upload_list:
      file_name = (uploaded_file.filename or "").strip()

      if not file_name.lower().endswith(".pdf"):
        skipped_invalid.append(file_name or "unknown")
        continue

      file_bytes = await uploaded_file.read()
      if not file_bytes:
        skipped_invalid.append(file_name)
        continue

      existing_doc = await coll.find_one(
        {"user_id": user["sub"], "file_name": file_name},
        {"_id": 1}
      )
      if existing_doc:
        skipped_duplicates.append(file_name)
        continue

      # Upload to Supabase
      file_path = f"{user['sub']}_{file_name}"
      try:
        file_url = await StorageService.upload_file(
          file_bytes=file_bytes,
          file_path=file_path
        )
      except DuplicateFileError:
        skipped_duplicates.append(file_name)
        continue

      if not file_url:
        logging.error("Failed to upload file %s for user %s", file_name, user["sub"])
        continue

      # Create DB record with status pending
      document = {
        "user_id": user["sub"],
        "file_name": file_name,
        "file_url": file_url,
        "status": "pending",
        "created_at": datetime.utcnow()
      }
      res = await coll.insert_one(document)
      doc_id = str(res.inserted_id)
      created.append({"document_id": doc_id, "file_url": file_url, "file_name": file_name})

      # schedule background processing
      # use asyncio.create_task to run async worker without blocking response
      asyncio.create_task(_process_and_update(doc_id, file_bytes))

    return {
      "message": "Files received",
      "documents": created,
      "skipped_duplicates": skipped_duplicates,
      "skipped_invalid": skipped_invalid,
    }

  except HTTPException:
    raise

  except Exception as e:
    logging.exception("Upload failed")
    raise HTTPException(status_code=500, detail=str(e))
