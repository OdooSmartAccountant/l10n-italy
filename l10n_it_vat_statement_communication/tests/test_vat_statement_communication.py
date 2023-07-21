# Copyright 2023 Tony Masci (Rapsodoo)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import Form, TransactionCase


class VatStatementCommunicationCase(TransactionCase):
    def setUp(self):
        super(VatStatementCommunicationCase, self).setUp()

        # Comunicazione liquidazione

        self.comunicazione_liquidazione = self.env["comunicazione.liquidazione"].create(
            self.get_vals_comunicazione_liquidazione()
        )
        # Journals

        self.miscellaneous_journal = self.env["account.journal"].search(
            [("type", "=", "general")], limit=1
        )

        # Accounts

        self.account_erario = self.env["account.account"].search(
            [("code", "=", "252000")], limit=1
        )
        self.account_interessi = self.env["account.account"].search(
            [("code", "=", "600000")], limit=1
        )

        self.paid_vat_account = self.env["account.account"].search(
            [("account_type", "=", "asset_current")], limit=1
        )
        self.received_vat_account = self.env["account.account"].search(
            [("account_type", "=", "liability_current")], limit=1
        )

        # Taxes

        tax_model = self.env["account.tax"]

        self.tax_22_purchase = tax_model.create(
            {
                "name": "IVA 22 Purchase",
                "description": "22",
                "amount": 22.00,
                "type_tax_use": "purchase",
                "invoice_repartition_line_ids": [
                    (5, 0, 0),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": self.paid_vat_account.id,
                        },
                    ),
                ],
                "refund_repartition_line_ids": [
                    (5, 0, 0),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": self.paid_vat_account.id,
                        },
                    ),
                ],
            }
        )

        self.tax_22_sale = tax_model.create(
            {
                "name": "IVA 22 Sale",
                "description": "22",
                "amount": 22.00,
                "type_tax_use": "sale",
                "invoice_repartition_line_ids": [
                    (5, 0, 0),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": self.received_vat_account.id,
                        },
                    ),
                ],
                "refund_repartition_line_ids": [
                    (5, 0, 0),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": self.received_vat_account.id,
                        },
                    ),
                ],
            }
        )

        # Set VAT revenue account in taxes to take in VAT statement
        self.env["account.tax"].search([("type_tax_use", "=", "sale")]).write(
            {"vat_statement_account_id": self.received_vat_account.id}
        )
        self.env["account.tax"].search([("type_tax_use", "=", "purchase")]).write(
            {"vat_statement_account_id": self.paid_vat_account.id}
        )

        # Partners

        self.res_partner_1 = self.env.ref("base.res_partner_1")

        # Type of periods

        self.type_month = self.env["date.range.type"].create({"name": "Month"})

        self.type_quarter = self.env["date.range.type"].create({"name": "Quarter"})

    def get_vals_comunicazione_liquidazione(self):
        return {
            "year": 2022,
            "taxpayer_vat": "11876260784",
            "taxpayer_fiscalcode": "FNCPLC19D01I168X",
            "declarant_fiscalcode": "FNCPLC19D01I168X",
            "codice_carica_id": self.env.ref("l10n_it_appointment_code.1").id,
        }

    def _create_invoice(self, invoice_date, move_type="out_invoice", amount=1.0):
        if move_type == "out_invoece":
            tax = self.tax_22_sale
        else:
            tax = self.tax_22_purchase

        product_product_10 = self.env.ref("product.product_product_10")

        with Form(
            self.env["account.move"].with_context(default_move_type=move_type)
        ) as move_form:
            move_form.invoice_date = fields.Date.from_string(invoice_date)
            move_form.partner_id = self.res_partner_1
            with move_form.invoice_line_ids.new() as line_form:
                line_form.product_id = product_product_10
                line_form.price_unit = amount
                line_form.quantity = 1
                line_form.tax_ids.clear()
                line_form.tax_ids.add(tax)

        invoice = move_form.save()

        return invoice

    def _create_vat_statement(
        self,
        vat_statement_date,
        interest,
        name_period,
        type_period,
        date_start_period,
        date_end_period,
    ):
        with Form(self.env["account.vat.period.end.statement"]) as vat_statement_form:
            vat_statement_form.journal_id = self.miscellaneous_journal
            vat_statement_form.date = fields.Date.from_string(vat_statement_date)
            vat_statement_form.authority_vat_account_id = self.account_erario
            vat_statement_form.interest = interest

        vat_statement = vat_statement_form.save()

        with Form(self.env["date.range"]) as date_range_form:
            date_range_form.name = name_period
            date_range_form.type_id = type_period
            date_range_form.date_start = fields.Date.from_string(date_start_period)
            date_range_form.date_end = fields.Date.from_string(date_end_period)

        date_range = date_range_form.save()

        date_range.write({"vat_statement_id": vat_statement.id})

        vat_statement.compute_amounts()
        vat_statement._compute_authority_vat_amount()

        vat_statement.create_move()

        return vat_statement

    def test_name(self):
        comunicazione_liquidazione = self.env["comunicazione.liquidazione"].create(
            self.get_vals_comunicazione_liquidazione()
        )

        self.assertEqual(comunicazione_liquidazione.name, "")

        comunicazione_liquidazione.write(
            {
                "quadri_vp_ids": [
                    [5, 0, 0],
                    [0, 0, {"period_type": "month", "month": 1}],
                    [0, 0, {"period_type": "month", "month": 2}],
                    [0, 0, {"period_type": "month", "month": 3}],
                ]
            }
        )

        comunicazione_liquidazione.env.invalidate_all()

        self.assertEqual(comunicazione_liquidazione.name, "2022 month, 1, 2, 3")

        comunicazione_liquidazione.write(
            {
                "quadri_vp_ids": [
                    [5, 0, 0],
                    [0, 0, {"period_type": "quarter", "quarter": 1}],
                ]
            }
        )

        comunicazione_liquidazione.env.invalidate_all()

        self.assertEqual(comunicazione_liquidazione.name, "2022 quarter, 1")

    def test_identificativo(self):
        comunicazione_liquidazione = self.env["comunicazione.liquidazione"].create(
            self.get_vals_comunicazione_liquidazione()
        )

        self.assertEqual(comunicazione_liquidazione.identificativo, 2)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["identificativo"] = 2
            self.env["comunicazione.liquidazione"].create(vals)

        comunicazione_liquidazione = self.env["comunicazione.liquidazione"].create(
            self.get_vals_comunicazione_liquidazione()
        )

        self.assertEqual(comunicazione_liquidazione.identificativo, 3)

    def test_validate(self):
        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["taxpayer_fiscalcode"] = "FNCPLC"
            self.env["comunicazione.liquidazione"].create(vals)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["taxpayer_fiscalcode"] = "FNCPLC19D01"
            del vals["declarant_fiscalcode"]
            self.env["comunicazione.liquidazione"].create(vals)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["liquidazione_del_gruppo"] = True
            vals["controller_vat"] = "controller_vat"
            self.env["comunicazione.liquidazione"].create(vals)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["liquidazione_del_gruppo"] = True
            self.env["comunicazione.liquidazione"].create(vals)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            del vals["codice_carica_id"]
            self.env["comunicazione.liquidazione"].create(vals)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["codice_carica_id"] = self.env.ref("l10n_it_appointment_code.9").id
            self.env["comunicazione.liquidazione"].create(vals)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["delegate_fiscalcode"] = "FNCPLC19D01I168X"
            self.env["comunicazione.liquidazione"].create(vals)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["delegate_fiscalcode"] = "FNCPLC19D01I168X"
            vals["delegate_commitment"] = "1"
            self.env["comunicazione.liquidazione"].create(vals)

        with self.assertRaises(ValidationError):
            vals = self.get_vals_comunicazione_liquidazione()
            vals["delegate_fiscalcode"] = "FNCPLC19D01I168X"
            vals["delegate_commitment"] = "1"
            vals["date_commitment"] = "2023-02-01"
            self.env["comunicazione.liquidazione"].create(vals)

    def test_onchange_company(self):
        comunicazione_liquidazione = self.env["comunicazione.liquidazione"].create(
            self.get_vals_comunicazione_liquidazione()
        )

        old_company = comunicazione_liquidazione.company_id

        old_company.partner_id.write(
            {"vat": "IT12345670017", "fiscalcode": "FNCPLC19D01I168X"}
        )

        company = self.env["res.company"].create(
            {"name": "foo", "vat": "IT12345670017", "fiscalcode": "FNCPLC19D01I168X"}
        )

        with Form(comunicazione_liquidazione) as invoice_form:
            invoice_form.company_id = company

        self.assertEqual(
            comunicazione_liquidazione.taxpayer_vat, company.partner_id.vat[2:]
        )
        self.assertEqual(
            comunicazione_liquidazione.taxpayer_fiscalcode,
            company.partner_id.fiscalcode,
        )

        with Form(comunicazione_liquidazione) as invoice_form:
            invoice_form.company_id = old_company

        self.assertEqual(
            comunicazione_liquidazione.taxpayer_vat, old_company.partner_id.vat[2:]
        )
        self.assertEqual(
            comunicazione_liquidazione.taxpayer_fiscalcode,
            old_company.partner_id.fiscalcode,
        )

    def _check_file_report(self, comunicazione_liquidazione):
        wizard = (
            self.env["comunicazione.liquidazione.export.file"]
            .with_context(active_ids=comunicazione_liquidazione.ids)
            .create({})
        )

        self.assertFalse(wizard.file_export)

        wizard.export()

        self.assertTrue(wizard.file_export)

    def test_export_xml(self):
        with self.assertRaises(UserError):
            wizard = self.env["comunicazione.liquidazione.export.file"].create({})
            wizard.export()

        with self.assertRaises(UserError):
            comunicazione_liquidazione = self.env["comunicazione.liquidazione"].create(
                self.get_vals_comunicazione_liquidazione()
            )
            wizard = (
                self.env["comunicazione.liquidazione.export.file"]
                .with_context(
                    active_ids=comunicazione_liquidazione.ids
                    + self.comunicazione_liquidazione.ids
                )
                .create({})
            )
            wizard.export()

        self._check_file_report(self.comunicazione_liquidazione)

        # Set interest and account in company
        self.env.company.write(
            {
                "of_account_end_vat_statement_interest": True,
                "of_account_end_vat_statement_interest_percent": 1.0,
                "of_account_end_vat_statement_interest_account_id": self.account_interessi.id,
            }
        )

        # Invoices monthly without interest

        # Invoices july 2022

        invoice_july_customer = self._create_invoice("2022-07-01", "out_invoice", 10.0)

        invoice_july_customer.action_post()

        invoice_july_vendor = self._create_invoice("2022-07-01", "in_invoice", 5.0)

        invoice_july_vendor.action_post()

        # Invoices august 2022

        invoice_august_customer = self._create_invoice(
            "2022-08-01", "out_invoice", 10.0
        )

        invoice_august_customer.action_post()

        invoice_august_vendor = self._create_invoice("2022-08-01", "in_invoice", 5.0)

        invoice_august_vendor.action_post()

        # Invoices september 2022

        invoice_september_customer = self._create_invoice(
            "2022-09-01", "out_invoice", 10.0
        )

        invoice_september_customer.action_post()

        invoice_september_vendor = self._create_invoice("2022-09-01", "in_invoice", 5.0)

        invoice_september_vendor.action_post()

        # VAT Settlements

        # VAT Settlement july

        vat_statement_july = self._create_vat_statement(
            "2022-07-31",
            interest=False,
            name_period="07-2022",
            type_period=self.type_month,
            date_start_period="2022-07-01",
            date_end_period="2022-07-31",
        )

        # VAT Settlement august

        vat_statement_august = self._create_vat_statement(
            "2022-08-31",
            interest=False,
            name_period="08-2022",
            type_period=self.type_month,
            date_start_period="2022-08-01",
            date_end_period="2022-08-31",
        )

        # VAT Settlement september

        vat_statement_september = self._create_vat_statement(
            "2022-09-30",
            interest=False,
            name_period="09-2022",
            type_period=self.type_month,
            date_start_period="2022-09-01",
            date_end_period="2022-09-30",
        )

        # Invoices quarter with interest

        # Invoices last quarter 2022

        # October
        invoice_october_customer = self._create_invoice(
            "2022-10-01", "out_invoice", 10.0
        )

        invoice_october_customer.action_post()

        invoice_october_vendor = self._create_invoice("2022-10-01", "in_invoice", 5.0)

        invoice_october_vendor.action_post()

        # November

        invoice_november_customer = self._create_invoice(
            "2022-11-01", "out_invoice", 10.0
        )

        invoice_november_customer.action_post()

        invoice_november_vendor = self._create_invoice("2022-11-01", "in_invoice", 5.0)

        invoice_november_vendor.action_post()

        # December

        invoice_december_customer = self._create_invoice(
            "2022-12-01", "out_invoice", 10.0
        )

        invoice_december_customer.action_post()

        invoice_december_vendor = self._create_invoice("2022-12-01", "in_invoice", 5.0)

        invoice_december_vendor.action_post()

        # VAT Settlement last quarter 2022

        vat_statement_last_quarter_2022 = self._create_vat_statement(
            "2022-12-31",
            interest=True,
            name_period="4-2022",
            type_period=self.type_quarter,
            date_start_period="2022-10-01",
            date_end_period="2022-12-31",
        )

        # LIPE July/August/Setember
        comunicazione_liquidazione_months = self.env[
            "comunicazione.liquidazione"
        ].create(self.get_vals_comunicazione_liquidazione())

        with Form(comunicazione_liquidazione_months) as comunicazione_liquidazione_form:
            with comunicazione_liquidazione_form.quadri_vp_ids.new() as c_l_vp_form:
                c_l_vp_form.period_type = "month"
                c_l_vp_form.month = 7
                c_l_vp_form.liquidazioni_ids.add(vat_statement_july)

            with comunicazione_liquidazione_form.quadri_vp_ids.new() as c_l_vp_form:
                c_l_vp_form.period_type = "month"
                c_l_vp_form.month = 8
                c_l_vp_form.liquidazioni_ids.add(vat_statement_august)

            with comunicazione_liquidazione_form.quadri_vp_ids.new() as c_l_vp_form:
                c_l_vp_form.period_type = "month"
                c_l_vp_form.month = 9
                c_l_vp_form.liquidazioni_ids.add(vat_statement_september)

        self._check_file_report(comunicazione_liquidazione_months)

        # LIPE Llast quarter 2022

        comunicazione_liquidazione_quarter = self.env[
            "comunicazione.liquidazione"
        ].create(self.get_vals_comunicazione_liquidazione())

        with Form(
            comunicazione_liquidazione_quarter
        ) as comunicazione_liquidazione_form:
            with comunicazione_liquidazione_form.quadri_vp_ids.new() as c_l_vp_form:
                c_l_vp_form.period_type = "quarter"
                c_l_vp_form.quarter = 5
                c_l_vp_form.liquidazioni_ids.add(vat_statement_last_quarter_2022)

        self._check_file_report(comunicazione_liquidazione_quarter)
