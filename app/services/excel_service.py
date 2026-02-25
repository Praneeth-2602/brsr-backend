import io
import json
import pandas as pd
from typing import List, Dict, Any, Optional
import glob

# Optional: supabase client for cloud uploads. Keep import local in functions
# to avoid hard dependency if not used at runtime.


class ExcelService:
    """Service helpers to build a BRSR-style Excel and return either a file
    on disk or in-memory bytes suitable for returning from a web handler.

    Important: avoid using `os` for cloud-hosting flows; use in-memory bytes
    (`io.BytesIO`) and stream those to the client (Flask/FastAPI, etc.).
    """

    @staticmethod
    def load_json(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def safe_get(d, *keys):
        for k in keys:
            if d is None:
                return None
            d = d.get(k)
        return d

    @staticmethod
    def map_group_entity_type(raw: Optional[str]) -> str:
        if not raw:
            return ""
        key = raw.strip().lower()
        mapping = {
            "associate": "Associate Company",
            "associate company": "Associate Company",
            "joint venture": "Joint Venture",
            "subsidiary": "Subsidiary Company",
            "subsidiary company": "Subsidiary Company",
            "material wholly owned subsidiary": "Wholly Owned Subsidiary",
            "step down wholly owned subsidiary": "Wholly Owned Subsidiary",
            "wholly owned subsidiary": "Wholly Owned Subsidiary",
            "holding": "Holding Company",
            "intermediary holding": "Intermediary Holding Company",
            "ultimate holding": "Ultimate Holding Company",
            "step-down subsidiary": "Step-Down Subsidiary",
            "subsidiary (incorporated under section 8 of the companies act, 2013)": "Subsidiary Company",
        }
        if key in mapping:
            return mapping[key]
        if "wholly owned" in key:
            return "Wholly Owned Subsidiary"
        if "ultimate holding" in key:
            return "Ultimate Holding Company"
        if "intermediary" in key and "holding" in key:
            return "Intermediary Holding Company"
        if "associate" in key:
            return "Associate Company"
        if "joint" in key and "venture" in key:
            return "Joint Venture"
        if key == "holding" or key.endswith(" holding"):
            return "Holding Company"
        if "subsidiary" in key:
            return "Subsidiary Company"
        return raw.strip()

    @staticmethod
    def build_base_row(data: Dict[str, Any]) -> Dict[str, Any]:
        entity = data.get("entity_details", {})
        business = data.get("business_activity", {})
        products = data.get("products_services", [])
        locations = data.get("locations", {})
        markets = data.get("markets_served", {})
        employees = data.get("employees", {})
        women = data.get("women_representation", {})
        turnover = data.get("turnover_rate", {})
        csr = data.get("csr", {})
        grievances = data.get("grievances", {})

        product = products[0] if products else {}
        row: Dict[str, Any] = {}

        # core fields (1-15)
        row["Sector"] = entity.get("sector")
        row["1. Corporate Identity Number (CIN)"] = entity.get("cin")
        row["2. Name of Listed Entity"] = entity.get("name")
        row["3. Year of Incorporation"] = entity.get("year_of_incorporation")
        row["4. Registered office address"] = entity.get("registered_office_address")
        row["5. Corporate office address"] = entity.get("corporate_office_address")
        row["6. Email ID"] = entity.get("email")
        row["7. Telephone number"] = entity.get("telephone")
        row["8. Website"] = entity.get("website")
        row["9. Financial Year"] = entity.get("financial_year")
        row["10. Stock Exchange Listing"] = entity.get("stock_exchange_listing")
        row["11. Paid-up Capital"] = entity.get("paid_up_capital")
        row["12. Contact Person Details"] = entity.get("contact_person_details")
        row["13. Reporting boundary"] = entity.get("reporting_boundary")
        row["14. Name of assurance provider"] = entity.get("assurance_provider")
        row["15. Type of assurance"] = entity.get("assurance_type")

        # business activity (16)
        row["16. Business Activity"] = ""
        row["16.a Main Business Activity"] = business.get("main_activity_description")
        row["16.b Description of Business Activity"] = business.get("description")
        row["16.c % of Turnover"] = business.get("percent_of_turnover")

        # products (17)
        row["17. Products/Services"] = ""
        row["17.a Product/Service"] = product.get("product_service")
        row["17.b NIC Code"] = product.get("nic_code")
        row["17.c % Turnover"] = product.get("percent_of_total_turnover")

        # locations (18)
        row["18. Number of Locations"] = ""
        row["18.a National Plants"] = locations.get("national_plants")
        row["18.b National Offices"] = locations.get("national_offices")
        row["18.c International Plants"] = locations.get("international_plants")
        row["18.d International Offices"] = locations.get("international_offices")

        # markets (19)
        row["19.a International Countries"] = markets.get("international_countries")
        row["19.b Export %"] = markets.get("export_percent")
        row["19.c Customers Brief"] = markets.get("customers_brief")

        # employees/workers (20)
        row["20. Employees and Workers"] = ""
        emp = employees.get("employees", {})
        row["20.A Total Permanent Employees"] = emp.get("total_permanent")
        row["20.A Permanent Male Employees"] = emp.get("permanent_male")
        row["20.A Permanent Female Employees"] = emp.get("permanent_female")
        row["20.A Other than Permanent"] = emp.get("other_than_permanent")
        row["20.A Other Male"] = emp.get("other_than_permanent_male")
        row["20.A Other Female"] = emp.get("other_than_permanent_female")
        row["20.A Total Employees"] = emp.get("total_employees")
        row["20.A Total Male"] = emp.get("total_male")
        row["20.A Total Female"] = emp.get("total_female")

        workers = employees.get("workers", {})
        row["20.B Permanent Workers"] = workers.get("total_permanent")
        row["20.B Permanent Male Workers"] = workers.get("permanent_male")
        row["20.B Permanent Female Workers"] = workers.get("permanent_female")
        row["20.B Other Workers"] = workers.get("other_than_permanent")
        row["20.B Other Male Workers"] = workers.get("other_than_permanent_male")
        row["20.B Other Female Workers"] = workers.get("other_than_permanent_female")
        row["20.B Total Workers"] = workers.get("total_workers")
        row["20.B Total Male Workers"] = workers.get("total_male")
        row["20.B Total Female Workers"] = workers.get("total_female")

        da_emp = employees.get("differently_abled_employees", {})
        row["20.C DA Employees Total Permanent"] = da_emp.get("total_permanent")
        row["20.C DA Permanent Male"] = da_emp.get("permanent_male")
        row["20.C DA Permanent Female"] = da_emp.get("permanent_female")
        row["20.C DA Other"] = da_emp.get("other_than_permanent")
        row["20.C DA Other Male"] = da_emp.get("other_than_permanent_male")
        row["20.C DA Other Female"] = da_emp.get("other_than_permanent_female")
        row["20.C DA Total Employees"] = da_emp.get("total_employees")

        # women representation (21)
        row["21. Women Representation"] = ""
        row["21.a Board Total"] = women.get("board_of_directors_total")
        row["21.b Board Women"] = women.get("board_of_directors_women")
        row["21.c KMP Total"] = women.get("kmp_total")
        row["21.d KMP Women"] = women.get("kmp_women")

        # turnover (22)
        row["22. Turnover Rate"] = ""
        row["22.a Emp Male"] = ExcelService.safe_get(turnover, "permanent_employees", "male")
        row["22.b Emp Female"] = ExcelService.safe_get(turnover, "permanent_employees", "female")
        row["22.c Emp Total"] = ExcelService.safe_get(turnover, "permanent_employees", "total")
        row["22.d Worker Male"] = ExcelService.safe_get(turnover, "permanent_workers", "male")
        row["22.e Worker Female"] = ExcelService.safe_get(turnover, "permanent_workers", "female")
        row["22.f Worker Total"] = ExcelService.safe_get(turnover, "permanent_workers", "total")

        # holdings (23)
        holdings = data.get("holding_subsidiaries", [])
        first_holding = holdings[0] if holdings else {}
        row["23. Group Entity"] = first_holding.get("name")
        raw_type = first_holding.get("type")
        row["23. Group Entity Type"] = raw_type
        row["23. Mapped Group Entity Type"] = ExcelService.map_group_entity_type(raw_type)
        row["23. % Shares"] = first_holding.get("percent_shares_held")

        # CSR (24)
        row["24.a CSR Applicable"] = csr.get("is_applicable")
        row["24.b CSR Turnover"] = csr.get("turnover_inr_cr")
        row["24.c CSR Net Worth"] = csr.get("net_worth_inr_cr")

        # grievances (25)
        row["25. Grievance Redressal"] = ""
        mech = grievances.get("mechanism_in_place", {})
        row["25.a Communities"] = mech.get("communities")
        row["25.a Investors (other than shareholders)"] = mech.get("investors_other_than_shareholders")
        row["25.a Shareholders"] = mech.get("shareholders")
        row["25.a Employees and workers"] = mech.get("employees_and_workers")
        row["25.a Customers"] = mech.get("customers")
        row["25.a Value Chain Partners"] = mech.get("value_chain_partners")
        row["25.a Others"] = mech.get("other_please_specify")

        filed = grievances.get("filed", {})
        row["25.b Communities"] = filed.get("communities")
        row["25.b Investors (other than shareholders)"] = filed.get("investors_other_than_shareholders")
        row["25.b Shareholders"] = filed.get("shareholders")
        row["25.b Employees and workers"] = filed.get("employees_and_workers")
        row["25.b Customers"] = filed.get("customers")
        row["25.b Value Chain Partners"] = filed.get("value_chain_partners")
        row["25.b Others"] = filed.get("other_please_specify")

        pending = grievances.get("pending", {})
        row["25.c Communities"] = pending.get("communities")
        row["25.c Investors (other than shareholders)"] = pending.get("investors_other_than_shareholders")
        row["25.c Shareholders"] = pending.get("shareholders")
        row["25.c Employees and workers"] = pending.get("employees_and_workers")
        row["25.c Customers"] = pending.get("customers")
        row["25.c Value Chain Partners"] = pending.get("value_chain_partners")
        row["25.c Others"] = pending.get("other_please_specify")

        return row

    @staticmethod
    def expand_all(data: Dict[str, Any], base_row: Dict[str, Any]) -> List[Dict[str, Any]]:
        holdings = sorted(data.get("holding_subsidiaries", []), key=lambda x: x.get("type", ""))
        risks = data.get("material_risks_opportunities", {})
        risk_rows: List[Dict[str, Any]] = []

        def _items_for_category(risks_obj, category_name):
            if isinstance(risks_obj, dict):
                return risks_obj.get(category_name, []) or []
            if isinstance(risks_obj, list):
                items = []
                for el in risks_obj:
                    if not isinstance(el, dict):
                        continue
                    if category_name in el and isinstance(el[category_name], list):
                        items.extend(el[category_name])
                        continue
                    if any(k in el for k in ("material_issue", "rationale", "risk_or_opportunity")):
                        items.append(el)
                return items
            return []

        for category in ["environment", "social", "governance"]:
            for item in _items_for_category(risks, category):
                risk_rows.append({
                    "26. Category": category.capitalize(),
                    "26. Material Issue": item.get("material_issue"),
                    "26. Risk/Opportunity": item.get("risk_or_opportunity"),
                    "26. Rationale": item.get("rationale"),
                    "26. Financial Impact": item.get("financial_implications"),
                    "26. Approach to Adapt/Mitigate": item.get("approach_to_adapt_mitigate"),
                })

        max_rows = max(1, len(holdings), len(risk_rows))
        final_rows: List[Dict[str, Any]] = []

        for i in range(max_rows):
            if i == 0:
                row = base_row.copy()
            else:
                row = {k: "" for k in base_row.keys()}
                row["1. Corporate Identity Number (CIN)"] = base_row.get("1. Corporate Identity Number (CIN)")
                row["2. Name of Listed Entity"] = base_row.get("2. Name of Listed Entity")

            if i < len(holdings):
                row["23. Group Entity"] = holdings[i].get("name")
                raw_type = holdings[i].get("type")
                row["23. Group Entity Type"] = raw_type
                row["23. Mapped Group Entity Type"] = ExcelService.map_group_entity_type(raw_type)
                row["23. % Shares"] = holdings[i].get("percent_shares_held")

            if i < len(risk_rows):
                row.update(risk_rows[i])

            final_rows.append(row)

        return final_rows

    @staticmethod
    def expand_risks(data: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        final_rows: List[Dict[str, Any]] = []
        risks = data.get("material_risks_opportunities", {})

        def _items_for_category(risks_obj, category_name):
            if isinstance(risks_obj, dict):
                return risks_obj.get(category_name, []) or []
            if isinstance(risks_obj, list):
                items = []
                for el in risks_obj:
                    if not isinstance(el, dict):
                        continue
                    if category_name in el and isinstance(el[category_name], list):
                        items.extend(el[category_name])
                        continue
                    if any(k in el for k in ("material_issue", "rationale", "risk_or_opportunity")):
                        items.append(el)
                return items
            return []

        for r in rows:
            for category in ["environment", "social", "governance"]:
                items = _items_for_category(risks, category)
                for item in items:
                    new_row = r.copy()
                    new_row["26. Category"] = category.capitalize()
                    new_row["26. Material Issue"] = item.get("material_issue")
                    new_row["26. Risk/Opportunity"] = item.get("risk_or_opportunity")
                    new_row["26. Rationale"] = item.get("rationale")
                    new_row["26. Financial Impact"] = item.get("financial_implications")
                    new_row["26. Approach to Adapt/Mitigate"] = item.get("approach_to_adapt_mitigate")
                    final_rows.append(new_row)

        return final_rows

    # ----- Export helpers -----
    @staticmethod
    def json_paths_to_dataframe(json_paths: List[str]) -> pd.DataFrame:
        all_rows: List[Dict[str, Any]] = []
        for path in json_paths:
            data = ExcelService.load_json(path)
            base = ExcelService.build_base_row(data)
            expanded = ExcelService.expand_all(data, base)
            all_rows.extend(expanded)
        return pd.DataFrame(all_rows)

    @staticmethod
    def dataframe_to_excel_bytes(df: pd.DataFrame, engine: str = "openpyxl") -> bytes:
        """Return Excel file bytes for streaming to clients (no disk I/O)."""
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine=engine) as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)
        return buf.read()

    @staticmethod
    def json_to_excel_bytes(json_paths: List[str]) -> bytes:
        df = ExcelService.json_paths_to_dataframe(json_paths)
        return ExcelService.dataframe_to_excel_bytes(df)

    @staticmethod
    def json_to_excel_file(json_paths: List[str], output_file: str = "brsr_output.xlsx") -> None:
        """Convenience: write Excel to disk (if you still want that)."""
        df = ExcelService.json_paths_to_dataframe(json_paths)
        df.to_excel(output_file, index=False)

    @staticmethod
    def generate_excel(json_docs: List[Dict[str, Any]]):
        """Generate an in-memory Excel file (BytesIO) from a list of JSON-like dicts.

        This accepts already-parsed JSON objects (extracted_json) rather than file paths.
        Returns an `io.BytesIO` positioned at start suitable for StreamingResponse.
        """
        all_rows: List[Dict[str, Any]] = []
        for data in json_docs:
            base = ExcelService.build_base_row(data)
            expanded = ExcelService.expand_all(data, base)
            all_rows.extend(expanded)

        df = pd.DataFrame(all_rows)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        buf.seek(0)
        return buf


