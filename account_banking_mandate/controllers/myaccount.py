# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from collections import OrderedDict

from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.osv.expression import AND, OR

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class CustomerPortalAccountBankingMandate(CustomerPortal):
    """Routes called in portal mode to manage account banking mandate."""

    def _prepare_banking_mandates_domain(self, user):
        return [
            "|",
            ("partner_id", "child_of", [user.commercial_partner_id.id]),
            ("message_partner_ids", "child_of", [user.commercial_partner_id.id]),
        ]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        user = request.env.user
        if "mandate_count" in counters:
            mandate_model = request.env["account.banking.mandate"]
            mandate_count = (
                mandate_model.search_count(self._prepare_banking_mandates_domain(user))
                if mandate_model.check_access_rights("read", raise_exception=False)
                else 0
            )
            values["mandate_count"] = mandate_count
        return values

    @http.route(
        ["/my/mandates", "/my/mandates/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_mandates(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        filterby=None,
        search=None,
        search_in=None,
        groupby=None,
        **kw
    ):
        AccountBankingMandate = request.env["account.banking.mandate"]
        # Avoid error if the user does not have access.
        if not AccountBankingMandate.check_access_rights("read", raise_exception=False):
            return request.redirect("/my")

        values = self._prepare_portal_layout_values()
        user = request.env.user
        domain = self._prepare_banking_mandates_domain(user)

        searchbar_sortings = self._mandate_get_searchbar_sortings()
        searchbar_sortings = dict(
            sorted(
                self._mandate_get_searchbar_sortings().items(),
                key=lambda item: item[1]["sequence"],
            )
        )

        searchbar_filters = {
            "all": {"label": _("All"), "domain": domain},
        }

        searchbar_inputs = self._mandate_get_searchbar_inputs()
        searchbar_groupby = self._mandate_get_searchbar_groupby()

        if not sortby:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]

        if not filterby:
            filterby = "all"
        domain = searchbar_filters.get(filterby, searchbar_filters.get("all"))["domain"]

        if not groupby:
            groupby = "none"

        if date_begin and date_end:
            domain += [
                ("create_date", ">", date_begin),
                ("create_date", "<=", date_end),
            ]

        if not search_in:
            search_in = "all"
        if search:
            domain += self._mandate_get_search_domain(search_in, search)

        domain = AND(
            [
                domain,
                request.env["ir.rule"]._compute_domain(
                    AccountBankingMandate._name, "read"
                ),
            ]
        )

        # count for pager
        mandate_count = AccountBankingMandate.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/mandates",
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
                "filterby": filterby,
                "groupby": groupby,
                "search": search,
                "search_in": search_in,
            },
            total=mandate_count,
            page=page,
            step=self._items_per_page,
        )

        order = self._mandate_get_order(order, groupby)
        mandates = AccountBankingMandate.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        request.session["my_mandates_history"] = mandates.ids[:100]

        values.update(
            {
                "date": date_begin,
                "date_end": date_end,
                "mandates": mandates.sudo(),
                "page_name": "mandate",
                "default_url": "/my/mandates",
                "pager": pager,
                "searchbar_sortings": searchbar_sortings,
                "searchbar_groupby": searchbar_groupby,
                "searchbar_inputs": searchbar_inputs,
                "search_in": search_in,
                "search": search,
                "sortby": sortby,
                "groupby": groupby,
                "searchbar_filters": OrderedDict(sorted(searchbar_filters.items())),
                "filterby": filterby,
            }
        )
        return request.render("account_banking_mandate.portal_my_mandates", values)

    @http.route(
        ["/my/mandate/<int:mandate_id>"], type="http", auth="public", website=True
    )
    def portal_my_mandate_page(self, mandate_id, access_token=None, **kw):
        try:
            mandate_sudo = self._document_check_access(
                "account.banking.mandate", mandate_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return request.redirect("/my")

        values = self._mandate_get_page_view_values(mandate_sudo, access_token, **kw)
        return request.render(
            "account_banking_mandate.portal_account_banking_mandate_page", values
        )

    def _mandate_get_page_view_values(self, mandate, access_token, **kwargs):
        values = {
            "page_name": "mandate",
            "mandate": mandate,
            "user": request.env.user,
        }
        return self._get_page_view_values(
            mandate, access_token, values, "my_mandates_history", False, **kwargs
        )

    def _mandate_get_searchbar_sortings(self):
        return {
            "date": {
                "label": _("Newest"),
                "order": "create_date desc",
                "sequence": 1,
            },
            "name": {
                "label": _("Mandate Reference"),
                "order": "unique_mandate_reference",
                "sequence": 2,
            },
            "partner_bank_id": {
                "label": _("Bank Account"),
                "order": "partner_bank_id",
                "sequence": 3,
            },
            "signature_date": {
                "label": _("Signature Date"),
                "order": "signature_date",
                "sequence": 4,
            },
            "last_debit_date": {
                "label": _("Last Debit Date"),
                "order": "last_debit_date desc",
                "sequence": 5,
            },
            "state": {"label": _("State"), "order": "state", "sequence": 6},
        }

    def _mandate_get_searchbar_groupby(self):
        values = {
            "none": {"input": "none", "label": _("None"), "order": 1},
            "company_id": {
                "input": "company_id",
                "label": _("Company"),
                "order": 2,
            },
            "state": {"input": "state", "label": _("State"), "order": 3},
        }
        return dict(sorted(values.items(), key=lambda item: item[1]["order"]))

    def _mandate_get_searchbar_inputs(self):
        values = {
            "all": {"input": "all", "label": _("Search in All"), "order": 1},
            "number": {
                "input": "unique_mandate_reference",
                "label": _("Search in Mandate Reference"),
                "order": 2,
            },
            "partner_bank_id": {
                "input": "partner_bank_id",
                "label": _("Search in Bank Account"),
                "order": 3,
            },
        }
        return dict(sorted(values.items(), key=lambda item: item[1]["order"]))

    def _mandate_get_search_domain(self, search_in, search):
        search_domain = []
        if search_in in ("unique_mandate_reference", "all"):
            search_domain.append([("unique_mandate_reference", "ilike", search)])
        if search_in in ("partner_bank_id", "all"):
            search_domain.append([("partner_bank_id", "=", search)])
        return OR(search_domain)

    def _mandate_get_groupby_mapping(self):
        return {
            "company_id": "company_id",
            "state": "state",
        }

    def _mandate_get_order(self, order, groupby):
        groupby_mapping = self._mandate_get_groupby_mapping()
        field_name = groupby_mapping.get(groupby, "")
        if not field_name:
            return order
        return "%s, %s" % (field_name, order)
