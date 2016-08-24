# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from openerp import models, fields, api, _
from openerp.exceptions import Warning
from openerp import modules
import logging

_logger = logging.getLogger(__name__)
uninstallables = ['to_review', 'future_versions', 'unusable']
# installables = ['to_review', 'future_versions', 'unusable']
not_installed = ['uninstalled', 'uninstallable', 'to install']
# installed = ['installed', 'to install', 'to upgrade']
installed = ['installed', 'to upgrade', 'to remove']


class AdhocModuleModule(models.Model):
    _inherit = 'ir.module.module'
    # nos parece mas facil ver el nombre tecnico directamente, ayuda mucho
    # en los m2m_tags
    _rec_name = 'name'
    _order = 'review desc,technically_critical desc,support_type,sequence,name'

    # because default sequence is overwrited every time we update module list
    # we create a new sequence field
    # era complicado agregar este campo porque empieza a dar errores y no
    # podemos actualizar, vamos a probar usando sequence por defecto de odoo
    # haria falta luego de actualizar lista de modulos refrescar desde adhoc
    # o al menos tener copiado este campo
    # si volvemos a agregar este campo entonces deberiamos
    # cambiar para que sea este quien se actualice
    # new_sequence = fields.Integer(
    #     'New Sequence',
    #     default='100'
    # )
    adhoc_category_id = fields.Many2one(
        'adhoc.module.category',
        'ADHOC Category',
        auto_join=True,
        readonly=True,
    )
    computed_summary = fields.Char(
        compute='get_computed_summary',
        inverse='set_adhoc_summary',
        readonly=True,
    )
    adhoc_summary = fields.Char(
        readonly=True,
    )
    adhoc_description_html = fields.Html(
        readonly=True,
    )
    support_type = fields.Selection([
        ('supported', 'Soportado'),
        ('unsupported', 'No Soportado'),
        # ('unsupport_all', 'No Soporta BD'),
    ],
        string='Support Type',
        readonly=True,
        # no lo hacemos required aca porque es un poco delicado y nos da error
        # al actualizar, lo hacemos en server, deberiamos hacer por script
        # de migracion que setee este valor y ahí si lo ponemos
        # required=True,
        default='unsupported',
    )
    technically_critical = fields.Boolean(
        readonly=True,
        # agregamos default para que se ordenen correctamente porque es
        # distinto a vacio
        default=False,
    )
    review = fields.Selection([
        ('0', 'Not Recommended'),
        ('1', 'Only If Necessary'),
        ('2', 'Neutral'),
        ('3', 'Recommended'),
        ('4', 'Highly Recommended'),
    ], 'Review',
        select=True,
        readonly=True,
        default='0',
    )
    conf_visibility = fields.Selection([
        # instalables
        ('normal', 'Manual'),
        # auto install va a setear auto_install de odoo
        ('auto_install', 'Auto Instalar por Dep.'),
        ('auto_install_by_code', 'Auto Instalado por Cód.'),
        # auto install va a marcar to install si categoria contratada
        ('auto_install_by_categ', 'Auto Instalar por Cat.'),
        # estos dos no son visibles de manera predeterminada
        ('installed_by_others', 'Instalado por Otro'),
        ('on_config_wizard', 'En asistente de configuración'),
        # no instalable
        ('to_review', 'A Revisar'),
        ('future_versions', 'Versiones Futuras'),
        ('unusable', 'No Usable'),
    ],
        'Visibility',
        # no lo hacemos required aca porque es un poco delicado y nos da error
        # al actualizar, lo hacemos en server
        readonly=True,
        # no le ponemos por defecto to_review porque es muy fuerte y los
        # hace no instalables de entrada
        default='normal',
        help="Módulos que se pueden instalar:\n"
        "* Manual: debe seleccionar manualmente si desea intalarlo\n"
        # "* Solo si dep.: se muestra solo si dependencias instaladas\n"
        "* Auto Instalar por Dep.: auto instalar si se cumplen dependencias\n"
        "* Auto Instalado por Código: auto instalado si se cumplen dependencias\n"
        "* Auto Instalar por Cat.: auto instalar si se categoría contratada\n"
        "* Auto Instalado Por Módulo: se instala si se cumplen dependencias\n"
        "* Instalado por Otro: algún otro módulo dispara la instalación\n"
        "* En asistente de configuración: este módulo esta presente en el "
        "asistente de configuración\n"
        "\nMódulos en los que se bloquea la instalación:\n"
        "* A Revisar: hay que analizar como lo vamos a utilizar\n"
        "* Versiones Futuras: se va a incorporar más adelante\n"
        "* No Usable: no se usa ni se va a sugerir uso en versiones futuras\n"
    )
    visibility_obs = fields.Char(
        'Visibility Observation',
        readonly=True,
    )
    # visible = fields.Boolean(
    #     compute='get_visible',
    #     search='search_visible',
    # )
    state = fields.Selection(
        selection_add=[('ignored', 'Ignored')]
    )

    @api.one
    @api.constrains('state')
    def check_contracted(self):
        if (
                self.state == 'to install' and
                self.adhoc_category_id and
                not self.adhoc_category_id.contracted):
            raise Warning(_(
                'You can not install module "%s" as category "%s" is not '
                'contracted') % (self.name, self.adhoc_category_id.name))

    @api.model
    def update_list(self):
        res = super(AdhocModuleModule, self).update_list()
        self.update_data_from_visibility()
        return res

    @api.model
    def _get_installed_uninstallable_modules(self):
        return self.search([
            ('conf_visibility', 'in', uninstallables),
            ('state', 'in', installed),
        ])

    @api.model
    def _get_not_installed_uninstallable_modules(self):
        return self.search([
            ('conf_visibility', 'in', uninstallables),
            ('state', 'in', not_installed),
        ])

    # @api.model
    # def _get_uninstalled_uncontracted_modules(self):
    #     contracted_categories = self.env[
    #         'adhoc.module.category'].get_contracted_categories()
    #     return self.search([
    #         ('adhoc_category_id', '!=', False),
    #         ('adhoc_category_id', 'not in', contracted_categories.ids),
    #         ('state', '=', 'uninstalled'),
    #     ])

    @api.model
    def _get_installed_uncontracted_modules(self):
        contracted_categories = self.env[
            'adhoc.module.category'].get_contracted_categories()
        return self.search([
            ('adhoc_category_id', '!=', False),
            ('adhoc_category_id', 'not in', contracted_categories.ids),
            ('state', 'in', installed),
        ])

    @api.model
    def _get_not_installed_by_category_modules(self):
        # make none auto_install modules auto_install if vis. auto_install and
        # in categorias contratadas o que no requieren contrato
        contracted_categories = self.env[
            'adhoc.module.category'].get_contracted_categories()
        return self.search([
            '&', ('conf_visibility', '=', 'auto_install_by_categ'),
            ('adhoc_category_id', 'in', contracted_categories.ids),
            ('state', '=', 'uninstalled'),
        ])

    @api.model
    def update_data_from_visibility(self):
        self.update_auto_install_from_visibility()
        self.set_to_install_from_category()
        self.update_uninstallable_state_from_visibility()

    @api.model
    def set_to_install_from_category(self):
        """
        Marcamos para instalar todos los modulos que tengan auto install if
        categ y las categ esten contratadas
        """
        to_install_modules = self._get_not_installed_by_category_modules()
        to_install_modules._set_to_install()

    @api.model
    def update_auto_install_from_visibility(self):
        # make none auto_install modules auto_install if vis. auto_install
        visibility_auto_install_modules = self.search([
            ('conf_visibility', '=', 'auto_install'),
            ('auto_install', '=', False),
        ])
        visibility_auto_install_modules.write({'auto_install': True})

        # in case an auto_install module became normal
        # we check modules with auto_install and no visibility auto install
        visibility_none_auto_install_auto_modules = self.search([
            ('conf_visibility', '!=', 'auto_install'),
            ('auto_install', '=', True),
        ])
        visibility_none_auto_install_auto_modules_names = dict(
            [(m.name, m) for m in visibility_none_auto_install_auto_modules])
        for mod_name in modules.get_modules():
            # mod is the in database
            mod = visibility_none_auto_install_auto_modules_names.get(mod_name)
            # terp is the module on file
            terp = self.get_module_info(mod_name)
            if mod:
                # si terp dice que es no es auto_intall lo ponemos false
                if not terp.get('auto_install', False):
                    mod.auto_install = False

    # @api.model
    # def update_uninstallable_for_uncontracted_categories(self):
    #     self._get_uninstalled_uncontracted_modules().write(
    #         {'state': 'uninstallable'})

    @api.model
    def update_uninstallable_state_from_visibility(self):
        """
        Just in case module list update overwrite some of our values
        """
        # make uninstallable all not installed modules that has a none
        # istallable visibility
        self._get_not_installed_uninstallable_modules().write(
            {'state': 'uninstallable'})

        # we check if some uninstallable modules has become installable
        uninstallable_installable_modules = self.search([
            ('conf_visibility', 'not in', uninstallables),
            ('state', '=', 'uninstallable'),
        ])
        uninstallable_installable_modules_names = dict(
            [(m.name, m) for m in uninstallable_installable_modules])
        for mod_name in modules.get_modules():
            # mod is the in database
            mod = uninstallable_installable_modules_names.get(mod_name)
            # terp is the module on file
            terp = self.get_module_info(mod_name)
            if mod:
                # si terp dice que es instalable lo ponemos uninstalled
                if terp.get('installable', True):
                    mod.state = 'uninstalled'

    @api.model
    def set_adhoc_summary(self):
        self.adhoc_summary = self.computed_summary

    @api.one
    def get_computed_summary(self):
        self.computed_summary = self.adhoc_summary or self.summary

    @api.multi
    def button_un_ignore(self):
        return self.write({'state': 'uninstalled'})

    @api.multi
    def button_ignore(self):
        return self.write({'state': 'ignored'})

    @api.multi
    def _get_not_installed_autoinstall_modules(self):
        # Mark (recursively) the newly satisfied modules to also be installed

        # Select all auto-installable (but not yet installed) modules.
        domain = [('state', '=', 'uninstalled'), ('auto_install', '=', True)]
        uninstalled_modules = self.search(domain)

        # Keep those with:
        #  - all dependencies satisfied (installed or to be installed),
        #  - at least one dependency being 'to install'

        satisfied_states = frozenset(('installed', 'to install', 'to upgrade'))

        # la diferencia respecto al siguiente es que no buscamos ninguno que
        # este en "to intall"
        def all_depencies_satisfied(m):
            states = set(d.state for d in m.dependencies_id)
            return states.issubset(
                satisfied_states)

        to_install_modules = filter(
            all_depencies_satisfied, uninstalled_modules)
        to_install_ids = map(lambda m: m.id, to_install_modules)
        return self.browse(to_install_ids)

    @api.multi
    def _get_to_install_autoinstall_modules(self):
        # Mark (recursively) the newly satisfied modules to also be installed

        # Select all auto-installable (but not yet installed) modules.
        domain = [('state', '=', 'uninstalled'), ('auto_install', '=', True)]
        uninstalled_modules = self.search(domain)

        # Keep those with:
        #  - all dependencies satisfied (installed or to be installed),
        #  - at least one dependency being 'to install'

        satisfied_states = frozenset(('installed', 'to install', 'to upgrade'))

        def all_depencies_satisfied(m):
            states = set(d.state for d in m.dependencies_id)
            return states.issubset(
                satisfied_states) and ('to install' in states)

        to_install_modules = filter(
            all_depencies_satisfied, uninstalled_modules)
        to_install_ids = map(lambda m: m.id, to_install_modules)
        return self.browse(to_install_ids)

    @api.model
    def get_overall_update_state(self):
        res = super(AdhocModuleModule, self).get_overall_update_state()
        # solo cambiamos estado si estado es ok, es decir, nuevos estados
        # tienen menos prioridad
        installed_uninstallable = self._get_installed_uninstallable_modules()
        installed_uncontracted = self._get_installed_uncontracted_modules()
        uninstalled_auto_install = (
            self._get_not_installed_autoinstall_modules())
        new_detail = {
            'installed_uninstallable': installed_uninstallable.mapped(
                'name'),
            'installed_uncontracted': installed_uncontracted.mapped(
                'name'),
            'uninstalled_auto_install': uninstalled_auto_install.mapped(
                'name'),
        }
        res['detail'].update(new_detail)
        if res.get('state') == 'ok':
            if installed_uninstallable:
                res['state'] = 'installed_uninstallable'
            elif uninstalled_auto_install:
                res['state'] = 'uninstalled_auto_install'
            # ultime prioridad porque es el unico que no se arregla con fix
            elif installed_uncontracted:
                res['state'] = 'installed_uncontracted'
        return res
