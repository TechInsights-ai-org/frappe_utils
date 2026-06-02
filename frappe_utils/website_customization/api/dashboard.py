import frappe
from frappe.utils import flt

@frappe.whitelist()
def get_financial_info(customer: str):
    """
    Returns per-company credit limit, outstanding and balance
    for the given customer, aggregated efficiently.
    """

    if not customer:
        raise ValueError("Customer is required")

    # 1) Get credit limits per company
    credit_limit_rows = frappe.get_list(
        "Customer Credit Limit",
        filters={"parent": customer},
        fields=["company", "credit_limit"],
        limit=0
    )
    cl_map = {}
    for r in credit_limit_rows:
        cl_map[r.company] = cl_map.get(r.company, 0) + flt(r.credit_limit)

    # 2) Get outstanding amounts per company
    invoice_rows = frappe.get_list(
        "Sales Invoice",
        filters={"customer": customer, "docstatus": 1},
        fields=["company", "outstanding_amount"],
        limit=0
    )
    out_map = {}
    for r in invoice_rows:
        out_map[r.company] = out_map.get(r.company, 0) + flt(r.outstanding_amount)

    # 3) Build result list
    results = []
    total_credit = total_outstanding = total_balance = 0

    # combine all companies found in either map
    companies = set(list(cl_map.keys()) + list(out_map.keys()))

    for comp in companies:
        cr = cl_map.get(comp, 0)
        out = out_map.get(comp, 0)
        bal = cr - out

        total_credit += cr
        total_outstanding += out
        total_balance += bal

        results.append({
            "company": comp,
            "credit_limit": cr,
            "outstanding": out,
            "balance": bal
        })

    return {
        "customer": customer,
        "company_wise": results,
        "totals": {
            "credit_limit": total_credit,
            "outstanding": total_outstanding,
            "balance": total_balance
        }
    }
