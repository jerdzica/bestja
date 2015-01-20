# -*- coding: utf-8 -*-

from openerp import models, fields, api, exceptions
from dateutil import parser


class Project(models.Model):
    _inherit = 'bestja.project'

    detailed_reports = fields.One2many('bestja.detailed_report', inverse_name='project')


class CommodityGroup (models.Model):
    _name = 'bestja.commodity_group'

    code = fields.Char(string="Kod")
    name = fields.Char(string="Nazwa")

class ReportEntry(models.Model):
    _name = 'bestja.report_entry'

    detailed_report= fields.Many2one('bestja.detailed_report', ondelete='cascade', required=True)
    commodity = fields.Many2one('bestja.commodity_group', string="Nazwa", required=True, ondelete='cascade')
    commodity_code = fields.Char(string='Kod', related="commodity.code")
    quantity = fields.Float(required=True, string="tonaż (kg)")
    parent_project = fields.Many2one(
            'bestja.project',
            string="Projekt nadrzędny",
            store=True,  # Needed by graph view
            related='detailed_report.parent_project',
    )
            
class DetailedReport(models.Model):
    _name = 'bestja.detailed_report'
    _order = 'write_uid desc'
    STATES = [
        ('sent', "wysłany"),
        ('accepted', "zaakceptowany"),
        ('draft', "szkic"),
        ('rejected', "odrzucony"),
    ]

    project = fields.Many2one(
        'bestja.project',
        required=True,
        string="Projekt",
        domain=lambda self: [
            ('detailed_reports', '=', False),
            '|',
            ('manager', '=', self.env.user.id),
            ('organization.coordinator', '=', self.env.user.id)],
        ondelete='restrict',
    )
    parent_project = fields.Many2one(
            'bestja.project',
            string="Projekt nadrzędny",
            related='project.parent',
            store=True,
    )
    name = fields.Char(string="Nazwa Projektu", related="project.name")
    dates = fields.Char(string="Termin", compute="compute_project_dates", store=True) 
    state = fields.Selection(STATES, default='draft', string="Status:")
    report_entries = fields.One2many('bestja.report_entry', inverse_name='detailed_report', string="Produkt")
    user_can_moderate = fields.Boolean(compute="compute_user_can_moderate")
    
    _sql_constraints = [
        ('report_entries_uniq', 
        'unique("bestja.detailed_report", "bestja.report_entry")', 
        "Dany element można wybrać tylko raz!")
    ]
    
    @api.one
    @api.depends('parent_project')
    def compute_user_can_moderate(self):
        """
        Is current user authorized to moderate (accept/reject) the detailed_report?
        """
        self.user_can_moderate = (
            self.parent_project.manager.id == self.env.user.id or
            self.parent_project.organization.coordinator.id == self.env.user.id
        )
    
    @api.one
    @api.constrains('report_entries')
    def check_report_entries(self):
        listlen = len(self.report_entries)
        newlist = set([(i.commodity_code, i.detailed_report) for i in self.report_entries])
        if (listlen > len(newlist)):
            raise exceptions.ValidationError("Produkt o danym kodzie może mieć co najwyżej jeden wpis!")

    @api.one
    @api.depends('project')
    def compute_project_dates(self):
        """ 
        For nice format in the list of all projects.
        """
        if self.project:
            tmp_date = parser.parse(self.project.date_start).strftime("%d-%m-%Y")
            tmp_date += " - "
            tmp_date += parser.parse(self.project.date_stop).strftime("%d-%m-%Y")
            self.dates = tmp_date

    @api.one
    def set_sent(self):
        self.state = 'sent'

    @api.one
    def set_accepted(self):
        self.state = 'accepted'

    @api.multi
    def continue_action(self):
        """ 
        For the continue button.
        """
        pass

    @api.multi
    def add_all_commodity_groups(self):
        """
        Button which adds all commodity groups to the report
        """
        codes = []
        for i in self.env['bestja.commodity_group'].search([
            ('code', 'not in', [c.commodity_code for c in self.report_entries])]):
            codes.append(i)
            report_id = self.id
            e = self.env['bestja.report_entry'].create({
                'commodity': i.id,
                'detailed_report': report_id,
                'quantity': 0.0, 
            })
