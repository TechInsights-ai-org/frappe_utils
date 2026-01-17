import frappe
from frappe.utils import validate_email_address
from frappe.core.doctype.user.user import reset_password

@frappe.whitelist(allow_guest=True)
def reset(identifier=None):
    if not identifier:
        return {"status": "fail", "message": _("Identifier is required.")}

    identifier = identifier.strip().lower()

    # RAW SQL search case-insensitively across username, email, phone
    user = frappe.db.sql(
        """
        SELECT `name`, `email`
        FROM `tabUser`
        WHERE
            LOWER(`username`) = %s
            OR LOWER(`email`) = %s
            OR LOWER(IFNULL(`phone`, '')) = %s
            AND `enabled` = 1
        LIMIT 1
        """,
        (identifier, identifier, identifier),
        as_dict=1,
    )

    if not user:
        return {"status": "fail", "message":"No user found."}

    user = user[0]

    # ensure the email field exists before attempting reset
    email = user.get("email")
    if not email or not validate_email_address(email, True):
        return {"status": "fail", "message": "User has no valid email."}
    try:
        reset_password(user=user["name"])
        return {
            "status": "success",
            "message": f"Password reset link sent to {email}",
            "email_sent_to": email
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Password Reset API Error")
        return {"status": "fail", "message": "Failed to send reset link."}
