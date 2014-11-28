# -*- coding: utf-8 -*-
from lxml import etree

from openerp import models, fields, api, SUPERUSER_ID

from openerp.addons.bestja_offers.models import Offer


class OfferWithModeration(models.Model):
    _name = 'offer'
    _inherit = [
        'offer',
        'ir.needaction_mixin',
    ]
    STATES = Offer.STATES + [
        ('pending', "oczekująca na akceptację"),
    ]
    state = fields.Selection(STATES)

    def is_moderator(self):
        """
        Returns a boolean value indicating whether current user
        is an offer moderator.
        """
        return self.env['res.users'] \
            .has_group('bestja_offers_moderation.offers_moderator')

    @api.one
    def set_pending(self):
        self.state = 'pending'

    @api.one
    def set_pending_if_needed(self):
        """
        Sets offer state to pending,
        provided current user is not the admin or an offer moderator.
        """
        if self.state == 'published' \
                and self.env.user.id != SUPERUSER_ID \
                and not self.is_moderator():
            self.set_pending()

    @api.model
    def create(self, vals):
        record = super(OfferWithModeration, self).create(vals)
        record.set_pending_if_needed()
        return record

    @api.multi
    def write(self, vals):
        val = super(OfferWithModeration, self).write(vals)
        self.set_pending_if_needed()
        return val

    @api.model
    def fields_view_get(self, **kwargs):
        """
        Hide "send to moderation" button from moderators.
        """
        view = super(Offer, self).fields_view_get(**kwargs)
        if 'view_type' in kwargs and kwargs['view_type'] != 'form':
            return view

        doc = etree.XML(view['arch'])

        if self.is_moderator():
            button_pending = doc.xpath("//button[@name='set_pending']")
            if button_pending:
                button_pending[0].getparent().remove(button_pending[0])

        view['arch'] = etree.tostring(doc)
        return view

    @api.model
    def _needaction_domain_get(self):
        """
        Show pending offers count in menu - only for moderators.
        """
        if not self.is_moderator():
            return False
        return [('state', '=', 'pending')]
