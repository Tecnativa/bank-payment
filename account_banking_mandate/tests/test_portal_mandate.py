# Copyright 2023 Tecnativa - Carolina Fernandez
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
# import odoo.tests
from odoo.tests.common import new_test_user

from odoo.addons.base.tests.common import HttpCaseWithUserPortal


class TestAccountBankingMandatePortalBase(HttpCaseWithUserPortal):
    """Test controllers defined for portal mode.
    This is mostly for basic coverage; we don't go as far as fully validating
    HTML produced by our routes.
    """

    def setUp(self):
        super().setUp()
        ctx = {
            "mail_create_nolog": True,
            "mail_create_nosubscribe": True,
            "mail_notrack": True,
            "no_reset_password": True,
        }
        self.company = self.env.ref("base.main_company")
        self.partner_portal.parent_id = self.company.partner_id
        self.basic_user = new_test_user(self.env, login="test-basic-user", context=ctx)
        self.basic_user.parent_id = self.company.partner_id
        bank_account = self.env.ref("account_payment_mode.res_partner_12_iban")
        bank_account.partner_id = self.basic_user.partner_id.id

        self.mandate = self.env["account.banking.mandate"].create(
            {
                "partner_bank_id": bank_account.id,
                "signature_date": "2015-01-01",
                "company_id": self.company.id,
            }
        )
        self.basic_user_2 = self.user_portal.copy(
            default={"login": "portal2", "password": "portal2"}
        )
        bank_account_2 = self.env.ref("account_payment_mode.res_partner_12_iban")
        bank_account_2.partner_id = self.basic_user_2.partner_id.id

        self.mandate_2 = self.env["account.banking.mandate"].create(
            {
                "partner_bank_id": bank_account_2.id,
                "signature_date": "2015-01-01",
                "company_id": self.company.id,
            }
        )

    def test_mandate_list(self):
        """List mandates in portal mode, ensure it contains our test mandate."""
        self.authenticate("portal", "portal")
        resp = self.url_open("/my/mandates")
        self.assertEqual(resp.status_code, 200)

    def test_mandate_form(self):
        """Open our test mandate in portal mode."""
        self.authenticate("portal", "portal")
        resp = self.url_open(f"/my/mandate/{self.mandate.id}")
        self.assertEqual(resp.status_code, 200)

    def test_mandate_list_unauthenticated(self):
        """Attempt to list mandates without auth, ensure we get sent back to login."""
        resp = self.url_open("/my/mandates", allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.is_redirect)
        self.assertIn("/web/login", resp.headers["Location"])

    def test_mandate_list_authorized(self):
        """Attempt to list mandates without banking mandates permissions."""
        self.authenticate("test-basic-user", "test-basic-user")
        resp = self.url_open("/my/mandates", allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.is_redirect)

    def test_mandates_2_users(self):
        """Check mandates between 2 portal users; ensure they can't access each
        others' mandates.
        """
        self.partner_portal.parent_id = False

        mandate_1 = self.mandate
        mandate_2 = self.mandate_2

        # Portal mandate list: portal_user_1 only sees mandate_1
        self.authenticate("portal", "portal")
        resp = self.url_open("/my/mandates")
        self.assertEqual(resp.status_code, 200)

        # Portal mandate list: portal_user_2 only sees mandate_2
        self.authenticate("portal2", "portal2")
        resp = self.url_open("/my/mandates")
        self.assertEqual(resp.status_code, 200)

        # Portal mandate form: portal_user_1 can open mandate_1 but not mandate_2
        self.authenticate("portal", "portal")
        resp = self.url_open(f"/my/mandate/{mandate_1.id}")
        self.assertEqual(resp.status_code, 200)
        resp = self.url_open(f"/my/mandate/{mandate_2.id}", allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.is_redirect)
        self.assertTrue(resp.headers["Location"].endswith("/my"))

        # Portal mandate form: portal_user_2 can open mandate_2 but not mandate_1
        self.authenticate("portal2", "portal2")
        resp = self.url_open(f"/my/mandate/{mandate_1.id}", allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.is_redirect)
        self.assertTrue(resp.headers["Location"].endswith("/my"))
        resp = self.url_open(f"/my/mandate/{mandate_2.id}")
        self.assertEqual(resp.status_code, 200)
