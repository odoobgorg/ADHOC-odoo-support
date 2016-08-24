# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, api, _
import base64
import logging
_logger = logging.getLogger(__name__)


class Contract(models.Model):
    _inherit = 'account.analytic.account'

    @api.model
    def create_issue(
            self, contract_id, db_name, login,
            vals, attachments_data):
        _logger.info('Creating issue for contract %s, db %s, login %s' % (
            contract_id, db_name, login))
        contract = self.sudo().search([
            ('id', '=', contract_id), ('state', '=', 'open')], limit=1)
        if not contract:
            return {'error': _(
                "No open contract for id %s" % contract_id)}
        database = self.env['infrastructure.database'].sudo().search([
            ('name', '=', db_name), ('contract_id', '=', contract.id),
            ('state', '=', 'active')],
            limit=1)
        if not database:
            return {'error': _(
                "No database found")}
        _logger.info('Looking for user with login %s on database id %s' % (
            login, database.id))

        vals['database_id'] = database.id
        user = database.user_ids.search([
            ('database_id', '=', database.id), ('login', '=', login)], limit=1)
        if not user:
            return {'error': _(
                "User is not registered on support provider database")}

        if not user.authorized_for_issues:
            return {'error': _(
                "User is not authorized to register issues")}
        vals['partner_id'] = user.partner_id.id
        vals['email_from'] = user.partner_id.email

        project = self.env['project.project'].sudo().search(
            [('analytic_account_id', '=', contract.id)], limit=1)
        if project:
            vals['project_id'] = project.id

        issue = self.env['project.issue'].sudo().create(vals)

        attachments = []
        for data in attachments_data:
            attachments.append(
                (data['name'], base64.b64decode(data['datas'])))
            # we use b64decode because it will be encoded by message_post
            # attachments.append((data['name'], data['datas']))
        issue.message_post(
            body=None, subject=None, attachments=attachments)
        return {'issue_id': issue.id}