def json_to_excel(json_paths: List[str], output_file: str = "brsr_output.xlsx"):
    # backward-compatible function
    ExcelService.json_to_excel_file(json_paths, output_file)


if __name__ == "__main__":
    json_files = glob.glob("output/cement2/*.json")
    # produce bytes and also write file locally for convenience
    b = ExcelService.json_to_excel_bytes(json_files)
    with open("output/cement/output.xlsx", "wb") as f:
        f.write(b)
    print("Excel saved → output/cement/output.xlsx")


def upload_excel_to_supabase(
    json_paths: List[str],
    bucket: str,
    dest_path: str,
    supabase_url: str,
    supabase_key: str,
    make_public: bool = True,
    expires_in: int = 60 * 60 * 24,
) -> str:
    """Generate Excel bytes from `json_paths`, upload to Supabase Storage and
    return a public URL (or signed URL).

    Parameters:
    - json_paths: list of JSON file paths to include
    - bucket: Supabase storage bucket name
    - dest_path: destination path (including filename) in the bucket
    - supabase_url, supabase_key: credentials for Supabase project
    - make_public: if True, returns the public URL; otherwise returns a signed URL
    - expires_in: signed URL expiry in seconds (only if make_public is False)

    Returns: URL string
    """
    # build excel bytes
    excel_bytes = ExcelService.json_to_excel_bytes(json_paths)

    # import client here to avoid mandatory dependency unless used
    try:
        from supabase import create_client
    except Exception as e:
        raise RuntimeError("supabase package is required to upload to Supabase: pip install supabase") from e

    supabase = create_client(supabase_url, supabase_key)

    # upload expects a file-like or bytes object
    try:
        res = supabase.storage.from_(bucket).upload(dest_path, io.BytesIO(excel_bytes))
    except Exception:
        # Attempt to remove existing object and re-upload (common when file exists)
        try:
            supabase.storage.from_(bucket).remove([dest_path])
        except Exception:
            pass
        res = supabase.storage.from_(bucket).upload(dest_path, io.BytesIO(excel_bytes))

    if make_public:
        try:
            public = supabase.storage.from_(bucket).get_public_url(dest_path)
            # expected dict contains 'publicURL' or 'publicUrl'
            url = public.get("publicURL") or public.get("publicUrl")
            if url:
                return url
        except Exception:
            pass

    # fallback to signed url
    signed = supabase.storage.from_(bucket).create_signed_url(dest_path, expires_in)
    url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedURL")
    if not url:
        raise RuntimeError("Failed to obtain public or signed URL from Supabase response: %r" % (signed,))
    return url
