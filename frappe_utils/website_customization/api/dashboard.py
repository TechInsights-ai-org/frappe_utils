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
    credit_limits = frappe.db.sql("""
        SELECT
            company,
            SUM(credit_limit) AS credit_limit
        FROM `tabCustomer Credit Limit`
        WHERE parent = %s
        GROUP BY company
    """, customer, as_dict=1)

    cl_map = {d.company: flt(d.credit_limit) for d in credit_limits}

    # 2) Get outstanding amounts per company
    outstanding = frappe.db.sql("""
        SELECT
            si.company,
            SUM(IFNULL(si.outstanding_amount, 0)) AS outstanding
        FROM `tabSales Invoice` si
        WHERE
            si.customer = %s
            AND si.docstatus = 1
        GROUP BY si.company
    """, customer, as_dict=1)

    out_map = {d.company: flt(d.outstanding) for d in outstanding}

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
