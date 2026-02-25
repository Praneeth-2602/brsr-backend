from fastapi import APIRouter, UploadFile, Depends, HTTPException, File, BackgroundTasks
from typing import List, Optional
import asyncio
from bson import ObjectId
from datetime import datetime
import logging

from ..auth import get_current_user
from ..database import documents_collection
from ..services.storage_service import StorageService
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

------------------------------------------
STRICT EXTRACTION RULES
------------------------------------------

1. Extract values exactly as written.
2. Do NOT summarize.
3. Do NOT infer.
4. Do NOT calculate derived fields.
5. If value not found:
  - Use "" for strings
  - Use null for numeric values
6. Preserve numeric values without formatting changes.
7. Do NOT change field names.
8. Do NOT add extra keys.
9. Output ONLY valid JSON.
10. Follow the example JSON structure exactly.

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
10. Stock Exchange Listing
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
    - Net Worth (INR Cr)

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
    "stock_exchange_listing": "",
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
      if not uploaded_file.filename.lower().endswith(".pdf"):
        continue

      file_bytes = await uploaded_file.read()
      if not file_bytes:
        continue

      # Upload to Supabase
      file_path = f"{user['sub']}_{uploaded_file.filename}"
      file_url = await StorageService.upload_file(
        file_bytes=file_bytes,
        file_path=file_path
      )

      if not file_url:
        logging.error("Failed to upload file %s for user %s", uploaded_file.filename, user["sub"])
        continue

      # Create DB record with status pending
      document = {
        "user_id": user["sub"],
        "file_name": uploaded_file.filename,
        "file_url": file_url,
        "status": "pending",
        "created_at": datetime.utcnow()
      }
      res = await coll.insert_one(document)
      doc_id = str(res.inserted_id)
      created.append({"document_id": doc_id, "file_url": file_url, "file_name": uploaded_file.filename})

      # schedule background processing
      # use asyncio.create_task to run async worker without blocking response
      asyncio.create_task(_process_and_update(doc_id, file_bytes))

    return {"message": "Files received", "documents": created}

  except Exception as e:
    logging.exception("Upload failed")
    raise HTTPException(status_code=500, detail=str(e))
