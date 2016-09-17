# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProductTempalte(models.Model):
    _inherit = 'product.template'

    contract_sequence = fields.Integer(
        string='Contract Sequence',
        help='This sequence will be used to order lines on contract',
        default=10,
        required=True,
    )
    contract_type = fields.Selection([
        ('app', 'App'),
        ('requirement', 'Requirement'),
    ],
        string='Contract Type',
    )
    adhoc_category_ids = fields.Many2many(
        'adhoc.module.category.server',
        'adhoc_module_category_product_rel',
        'product_tmpl_id', 'adhoca_category_id',
        string='Categories',
    )
    # TODO en realidad esta dependencia deberia ser en clase product
    # product
    adhoc_product_dependency_ids = fields.Many2many(
        'product.template',
        'product_adhoc_depedency_rel',
        'product_tmpl_id', 'product_tmpl_dependency_id',
        string='Dependencies',
    )


class ProductProduct(models.Model):
    _inherit = 'product.product'

    contract_quantity = fields.Integer(
        compute='_compute_contract_data',
        inverse='_set_contract_quantity',
    )
    contract_state = fields.Selection([
        ('contracted', 'contracted'), ('un_contracted', 'un_contracted')
    ],
        'Contract State',
        compute='_compute_contract_data',
    )

    @api.multi
    def _set_contract_quantity(self):
        contract = self._get_contract()
        if not contract:
            return False
        self._add_to_contract(contract)

    @api.multi
    def _compute_contract_data(self):
        contract = self._get_contract()
        if not contract:
            return False
        for product in self:
            # we use filtered instead of compute because of cache
            lines = contract.recurring_invoice_line_ids.filtered(
                lambda x: x.product_id == product)
            # if requirement, we want quantity, else, yes, no
            if product.contract_type == 'requirement':
                product.contract_quantity = (
                    lines and lines[0].quantity or False)
            else:
                if lines:
                    product.contract_state = 'contracted'
                else:
                    product.contract_state = 'un_contracted'

    @api.multi
    def _add_to_contract(self, contract):
        contract_line = self.env['account.analytic.invoice.line']
        partner = contract.partner_id
        pricelist = contract.pricelist_id
        for product in self:
            if product.contract_type == 'requirement':
                quantity = product.contract_quantity
            else:
                quantity = 1.0

            line = contract_line.search([
                ('analytic_account_id', '=', contract.id),
                ('product_id', '=', product.id)], limit=1)
            # just in case quantity is zero
            if line:
                line.quantity = quantity
            else:
                res = contract_line.product_id_change(
                    product.id, False, qty=quantity,
                    name=False, partner_id=partner.id, price_unit=False,
                    pricelist_id=pricelist.id, company_id=None).get(
                    'value', {})
                # TODO, tal vez podriamos actualizar por si algun otro modulo
                # creo otro campo
                # for k, v in vals.iteritems():
                #     setattr(line, k, v)
                vals = {
                    'analytic_account_id': contract.id,
                    'sequence': product.contract_sequence,
                    'product_id': product.id,
                    'quantity': quantity,
                    'name': res.get('name'),
                    'uom_id': res.get('uom_id'),
                    'price_unit': res.get('price_unit'),
                    'tax_id': res.get('tax_id'),
                }
                contract_line.create(vals)
            dep_prods = product.adhoc_product_dependency_ids.mapped(
                'product_variant_ids')
            dep_prods._add_to_contract(contract)

    @api.multi
    def _remove_from_contract(self, contract):
        contract_line = self.env['account.analytic.invoice.line']
        for product in self:
            contract_line.search([
                ('analytic_account_id', '=', contract.id),
                ('product_id', '=', product.id)]).unlink()
            upper_prods = self.search([(
                'adhoc_product_dependency_ids',
                '=',
                product.product_tmpl_id.id)])
            upper_prods._remove_from_contract(contract)

    @api.model
    def _get_contract(self):
        contract_id = self._context.get('active_id')
        model = self._context.get('active_model')
        # on tree editable, we get from params
        if not contract_id or model != 'account.analytic.account':
            params = self._context.get('params', False)
            if params:
                contract_id = params.get('id')
                model = params.get('model')
        if not contract_id or model != 'account.analytic.account':
            return False
        return self.env[model].browse(contract_id)

    @api.multi
    def action_add_to_contract(self):
        contract = self._get_contract()
        if not contract:
            return False
        self._add_to_contract(contract)

    @api.multi
    def action_remove_to_contract(self):
        contract = self._get_contract()
        if not contract:
            return False
        self._remove_from_contract(contract)
