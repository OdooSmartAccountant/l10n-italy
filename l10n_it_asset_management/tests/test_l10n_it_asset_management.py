# Copyright 2021 Sergio Corato <https://github.com/sergiocorato>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools.date_utils import relativedelta


class TestAssets(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # cls.data_account_type_current_assets = cls.env.ref(
        #     "account.data_account_type_current_assets"
        # )
        # cls.data_account_type_current_liabilities = cls.env.ref(
        #     "account.data_account_type_current_liabilities"
        # )
        cls.asset_category_1 = cls.env["asset.category"].create(
            {
                "name": "Asset category 1",
                "asset_account_id": cls.env["account.account"]
                .search(
                    [("account_type", "=", "asset_fixed")],
                    limit=1,
                )
                .id,
                "depreciation_account_id": cls.env["account.account"]
                .search(
                    [
                        (
                            "account_type",
                            "=",
                            "expense",
                        )
                    ],
                    limit=1,
                )
                .id,
                "fund_account_id": cls.env["account.account"]
                .search(
                    [("account_type", "=", "asset_non_current")],
                    limit=1,
                )
                .id,
                "gain_account_id": cls.env["account.account"]
                .search(
                    [("account_type", "=", "expense_direct_cost")],
                    limit=1,
                )
                .id,
                "journal_id": cls.env["account.journal"]
                .search([("type", "=", "general")], limit=1)
                .id,
                "loss_account_id": cls.env["account.account"]
                .search(
                    [("account_type", "=", "expense")],
                    limit=1,
                )
                .id,
                "type_ids": [
                    (
                        0,
                        0,
                        {
                            "depreciation_type_id": cls.env.ref(
                                "l10n_it_asset_management.ad_type_civilistico"
                            ).id,
                            "mode_id": cls.env.ref(
                                "l10n_it_asset_management.ad_mode_materiale"
                            ).id,
                        },
                    )
                ],
            }
        )
        cls.tax_account = cls.env["account.account"].create(
            {
                "name": "Deductable tax",
                "code": "DEDTAX",
                "account_type": "asset_current",
            }
        )
        cls.tax_22_partial_60 = cls.env["account.tax"].create(
            {
                "name": "22% deductable partial 60%",
                "type_tax_use": "purchase",
                "amount_type": "percent",
                "amount": 22,
                "invoice_repartition_line_ids": [
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
                            "factor_percent": 60,
                            "repartition_type": "tax",
                            "account_id": cls.tax_account.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 40,
                            "repartition_type": "tax",
                        },
                    ),
                ],
                "refund_repartition_line_ids": [
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
                            "factor_percent": 60,
                            "repartition_type": "tax",
                            "account_id": cls.tax_account.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 40,
                            "repartition_type": "tax",
                        },
                    ),
                ],
            }
        )

    def _create_asset(self):
        asset = self.env["asset.asset"].create(
            {
                "name": "Test asset",
                "category_id": self.asset_category_1.id,
                "company_id": self.env.ref("base.main_company").id,
                "currency_id": self.env.ref("base.main_company").currency_id.id,
                "purchase_amount": 1000.0,
                "purchase_date": fields.Date.today() + relativedelta(years=-1),
            }
        )
        return asset

    def test_00_create_asset_depreciate_and_sale(self):
        today = fields.Date.today()
        first_depreciation_date = today.replace(month=12, day=31) + relativedelta(
            years=-1
        )
        second_depreciation_date = today.replace(month=12, day=31)
        asset = self._create_asset()
        civ_type = self.env.ref("l10n_it_asset_management.ad_type_civilistico")
        depreciation_id = asset.depreciation_ids.filtered(
            lambda x: x.type_id == civ_type
        )
        self.assertEqual(len(depreciation_id), 1)
        depreciation_id.percentage = 25.0
        depreciation_id.mode_id.line_ids.coefficient = 0.5
        self.assertEqual(
            asset.state, "non_depreciated", "Asset is not in non depreciated state!"
        )

        wiz_vals = asset.with_context(
            **{"allow_reload_window": True}
        ).launch_wizard_generate_depreciations()
        wiz = (
            self.env["wizard.asset.generate.depreciation"]
            .with_context(**wiz_vals["context"])
            .create({"date_dep": first_depreciation_date})
        )
        wiz.do_generate()
        wiz_vals = asset.with_context(
            **{"allow_reload_window": True}
        ).launch_wizard_generate_depreciations()
        wiz = (
            self.env["wizard.asset.generate.depreciation"]
            .with_context(**wiz_vals["context"])
            .create({"date_dep": second_depreciation_date})
        )
        wiz.do_generate()
        dep_lines = asset.depreciation_ids.line_ids
        self.assertTrue(dep_lines)
        self.assertEqual(len(dep_lines), 2)
        civ_dep_lines = dep_lines.filtered(
            lambda x: x.depreciation_id.type_id == civ_type
        )
        self.assertAlmostEqual(sum(civ_dep_lines.mapped("amount")), 375)
        self.assertEqual(asset.state, "partially_depreciated")

        # create sale invoice and link to asset
        sale_invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.env.ref("base.partner_demo").id,
                "journal_id": self.env["account.journal"]
                .search(
                    [
                        ("type", "=", "sale"),
                    ],
                    limit=1,
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": asset.category_id.asset_account_id.id,
                            "quantity": 1,
                            "price_unit": 600,
                        },
                    )
                ],
            }
        )
        sale_invoice.action_post()
        wiz_vals = sale_invoice.open_wizard_manage_asset()
        move_line_ids = wiz_vals["context"]["default_move_line_ids"][0][2]
        move_lines = self.env["account.move.line"].browse(move_line_ids)
        move_lines_to_do = move_lines.filtered(
            lambda x: x.account_id == asset.category_id.asset_account_id
        )
        wiz_vals["context"]["default_move_line_ids"] = [(6, 0, move_lines_to_do.ids)]
        wiz = (
            self.env["wizard.account.move.manage.asset"]
            .with_context(**wiz_vals["context"])
            .create(
                {
                    "management_type": "dismiss",
                    "asset_id": asset.id,
                }
            )
        )
        with self.assertRaises(ValidationError) as exc:
            wiz.link_asset()
        self.assertEqual(
            exc.exception.args[0],
            "Cannot dismiss an asset earlier than the last depreciation date.\n"
            "(Dismiss date: %s, last depreciation date: %s)."
            % (today, second_depreciation_date),
        )
        sale_invoice.button_cancel()
        sale_invoice.button_draft()
        # Reset name to allow sequence year changing
        sale_invoice.name = "/"
        sale_invoice.invoice_date = second_depreciation_date + relativedelta(days=10)
        sale_invoice.action_post()
        self.assertEqual(sale_invoice.state, "posted")
        move_lines_to_do = move_lines.filtered(
            lambda x: x.account_id == asset.category_id.asset_account_id
        )
        wiz_vals["context"]["default_move_line_ids"] = [(6, 0, move_lines_to_do.ids)]
        wiz = (
            self.env["wizard.account.move.manage.asset"]
            .with_context(**wiz_vals["context"])
            .create(
                {
                    "management_type": "dismiss",
                    "asset_id": asset.id,
                    "dismiss_date": sale_invoice.invoice_date,
                }
            )
        )
        asset = wiz.link_asset()
        self.assertTrue(asset.sold)

    def test_01_asset_from_purchase_invoice(self):
        # create purchase invoice and generate asset
        today = fields.Date.today()
        purchase_invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "invoice_date": today,
                "partner_id": self.env.ref("base.partner_demo").id,
                "journal_id": self.env["account.journal"]
                .search(
                    [
                        ("type", "=", "purchase"),
                    ],
                    limit=1,
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.asset_category_1.asset_account_id.id,
                            "quantity": 1,
                            "price_unit": 7000,
                        },
                    )
                ],
            }
        )
        purchase_invoice.action_post()
        self.assertEqual(purchase_invoice.state, "posted")
        wiz_vals = purchase_invoice.open_wizard_manage_asset()
        move_line_ids = wiz_vals["context"]["default_move_line_ids"][0][2]
        move_lines = self.env["account.move.line"].browse(move_line_ids)
        move_lines_to_do = move_lines.filtered(
            lambda x: x.account_id == self.asset_category_1.asset_account_id
        )
        wiz_vals["context"]["default_move_line_ids"] = [(6, 0, move_lines_to_do.ids)]
        wiz = (
            self.env["wizard.account.move.manage.asset"]
            .with_context(**wiz_vals["context"])
            .create(
                {
                    "management_type": "create",
                    "category_id": self.asset_category_1.id,
                    "name": "Test asset",
                }
            )
        )
        asset = wiz.link_asset()
        self.assertEqual(asset.purchase_amount, 7000)
        # dismiss asset with sale
        # create sale invoice and link to asset
        sale_invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.env.ref("base.partner_demo").id,
                "journal_id": self.env["account.journal"]
                .search(
                    [
                        ("type", "=", "sale"),
                    ],
                    limit=1,
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": asset.category_id.asset_account_id.id,
                            "quantity": 1,
                            "price_unit": 6000,
                        },
                    )
                ],
            }
        )
        sale_invoice.action_post()
        wiz_vals = sale_invoice.open_wizard_manage_asset()
        move_line_ids = wiz_vals["context"]["default_move_line_ids"][0][2]
        move_lines = self.env["account.move.line"].browse(move_line_ids)
        move_lines_to_do = move_lines.filtered(
            lambda x: x.account_id == asset.category_id.asset_account_id
        )
        wiz_vals["context"]["default_move_line_ids"] = [(6, 0, move_lines_to_do.ids)]
        wiz = (
            self.env["wizard.account.move.manage.asset"]
            .with_context(**wiz_vals["context"])
            .create(
                {
                    "management_type": "dismiss",
                    "asset_id": asset.id,
                }
            )
        )
        wiz.link_asset()
        self.assertTrue(asset.sold)

    def test_01_asset_partial_deductible_from_purchase_invoice(self):
        # create purchase invoice partial deductible and generate asset
        today = fields.Date.today()
        purchase_invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "invoice_date": today,
                "partner_id": self.env.ref("base.partner_demo").id,
                "journal_id": self.env["account.journal"]
                .search(
                    [
                        ("type", "=", "purchase"),
                    ],
                    limit=1,
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.asset_category_1.asset_account_id.id,
                            "quantity": 1,
                            "price_unit": 7000,
                            "tax_ids": [(6, 0, [self.tax_22_partial_60.id])],
                        },
                    )
                ],
            }
        )
        purchase_invoice.action_post()
        self.assertEqual(purchase_invoice.state, "posted")
        self.assertAlmostEqual(
            sum(
                line.debit
                for line in purchase_invoice.line_ids
                if line.account_id == self.asset_category_1.asset_account_id
            ),
            7000 + (7000 * 0.22 * 0.4),
        )
        wiz_vals = purchase_invoice.open_wizard_manage_asset()
        move_line_ids = wiz_vals["context"]["default_move_line_ids"][0][2]
        move_lines = self.env["account.move.line"].browse(move_line_ids)
        move_lines_to_do = move_lines.filtered(
            lambda x: x.account_id == self.asset_category_1.asset_account_id
        )
        wiz_vals["context"]["default_move_line_ids"] = [(6, 0, move_lines_to_do.ids)]
        wiz = (
            self.env["wizard.account.move.manage.asset"]
            .with_context(**wiz_vals["context"])
            .create(
                {
                    "management_type": "create",
                    "category_id": self.asset_category_1.id,
                    "name": "Test asset",
                }
            )
        )
        asset = wiz.link_asset()
        self.assertAlmostEqual(asset.purchase_amount, 7000 + (7000 * 0.22 * 0.4), 2)
