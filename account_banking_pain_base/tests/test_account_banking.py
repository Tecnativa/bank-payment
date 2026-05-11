from lxml import etree

from odoo import fields
from odoo.exceptions import UserError

from odoo.addons.base.tests.common import BaseCommon


class TestPainBase(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Method = cls.env["account.payment.method"].create(
            {
                "name": "Test Method",
                "code": "TEST",
                "payment_type": "inbound",
            }
        )
        cls.Mode = cls.env["account.payment.mode"].create(
            {
                "name": "Test Mode",
                "payment_method_id": Method.id,
                "bank_account_link": "variable",
            }
        )
        Journal = cls.env["account.journal"].search([], limit=1)
        cls.partner = cls.env["res.partner"].create({"name": "Partner"})
        Bank = cls.env["res.bank"].create({"name": "Bank", "bic": "NEDSZAJJXXX"})
        cls.partner_bank = cls.env["res.partner.bank"].create(
            {
                "partner_id": cls.partner.id,
                "bank_id": Bank.id,
                "acc_number": "ES12345678901234567890",
            }
        )
        cls.order = cls.env["account.payment.order"].create(
            {"name": "TST001", "payment_mode_id": cls.Mode.id, "journal_id": Journal.id}
        )
        cls.gen_args = {
            "pain_flavor": "pain.001.001.03",
            "bic_xml_tag": "BIC",
            "payment_method": "DD",
            "file_prefix": "PF_",
        }
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Company",
                "country_id": cls.env.ref("base.be").id,
                "vat": "BE0477472701",
            }
        )
        cls.company.partner_id.write(
            {
                "street": "Company Street 1",
                "street2": "Suite 2",
                "zip": "1000",
                "city": "Amsterdam",
                "country_id": cls.env.ref("base.be").id,
            }
        )

    def test_generate_pain_nsmap(self):
        nsmap = self.order.generate_pain_nsmap()
        self.assertIn("xsi", nsmap)
        self.assertIn(None, nsmap)
        self.assertTrue(nsmap[None].endswith("False"))

    def test_generate_group_header_block(self):
        root = etree.Element("Document")
        self.order.write({"company_partner_bank_id": self.partner_bank.id})
        ok = self.order.generate_group_header_block(root, self.gen_args)
        self.assertTrue(ok)
        grp = root.find("GrpHdr")
        self.assertIsNotNone(grp)
        self.assertIsNotNone(grp.find("MsgId"))
        self.assertIsNotNone(grp.find("CreDtTm"))
        self.Mode.company_id.write({"initiating_party_identifier": "KBO-BCE"})
        ok = self.order.generate_group_header_block(root, self.gen_args)
        self.assertTrue(ok)

    def test_generate_party_agent_with_bic(self):
        parent = etree.Element("CdtTrfTxInf")
        res = self.order.generate_party_agent(
            parent, "Cdtr", "B", self.partner_bank, self.gen_args
        )
        self.assertTrue(res)
        self.assertIsNotNone(parent.find("CdtrAgt/FinInstnId/BIC"))
        self.partner_bank.bank_bic = False
        res = self.order.generate_party_agent(
            parent, "Cdtr", "B", self.partner_bank, self.gen_args
        )

    def test_generate_party_acc_number_iban(self):
        parent = etree.Element("CdtTrfTxInf")
        res = self.order.generate_party_acc_number(
            parent, "Dbtr", "B", self.partner_bank, self.gen_args
        )
        self.assertTrue(res)

    def test_generate_address_block(self):
        parent = etree.Element("Dbtr")
        self.partner.country_id = self.env.ref("base.es")
        self.partner.zip = "08001"
        res = self.order.generate_address_block(parent, self.partner, self.gen_args)
        self.assertTrue(res)
        self.assertIsNotNone(parent.find("PstlAdr"))
        self.partner.city = "Madrid"
        res = self.order.generate_address_block(parent, self.partner, self.gen_args)
        self.assertTrue(res)
        self.assertIsNotNone(parent.find("PstlAdr"))

    def test_generate_address_block_pain09_minimal(self):
        country = self.env["res.country"].search([("code", "=", "NL")], limit=1)
        partner = self.env["res.partner"].create(
            {
                "name": "Hybrid Partner 09",
                "street": "Oudestraat 1",
                "street2": "2/2.14",
                "zip": "3942 NR",
                "city": "Adelala",
                "country_id": country.id,
            }
        )
        self.Mode.payment_method_id.sepa_pain09_address_mode = "minimal"
        gen_args = {"pain_flavor": "pain.001.001.09"}
        root = etree.Element("Root")
        self.order.generate_address_block(root, partner, gen_args)
        pstl = root.find("PstlAdr")
        self.assertIsNotNone(pstl)
        self.assertEqual(pstl.find("TwnNm").text, partner.city)
        self.assertEqual(pstl.find("Ctry").text, partner.country_id.code)
        self.assertIsNone(pstl.find("PstCd"))
        self.assertEqual(len(pstl.findall("AdrLine")), 0)

    def test_generate_address_block_pain09_requires_city(self):
        country = self.env["res.country"].search([("code", "=", "NL")], limit=1)
        partner = self.env["res.partner"].create(
            {
                "name": "Hybrid Partner 09 No City",
                "street": "Oudestraat 1",
                "zip": "3842 NK",
                "city": False,
                "country_id": country.id,
            }
        )
        gen_args = {"pain_flavor": "pain.001.001.09"}
        root = etree.Element("Root")
        with self.assertRaises(UserError):
            self.order.generate_address_block(root, partner, gen_args)

    def test_generate_address_block_pain09_hybrid(self):
        country = self.env["res.country"].search([("code", "=", "NL")], limit=1)
        partner = self.env["res.partner"].create(
            {
                "name": "Hybrid Partner 09 Hybrid",
                "street": "Oudestraat 1",
                "street2": "2/2.14",
                "zip": "3942 NR",
                "city": "Adelala",
                "country_id": country.id,
            }
        )
        self.Mode.payment_method_id.sepa_pain09_address_mode = "hybrid"
        gen_args = {"pain_flavor": "pain.001.001.09"}
        root = etree.Element("Root")
        self.order.generate_address_block(root, partner, gen_args)
        pstl = root.find("PstlAdr")
        self.assertIsNotNone(pstl)
        tags = [c.tag for c in list(pstl)]
        self.assertEqual(tags[0], "PstCd")
        self.assertEqual(tags[1], "TwnNm")
        self.assertEqual(tags[2], "Ctry")
        self.assertEqual(pstl.find("PstCd").text, partner.zip)
        self.assertEqual(pstl.find("TwnNm").text, partner.city)
        self.assertEqual(pstl.find("Ctry").text, partner.country_id.code)
        adr_lines = pstl.findall("AdrLine")
        self.assertEqual(len(adr_lines), 2)
        self.assertEqual(adr_lines[0].text, partner.street)
        self.assertEqual(adr_lines[1].text, partner.street2)

    def test_requested_date_pain09(self):
        root = etree.Element("Root")
        gen_args = {"pain_flavor": "pain.001.001.09", "payment_method": "TRF"}
        requested_date = fields.Date.to_string(fields.Date.today())
        (
            payment_info,
            nb_of_transactions,
            control_sum,
        ) = self.order.generate_start_payment_info_block(
            parent_node=root,
            payment_info_ident="'TEST'",
            priority=False,
            local_instrument=False,
            category_purpose=False,
            sequence_type=False,
            requested_date=requested_date,
            eval_ctx={},
            gen_args=gen_args,
        )
        self.assertIsNotNone(payment_info.find("ReqdExctnDt"))
        dt = payment_info.find("ReqdExctnDt/Dt")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.text, requested_date)

    def test_default_initiating_party(self):
        self.company._default_initiating_party()
        self.assertEqual(self.company.initiating_party_issuer, "KBO-BCE")
        self.assertEqual(self.company.initiating_party_identifier, "0477472701")

    def test_except_messages_prepare_field(self):
        partner_bank = self.env["res.partner.bank"].create(
            {
                "partner_id": self.partner.id,
                "acc_number": "ES1299999999509999999999",
            }
        )
        payment_line = self.env["account.payment.line"].create(
            {
                "order_id": self.order.id,
                "partner_id": self.partner.id,
                "partner_bank_id": partner_bank.id,
                "amount_currency": 100.0,
            }
        )
        eval_ctx = {
            "line": payment_line,
            "partner_bank": partner_bank,
        }
        error_messages = self.order.except_messages_prepare_field(
            eval_ctx, "Test Field"
        )
        self.assertIn(
            f"Payment Line has reference '{payment_line.name}'.", error_messages
        )
        self.assertIn(
            f"Partner's bank account is '{partner_bank.display_name}'.",
            error_messages,
        )

    def test_generate_party_block(self):
        parent_node = etree.Element("PmtInf")
        result = self.order.generate_party_block(
            parent_node,
            party_type="Cdtr",
            order="B",
            partner_bank=self.partner_bank,
            gen_args=self.gen_args,
        )
        self.assertTrue(result)

    def test_generate_start_payment_info_block(self):
        parent_node = etree.Element("Document")
        payment_info_ident = "'PAYINFO001'"
        priority = "NORM"
        local_instrument = "INST"
        category_purpose = "SUPP"
        sequence_type = "FRST"
        requested_date = "2025-05-15"
        eval_ctx = {"self": self.order}
        payment_info, _, _ = self.order.generate_start_payment_info_block(
            parent_node,
            payment_info_ident,
            priority,
            local_instrument,
            category_purpose,
            sequence_type,
            requested_date,
            eval_ctx,
            self.gen_args,
        )
        self.assertIsNotNone(payment_info)
        self.assertEqual(payment_info.tag, "PmtInf")

    def test_prepare_field_with_convert_to_ascii(self):
        field_name = "Test Field"
        field_value = "'áéíóúñÑçÇ@#$%&*<>!'"
        eval_ctx = {"self": self.order}
        gen_args = {"convert_to_ascii": True}
        result = self.order._prepare_field(
            field_name, field_value, eval_ctx, gen_args=gen_args
        )
        self.assertEqual(result, "aeiounNcC---------")
        with self.assertRaises(UserError):
            self.order._prepare_field(field_name, "''", eval_ctx, gen_args=gen_args)
        long_value = "'{}'".format("a" * 50)
        result = self.order._prepare_field(
            field_name, long_value, eval_ctx, max_size=35, gen_args=gen_args
        )
        self.assertEqual(result, "a" * 35)

    def test_default_batch_booking(self):
        self.assertFalse(self.order.batch_booking)
        self.assertFalse(self.Mode.default_batch_booking)
        self.Mode.default_batch_booking = True
        journal = self.env["account.journal"].search([], limit=1)
        order = self.env["account.payment.order"].create(
            {
                "name": "TESTDBB",
                "payment_mode_id": self.Mode.id,
                "journal_id": journal.id,
            }
        )
        self.assertTrue(order.batch_booking)
        self.assertTrue(self.Mode.default_batch_booking)
        new_order = self.env["account.payment.order"].create(
            {
                "name": "TESTDBB2",
                "payment_mode_id": self.Mode.id,
                "journal_id": journal.id,
                "batch_booking": False,
            }
        )
        self.assertFalse(new_order.batch_booking)
        self.assertTrue(self.Mode.default_batch_booking)
